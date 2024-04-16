import time
from STPSegment import SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN


def log_event(action, segment_type, seqno, num_bytes, control_block):
    current_time = time.time() * 1000
    segment_type_str = {SEGMENT_TYPE_DATA: "DATA", SEGMENT_TYPE_ACK: "ACK",
                        SEGMENT_TYPE_SYN: "SYN", SEGMENT_TYPE_FIN: "FIN"}.get(segment_type, "UNKNOWN")
    if segment_type_str == "SYN":
        control_block.start_time = current_time
        time_offset = 0
    else:
        time_offset = current_time - control_block.start_time
    with open("sender_log.txt", "a") as log_file:
        log_file.write(
            f"{action} {time_offset:.2f} {segment_type_str} {seqno} {num_bytes}\n")