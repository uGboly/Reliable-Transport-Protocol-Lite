import time
import socket
import random
from STPSegment import STPSegment, ACK, DATA, SYN, FIN

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
        syn_segment = STPSegment(SYN, self.control_block.isn)
        self.send_message(syn_segment)
        self.wait_for_ack(self.control_block.isn + 1, "ESTABLISHED", syn_segment)

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
            self.sender_socket.sendto(segment.serialize(), self.receiver_address)
            self.logger.log("snd", segment.type, segment.seqno, num_bytes)

            if segment.type == DATA:
                if is_retransmitted:
                    self.control_block.retransmitted_segments += 1
                else:
                    self.control_block.original_data_sent += num_bytes
                    self.control_block.original_segments_sent += 1
            self.sender_socket.sendto(segment.serialize(), self.receiver_address)

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