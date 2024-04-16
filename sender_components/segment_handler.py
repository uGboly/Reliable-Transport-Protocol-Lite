import random
from STPSegment import STPSegment
import struct
from sender_components.logger import log_event


def send_segment(control_block, type, seqno, data=b'', is_retransmitted=False):
    num_bytes = len(data) if type == 0 else 0

    if random.random() < control_block.parameters['flp']:
        if type == 0:
            control_block.data_segments_dropped += 1
            if not is_retransmitted:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1

        log_event("drp", type,
                  seqno, num_bytes, control_block)
    else:
        sent_data = struct.pack('!HH', type, seqno) + data
        control_block.sock.sendto(sent_data, control_block.dest)
        log_event("snd", type,
                  seqno, num_bytes, control_block)

        if type == 0:
            if is_retransmitted:
                control_block.retransmitted_segments += 1
            else:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1


def receive_segment(control_block):
    response, _ = control_block.sock.recvfrom(1024)
    _, ack_seqno = struct.unpack('!HH', response)

    if random.random() < control_block.parameters['rlp']:
        control_block.ack_segments_dropped += 1
        log_event("drp", 1, ack_seqno, 0, control_block)
        return
    else:
        log_event("rcv", 1, ack_seqno, 0, control_block)
        return ack_seqno
