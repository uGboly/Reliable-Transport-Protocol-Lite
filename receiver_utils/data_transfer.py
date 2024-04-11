from segment import Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError
from receiver_utils.tear_down import tear_down

def data_transfer(control_block):
    sliding_window = {}
    with open(control_block.file_to_save, 'wb') as file:
        while True:
            try:
                segment, sender_address = receive_segment(control_block)
                if segment.segment_type == SEGMENT_TYPE_SYN:
                    handle_syn_segment(control_block, segment, sender_address)
                elif segment.segment_type == SEGMENT_TYPE_DATA:
                    handle_data_segment(
                        control_block, segment, sender_address, file, sliding_window)
                elif segment.segment_type == SEGMENT_TYPE_FIN:
                    handle_fin_segment(control_block, segment, sender_address)
                    break
            except ReceiveError:
                continue


def handle_syn_segment(control_block, segment, sender_address):
    log_and_acknowledge(control_block, segment, sender_address)


def handle_data_segment(control_block, segment, sender_address, file, sliding_window):
    log_actions(control_block, "rcv", segment, len(segment.data))
    process_in_order_segment(control_block, segment, file, sliding_window)
    process_out_of_order_segment(control_block, segment, sliding_window)
    send_acknowledgement(control_block, sender_address)


def process_in_order_segment(control_block, segment, file, sliding_window):
    if segment.seqno == control_block.expected_seqno:
        write_data_and_update_control(control_block, segment.data, file)
        check_and_write_sliding_buffered_data(control_block, file, sliding_window)


def process_out_of_order_segment(control_block, segment, sliding_window):
    if segment.seqno > control_block.expected_seqno:
        if segment.seqno not in sliding_window:
            sliding_window[segment.seqno] = segment.data
        else:
            control_block.dup_data_segments_received += 1


def write_data_and_update_control(control_block, data, file):
    file.write(data)
    control_block.original_data_received += len(data)
    control_block.original_segments_received += 1
    control_block.expected_seqno += len(data)


def check_and_write_sliding_buffered_data(control_block, file, sliding_window):
    while control_block.expected_seqno in sliding_window:
        data = sliding_window.pop(control_block.expected_seqno)
        write_data_and_update_control(control_block, data, file)


def send_acknowledgement(control_block, sender_address):
    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno)
    send_segment(control_block, ack_segment, sender_address)
    log_actions(control_block, "snd", ack_segment, 0)
    control_block.total_ack_segments_sent += 1


def handle_fin_segment(control_block, segment, sender_address):
    log_actions(control_block, "rcv", segment, 0)
    tear_down(control_block, sender_address)


def log_and_acknowledge(control_block, segment, sender_address):
    log_actions(control_block, "rcv", segment, 0)

    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno)
    send_segment(control_block, ack_segment, sender_address)

    log_actions(control_block, "snd", ack_segment, 0)

    control_block.total_ack_segments_sent += 1
