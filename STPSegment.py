import struct

DATA = 0
ACK = 1
SYN = 2
FIN = 3


class STPSegment:
    def __init__(self, type, seqno, data=b''):
        self.type = type
        self.seqno = seqno
        self.data = data

    def serialize(self):
        header = struct.pack('!HH', self.type, self.seqno)
        return header + self.data

    @staticmethod
    def unserialize(packet):
        header = packet[:4]
        type, seqno = struct.unpack('!HH', header)
        data = packet[4:]
        return STPSegment(type, seqno, data)
