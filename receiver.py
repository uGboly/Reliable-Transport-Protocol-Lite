import socket
import sys
import threading
from STPSegment import STPSegment, DATA, ACK, SYN, FIN
from receiver_utils import ReceiverLogger


class STPReceiver:
    def __init__(self, receiver_port, sender_port, file_to_save, max_win):
        self.receiver_port = receiver_port
        self.sender_port = sender_port
        self.file_to_save = file_to_save
        self.max_win = max_win
        self.init_seqno = 0
        self.expected_seqno = 0
        self.receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receiver_socket.bind(('', receiver_port))
        self.original_data_received = 0
        self.original_segments_received = 0
        self.dup_data_segments_received = 0
        self.total_ack_segments_sent = 0
        self.receiver_socket.settimeout(2.0)
        self.logger = ReceiverLogger()

    def send_ack(self, seqno, address):
        ack = STPSegment(ACK, seqno)
        self.receiver_socket.sendto(ack.serialize(), address)
        self.total_ack_segments_sent += 1
        self.logger.log("snd", ack)

    def receive_segment(self, timeout=2.0):
        self.receiver_socket.settimeout(timeout)
        try:
            packet, sender_address = self.receiver_socket.recvfrom(1024)
            segment = STPSegment.unserialize(packet)
            self.logger.log("rcv", segment, len(segment.data))
            return segment, sender_address
        except socket.timeout:
            return None, None

    def start(self):
        self.handle_syn()
        self.receive_data()

    def handle_syn(self):
        # 等待并处理SYN
        while True:
            try:
                segment, sender_address = self.receive_segment()
                if segment.type == SYN:
                    self.expected_seqno = (segment.seqno + 1) % (2 ** 16 - 1)
                    self.init_seqno = (segment.seqno + 1) % (2 ** 16 - 1)
                    self.send_ack(self.expected_seqno, sender_address)
                    break
            except AttributeError:
                continue

    def receive_data(self):
        buffer = {}  # 使用字典作为缓冲区，键为序列号，值为数据
        with open(self.file_to_save, 'wb') as file:
            while True:
                try:
                    segment, sender_address = self.receive_segment()

                    if segment.type == SYN:
                        self.send_ack(self.init_seqno, sender_address)

                    elif segment.type == DATA:
                        # 如果数据段按序到达，直接写入文件，并检查缓冲区中是否有连续的后续数据
                        if segment.seqno == self.expected_seqno:
                            self.original_data_received += len(segment.data)
                            self.original_segments_received += 1
                            file.write(segment.data)
                            self.expected_seqno = (
                                self.expected_seqno + len(segment.data)) % (2 ** 16 - 1)

                            # 检查并写入缓冲区中按序的数据
                            while self.expected_seqno in buffer:
                                data = buffer.pop(self.expected_seqno)
                                file.write(data)
                                self.expected_seqno = (
                                    self.expected_seqno + len(data)) % (2 ** 16 - 1)
                        elif segment.seqno > self.expected_seqno:  # 到达了乱序数据
                            if segment.seqno in buffer:
                                self.dup_data_segments_received += 1
                            else:
                                self.original_data_received += len(
                                    segment.data)
                                self.original_segments_received += 1
                                buffer[segment.seqno] = segment.data

                        self.send_ack(self.expected_seqno, sender_address)

                    elif segment.type == FIN:
                        self.logger.log("rcv", segment)
                        self.handle_fin(sender_address)
                        break
                except AttributeError:
                    continue

    def handle_fin(self, sender_address):
        self.send_ack((self.expected_seqno + 1) % (2 ** 16 - 1), sender_address)

        # 定义处理FIN重传的线程函数
        def handle_fin_retransmissions():
            try:
                while True:
                    segment, _ = self.receive_segment()

                    if segment.type == FIN:
                        # 对于重传的FIN，再次发送ACK
                        self.send_ack((self.expected_seqno + 1) % (2 ** 16 - 1), sender_address)
            except AttributeError:
                pass

        # 启动处理FIN重传的线程
        fin_thread = threading.Thread(target=handle_fin_retransmissions)
        fin_thread.start()
        fin_thread.join()
        self.logger.log_statatics(self)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(
            "Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    with open("receiver_log.txt", "w") as log_file:
        pass

    receiver = STPReceiver(receiver_port, sender_port,
                           txt_file_received, max_win)
    receiver.start()
