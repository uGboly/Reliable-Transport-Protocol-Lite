import random
import struct


def snd_seg(control_block, type, seqno, data=b'', old_seg=False):
    len_data = len(data) if type == 0 else 0

    if random.random() < control_block.parameters['flp']:
        if type == 0:
            control_block.action_logger.data_segments_dropped += 1
            if not old_seg:
                control_block.action_logger.original_data_sent += len_data
                control_block.action_logger.original_segments_sent += 1

        control_block.action_logger.action_logging("drp", type,
                  seqno, len_data)
    else:
        sent_data = struct.pack('!HH', type, seqno) + data
        control_block.sock.sendto(sent_data, control_block.dest)
        control_block.action_logger.action_logging("snd", type,
                  seqno, len_data)

        if type == 0:
            if old_seg:
                control_block.action_logger.retransmitted_segments += 1
            else:
                control_block.action_logger.original_data_sent += len_data
                control_block.action_logger.original_segments_sent += 1


def rcv_seg(control_block):
    response, _ = control_block.sock.recvfrom(1024)
    _, ack_seqno = struct.unpack('!HH', response)

    if random.random() < control_block.parameters['rlp']:
        control_block.action_logger.ack_segments_dropped += 1
        control_block.action_logger.action_logging("drp", 1, ack_seqno)
        return
    else:
        control_block.action_logger.action_logging("rcv", 1, ack_seqno)
        return ack_seqno
