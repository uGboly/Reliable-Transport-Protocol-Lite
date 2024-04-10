import random
from segment import Segment, SEGMENT_TYPE_DATA

def send_segment(socket, address, segment, control_block, is_retransmitted=False):
    num_bytes = len(
        segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

    # Simulate segment dropping based on flp (failure probability)
    if random.random() < control_block.flp:
        # Updated to use the enhanced logging method
        control_block.log_event("drp", segment)
        if segment.segment_type == SEGMENT_TYPE_DATA:
            update_drop_stats(control_block, num_bytes, is_retransmitted)
    else:
        socket.sendto(segment.pack(), address)
        # Updated to use the enhanced logging method
        control_block.log_event("snd", segment)
        if segment.segment_type == SEGMENT_TYPE_DATA:
            update_send_stats(control_block, num_bytes, is_retransmitted)


def update_drop_stats(control_block, num_bytes, is_retransmitted):
    control_block.data_segments_dropped += 1
    if not is_retransmitted:
        control_block.original_data_sent += num_bytes
        control_block.original_segments_sent += 1


def update_send_stats(control_block, num_bytes, is_retransmitted):
    if is_retransmitted:
        control_block.retransmitted_segments += 1
    else:
        control_block.original_data_sent += num_bytes
        control_block.original_segments_sent += 1


def receive_segment(socket, control_block):
    # Adjust the buffer size if necessary
    response, _ = socket.recvfrom(1024)
    segment = Segment.unpack(response)

    # Simulate ACK segment dropping based on rlp (failure probability for ACK segments)
    if random.random() < control_block.rlp:
        control_block.log_event("drp", segment)  # Log the drop
        control_block.ack_segments_dropped += 1
        return None
    else:
        control_block.log_event("rcv", segment)  # Log the receipt
        return segment