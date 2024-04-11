import socket
import time
from segment import Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN

SEGMENT_TYPE_STRINGS = {
    SEGMENT_TYPE_DATA: "DATA",
    SEGMENT_TYPE_ACK: "ACK",
    SEGMENT_TYPE_SYN: "SYN",
    SEGMENT_TYPE_FIN: "FIN",
}

def log_actions(control_block, action, segment, num_bytes):
    current_time = int(time.time() * 1000)
    segment_type_str = SEGMENT_TYPE_STRINGS.get(segment.segment_type, "UNKNOWN")
    
    # Initialize or update the start_time and calculate time_offset
    time_offset = initialize_or_update_time(control_block, current_time, segment_type_str)
    
    # Log the event
    log_to_file(action, time_offset, segment_type_str, segment.seqno, num_bytes)

def initialize_or_update_time(control_block, current_time, segment_type_str):
    if control_block.start_time == 0:
        control_block.start_time = current_time
        with open("receiver_log.txt", "w") as log_file:
            pass
        return 0  # No time offset for the SYN segment
    else:
        return current_time - control_block.start_time

def log_to_file(action, time_offset, segment_type, seqno, num_bytes):
    with open("receiver_log.txt", "a") as log_file:
        log_entry = f"{action} {time_offset:.2f} {segment_type} {seqno} {num_bytes}\n"
        log_file.write(log_entry)

def receive_segment(control_block):
    try:
        packet, sender_address = control_block.receiver_socket.recvfrom(
                    1024)
        segment = Segment.unpack(packet)

        return [segment, sender_address]
    except socket.timeout:
        raise ReceiveError("socke timeout!")
    
def send_segment(control_block, segment, target):
    packed_segment = segment.pack()
    control_block.receiver_socket.sendto(packed_segment, target)
    
class ReceiveError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)