import socket
import random
import sys
import os
import time
from threading import Thread, Lock
import threading
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
        self.window_size = max_win
        self.rto = rto
        self.unack_segments = []  # 存储已发送但未确认的段
        self.timer = None
        self.dup_ack_count = {}  # 记录每个段的重复ACK数


def log_event(action, time_offset, segment_type, seqno, num_bytes):
    segment_type_str = {SEGMENT_TYPE_DATA: "DATA", SEGMENT_TYPE_ACK: "ACK", SEGMENT_TYPE_SYN: "SYN", SEGMENT_TYPE_FIN: "FIN"}[segment_type]
    log_entry = f"{action} {time_offset:.2f} {segment_type_str} {seqno} {num_bytes}\n"
    with open("sender_log.txt", "a") as log_file:
        log_file.write(log_entry)

def establish_connection(sender_socket, receiver_address, control_block):
    # 创建并发送SYN段
    syn_segment = STPSegment(SEGMENT_TYPE_SYN, control_block.isn)
    sender_socket.sendto(syn_segment.pack(), receiver_address)
    print("SYN sent.")

    # 设置接收ACK的超时
    sender_socket.settimeout(5.0)

    try:
        # 等待接收ACK
        while True:
            response, _ = sender_socket.recvfrom(1024)
            ack_segment = STPSegment.unpack(response)
            if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.isn + 1:
                control_block.ackno = ack_segment.seqno
                control_block.state = "ESTABLISHED"
                break
    except socket.timeout:
        sys.exit(1)


def ack_receiver(control_block, sender_socket, sender_address):
    while True:
        # 接收ACK
        try:
            response, _ = sender_socket.recvfrom(1024)
            ack_segment = STPSegment.unpack(response)

            if ack_segment.segment_type != SEGMENT_TYPE_ACK:
                continue  # 忽略非ACK段

            with control_block.lock:
                # 检查ACK是否为新的
                if ack_segment.seqno > control_block.ackno:
                    # 更新确认号
                    control_block.ackno = ack_segment.seqno

                    # 移除所有已确认的段
                    control_block.unack_segments = [seg for seg in control_block.unack_segments if seg.seqno >= ack_segment.seqno]

                    # 如果有未确认的段，重置计时器
                    if control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto
                    else:
                        control_block.timer = None

                    # 重置dup_ack_count
                    control_block.dup_ack_count = {}

                else:
                    # 处理重复ACK
                    if ack_segment.seqno in control_block.dup_ack_count:
                        control_block.dup_ack_count[ack_segment.seqno] += 1
                    else:
                        control_block.dup_ack_count[ack_segment.seqno] = 1

                    # 如果dup_ack_count等于3，进行快速重传
                    if control_block.dup_ack_count[ack_segment.seqno] == 3:
                        # 找到需要重传的段
                        for seg in control_block.unack_segments:
                            if seg.seqno == ack_segment.seqno:
                                sender_socket.sendto(seg.pack(), sender_address)
                                # 重置计时器
                                control_block.timer = time.time() * 1000 + control_block.rto
                                break

        except socket.timeout:
            # 如果socket阻塞超时，继续监听（根据你的socket设置）
            continue

def timer_thread(control_block, sender_socket, sender_address):
    while True:
        with control_block.lock:
            if control_block.timer is not None:
                current_time = time.time() * 1000  # 当前时间，单位为毫秒
                # 检查计时器是否超时
                if current_time >= control_block.timer:
                    # 如果有未确认的段，则重传最老的未确认段
                    if control_block.unack_segments:
                        oldest_unack_segment = control_block.unack_segments[0]
                        sender_socket.sendto(oldest_unack_segment.pack(), sender_address)
                        # 重置计时器
                        control_block.timer = current_time + control_block.rto
                        print(f"Timeout, retransmitting segment {oldest_unack_segment.seqno}")

                        # 重置dup_ack_count，因为我们已经重传了段
                        control_block.dup_ack_count = {}


def send_file(sender_port, receiver_port, filename, control_block, sender_socket):
    with open(filename, 'rb') as file:
        file_data = file.read()
        total_length = len(file_data)
        sent_length = 0

        # 数据发送循环
        while sent_length < total_length or control_block.unack_segments:
            with control_block.lock:
                window_space = control_block.window_size - (len(control_block.unack_segments) * MSS)

            # 确定是否有窗口空间发送更多数据
            if window_space > 0 and sent_length < total_length:
                # 确定本次发送的数据大小
                segment_size = min(MSS, total_length - sent_length, window_space)
                segment_data = file_data[sent_length:sent_length+segment_size]
                new_segment = STPSegment(SEGMENT_TYPE_DATA, control_block.seqno, segment_data)
                sender_socket.sendto(new_segment.pack(), ('localhost', receiver_port))

                with control_block.lock:
                    # 更新控制块信息
                    if not control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto  # 如果是第一个未确认的段，设置计时器
                    control_block.unack_segments.append(new_segment)
                    control_block.seqno += segment_size

                sent_length += segment_size

            time.sleep(0.01)  # 防止过快填充网络

    # # 发送完成后发送FIN段
    # fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
    # with control_block.lock:
    #     sender_socket.sendto(fin_segment.pack(), ('localhost', receiver_port))
    #     control_block.unack_segments.append(fin_segment)
    #     if not control_block.timer:
    #         control_block.timer = time.time() * 1000 + control_block.rto

def close_connection(sender_socket, receiver_address, control_block):
    # 创建并发送FIN段
    fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
    sender_socket.sendto(fin_segment.pack(), receiver_address)
    print("FIN sent.")

    # 更新控制块状态
    control_block.state = "FIN_WAIT"

    # 设置接收ACK的超时
    sender_socket.settimeout(5.0)

    try:
        # 等待接收ACK for FIN
        while True:
            response, _ = sender_socket.recvfrom(1024)
            ack_segment = STPSegment.unpack(response)
            if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.seqno + 1:
                print("ACK for FIN received.")
                control_block.state = "CLOSED"
                break
    except socket.timeout:
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 6:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send max_win rto")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]
    max_win = int(sys.argv[4])
    rto = int(sys.argv[5])

    control_block = STPControlBlock()
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    sender_address = ('localhost', receiver_port)

    # 设置接收方的地址
    receiver_address = ('localhost', receiver_port)

    # 建立连接
    establish_connection(sender_socket, receiver_address, control_block)

    if control_block.state != "ESTABLISHED":
        print("Failed to establish connection.")
        sys.exit(1)

    # 启动ACK接收线程和计时器线程
    ack_thread = threading.Thread(target=ack_receiver, args=(control_block, sender_socket, sender_address))
    timer_thread = threading.Thread(target=timer_thread, args=(control_block, sender_socket, sender_address))
    ack_thread.start()
    timer_thread.start()

    # 开始文件发送
    send_file(sender_port, receiver_port, txt_file_to_send, control_block, sender_socket)

    # 发送完成后关闭连接
    close_connection(sender_socket, receiver_address, control_block)

    # 等待线程结束
    ack_thread.join()
    timer_thread.join()

    # 关闭套接字
    sender_socket.close()