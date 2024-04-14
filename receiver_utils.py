import time

class ReceiverLogger:
    def __init__(self, log_file_path="receiver_log.txt"):
        self.log_file_path = log_file_path
        self.init_time = None

    def log(self, act_type, segment, len=0):
        current_time = time.time() * 1000
        if self.init_time is None:
            self.init_time = current_time
            interval = 0
            with open(self.log_file_path, "w") as log_file:
                log_file.write("")
        else:
            interval = current_time - self.init_time
        type_name_list = ["DATA", "ACK", "SYN", "FIN"]

        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"{act_type} {interval:.2f} {type_name_list[segment.type]} {segment.seqno} {len}\n")

    def log_statatics(self, stat):
        with open(self.log_file_path, "a") as log_file:
            log_file.write(f"Original data received: {stat.window_manager.original_data_received}\n")
            log_file.write(f"Original segments received: {stat.window_manager.original_segments_received}\n")
            log_file.write(f"Dup data segments received: {stat.window_manager.dup_data_segments_received}\n")
            log_file.write(f"Dup ack segments sent: {stat.total_ack_segments_sent - stat.window_manager.original_segments_received - 2}\n")


class WindowManager:
    def __init__(self, receiver, file_path):
        self.file_path = file_path
        self.win = {}
        self.receiver = receiver
        self.original_data_received = 0
        self.original_segments_received = 0
        self.dup_data_segments_received = 0

    def handle_segment(self, segment):
        with open(self.file_path, 'ab') as file:
            if segment.seqno == self.receiver.next_seqno:  # In-order segment
                self.original_data_received += len(segment.data)
                self.original_segments_received += 1
                file.write(segment.data)
                self.update_next_seqno(len(segment.data))

                # Write any buffered, now in-order, segments
                while self.receiver.next_seqno in self.win:
                    data = self.win.pop(self.receiver.next_seqno)
                    file.write(data)
                    self.update_next_seqno(len(data))

            elif segment.seqno > self.receiver.next_seqno:  # Out-of-order segment
                if segment.seqno not in self.win:
                    self.win[segment.seqno] = segment.data
                else:
                    self.dup_data_segments_received += 1

    def update_next_seqno(self, data_length):
        self.receiver.next_seqno = (self.receiver.next_seqno + data_length) % (2 ** 16 - 1)