import time
import threading
import random
from segment import SEGMENT_TYPE_DATA


class ControlBlock:
    def __init__(self, max_win, rto, flp, rlp):
        self.state = "CLOSED"
        random.seed()
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.ackno = 0
        self.lock = threading.Lock()
        self.window_size = max_win
        self.rto = rto
        self.flp = flp
        self.rlp = rlp
        self.unack_segments = []
        self.timer = None
        self.dup_ack_count = {}
        self.start_time = 0
        self.is_syned = False
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

        if not self.is_syned:
            with open("sender_log.txt", "w") as log_file:
                log_file.write("")
            self.is_syned = True
            self.start_time = current_time

        time_offset = current_time - self.start_time
        segment_type_str = segment.segment_type_name()
        num_bytes = len(
            segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

        with open("sender_log.txt", "a") as log_file:
            log_file.write(
                f"{action} {time_offset:.2f} {segment_type_str} {segment.seqno} {num_bytes}\n")

    def print_statistics(self):
        with open("sender_log.txt", "a") as log_file:
            log_file.write(f"Original data sent: {self.original_data_sent}\n")
            log_file.write(
                f"Original data acked: {self.original_data_acked}\n")
            log_file.write(
                f"Original segments sent: {self.original_segments_sent}\n")
            log_file.write(
                f"Retransmitted segments: {self.retransmitted_segments}\n")
            log_file.write(f"Dup acks received: {self.dup_acks_received}\n")
            log_file.write(
                f"Data segments dropped: {self.data_segments_dropped}\n")
            log_file.write(
                f"Ack segments dropped: {self.ack_segments_dropped}\n")
