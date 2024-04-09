import socket
import sys
import threading
import time
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

class STPReceiver:
    def __init__(self, receiver_port, sender_port, file_to_save, max_win):
        self.receiver_port = receiver_port
        self.sender_port = sender_port
        self.file_to_save = file_to_save
        self.max_win = max_win
        self.expected_seqno = 0
        self.receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiver_socket.bind(('', receiver_port))
        self.original_data_received = 0
        self.original_segments_received = 0
        self.dup_data_segments_received = 0
        self.total_ack_segments_sent = 0
        self.receiver_socket.settimeout(2.0)

    def start(self):
        self.handle_syn()
        self.receive_data()

    def log_event(self, action, segment, num_bytes):
        current_time = time.time() * 1000
        segment_type_str = {SEGMENT_TYPE_DATA: "DATA", SEGMENT_TYPE_ACK: "ACK", SEGMENT_TYPE_SYN: "SYN", SEGMENT_TYPE_FIN: "FIN"}.get(segment.segment_type, "UNKNOWN")
        if segment_type_str == "SYN":
            self.start_time = current_time
            time_offset = 0
        else:
            time_offset = current_time - self.start_time

        with open("receiver_log.txt", "a") as log_file:
            log_file.write(f"{action} {time_offset:.2f} {segment_type_str} {segment.seqno} {num_bytes}\n")

    def handle_syn(self):
        # 等待并处理SYN
        while True:
            try:
                packet, sender_address = self.receiver_socket.recvfrom(1024)
                segment = STPSegment.unpack(packet)
                if segment.segment_type == SEGMENT_TYPE_SYN:
                    self.log_event("rcv", segment, 0)
                    self.expected_seqno = segment.seqno + 1
                    ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno)
                    self.receiver_socket.sendto(ack_segment.pack(), sender_address)
                    self.total_ack_segments_sent += 1
                    self.log_event("snd", ack_segment, 0)
                    break
            except socket.timeout:
                continue

    def receive_data(self):
        buffer = {}  # 使用字典作为缓冲区，键为序列号，值为数据
        with open(self.file_to_save, 'wb') as file:
            while True:
                try:
                    packet, sender_address = self.receiver_socket.recvfrom(1024)
                    segment = STPSegment.unpack(packet)

                    if segment.segment_type == SEGMENT_TYPE_SYN:
                        self.log_event("rcv", segment, 0)
                        ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno)
                        self.receiver_socket.sendto(ack_segment.pack(), sender_address)
                        self.total_ack_segments_sent += 1
                        self.log_event("snd", ack_segment, 0)

                    
                    if segment.segment_type == SEGMENT_TYPE_DATA:
                        self.log_event("rcv", segment, len(segment.data))
                        # 如果数据段按序到达，直接写入文件，并检查缓冲区中是否有连续的后续数据
                        if segment.seqno == self.expected_seqno:
                            self.original_data_received += len(segment.data)
                            self.original_segments_received += 1
                            file.write(segment.data)
                            self.expected_seqno += len(segment.data)

                            # 检查并写入缓冲区中按序的数据
                            while self.expected_seqno in buffer:
                                data = buffer.pop(self.expected_seqno)
                                file.write(data)
                                self.expected_seqno += len(data)
                        elif segment.seqno > self.expected_seqno:  #到达了乱序数据
                            if segment.seqno in buffer:
                                self.dup_data_segments_received += 1
                            else:
                                self.original_data_received += len(segment.data)
                                self.original_segments_received += 1
                                buffer[segment.seqno] = segment.data
                        else: #到达的数据段已经写入文件
                            self.dup_data_segments_received += 1

                        # 发送ACK
                        self.total_ack_segments_sent += 1
                        ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno)
                        self.receiver_socket.sendto(ack_segment.pack(), sender_address)
                        self.log_event("snd", ack_segment, 0) 

                    if segment.segment_type == SEGMENT_TYPE_FIN:
                        self.handle_fin(sender_address)
                        break
                except socket.timeout:
                    continue


    def handle_fin(self, sender_address):
        # 发送ACK for FIN
        ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno + 1)
        self.receiver_socket.sendto(ack_segment.pack(), sender_address)
        self.total_ack_segments_sent += 1
        self.log_event("snd", ack_segment, 0)

        # 定义处理FIN重传的线程函数
        def handle_fin_retransmissions():
            try:
                while True:
                    packet, _ = self.receiver_socket.recvfrom(1024)
                    segment = STPSegment.unpack(packet)
                    if segment.segment_type == SEGMENT_TYPE_FIN:
                        # 对于重传的FIN，再次发送ACK
                        self.receiver_socket.sendto(ack_segment.pack(), sender_address)
            except socket.timeout:
                # 超时意味着没有收到更多的FIN重传，线程结束
                pass

        # 启动处理FIN重传的线程
        fin_thread = threading.Thread(target=handle_fin_retransmissions)
        fin_thread.start()
        fin_thread.join()
        self.finalize_log()


    def finalize_log(self):
        with open("receiver_log.txt", "a") as log_file:
            log_file.write(f"Original data received: {self.original_data_received}\n")
            log_file.write(f"Original segments received: {self.original_segments_received}\n")
            log_file.write(f"Dup data segments received: {self.dup_data_segments_received}\n")
            log_file.write(f"Dup ack segments sent: {self.total_ack_segments_sent - self.original_segments_received - 2}\n")

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    with open("receiver_log.txt", "w") as log_file:
        pass

    receiver = STPReceiver(receiver_port, sender_port, txt_file_received, max_win)
    receiver.start()
