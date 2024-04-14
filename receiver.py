import socket
import sys
from STPSegment import STPSegment, ACK, SYN, FIN
from receiver_utils import ReceiverLogger, WindowManager


class Receiver:
    def __init__(self, receiver_port, sender_port, file_to_save, max_win):
        self.receiver_port = receiver_port
        self.sender_port = sender_port
        self.file_to_save = file_to_save
        self.max_win = max_win
        self.init_seqno = 0
        self.next_seqno = 0
        self.rcv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rcv_socket.bind(('', receiver_port))
        self.window_manager = WindowManager(self, file_to_save)
        self.logger = ReceiverLogger()
        self.total_ack_segments_sent = 0
        self.rcv_socket.settimeout(2.0)

    def send_ack(self, seqno, address):
        ack = STPSegment(ACK, seqno)
        self.rcv_socket.sendto(ack.serialize(), address)
        self.total_ack_segments_sent += 1
        self.logger.log("snd", ack)

    def receive_segment(self):
        packet, origination = self.rcv_socket.recvfrom(1024)
        segment = STPSegment.unserialize(packet)
        self.logger.log("rcv", segment, len(segment.data))
        return segment, origination


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(
            "Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    receiver = Receiver(receiver_port, sender_port,
                        txt_file_received, max_win)

    while True:
        try:
            segment, origination = receiver.receive_segment()
            if segment.type == SYN:
                receiver.init_seqno = (segment.seqno + 1) % (2 ** 16)
                receiver.next_seqno = receiver.init_seqno
                receiver.send_ack(receiver.next_seqno, origination)
                break
        except socket.timeout:
            continue

    while True:
        try:
            segment, origination = receiver.receive_segment()

            match segment.type:
                case 3:
                    break
                case 2:
                    receiver.send_ack(receiver.init_seqno, origination)
                case 0:
                    receiver.window_manager.handle_segment(segment)
                    receiver.send_ack(receiver.next_seqno, origination)
                case _:
                    pass

        except socket.timeout:
            continue


    receiver.send_ack((receiver.next_seqno + 1) %
                      (2 ** 16), origination)

    try:
        while True:
            segment, _ = receiver.receive_segment()

            if segment.type == FIN:
                receiver.send_ack((receiver.next_seqno + 1) %
                                  (2 ** 16), origination)
    except socket.timeout:
        pass
    receiver.logger.log_statatics(receiver)
