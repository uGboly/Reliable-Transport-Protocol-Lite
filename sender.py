import socket
import random
import sys
import time
import threading
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

MSS = 1000


class STPControlBlock:
    def __init__(self, max_win, rto):
        self.state = "CLOSED"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.ackno = 0
        self.lock = threading.Lock()
        self.window_size = max_win
        self.rto = rto
        self.unack_segments = []
        self.timer = None
        self.dup_ack_count = {}
        self.start_time = 0
        self.fin_segment = None
        # Statistics
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0

    def set_state(self, new_state):
        self.state = new_state

    def is_state(self, state):
        return self.state == state

    def start_timer(self, duration=None):
        if duration is None:
            duration = self.rto
        self.timer = time.time() * 1000 + duration

    def cancel_timer(self):
        self.timer = None

    def check_timer(self):
        if self.timer and time.time() * 1000 >= self.timer:
            self.timer = None  # Reset timer
            return True
        return False

    def add_unacknowledged_segment(self, segment):
        self.unack_segments.append(segment)
        if len(self.unack_segments) == 1:  # If this is the first unacknowledged segment
            self.start_timer()

    def acknowledge_segment(self, ackno):
        self.ackno = ackno

        for seg in self.unack_segments:
            if seg.seqno < ackno:
                self.original_data_acked += len(seg.data)

        # Remove acknowledged segments
        self.unack_segments = [
            seg for seg in self.unack_segments if seg.seqno >= ackno]
        
        if not self.unack_segments:
            self.cancel_timer()

    def safely_execute(self, func, *args, **kwargs):
        with self.lock:
            return func(*args, **kwargs)

    def log_event(self, action, segment):
        current_time = time.time() * 1000
        time_offset = 0 if self.start_time == 0 else current_time - self.start_time
        segment_type_str = segment.segment_type_name()
        num_bytes = len(
            segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

        with open("sender_log.txt", "a") as log_file:
            log_file.write(
                f"{action} {time_offset:.2f} {segment_type_str} {segment.seqno} {num_bytes}\n")

    def get_statistics(self):
        return {
            "original_data_sent": self.original_data_sent,
            "original_data_acked": self.original_data_acked,
            "original_segments_sent": self.original_segments_sent,
            "retransmitted_segments": self.retransmitted_segments,
            "dup_acks_received": self.dup_acks_received,
            "data_segments_dropped": self.data_segments_dropped,
            "ack_segments_dropped": self.ack_segments_dropped,
        }


def send_segment(socket, address, segment, control_block, is_retransmitted=False):
    num_bytes = len(
        segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

    # Simulate segment dropping based on flp (failure probability)
    if random.random() < flp:
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
    try:
        # Adjust the buffer size if necessary
        response, _ = socket.recvfrom(1024)
        segment = STPSegment.unpack(response)

        # Simulate ACK segment dropping based on rlp (failure probability for ACK segments)
        if random.random() < rlp:
            control_block.log_event("drp", segment)  # Log the drop
            control_block.ack_segments_dropped += 1
            return
        else:
            control_block.log_event("rcv", segment)  # Log the receipt
            return segment
    except socket.error as e:
        print(f"Socket error: {e}")
        return None


def establish_connection(sender_socket, receiver_address, control_block):
    # Set receive ACK timeout
    sender_socket.settimeout(control_block.rto / 1000.0)

    # Create and send SYN segment
    syn_segment = STPSegment(SEGMENT_TYPE_SYN, control_block.isn)
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
                    new_segment = STPSegment(
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
        fin_segment = STPSegment(SEGMENT_TYPE_FIN, control_block.seqno)
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


def finalize_log(control_block):
    stats = control_block.get_statistics()  # Thread-safe retrieval of statistics

    with open("sender_log.txt", "a") as log_file:
        log_file.write(f"Original data sent: {stats['original_data_sent']}\n")
        log_file.write(
            f"Original data acked: {stats['original_data_acked']}\n")
        log_file.write(
            f"Original segments sent: {stats['original_segments_sent']}\n")
        log_file.write(
            f"Retransmitted segments: {stats['retransmitted_segments']}\n")
        log_file.write(f"Dup acks received: {stats['dup_acks_received']}\n")
        log_file.write(
            f"Data segments dropped: {stats['data_segments_dropped']}\n")
        log_file.write(
            f"Ack segments dropped: {stats['ack_segments_dropped']}\n")


def main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp):
    random.seed()

    with open("sender_log.txt", "w") as log_file:
        log_file.write("")

    control_block = STPControlBlock(max_win, rto)
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    receiver_address = ('localhost', receiver_port)

    try:
        establish_connection(sender_socket, receiver_address, control_block)

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
        finalize_log(control_block)


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
