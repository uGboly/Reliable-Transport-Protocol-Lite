import struct

SEGMENT_TYPE_DATA = 0
SEGMENT_TYPE_ACK = 1
SEGMENT_TYPE_SYN = 2
SEGMENT_TYPE_FIN = 3
MSS = 1000

class Segment:
    def __init__(self, segment_type, seqno, data=b''):
        self.segment_type = segment_type
        self.seqno = seqno
        self.data = data

    def pack(self):
        # Pack the segment. Packet format: type(2 bytes) + seqno(2 bytes) + data
        header = struct.pack('!HH', self.segment_type, self.seqno)
        return header + self.data

    @staticmethod
    def unpack(packet):
        # Unpack the segment
        header = packet[:4]
        segment_type, seqno = struct.unpack('!HH', header)
        data = packet[4:]
        return Segment(segment_type, seqno, data)

    def segment_type_name(self):
        # Return a string representation of the segment type for logging
        type_names = {
            SEGMENT_TYPE_DATA: "DATA",
            SEGMENT_TYPE_ACK: "ACK",
            SEGMENT_TYPE_SYN: "SYN",
            SEGMENT_TYPE_FIN: "FIN"
        }
        return type_names.get(self.segment_type, "UNKNOWN")
