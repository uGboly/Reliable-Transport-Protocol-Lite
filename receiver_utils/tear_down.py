import threading
from segment import Segment, SEGMENT_TYPE_ACK, SEGMENT_TYPE_FIN
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError

def tear_down(control_block, sender_address):
    # 发送ACK for FIN
    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno + 1)
    send_segment(control_block, ack_segment, sender_address)
    control_block.total_ack_segments_sent += 1
    log_actions(control_block, "snd", ack_segment, 0)

    # 定义处理FIN重传的线程函数
    def handle_fin_retransmissions():
        try:
            while True:
                segment, _ = receive_segment(control_block)

                if segment.segment_type == SEGMENT_TYPE_FIN:
                    # 对于重传的FIN，再次发送ACK
                    log_actions(control_block, "rcv", segment, 0)
                    send_segment(control_block,
                                 ack_segment, sender_address)
                    log_actions(control_block, "snd", ack_segment, 0)
        except ReceiveError:
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