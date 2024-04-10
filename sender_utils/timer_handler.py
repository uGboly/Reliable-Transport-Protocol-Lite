from sender_utils.utils import send_segment

def timer_handler(control_block, sender_socket, receiver_address):
    while True:
        with control_block.lock:
            # Check if the connection has been closed
            if control_block.is_state("CLOSE"):
                break

            if control_block.check_timer():
                # Handle timeout actions in a thread-safe manner
                handle_timeout(control_block, sender_socket, receiver_address)


def handle_timeout(control_block, sender_socket, receiver_address):
    if control_block.unack_segments:
        # Retransmit the oldest unacknowledged segment
        oldest_unack_segment = control_block.unack_segments[0]
        send_segment(sender_socket, receiver_address,
                     oldest_unack_segment, control_block, is_retransmitted=True)
        control_block.start_timer()  # Reset the timer for retransmission

        # Reset duplicate ACK count, since we have retransmitted a segment
        control_block.dup_ack_count = {}

    elif control_block.is_state("FIN_WAIT") and control_block.fin_segment:
        # If in FIN_WAIT state and there's a FIN segment to retransmit due to timeout
        send_segment(sender_socket, receiver_address,
                     control_block.fin_segment, control_block, is_retransmitted=True)
        control_block.start_timer()  # Reset the timer for FIN retransmission