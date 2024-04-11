import socket
import sys
import threading
from segment import Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
from receiver_utils.control_block import ControlBlock
from receiver_utils.log_actions import log_actions

def handle_syn(control_block):
    # 等待并处理SYN
    while True:
        try:
            packet, sender_address = control_block.receiver_socket.recvfrom(
                1024)
            segment = Segment.unpack(packet)
            if segment.segment_type == SEGMENT_TYPE_SYN:
                log_actions(control_block, "rcv", segment, 0)
                control_block.expected_seqno = segment.seqno + 1
                ack_segment = Segment(
                    SEGMENT_TYPE_ACK, control_block.expected_seqno)
                control_block.receiver_socket.sendto(
                    ack_segment.pack(), sender_address)
                control_block.total_ack_segments_sent += 1
                log_actions(control_block, "snd", ack_segment, 0)
                break
        except socket.timeout:
            continue


def receive_data(control_block):
    buffer = {}  # 使用字典作为缓冲区，键为序列号，值为数据
    with open(control_block.file_to_save, 'wb') as file:
        while True:
            try:
                packet, sender_address = control_block.receiver_socket.recvfrom(
                    1024)
                segment = Segment.unpack(packet)

                if segment.segment_type == SEGMENT_TYPE_SYN:
                    log_actions(control_block, "rcv", segment, 0)
                    ack_segment = Segment(
                        SEGMENT_TYPE_ACK, control_block.expected_seqno)
                    control_block.receiver_socket.sendto(
                        ack_segment.pack(), sender_address)
                    control_block.total_ack_segments_sent += 1
                    log_actions(control_block, "snd", ack_segment, 0)

                if segment.segment_type == SEGMENT_TYPE_DATA:
                    log_actions(control_block, "rcv", segment, len(segment.data))
                    # 如果数据段按序到达，直接写入文件，并检查缓冲区中是否有连续的后续数据
                    if segment.seqno == control_block.expected_seqno:
                        control_block.original_data_received += len(
                            segment.data)
                        control_block.original_segments_received += 1
                        file.write(segment.data)
                        control_block.expected_seqno += len(segment.data)

                        # 检查并写入缓冲区中按序的数据
                        while control_block.expected_seqno in buffer:
                            data = buffer.pop(control_block.expected_seqno)
                            file.write(data)
                            control_block.expected_seqno += len(data)
                    elif segment.seqno > control_block.expected_seqno:  # 到达了乱序数据
                        if segment.seqno in buffer:
                            control_block.dup_data_segments_received += 1
                        else:
                            control_block.original_data_received += len(
                                segment.data)
                            control_block.original_segments_received += 1
                            buffer[segment.seqno] = segment.data
                    else:  # 到达的数据段已经写入文件
                        control_block.dup_data_segments_received += 1

                    # 发送ACK
                    control_block.total_ack_segments_sent += 1
                    ack_segment = Segment(
                        SEGMENT_TYPE_ACK, control_block.expected_seqno)
                    control_block.receiver_socket.sendto(
                        ack_segment.pack(), sender_address)
                    log_actions(control_block, "snd", ack_segment, 0)

                if segment.segment_type == SEGMENT_TYPE_FIN:
                    log_actions(control_block, "rcv", segment, 0)
                    handle_fin(control_block, sender_address)
                    break
            except socket.timeout:
                continue


def handle_fin(control_block, sender_address):
    # 发送ACK for FIN
    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno + 1)
    control_block.receiver_socket.sendto(ack_segment.pack(), sender_address)
    control_block.total_ack_segments_sent += 1
    log_actions(control_block, "snd", ack_segment, 0)

    # 定义处理FIN重传的线程函数
    def handle_fin_retransmissions():
        try:
            while True:
                packet, _ = control_block.receiver_socket.recvfrom(1024)
                segment = Segment.unpack(packet)

                if segment.segment_type == SEGMENT_TYPE_FIN:
                    # 对于重传的FIN，再次发送ACK
                    log_actions(control_block, "rcv", segment, 0)
                    control_block.receiver_socket.sendto(
                        ack_segment.pack(), sender_address)
                    log_actions(control_block, "snd", ack_segment, 0)
        except socket.timeout:
            # 超时意味着没有收到更多的FIN重传，线程结束
            pass

    # 启动处理FIN重传的线程
    fin_thread = threading.Thread(target=handle_fin_retransmissions)
    fin_thread.start()
    fin_thread.join()
    finalize_log(control_block)


def finalize_log(control_block):
    with open("receiver_log.txt", "a") as log_file:
        log_file.write(
            f"Original data received: {control_block.original_data_received}\n")
        log_file.write(
            f"Original segments received: {control_block.original_segments_received}\n")
        log_file.write(
            f"Dup data segments received: {control_block.dup_data_segments_received}\n")
        log_file.write(
            f"Dup ack segments sent: {control_block.total_ack_segments_sent - control_block.original_segments_received - 2}\n")


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(
            "Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    control_block = ControlBlock(receiver_port, sender_port,
                                 txt_file_received, max_win)
    handle_syn(control_block)
    receive_data(control_block)
