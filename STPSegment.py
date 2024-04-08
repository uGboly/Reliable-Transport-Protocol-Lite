import struct

# Segment 类型定义
SEGMENT_TYPE_DATA = 0
SEGMENT_TYPE_ACK = 1
SEGMENT_TYPE_SYN = 2
SEGMENT_TYPE_FIN = 3

class STPSegment:
    def __init__(self, segment_type, seqno, data=b''):
        self.segment_type = segment_type
        self.seqno = seqno
        self.data = data

    def pack(self):
        # 打包 segment，数据包格式：type(2 bytes) + seqno(2 bytes) + data
        header = struct.pack('!HH', self.segment_type, self.seqno)
        return header + self.data

    @staticmethod
    def unpack(packet):
        # 解包 segment
        header = packet[:4]
        segment_type, seqno = struct.unpack('!HH', header)
        data = packet[4:]
        return STPSegment(segment_type, seqno, data)