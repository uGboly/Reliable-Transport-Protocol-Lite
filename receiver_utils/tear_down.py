import threading
from segment import Segment, SEGMENT_TYPE_ACK, SEGMENT_TYPE_FIN
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError

def tear_down(control_block, sender_address):
    ack_segment = send_ack_for_fin(control_block, sender_address)
    handle_fin_retransmissions_in_background(control_block, sender_address, ack_segment)
    finalize_log(control_block)

def send_ack_for_fin(control_block, sender_address):
    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno + 1)
    send_segment(control_block, ack_segment, sender_address)
    control_block.total_ack_segments_sent += 1
    log_actions(control_block, "snd", ack_segment, 0)

    return ack_segment

def handle_fin_retransmissions_in_background(control_block, sender_address, ack_segment):
    stop_thread = threading.Event()

    def handle_fin_retransmissions():
        try:
            while not stop_thread.is_set():
                segment, _ = receive_segment(control_block)
                if segment.segment_type == SEGMENT_TYPE_FIN:
                    log_actions(control_block, "rcv", segment, 0)
                    send_segment(control_block, ack_segment, sender_address)
                    log_actions(control_block, "snd", ack_segment, 0)
        except ReceiveError:
            pass
        finally:
            stop_thread.set()

    fin_thread = threading.Thread(target=handle_fin_retransmissions)
    fin_thread.start()
    fin_thread.join()
    stop_thread.set()

def finalize_log(control_block):
    """Finalizes the log file with summary statistics."""
    summary_stats = f"""
Original data received: {control_block.original_data_received}
Original segments received: {control_block.original_segments_received}
Dup data segments received: {control_block.dup_data_segments_received}
Dup ack segments sent: {control_block.total_ack_segments_sent - control_block.original_segments_received - 2}
"""
    with open("receiver_log.txt", "a") as log_file:
        log_file.write(summary_stats)
