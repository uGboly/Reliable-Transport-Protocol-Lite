import socket
import random
import sys
import time
import threading
from STPSegment import STPSegment, DATA, ACK, SYN, FIN
from sender_utils import SenderLogger, ConnectionManager
MSS = 1000


class STPControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.ackno = 0
        self.lock = threading.Lock()
        self.window_size = max_win
        self.rto = rto
        self.unack_segments = []  # 存储已发送但未确认的段
        self.timer = None
        self.dup_ack_count = {}  # 记录每个段的重复ACK数
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0


def ack_receiver(control_block):
    while True:
        if control_block.state == "FIN_WAIT":
            break
        try:
            ack_segment = connection_manager.receive_message()

            with control_block.lock:
                # 检查ACK是否为新的
                if ack_segment.seqno >= control_block.ackno or ack_segment.seqno < control_block.isn:
                    # 更新确认号
                    control_block.ackno = ack_segment.seqno

                    for seg in control_block.unack_segments:
                        if seg.seqno < ack_segment.seqno:
                            control_block.original_data_acked += len(seg.data)
                    # 移除所有已确认的段
                    if ack_segment.seqno < control_block.isn:
                        control_block.unack_segments = [
                            seg for seg in control_block.unack_segments if seg.seqno < control_block.isn]
                    control_block.unack_segments = [
                        seg for seg in control_block.unack_segments if seg.seqno >= ack_segment.seqno]

                    # 如果有未确认的段，重置计时器
                    if control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto
                    else:
                        control_block.timer = None

                    # 重置dup_ack_count
                    control_block.dup_ack_count = {}

                else:
                    # 处理重复ACK
                    control_block.dup_acks_received += 1
                    if ack_segment.seqno in control_block.dup_ack_count:
                        control_block.dup_ack_count[ack_segment.seqno] += 1
                    else:
                        control_block.dup_ack_count[ack_segment.seqno] = 1

                    # 如果dup_ack_count等于3，进行快速重传
                    if control_block.dup_ack_count[ack_segment.seqno] == 3:
                        # 找到需要重传的段
                        for seg in control_block.unack_segments:
                            if seg.seqno == ack_segment.seqno:
                                connection_manager.send_message(seg, True)
                                # 重置计时器
                                control_block.timer = time.time() * 1000 + control_block.rto
                                break

        except socket.timeout:
            # 如果socket阻塞超时，继续监听
            continue
        except AttributeError:
            continue


def timer_thread(control_block):
    while True:
        with control_block.lock:
            if control_block.state == "FIN_WAIT":
                break
            if control_block.timer is not None:
                current_time = time.time() * 1000  # 当前时间，单位为毫秒
                # 检查计时器是否超时
                if current_time >= control_block.timer:
                    # 如果有未确认的段，则重传最老的未确认段
                    if control_block.unack_segments:
                        oldest_unack_segment = control_block.unack_segments[0]
                        connection_manager.send_message(
                            oldest_unack_segment, True)
                        # 重置计时器
                        control_block.timer = current_time + control_block.rto

                        # 重置dup_ack_count，因为我们已经重传了段
                        control_block.dup_ack_count = {}


def send_file(filename, control_block, sender_socket):
    with open(filename, 'rb') as file:
        file_data = file.read()
        total_length = len(file_data)
        sent_length = 0

        # 数据发送循环
        while sent_length < total_length or control_block.unack_segments:
            with control_block.lock:
                window_space = control_block.window_size - \
                    (len(control_block.unack_segments) * MSS)

            # 确定是否有窗口空间发送更多数据
            if window_space > 0 and sent_length < total_length:
                # 确定本次发送的数据大小
                segment_size = min(MSS, total_length -
                                   sent_length, window_space)
                segment_data = file_data[sent_length:sent_length+segment_size]
                new_segment = STPSegment(
                    DATA, control_block.seqno, segment_data)
                connection_manager.send_message(new_segment)
                with control_block.lock:
                    # 更新控制块信息
                    if not control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto  # 如果是第一个未确认的段，设置计时器
                    control_block.unack_segments.append(new_segment)
                    control_block.seqno = (
                        control_block.seqno + segment_size) % (2 ** 16 - 1)

                sent_length += segment_size

    while True:
        with control_block.lock:
            if not control_block.unack_segments:
                control_block.state = "FIN_WAIT"
                break


if __name__ == '__main__':
    if len(sys.argv) != 8:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send max_win rto flp rlp")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]
    max_win = int(sys.argv[4])
    rto = int(sys.argv[5])
    flp = float(sys.argv[6])
    rlp = float(sys.argv[7])

    random.seed()
    logger = SenderLogger("sender_log.txt")

    control_block = STPControlBlock()
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    sender_address = ('localhost', receiver_port)
    receiver_address = ('localhost', receiver_port)

    connection_manager = ConnectionManager(
        sender_socket, receiver_address, control_block, logger, rto, flp, rlp)
    connection_manager.setup()

    if control_block.state != "ESTABLISHED":
        print("Failed to establish connection.")
        sys.exit(1)

    ack_thread = threading.Thread(
        target=ack_receiver, args=(control_block, sender_socket))
    timer_thread = threading.Thread(
        target=timer_thread, args=(control_block, sender_socket))
    ack_thread.start()
    timer_thread.start()

    send_file(txt_file_to_send, control_block, sender_socket)
    ack_thread.join()
    timer_thread.join()
    connection_manager.finish()
