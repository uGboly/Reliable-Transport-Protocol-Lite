import socket
import random
import sys
import threading
from segment import MSS, Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
from sender_utils.control_block import ControlBlock, handshake
from sender_utils.utils import send_segment, receive_segment


def ack_receiver(control_block, sender_socket, receiver_address):
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
                if ack_segment.seqno <= control_block.ackno:
                    handle_duplicate_ack(
                        control_block, ack_segment, sender_socket, receiver_address)

        except socket.timeout:
            # If the socket blocks and times out, continue listening
            continue
        except AttributeError:
            # In case of an unexpected attribute error, possibly due to an unexpected segment format, ignore and continue
            continue


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


def send_file(filename, control_block, sender_socket, receiver_address):
    try:
        with open(filename, 'rb') as file:
            file_data = file.read()

        total_length = len(file_data)
        sent_length = 0

        # Data sending loop
        while sent_length < total_length or control_block.unack_segments:
            # Calculate the window space taking into account the unacknowledged segments
            with control_block.lock:
                window_space = calculate_window_space(control_block)

                # Check if there is window space to send more data
                if window_space > 0 and sent_length < total_length:
                    # Determine the size of the data to send in this segment
                    segment_size = min(MSS, total_length -
                                    sent_length, window_space)
                    segment_data = file_data[sent_length:sent_length+segment_size]
                    new_segment = Segment(
                        SEGMENT_TYPE_DATA, control_block.seqno, data=segment_data)

                    # Send the new data segment
                    send_segment(sender_socket, receiver_address,
                                new_segment, control_block)

                    # Update control block information for the sent segment
                    update_control_block_for_sent_segment(
                        control_block, segment_size, new_segment)

                    sent_length += segment_size
    except IOError as e:
        print(f"Error reading file {filename}: {e}")


def calculate_window_space(control_block):
    return control_block.window_size - (len(control_block.unack_segments) * MSS)


def update_control_block_for_sent_segment(control_block, segment_size, segment):
    if not control_block.unack_segments:
        control_block.start_timer()  # Start the timer for the first unacknowledged segment
    control_block.unack_segments.append(segment)
    control_block.seqno += segment_size


def close_connection(sender_socket, receiver_address, control_block):
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


def main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp):
    random.seed()

    with open("sender_log.txt", "w") as log_file:
        log_file.write("")

    control_block = ControlBlock(max_win, rto, flp, rlp)
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    receiver_address = ('localhost', receiver_port)

    try:
        handshake(sender_socket, receiver_address, control_block)

        ack_thread = threading.Thread(target=ack_receiver, args=(
            control_block, sender_socket, receiver_address))
        timer_thread = threading.Thread(target=timer_handler, args=(
            control_block, sender_socket, receiver_address))
        ack_thread.start()
        timer_thread.start()

        send_file(txt_file_to_send, control_block,
                  sender_socket, receiver_address)

        close_connection(sender_socket, receiver_address, control_block)

        ack_thread.join()
        timer_thread.join()

    finally:
        sender_socket.close()
        control_block.print_statistics()


if __name__ == '__main__':
    if len(sys.argv) != 8:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send max_win rto flp rlp")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]
    max_win = int(sys.argv[4])
    rto = int(sys.argv[5])
    flp = float(sys.argv[6])
    rlp = float(sys.argv[7])

    main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp)
