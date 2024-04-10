import socket
from segment import MSS, Segment, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN
from sender_utils.utils import send_segment, receive_segment

def handshake(sender_socket, receiver_address, control_block):
    # Set receive ACK timeout
    sender_socket.settimeout(control_block.rto / 1000.0)

    # Create and send SYN segment
    syn_segment = Segment(SEGMENT_TYPE_SYN, control_block.isn)
    control_block.set_state("SYN_SENT")  # Transition to SYN_SENT state
    send_segment(sender_socket, receiver_address, syn_segment, control_block)

    # Wait to receive ACK
    while True:
        try:
            ack_segment = receive_segment(sender_socket, control_block)

            if ack_segment.segment_type == SEGMENT_TYPE_ACK and ack_segment.seqno == control_block.isn + 1:
                # Transition to ESTABLISHED state
                control_block.set_state("ESTABLISHED")
                break
        except socket.timeout:
            # If waiting for ACK times out, resend SYN segment
            send_segment(sender_socket, receiver_address,
                         syn_segment, control_block, is_retransmitted=True)
        except AttributeError:
            # In case of an unexpected attribute error, possibly due to an unexpected segment format, ignore and continue
            continue