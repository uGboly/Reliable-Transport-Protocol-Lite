import socket
import random
import sys
import os
from threading import Thread, Lock
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

# Segment 类型定义
SEGMENT_TYPE_DATA = 0
SEGMENT_TYPE_ACK = 1
SEGMENT_TYPE_SYN = 2
SEGMENT_TYPE_FIN = 3

# MSS 定义
MSS = 1000



class STPControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.ackno = 0
        self.lock = Lock()

def send_file(sender_port, receiver_port, filename):
    # 创建 UDP socket
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))

    control_block = STPControlBlock()

    # 发送 SYN
    syn_segment = STPSegment(SEGMENT_TYPE_SYN, control_block.isn)
    sender_socket.sendto(syn_segment.pack(), ('localhost', receiver_port))
    control_block.state = "SYN_SENT"

    # 等待 ACK
    response, _ = sender_socket.recvfrom(1024)
    ack_segment = STPSegment.unpack(response)
    if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.isn + 1:
        control_block.state = "ESTABLISHED"

    # 发送数据
    with open(filename, 'rb') as file:
        while control_block.state == "ESTABLISHED":
            data = file.read(MSS)
            if not data:
                break  # 文件结束
            data_segment = STPSegment(SEGMENT_TYPE_DATA, control_block.seqno, data)
            sender_socket.sendto(data_segment.pack(), ('localhost', receiver_port))
            control_block.seqno += len(data)

    # 发送 FIN
    fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
    sender_socket.sendto(fin_segment.pack(), ('localhost', receiver_port))
    control_block.state = "FIN_WAIT"

    # 等待 ACK for FIN
    response, _ = sender_socket.recvfrom(1024)
    ack_segment = STPSegment.unpack(response)
    if ack_segment.segment_type == SEGMENT_TYPE_ACK:
        control_block.state = "CLOSED"

    sender_socket.close()

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]

    send_file(sender_port, receiver_port, txt_file_to_send)
