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
        with open("sender_log.txt", "w"):
            pass

    def action_logging(self, action, type, seqno, len_data=0):
        time_now = time.time() * 1000
        type_name = {0: "DATA", 1: "ACK",
                     2: "SYN", 3: "FIN"}.get(type, "UNKNOWN")
        if not self.started:
            self.time_base = time_now
            self.started = True
            time_stamp = 0
        else:
            time_stamp = time_now - self.time_base
        with open("sender_log.txt", "a") as sender_log:
            sender_log.write(
                f"{action}\t{time_stamp:.2f}\t{type_name}\t{seqno}\t{len_data}\n")

    def summary(self):
        with open("sender_log.txt", "a") as sender_log:
            sender_log.write(
                f"Original data sent:          \t{self.original_data_sent}\n")
            sender_log.write(
                f"Original data acked:         \t{self.original_data_acked}\n")
            sender_log.write(
                f"Original segments sent:      \t{self.original_segments_sent}\n")
            sender_log.write(
                f"Retransmitted segments sent: \t{self.data_segments_dropped + self.ack_segments_dropped}\n")
            sender_log.write(
                f"Dup acks received:           \t{self.dup_acks_received}\n")
            sender_log.write(
                f"Data segments dropped:       \t{self.data_segments_dropped}\n")
            sender_log.write(
                f"Ack segments dropped:        \t{self.ack_segments_dropped}\n")
