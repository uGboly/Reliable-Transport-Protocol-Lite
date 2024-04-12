from sender_utils.utils import send_segment, receive_segment, ReceiveError

def ack_handler(control_block, sender_socket, receiver_address):
    while True:
        try:
            with control_block.lock:
                # Receive ACK
                ack_segment = receive_segment(sender_socket, control_block)

                # Handle ACK reception based on the current state
                if control_block.is_state("FIN_WAIT") and ack_segment.seqno == control_block.seqno + 1:
                    # If in FIN_WAIT state and the ACK for the FIN is received
                    control_block.set_state("CLOSE")
                    break  # Exit the loop, closing the connection

                control_block.acknowledge_segment(ack_segment.seqno)

                # Handle duplicate ACKs
                if ack_segment.seqno < control_block.ackno:
                    handle_duplicate_ack(
                        control_block, ack_segment, sender_socket, receiver_address)

        except ReceiveError:
            pass



def handle_duplicate_ack(control_block, ack_segment, sender_socket, receiver_address):
    control_block.dup_acks_received += 1
    if ack_segment.seqno in control_block.dup_ack_count:
        control_block.dup_ack_count[ack_segment.seqno] += 1
    else:
        control_block.dup_ack_count[ack_segment.seqno] = 1

        # Fast retransmit on the third duplicate ACK
        if control_block.dup_ack_count[ack_segment.seqno] == 3:
            for seg in control_block.unack_segments:
                if seg.seqno == ack_segment.seqno:
                    # Retransmit the segment
                    send_segment(sender_socket, receiver_address,
                                 seg, control_block, is_retransmitted=True)
                    # Reset the timer for retransmission
                    control_block.start_timer()
                    break