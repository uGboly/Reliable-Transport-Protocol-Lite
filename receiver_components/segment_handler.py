import struct

def rcv_seg(receiver):
    packet, orig = receiver.sock.recvfrom(1024)
    header = packet[:4]
    type, seqno = struct.unpack('!HH', header)
    data = packet[4:]

    receiver.logger.action_logging('rcv', type, seqno, len(data))
    return [type, seqno, data, orig]

def snd_ack(receiver, orig):
    ack = struct.pack('!HH', 1, receiver.waited_seqno)
    receiver.sock.sendto(ack, orig)
    receiver.logger.action_logging('snd', 1, receiver.waited_seqno)
    receiver.logger.total_ack_segments_sent += 1