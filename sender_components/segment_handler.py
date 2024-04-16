import random
import struct


def snd_seg(sender, type, seqno, data=b'', old_seg=False):
    len_data = len(data) if not type else 0

    if random.random() < sender.parameters['flp']:
        if not type:
            sender.action_logger.data_segments_dropped += 1
            if not old_seg:
                sender.action_logger.original_data_sent += len_data
                sender.action_logger.original_segments_sent += 1

        sender.action_logger.action_logging("drp", type,
                  seqno, len_data)
    else:
        sent_data = struct.pack('!HH', type, seqno) + data
        sender.sock.sendto(sent_data, sender.dest)
        sender.action_logger.action_logging("snd", type,
                  seqno, len_data)

        if not type:
            if old_seg:
                sender.action_logger.retransmitted_segments += 1
            else:
                sender.action_logger.original_data_sent += len_data
                sender.action_logger.original_segments_sent += 1


def rcv_seg(sender):
    response, _ = sender.sock.recvfrom(1024)
    _, ack_seqno = struct.unpack('!HH', response)

    if random.random() < sender.parameters['rlp']:
        sender.action_logger.ack_segments_dropped += 1
        sender.action_logger.action_logging("drp", 1, ack_seqno)
        return
    else:
        sender.action_logger.action_logging("rcv", 1, ack_seqno)
        return ack_seqno
