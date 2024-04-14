import time
import socket
import random
from STPSegment import STPSegment, ACK, DATA, SYN, FIN


class SenderLogger:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.init_time = None

    def log(self, action_type, type, seqno, len=0):
        if self.init_time is None:
            self.init_time = time.time() * 1000
            interval = 0
            with open(self.log_file_path, "w") as log_file:
                log_file.write("")
        else:
            current_time = time.time() * 1000
            interval = current_time - self.init_time

        type_name_list = ["DATA", "ACK", "SYN", "FIN"]
        log_entry = f"{action_type} {interval:.2f} {type_name_list[type]} {seqno} {len}\n"
        self.write_log(log_entry)

    def log_statatics(self, control_block):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(
                f"Original data sent: {control_block.original_data_sent}\n")
            log_file.write(
                f"Original data acked: {control_block.original_data_acked}\n")
            log_file.write(
                f"Original segments sent: {control_block.original_segments_sent}\n")
            log_file.write(
                f"Retransmitted segments: {control_block.retransmitted_segments}\n")
            log_file.write(
                f"Dup acks received: {control_block.dup_acks_received}\n")
            log_file.write(
                f"Data segments dropped: {control_block.data_segments_dropped}\n")
            log_file.write(
                f"Ack segments dropped: {control_block.ack_segments_dropped}\n")

    def write_log(self, log_entry):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(log_entry)


class ConnectionManager:
    def __init__(self, sender_socket, receiver_address, control_block, logger, rto, flp, rlp):
        self.sender_socket = sender_socket
        self.receiver_address = receiver_address
        self.control_block = control_block
        self.rto = rto
        self.flp = flp
        self.rlp = rlp
        self.logger = logger

    def setup(self):
        # Send SYN and wait for ACK to establish connection
        syn_segment = STPSegment(SYN, self.control_block.init_seqno)
        self.send_message(syn_segment)
        self.wait_for_ack(self.control_block.init_seqno +
                          1, "ESTABLISHED", syn_segment)

    def wait_for_ack(self, expected_seqno, next_state, message_to_retransmit):
        # Wait for ACK with a specific sequence number to transition to the next state
        self.sender_socket.settimeout(self.rto / 1000.0)
        while True:
            try:
                ack_segment = self.receive_message()
                if ack_segment.type == ACK and ack_segment.seqno == expected_seqno:
                    self.control_block.ackno = ack_segment.seqno
                    self.control_block.state = next_state
                    break
            except socket.timeout:
                self.send_message(message_to_retransmit)
            except AttributeError:
                pass

    def send_message(self, segment, is_retransmitted=False):
        num_bytes = len(segment.data) if segment.type == DATA else 0

        if random.random() < self.flp and segment.type == DATA:
            self.control_block.data_segments_dropped += 1
            if not is_retransmitted:
                self.control_block.original_data_sent += num_bytes
                self.control_block.original_segments_sent += 1

            self.logger.log("drp", segment.type, segment.seqno, num_bytes)
        else:
            self.sender_socket.sendto(
                segment.serialize(), self.receiver_address)
            self.logger.log("snd", segment.type, segment.seqno, num_bytes)

            if segment.type == DATA:
                if is_retransmitted:
                    self.control_block.retransmitted_segments += 1
                else:
                    self.control_block.original_data_sent += num_bytes
                    self.control_block.original_segments_sent += 1
            self.sender_socket.sendto(
                segment.serialize(), self.receiver_address)

    def receive_message(self):
        # Logic to receive a segment
        response, _ = self.sender_socket.recvfrom(1024)
        segment = STPSegment.unserialize(response)

        if random.random() < self.rlp:
            self.control_block.ack_segments_dropped += 1
            self.logger.log("drp", segment.type, segment.seqno)
            return
        else:
            self.logger.log("rcv", segment.type, segment.seqno)
            return segment

    def finish(self):
        # Send FIN and wait for ACK to close connection
        fin_segment = STPSegment(FIN, self.control_block.seqno)
        self.send_message(fin_segment)
        self.wait_for_ack(self.control_block.seqno + 1, "CLOSED", fin_segment)
        self.sender_socket.close()
        self.logger.log_statatics(self.control_block)


class DataTransmissionManager:
    MSS = 1000  # Maximum Segment Size

    def __init__(self, control_block, connection_manager, data):
        self.control_block = control_block
        self.connection_manager = connection_manager
        self.data = data

    def send_data(self):
        total_length = len(self.data)
        sent_length = 0

        while sent_length < total_length or self.control_block.sliding_window:
            window_space = self.calculate_window_space()

            if window_space > 0 and sent_length < total_length:
                segment_size, segment_data = self.segment_data(
                    sent_length, total_length, window_space)
                self.send_segment_data(segment_data, segment_size)
                sent_length += segment_size

    def calculate_window_space(self):
        with self.control_block.lock:
            return self.control_block.max_win - (len(self.control_block.sliding_window) * self.MSS)

    def segment_data(self, sent_length, total_length, window_space):
        segment_size = min(self.MSS, total_length - sent_length, window_space)
        segment_data = self.data[sent_length:sent_length + segment_size]
        return segment_size, segment_data

    def send_segment_data(self, segment_data, segment_size):
        new_segment = STPSegment(DATA, self.control_block.seqno, segment_data)
        self.connection_manager.send_message(new_segment)

        with self.control_block.lock:
            if not self.control_block.sliding_window:
                self.control_block.timer = time.time() * 1000 + self.control_block.rto
            self.control_block.sliding_window.append(new_segment)
            self.control_block.seqno = (
                self.control_block.seqno + segment_size) % (2 ** 16 - 1)

class AckReceiver:
    def __init__(self, control_block, connection_manager):
        self.control_block = control_block
        self.connection_manager = connection_manager

    def run(self):
        while True:
            if self.control_block.state == "FIN_WAIT":
                break

            try:
                ack_segment = self.connection_manager.receive_message()
                self.process_ack_segment(ack_segment)
            except socket.timeout:
                continue
            except AttributeError:
                continue

    def process_ack_segment(self, ack_segment):
        with self.control_block.lock:
            if self.is_new_ack(ack_segment):
                self.update_control_block_for_new_ack(ack_segment)
            else:
                self.handle_duplicate_ack(ack_segment)

    def is_new_ack(self, ack_segment):
        return ack_segment.seqno >= self.control_block.ackno or ack_segment.seqno < self.control_block.init_seqno

    def update_control_block_for_new_ack(self, ack_segment):
        self.control_block.ackno = ack_segment.seqno
        # Update original data acked and sliding window
        self.control_block.original_data_acked += sum(len(seg.data) for seg in self.control_block.sliding_window if seg.seqno < ack_segment.seqno)
        self.control_block.sliding_window = [seg for seg in self.control_block.sliding_window if seg.seqno >= ack_segment.seqno]
        # Reset timer if there are unacknowledged segments
        self.control_block.timer = time.time() * 1000 + self.control_block.rto if self.control_block.sliding_window else None
        self.control_block.ack_counter = {}

    def handle_duplicate_ack(self, ack_segment):
        self.control_block.dup_acks_received += 1
        self.control_block.ack_counter[ack_segment.seqno] = self.control_block.ack_counter.get(ack_segment.seqno, 0) + 1
        if self.control_block.ack_counter[ack_segment.seqno] == 3:
            self.fast_retransmit(ack_segment.seqno)

    def fast_retransmit(self, seqno):
        for seg in self.control_block.sliding_window:
            if seg.seqno == seqno:
                self.connection_manager.send_message(seg, True)
                # Reset timer
                self.control_block.timer = time.time() * 1000 + self.control_block.rto
                break


class TimerManager:
    def __init__(self, control_block, connection_manager):
        self.control_block = control_block
        self.connection_manager = connection_manager

    def run(self):
        while True:
            with self.control_block.lock:
                if self.control_block.state == "FIN_WAIT":
                    break
                self.check_and_handle_timeout()

    def check_and_handle_timeout(self):
        current_time = time.time() * 1000  # Current time in milliseconds
        if self.control_block.timer is not None and current_time >= self.control_block.timer:
            self.handle_timeout()

    def handle_timeout(self):
        if self.control_block.sliding_window:
            oldest_unack_segment = self.control_block.sliding_window[0]
            self.retransmit_segment(oldest_unack_segment)
            # Reset the timer for the next timeout check
            self.control_block.timer = time.time() * 1000 + self.control_block.rto
            # Reset the ACK counter since we're performing a retransmission
            self.control_block.ack_counter = {}

    def retransmit_segment(self, segment):
        # Logic to mark the segment as a retransmission could be added here
        self.connection_manager.send_message(segment, True)
