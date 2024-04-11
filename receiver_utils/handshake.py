from segment import Segment, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError

def handshake(control_block):
    received_syn = False
    while not received_syn:
        received_syn = process_syn_segment(control_block)
    
def process_syn_segment(control_block):
    try:
        segment, sender_address = receive_segment(control_block)
        if segment.segment_type == SEGMENT_TYPE_SYN:
            handle_syn_received(control_block, segment, sender_address)
            return True
    except ReceiveError:
        pass
    return False

def handle_syn_received(control_block, segment, sender_address):
    log_actions(control_block, "rcv", segment, 0)  # Log receiving SYN
    control_block.expected_seqno = segment.seqno + 1  # Update expected sequence number
    
    # Create and send ACK segment
    ack_segment = Segment(SEGMENT_TYPE_ACK, control_block.expected_seqno)
    send_segment(control_block, ack_segment, sender_address)
    
    # Update control_block and log sending ACK
    control_block.total_ack_segments_sent += 1
    log_actions(control_block, "snd", ack_segment, 0)
