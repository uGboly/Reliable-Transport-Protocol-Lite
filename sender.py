import socket
import random
import sys
import time
import threading
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

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
        self.start_time = 0
        self.fin_segment = None
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0


def log_event(action, segment_type, seqno, num_bytes, control_block):
    current_time = time.time() * 1000
    segment_type_str = {SEGMENT_TYPE_DATA: "DATA", SEGMENT_TYPE_ACK: "ACK",
                        SEGMENT_TYPE_SYN: "SYN", SEGMENT_TYPE_FIN: "FIN"}.get(segment_type, "UNKNOWN")
    if segment_type_str == "SYN":
        control_block.start_time = current_time
        time_offset = 0
    else:
        time_offset = current_time - control_block.start_time
    with open("sender_log.txt", "a") as log_file:
        log_file.write(
            f"{action} {time_offset:.2f} {segment_type_str} {seqno} {num_bytes}\n")


def send_segment(socket, address, segment, control_block, is_retransmitted=False):
    num_bytes = len(
        segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

    if random.random() < flp:
        if segment.segment_type == SEGMENT_TYPE_DATA:
            control_block.data_segments_dropped += 1
            if not is_retransmitted:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1

        log_event("drp", segment.segment_type,
                  segment.seqno, num_bytes, control_block)
    else:
        socket.sendto(segment.pack(), address)
        log_event("snd", segment.segment_type,
                  segment.seqno, num_bytes, control_block)

        if segment.segment_type == SEGMENT_TYPE_DATA:
            if is_retransmitted:
                control_block.retransmitted_segments += 1
            else:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1


def receive_segment(socket, control_block):
    response, _ = socket.recvfrom(1024)
    segment = STPSegment.unpack(response)

    if random.random() < rlp:
        control_block.ack_segments_dropped += 1
        log_event("drp", segment.segment_type, segment.seqno, 0, control_block)
        return
    else:
        log_event("rcv", segment.segment_type, segment.seqno, 0, control_block)
        return segment


def establish_connection(sender_socket, receiver_address, control_block):
    # 创建并发送SYN段
    syn_segment = STPSegment(SEGMENT_TYPE_SYN, control_block.isn)
    send_segment(sender_socket, receiver_address, syn_segment, control_block)

    # 设置接收ACK的超时
    sender_socket.settimeout(control_block.rto / 1000.0)

    # 等待接收ACK
    while True:
        try:
            ack_segment = receive_segment(sender_socket, control_block)

            if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.isn + 1:
                control_block.ackno = ack_segment.seqno
                control_block.state = "ESTABLISHED"
                break
        except socket.timeout:
            send_segment(sender_socket, receiver_address,
                         syn_segment, control_block)
        except AttributeError:
            continue


def ack_receiver(control_block, sender_socket):
    while True:
        # 接收ACK
        try:
            ack_segment = receive_segment(sender_socket, control_block)

            if ack_segment.segment_type != SEGMENT_TYPE_ACK:
                continue  # 忽略非ACK段

            with control_block.lock:
                if control_block.state == "FIN_WAIT" and ack_segment.seqno == control_block.seqno + 1:
                    # 如果在FIN_WAIT状态，检查到对FIN的ACK，则进入CLOSE状态并退出循环
                    control_block.fin_segment = None
                    control_block.state = "CLOSE"
                    break
                # 检查ACK是否为新的
                elif ack_segment.seqno in [(seg.seqno + len(seg.data)) % 2 ** 16 for seg in control_block.unack_segments]:
                    # 更新确认号
                    index_ack_seg = [i for i, seg in enumerate(
                        control_block.unack_segments) if (seg.seqno + len(seg.data)) % 2 ** 16 == ack_segment.seqno][0]
                    for seg in control_block.unack_segments[:index_ack_seg + 1]:
                        control_block.original_data_acked += len(seg.data)

                    control_block.unack_segments = control_block.unack_segments[index_ack_seg + 1:]

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
                        send_segment(sender_socket, receiver_address,
                                     control_block.unack_segments[0], control_block, True)
                        # 重置计时器
                        control_block.timer = time.time() * 1000 + control_block.rto

        except socket.timeout:
            # 如果socket阻塞超时，继续监听
            continue
        except AttributeError:
            continue


def timer_thread(control_block, sender_socket):
    while True:
        with control_block.lock:
            if control_block.state == "CLOSE":
                # 如果在CLOSE状态，退出循环
                break
            if control_block.timer is not None:
                current_time = time.time() * 1000  # 当前时间，单位为毫秒
                # 检查计时器是否超时
                if current_time >= control_block.timer:
                    # 如果有未确认的段，则重传最老的未确认段
                    if control_block.unack_segments:
                        oldest_unack_segment = control_block.unack_segments[0]
                        send_segment(sender_socket, receiver_address,
                                     oldest_unack_segment, control_block, True)
                        # 重置计时器
                        control_block.timer = current_time + control_block.rto

                        # 重置dup_ack_count，因为我们已经重传了段
                        control_block.dup_ack_count = {}
                    elif control_block.state == "FIN_WAIT" and control_block.fin_segment:
                        # FIN超时，只重传FIN与重置计时器，无需重置dup_ack_count
                        send_segment(sender_socket, receiver_address,
                                     control_block.fin_segment, control_block, True)
                        control_block.timer = current_time + control_block.rto


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
                        SEGMENT_TYPE_DATA, control_block.seqno, segment_data)
                    send_segment(sender_socket, receiver_address,
                                 new_segment, control_block)
                    # 更新控制块信息
                    if not control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto  # 如果是第一个未确认的段，设置计时器
                    control_block.unack_segments.append(new_segment)
                    control_block.seqno = (
                        control_block.seqno + segment_size) % (2 ** 16)

                    sent_length += segment_size


def close_connection(sender_socket, receiver_address, control_block):
    while True:
        with control_block.lock:
            if not control_block.unack_segments:  # 确保文件已经可靠地到达receiver
                # 创建并发送FIN段
                fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
                control_block.fin_segment = fin_segment
                send_segment(sender_socket, receiver_address,
                             fin_segment, control_block)
                control_block.timer = time.time() * 1000 + control_block.rto  # 重置计时器以便FIN超时时重传
                control_block.state = "FIN_WAIT"
                break


def finalize_log(control_block):
    with open("sender_log.txt", "a") as log_file:
        log_file.write(
            f"Original data sent: {control_block.original_data_sent}\n")
        log_file.write(
            f"Original data acked: {control_block.original_data_acked}\n")
        log_file.write(
            f"Original segments sent: {control_block.original_segments_sent}\n")
        log_file.write(
            f"Retransmitted segments: {control_block.retransmitted_segments}\n")
        log_file.write(
            f"Dup acks received: {control_block.dup_acks_received}\n")
        log_file.write(
            f"Data segments dropped: {control_block.data_segments_dropped}\n")
        log_file.write(
            f"Ack segments dropped: {control_block.ack_segments_dropped}\n")


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

    with open("sender_log.txt", "w") as log_file:
        log_file.write("")

    random.seed()

    control_block = STPControlBlock()
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    sender_address = ('localhost', receiver_port)
    receiver_address = ('localhost', receiver_port)

    establish_connection(sender_socket, receiver_address, control_block)

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

    close_connection(sender_socket, receiver_address, control_block)

    ack_thread.join()
    timer_thread.join()

    sender_socket.close()

    with control_block.lock:
        finalize_log(control_block)
