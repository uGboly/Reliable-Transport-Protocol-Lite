import time


class ActionLogger:
    def __init__(self):
        self.started = False
        self.time_base = None
        self.original_data_received = 0
        self.original_segments_received = 0
        self.dup_data_segments_received = 0
        self.total_ack_segments_sent = 0
        self.log_file_path = "receiver_log.txt"
        # Clear or create the log file at initialization
        with open(self.log_file_path, "w"):
            pass

    def action_logging(self, action, event_type, seq_no, data_length=0):
        current_time_millis = self._get_current_time_millis()
        event_name = self._get_event_name(event_type)
        time_stamp = self._calculate_time_stamp(current_time_millis)

        log_entry = f"{action}\t{time_stamp:.2f}\t{event_name}\t{seq_no}\t{data_length}\n"
        self._append_to_log(log_entry)

    def _get_current_time_millis(self):
        """Returns the current time in milliseconds."""
        return time.time() * 1000

    def _get_event_name(self, event_type):
        """Translates an event type into a readable event name."""
        return {0: "DATA", 1: "ACK", 2: "SYN", 3: "FIN"}.get(event_type, "UNKNOWN")

    def _calculate_time_stamp(self, current_time_millis):
        """Calculates the time stamp since logging started, or initializes logging."""
        if not self.started:
            self.time_base = current_time_millis
            self.started = True
            return 0  # Initial event timestamp
        else:
            return current_time_millis - self.time_base  # Subsequent event timestamps

    def _append_to_log(self, log_entry):
        """Appends the given log entry to the log file."""
        with open(self.log_file_path, "a") as log_file:
            log_file.write(log_entry)

    def summary(self):
        with open("receiver_log.txt", "a") as receiver_log:
            receiver_log.write(
                f"Original data received:     \t{self.original_data_received}\n")
            receiver_log.write(
                f"Original segments received: \t{self.original_segments_received}\n")
            receiver_log.write(
                f"Dup data segments received: \t{self.dup_data_segments_received}\n")
            receiver_log.write(
                f"Dup ack segments sent:      \t{self.total_ack_segments_sent - self.original_segments_received - 2}")
