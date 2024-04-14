import time

class SenderLogger:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.init_time = None

    def log(self, action_type, type, seqno, len = 0):
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
            log_file.write(f"Original data sent: {control_block.original_data_sent}\n")
            log_file.write(f"Original data acked: {control_block.original_data_acked}\n")
            log_file.write(f"Original segments sent: {control_block.original_segments_sent}\n")
            log_file.write(f"Retransmitted segments: {control_block.retransmitted_segments}\n")
            log_file.write(f"Dup acks received: {control_block.dup_acks_received}\n")
            log_file.write(f"Data segments dropped: {control_block.data_segments_dropped}\n")
            log_file.write(f"Ack segments dropped: {control_block.ack_segments_dropped}\n")

    def write_log(self, log_entry):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(log_entry)