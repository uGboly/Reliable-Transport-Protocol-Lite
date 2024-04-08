import socket
import sys
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

    def start(self):
        self.handle_syn()
        self.receive_data()
        self.handle_fin()

    def handle_syn(self):
        # 等待并处理SYN
        while True:
            packet, sender_address = self.receiver_socket.recvfrom(1024)
            segment = STPSegment.unpack(packet)
            if segment.segment_type == SEGMENT_TYPE_SYN:
                self.expected_seqno = segment.seqno + 1
                ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno)
                self.receiver_socket.sendto(ack_segment.pack(), sender_address)
                break

    def receive_data(self):
        buffer = {}  # 使用字典作为缓冲区，键为序列号，值为数据
        with open(self.file_to_save, 'wb') as file:
            while True:
                packet, sender_address = self.receiver_socket.recvfrom(1024)
                segment = STPSegment.unpack(packet)
                
                if segment.segment_type == SEGMENT_TYPE_DATA:
                    # 如果数据段按序到达，直接写入文件，并检查缓冲区中是否有连续的后续数据
                    if segment.seqno == self.expected_seqno:
                        file.write(segment.data)
                        self.expected_seqno += len(segment.data)

                        # 检查并写入缓冲区中按序的数据
                        while self.expected_seqno in buffer:
                            data = buffer.pop(self.expected_seqno)
                            file.write(data)
                            self.expected_seqno += len(data)
                    else:
                        # 如果数据段未按序到达，存入缓冲区
                        buffer[segment.seqno] = segment.data

                    # 发送ACK
                    ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno)
                    self.receiver_socket.sendto(ack_segment.pack(), sender_address)

                if segment.segment_type == SEGMENT_TYPE_FIN:
                    self.handle_fin(sender_address)
                    break


    def handle_fin(self, sender_address):
        # 发送ACK for FIN
        ack_segment = STPSegment(SEGMENT_TYPE_ACK, self.expected_seqno + 1)
        self.receiver_socket.sendto(ack_segment.pack(), sender_address)

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    receiver = STPReceiver(receiver_port, sender_port, txt_file_received, max_win)
    receiver.start()
