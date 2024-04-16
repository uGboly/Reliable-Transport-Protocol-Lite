import random
import struct


def snd_seg(sender, seg_type, seqno, data=b'', is_old_segment=False):
    # Determine length of data to send based on segment type
    data_length = 0 if seg_type else len(data)

    def log_action(action, length=data_length):
        """Helper function to log actions."""
        sender.action_logger.action_logging(action, seg_type, seqno, length)
        if not seg_type:
            if not is_old_segment:
                sender.action_logger.original_data_sent += length
                sender.action_logger.original_segments_sent += 1
            else:
                sender.action_logger.retransmitted_segments += 1
                

    if random.random() < sender.parameters['flp']:
        # Log data segment drop
        log_action("drp")
        if seg_type:
            pass
        else:
            sender.action_logger.data_segments_dropped += 1
    else:
        # Prepare and send data
        sent_data = struct.pack('!HH', seg_type, seqno) + data
        sender.sock.sendto(sent_data, sender.dest)
        # Log data sent
        log_action("snd")


def rcv_seg(sender):
    ack = sender.sock.recvfrom(1024)[0]

    ack_seqno = struct.unpack('!HH', ack)[1]

    if random.random() < sender.parameters['rlp']:
        sender.action_logger.ack_segments_dropped += 1
        sender.action_logger.action_logging("drp", 1, ack_seqno)
        return
    else:
        sender.action_logger.action_logging("rcv", 1, ack_seqno)
        return ack_seqno
