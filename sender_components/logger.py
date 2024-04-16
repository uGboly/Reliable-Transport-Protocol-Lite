import time


class ActionLogger:
    def __init__(self):
        self.started = False
        self.time_base = None
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0
        self.log_file_path = "sender_log.txt"
        with open(self.log_file_path, "w") as file:
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
        """Returns the name of the event based on its type."""
        return {0: "DATA", 1: "ACK", 2: "SYN", 3: "FIN"}.get(event_type, "UNKNOWN")

    def _calculate_time_stamp(self, current_time_millis):
        """Calculates the time stamp relative to the base time if logging has started."""
        if not self.started:
            self.time_base = current_time_millis
            self.started = True
            return 0
        else:
            return current_time_millis - self.time_base

    def _append_to_log(self, log_entry):
        """Appends a given log entry to the log file."""
        with open(self.log_file_path, "a") as log_file:
            log_file.write(log_entry)

    def summary(self):
        summary_content = [
            ("Original data sent", self.original_data_sent),
            ("Original data acked", self.original_data_acked),
            ("Original segments sent", self.original_segments_sent),
            ("Retransmitted segments sent", self.data_segments_dropped + self.ack_segments_dropped),
            ("Dup acks received", self.dup_acks_received),
            ("Data segments dropped", self.data_segments_dropped),
            ("Ack segments dropped", self.ack_segments_dropped),
        ]

        # Open the log file once and write all summary lines
        with open("sender_log.txt", "a") as sender_log:
            for description, value in summary_content:
                if description == "Ack segments dropped":
                    sender_log.write(f"{description}: \t{value}")
                else:
                    sender_log.write(f"{description}: \t{value}\n")
