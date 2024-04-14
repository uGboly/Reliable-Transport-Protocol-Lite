import time
import socket
import random
from STPSegment import STPSegment, ACK, DATA, SYN, FIN


class SenderLogger:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.init_time = None

    def log(self, action_type, type, seqno, len=0):
        current_time = time.time() * 1000
        if self.init_time is None:
            self.init_time = time.time() * 1000
            interval = 0
            with open(self.log_file_path, "w") as log_file:
                log_file.write("")
        else:
            interval = current_time - self.init_time

        type_name_list = ["DATA", "ACK", "SYN", "FIN"]
        log_entry = f"{action_type} {interval:.2f} {type_name_list[type]} {seqno} {len}\n"
        self.write_log(log_entry)

    def log_statatics(self, ctrlblo):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(
                f"Original data sent: {ctrlblo.original_data_sent}\n")
            log_file.write(
                f"Original data acked: {ctrlblo.original_data_acked}\n")
            log_file.write(
                f"Original segments sent: {ctrlblo.original_segments_sent}\n")
            log_file.write(
                f"Retransmitted segments: {ctrlblo.retransmitted_segments}\n")
            log_file.write(
                f"Dup acks received: {ctrlblo.dup_acks_received}\n")
            log_file.write(
                f"Data segments dropped: {ctrlblo.data_segments_dropped}\n")
            log_file.write(
                f"Ack segments dropped: {ctrlblo.ack_segments_dropped}\n")

    def write_log(self, log_entry):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(log_entry)


class ConnectionManager:
    def __init__(self, sender_socket, destination, ctrlblo, logger, rto, flp, rlp):
        self.sender_socket = sender_socket
        self.destination = destination
        self.ctrlblo = ctrlblo
        self.rto = rto
        self.flp = flp
        self.rlp = rlp
        self.logger = logger

    def setup(self):
        # Send SYN and wait for ACK to establish connection
        syn_segment = STPSegment(SYN, self.ctrlblo.init_seqno)
        self.send_message(syn_segment)
        self.wait_for_ack(self.ctrlblo.init_seqno +
                          1, "ESTABLISHED", syn_segment)

    def wait_for_ack(self, expected_seqno, next_state, message_to_retransmit):
        # Wait for ACK with a specific sequence number to transition to the next state
        self.sender_socket.settimeout(self.rto / 1000.0)
        while True:
            try:
                ackseg = self.receive_message()
                if ackseg.type == ACK and ackseg.seqno == expected_seqno:
                    self.ctrlblo.state = next_state
                    break
            except socket.timeout:
                self.send_message(message_to_retransmit)
            except AttributeError:
                pass

    def send_message(self, segment, retransmission=False):
        message_length = len(segment.data) if segment.type == DATA else 0

        if random.random() < self.flp and segment.type == DATA:
            self.ctrlblo.data_segments_dropped += 1
            if not retransmission:
                self.ctrlblo.original_data_sent += message_length
                self.ctrlblo.original_segments_sent += 1

            self.logger.log("drp", segment.type, segment.seqno, message_length)
        else:
            self.sender_socket.sendto(
                segment.serialize(), self.destination)
            self.logger.log("snd", segment.type, segment.seqno, message_length)

            if segment.type == DATA:
                if retransmission:
                    self.ctrlblo.retransmitted_segments += 1
                else:
                    self.ctrlblo.original_data_sent += message_length
                    self.ctrlblo.original_segments_sent += 1

    def receive_message(self):
        # Logic to receive a segment
        response, _ = self.sender_socket.recvfrom(1024)
        segment = STPSegment.unserialize(response)

        if random.random() < self.rlp:
            self.ctrlblo.ack_segments_dropped += 1
            self.logger.log("drp", segment.type, segment.seqno)
            return
        else:
            self.logger.log("rcv", segment.type, segment.seqno)
            return segment

    def finish(self):
        # Send FIN and wait for ACK to close connection
        fin_segment = STPSegment(FIN, self.ctrlblo.seqno)
        self.send_message(fin_segment)
        self.wait_for_ack(self.ctrlblo.seqno + 1, "CLOSED", fin_segment)
        self.sender_socket.close()
        self.logger.log_statatics(self.ctrlblo)


class DataTransmissionManager:
    def __init__(self, ctrlblo, connection_manager, data):
        self.ctrlblo = ctrlblo
        self.connection_manager = connection_manager
        self.data = data

    def send_data(self):
            total_length = len(self.data)
            sent_length = 0

            while sent_length < total_length or self.ctrlblo.sliding_window:
                with self.ctrlblo.lock:
                    window_space = self.calculate_window_space()

                    if window_space > 0 and sent_length < total_length:
                        segment_size, segment_data = self.segment_data(
                            sent_length, total_length, window_space)
                        self.send_segment_data(segment_data, segment_size)
                        sent_length += segment_size
            with self.ctrlblo.lock:
                self.ctrlblo.state = "FIN_WAIT"


    def calculate_window_space(self):
        return self.ctrlblo.max_win - (len(self.ctrlblo.sliding_window) * 1000)

    def segment_data(self, sent_length, total_length, window_space):
        segment_size = min(1000, total_length - sent_length, window_space)
        segment_data = self.data[sent_length:sent_length + segment_size]
        return segment_size, segment_data

    def send_segment_data(self, segment_data, segment_size):
        new_segment = STPSegment(DATA, self.ctrlblo.seqno, segment_data)

        if not self.ctrlblo.sliding_window:
            self.ctrlblo.timer = time.time() * 1000 + self.ctrlblo.rto
        self.ctrlblo.sliding_window.append(new_segment)
        self.ctrlblo.seqno = (
            self.ctrlblo.seqno + segment_size) % (2 ** 16)
        self.connection_manager.send_message(new_segment)


class AckReceiver:
    def __init__(self, ctrlblo, connection_manager):
        self.ctrlblo = ctrlblo
        self.connection_manager = connection_manager

    def run(self):
        while True:
            if self.ctrlblo.state == "FIN_WAIT":
                break

            try:
                ackseg = self.connection_manager.receive_message()
                self.process_ackseg(ackseg)
            except socket.timeout:
                continue
            except AttributeError:
                continue

    def process_ackseg(self, ackseg):
        with self.ctrlblo.lock:
            if self.is_new_ack(ackseg):
                self.update_ctrlblo_for_new_ack(ackseg)
            else:
                self.handle_duplicate_ack(ackseg)

    def is_new_ack(self, ackseg):
        return ackseg.seqno in [(seg.seqno + len(seg.data)) % 2 ** 16 for seg in self.ctrlblo.sliding_window]

    def update_ctrlblo_for_new_ack(self, ackseg):
        # Update original data acked and sliding window
        index_ack_seg = [index for index, seg in enumerate(
            self.ctrlblo.sliding_window) if (seg.seqno + len(seg.data)) % 2 ** 16 == ackseg.seqno][0]
        for seg in self.ctrlblo.sliding_window[:index_ack_seg + 1]:
            self.ctrlblo.original_data_acked += len(seg.data)

        self.ctrlblo.sliding_window = self.ctrlblo.sliding_window[index_ack_seg + 1:]
        # Reset timer if there are unacknowledged segments
        self.ctrlblo.timer = time.time() * 1000 + \
            self.ctrlblo.rto if self.ctrlblo.sliding_window else None
        self.ctrlblo.ack_counter = {}

    def handle_duplicate_ack(self, ackseg):
        self.ctrlblo.dup_acks_received += 1
        self.ctrlblo.ack_counter[ackseg.seqno] = self.ctrlblo.ack_counter.get(
            ackseg.seqno, 0) + 1
        if self.ctrlblo.ack_counter[ackseg.seqno] == 3:
            self.fast_retransmit()

    def fast_retransmit(self):
        self.connection_manager.send_message(
            self.ctrlblo.sliding_window[0], True)
        # Reset timer
        self.ctrlblo.timer = time.time() * 1000 + self.ctrlblo.rto
        self.ctrlblo.ack_counter = {}


class TimerManager:
    def __init__(self, ctrlblo, connection_manager):
        self.ctrlblo = ctrlblo
        self.connection_manager = connection_manager

    def run(self):
        while True:
            with self.ctrlblo.lock:
                if self.ctrlblo.state == "FIN_WAIT":
                    break
                self.check_and_handle_timeout()

    def check_and_handle_timeout(self):
        current_time = time.time() * 1000  # Current time in milliseconds
        if self.ctrlblo.timer is not None and current_time >= self.ctrlblo.timer:
            self.handle_timeout()

    def handle_timeout(self):
        if self.ctrlblo.sliding_window:
            oldest_unackseg = self.ctrlblo.sliding_window[0]
            self.retransmit_segment(oldest_unackseg)
            # Reset the timer for the next timeout check
            self.ctrlblo.timer = time.time() * 1000 + self.ctrlblo.rto
            # Reset the ACK counter since we're performing a retransmission
            self.ctrlblo.ack_counter = {}

    def retransmit_segment(self, segment):
        # Logic to mark the segment as a retransmission could be added here
        self.connection_manager.send_message(segment, True)
