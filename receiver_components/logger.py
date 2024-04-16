import time


class ActionLogger:
    def __init__(self):
        self.started = False
        self.time_base = None
        self.original_data_received = 0
        self.original_segments_received = 0
        self.dup_data_segments_received = 0
        self.total_ack_segments_sent = 0
        with open("receiver_log.txt", "w"):
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
        with open("receiver_log.txt", "a") as receiver_log:
            receiver_log.write(
                f"{action} {time_stamp:.2f} {type_name} {seqno} {len_data}\n")

    def summary(self):
        with open("receiver_log.txt", "a") as receiver_log:
            receiver_log.write(
                f"Original data received: {self.original_data_received}\n")
            receiver_log.write(
                f"Original segments received: {self.original_segments_received}\n")
            receiver_log.write(
                f"Dup data segments received: {self.dup_data_segments_received}\n")
            receiver_log.write(
                f"Dup ack segments sent: {self.total_ack_segments_sent - self.original_segments_received - 2}\n")
