import socket
import random
import sys
import os
import time
from threading import Thread, Lock
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

# MSS 定义
MSS = 1000

class STPControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.ackno = 0
        self.lock = Lock()

def log_event(action, time_offset, segment_type, seqno, num_bytes):
    segment_type_str = {SEGMENT_TYPE_DATA: "DATA", SEGMENT_TYPE_ACK: "ACK", SEGMENT_TYPE_SYN: "SYN", SEGMENT_TYPE_FIN: "FIN"}[segment_type]
    log_entry = f"{action} {time_offset:.2f} {segment_type_str} {seqno} {num_bytes}\n"
    with open("sender_log.txt", "a") as log_file:
        log_file.write(log_entry)


def send_file(sender_port, receiver_port, filename):
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))

    start_time = time.time() * 1000  # 记录开始时间，转换为毫秒

    control_block = STPControlBlock()

    # 发送 SYN
    syn_segment = STPSegment(SEGMENT_TYPE_SYN, control_block.isn)
    sender_socket.sendto(syn_segment.pack(), ('localhost', receiver_port))
    log_event("snd", 0, SEGMENT_TYPE_SYN, control_block.isn, 0)  # 记录日志，时间为0
    control_block.state = "SYN_SENT"

    # 等待 ACK
    response, _ = sender_socket.recvfrom(1024)
    ack_segment = STPSegment.unpack(response)
    if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.isn + 1:
        control_block.state = "ESTABLISHED"
        log_event("rcv", time.time() * 1000 - start_time, SEGMENT_TYPE_ACK, ack_segment.seqno, 0)  # 记录接收到的ACK

    # 发送数据
    with open(filename, 'rb') as file:
        while control_block.state == "ESTABLISHED":
            data = file.read(MSS)
            if not data:
                break  # 文件结束
            data_segment = STPSegment(SEGMENT_TYPE_DATA, control_block.seqno, data)
            sender_socket.sendto(data_segment.pack(), ('localhost', receiver_port))
            log_event("snd", time.time() * 1000 - start_time, SEGMENT_TYPE_DATA, control_block.seqno, len(data))  # 记录发送的DATA
            control_block.seqno += len(data)

    # 发送 FIN
    fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
    sender_socket.sendto(fin_segment.pack(), ('localhost', receiver_port))
    control_block.state = "FIN_WAIT"
    log_event("snd", time.time() * 1000 - start_time, SEGMENT_TYPE_FIN, control_block.seqno, 0)  # 记录发送的FIN

    # 等待 ACK for FIN
    response, _ = sender_socket.recvfrom(1024)
    ack_segment = STPSegment.unpack(response)
    if ack_segment.segment_type == SEGMENT_TYPE_ACK:
        control_block.state = "CLOSED"
        log_event("rcv", time.time() * 1000 - start_time, SEGMENT_TYPE_ACK, ack_segment.seqno, 0)  # 记录接收到的ACK for FIN

    sender_socket.close()


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]

    send_file(sender_port, receiver_port, txt_file_to_send)
