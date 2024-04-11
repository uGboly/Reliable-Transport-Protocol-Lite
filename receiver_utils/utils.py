import socket
from segment import Segment

def receive_segment(control_block):
    try:
        packet, sender_address = control_block.receiver_socket.recvfrom(
                    1024)
        segment = Segment.unpack(packet)

        return [segment, sender_address]
    except socket.timeout:
        raise ReceiveError("socke timeout!")
    
def send_segment(control_block, segment, target):
    packed_segment = segment.pack()
    control_block.receiver_socket.sendto(packed_segment, target)
    
class ReceiveError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)