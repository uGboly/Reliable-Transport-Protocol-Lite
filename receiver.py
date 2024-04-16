import socket
import sys
from receiver_components.logger import ActionLogger
from receiver_components.segment_handler import snd_ack, rcv_seg
from utils import calc_new_seqno, calc_rcv_syn_fin_seqno

class STPReceiver:
    def __init__(self, receiver_port, file_to_save):
        self.receiver_port = receiver_port
        self.file_to_save = file_to_save
        self.syn_seqno = 0
        self.waited_seqno = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', receiver_port))
        self.logger = ActionLogger()
        self.unordered_seg = {}
        self.sock.settimeout(2.0)

    def rcv_syn(self):
        while True:
            try:
                type, seqno, _, orig = rcv_seg(self)
                if type == 2:
                    self.syn_seqno = calc_rcv_syn_fin_seqno(seqno)
                    self.waited_seqno = calc_rcv_syn_fin_seqno(seqno)
                    snd_ack(self, orig)
                    break
            except socket.timeout:
                continue

    def rcv_dat(self):
        with open(self.file_to_save, 'wb') as file:
            while True:
                try:
                    type, seqno, data, orig = rcv_seg(self)

                    if type == 2:
                        snd_ack(self, orig)

                    if type == 0:
                        if seqno == self.waited_seqno:
                            self.logger.original_data_received += len(data)
                            self.logger.original_segments_received += 1
                            file.write(data)
                            self.waited_seqno = calc_new_seqno(self.waited_seqno, data)

                            while self.waited_seqno in self.unordered_seg:
                                data = self.unordered_seg.pop(self.waited_seqno)
                                file.write(data)
                                self.waited_seqno = calc_new_seqno(self.waited_seqno, data)
                        elif seqno > self.waited_seqno:
                            if seqno in self.unordered_seg:
                                self.logger.dup_data_segments_received += 1
                            else:
                                self.logger.original_data_received += len(data)
                                self.logger.original_segments_received += 1
                                self.unordered_seg[seqno] = data
                        else:
                            self.logger.dup_data_segments_received += 1

                        snd_ack(self, orig)

                    if type == 3:
                        self.waited_seqno = calc_rcv_syn_fin_seqno(self.waited_seqno)
                        self.handle_fin(orig)
                        break
                except socket.timeout:
                    continue

    def handle_fin(self, orig):
        snd_ack(self, orig)

        try:
            while True:
                type = rcv_seg(self)[0]
                if type == 3:
                    snd_ack(self, orig)
        except socket.timeout:
            pass

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(
            "Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    stp_receiver = STPReceiver(receiver_port, txt_file_received)
    stp_receiver.rcv_syn()
    stp_receiver.rcv_dat()
    stp_receiver.logger.summary()