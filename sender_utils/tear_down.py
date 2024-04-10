from segment import Segment, SEGMENT_TYPE_FIN
from sender_utils.utils import send_segment


def tear_down(sender_socket, receiver_address, control_block):
    # Ensure all data has been acknowledged before initiating closure
    with control_block.lock:
        wait_for_acknowledgements(control_block)

        # Create and send the FIN segment
        fin_segment = Segment(SEGMENT_TYPE_FIN, control_block.seqno)
        control_block.fin_segment = fin_segment
        send_segment(sender_socket, receiver_address, fin_segment,
                     control_block, is_retransmitted=False)

        # Transition to FIN_WAIT state and start the timer for potential retransmission
        transition_to_fin_wait(control_block)


def wait_for_acknowledgements(control_block):
    while control_block.unack_segments:
        pass  # Busy wait or sleep for a short duration


def transition_to_fin_wait(control_block):
    if not control_block.unack_segments:
        control_block.set_state("FIN_WAIT")
        control_block.start_timer()
