import time
import socket
from STPSegment import STPSegment, ACK, DATA, SYN, FIN

class ReceiverLogger:
    def __init__(self, log_file_path="receiver_log.txt"):
        self.log_file_path = log_file_path
        self.init_time = None

    def log(self, act_type, segment, len=0):
        current_time = time.time() * 1000
        if self.init_time is None:
            self.init_time = current_time
            with open(self.log_file_path, "w") as log_file:
                log_file.write("")

        interval = current_time - self.init_time
        type_name_list = ["DATA", "ACK", "SYN", "FIN"]

        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"{act_type} {interval:.2f} {type_name_list[segment.type]} {segment.seqno} {len}\n")

    def log_statatics(self, stat):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"Original data received: {stat.original_data_received}\n")
            log_file.write(f"Original segments received: {stat.original_segments_received}\n")
            log_file.write(f"Dup data segments received: {stat.dup_data_segments_received}\n")
            log_file.write(f"Dup ack segments sent: {stat.total_ack_segments_sent - stat.original_segments_received - 2}\n")
