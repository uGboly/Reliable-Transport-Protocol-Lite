import socket
import random
import sys
import time
import threading
from STPSegment import STPSegment, DATA
from sender_utils import SenderLogger, ConnectionManager

class STPControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.init_seqno = random.randint(0, 65535)
        self.seqno = self.init_seqno + 1
        self.ackno = 0
        self.lock = threading.Lock()
        self.max_win = max_win
        self.rto = rto
        self.sliding_window = []
        self.timer = None
        self.ack_counter = {}
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
                if ack_segment.seqno >= control_block.ackno or ack_segment.seqno < control_block.init_seqno:
                    # 更新确认号
                    control_block.ackno = ack_segment.seqno

                    for seg in control_block.sliding_window:
                        if seg.seqno < ack_segment.seqno:
                            control_block.original_data_acked += len(seg.data)
                    # 移除所有已确认的段
                    if ack_segment.seqno < control_block.init_seqno:
                        control_block.sliding_window = [
                            seg for seg in control_block.sliding_window if seg.seqno < control_block.init_seqno]
                    control_block.sliding_window = [
                        seg for seg in control_block.sliding_window if seg.seqno >= ack_segment.seqno]

                    # 如果有未确认的段，重置计时器
                    if control_block.sliding_window:
                        control_block.timer = time.time() * 1000 + control_block.rto
                    else:
                        control_block.timer = None

                    # 重置ack_counter
                    control_block.ack_counter = {}

                else:
                    # 处理重复ACK
                    control_block.dup_acks_received += 1
                    if ack_segment.seqno in control_block.ack_counter:
                        control_block.ack_counter[ack_segment.seqno] += 1
                    else:
                        control_block.ack_counter[ack_segment.seqno] = 1

                    # 如果ack_counter等于3，进行快速重传
                    if control_block.ack_counter[ack_segment.seqno] == 3:
                        # 找到需要重传的段
                        for seg in control_block.sliding_window:
                            if seg.seqno == ack_segment.seqno:
                                connection_manager.send_message(seg, True)
                                # 重置计时器
                                control_block.timer = time.time() * 1000 + control_block.rto
                                break

        except socket.timeout:
            pass
        except AttributeError:
            pass


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
                    if control_block.sliding_window:
                        oldest_unack_segment = control_block.sliding_window[0]
                        connection_manager.send_message(
                            oldest_unack_segment, True)
                        # 重置计时器
                        control_block.timer = current_time + control_block.rto

                        # 重置ack_counter，因为我们已经重传了段
                        control_block.ack_counter = {}


def send_file(filename, control_block):
    with open(filename, 'rb') as file:
        file_data = file.read()
        total_length = len(file_data)
        sent_length = 0

        # 数据发送循环
        while sent_length < total_length or control_block.sliding_window:
            with control_block.lock:
                window_space = control_block.max_win - \
                    (len(control_block.sliding_window) * 1000)

            # 确定是否有窗口空间发送更多数据
            if window_space > 0 and sent_length < total_length:
                # 确定本次发送的数据大小
                segment_size = min(1000, total_length -
                                   sent_length, window_space)
                segment_data = file_data[sent_length:sent_length+segment_size]
                new_segment = STPSegment(
                    DATA, control_block.seqno, segment_data)
                connection_manager.send_message(new_segment)
                with control_block.lock:
                    # 更新控制块信息
                    if not control_block.sliding_window:
                        control_block.timer = time.time() * 1000 + control_block.rto  # 如果是第一个未确认的段，设置计时器
                    control_block.sliding_window.append(new_segment)
                    control_block.seqno = (
                        control_block.seqno + segment_size) % (2 ** 16 - 1)

                sent_length += segment_size

        control_block.state = "FIN_WAIT"


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

    ack_thread = threading.Thread(
        target=ack_receiver, args=[control_block])
    timer_thread = threading.Thread(
        target=timer_thread, args=[control_block])
    ack_thread.start()
    timer_thread.start()

    send_file(txt_file_to_send, control_block)
    ack_thread.join()
    timer_thread.join()
    connection_manager.finish()
