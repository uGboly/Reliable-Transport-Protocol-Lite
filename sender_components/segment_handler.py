import random
from STPSegment import STPSegment, SEGMENT_TYPE_DATA
from sender_components.logger import log_event

def send_segment(socket, address, segment, control_block, is_retransmitted=False):
    num_bytes = len(
        segment.data) if segment.segment_type == SEGMENT_TYPE_DATA else 0

    if random.random() < control_block.parameters['flp']:
        if segment.segment_type == SEGMENT_TYPE_DATA:
            control_block.data_segments_dropped += 1
            if not is_retransmitted:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1

        log_event("drp", segment.segment_type,
                  segment.seqno, num_bytes, control_block)
    else:
        socket.sendto(segment.pack(), address)
        log_event("snd", segment.segment_type,
                  segment.seqno, num_bytes, control_block)

        if segment.segment_type == SEGMENT_TYPE_DATA:
            if is_retransmitted:
                control_block.retransmitted_segments += 1
            else:
                control_block.original_data_sent += num_bytes
                control_block.original_segments_sent += 1


def receive_segment(socket, control_block):
    response, _ = socket.recvfrom(1024)
    segment = STPSegment.unpack(response)

    if random.random() < control_block.parameters['rlp']:
        control_block.ack_segments_dropped += 1
        log_event("drp", segment.segment_type, segment.seqno, 0, control_block)
        return
    else:
        log_event("rcv", segment.segment_type, segment.seqno, 0, control_block)
        return segment