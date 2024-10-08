import socket
import sys
from receiver_components.logger import ActionLogger
from receiver_components.segment_handler import snd_ack, rcv_seg
from utils import calc_new_seqno, calc_rcv_syn_fin_seqno

class STPReceiver:
    def __init__(self, receiver_port, file_to_save):
        self.receiver_port = receiver_port
        self.file_to_save = file_to_save
        self.syn_seqno = None
        self.waited_seqno = None
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
                received = self._try_receive_segment()
                if received:
                    segment_type, seqno, data, orig = received
                    self._process_segment(segment_type, seqno, data, orig, file)
                    if segment_type == 3:  # If it's a FIN segment
                        break

    def _try_receive_segment(self):
        try:
            return rcv_seg(self)
        except socket.timeout:
            return None

    def _process_segment(self, segment_type, seqno, data, orig, file):
        if segment_type == 2: 
            self._send_ack(orig)
        elif segment_type == 0: 
            self._handle_data_segment(seqno, data, orig, file)
        elif segment_type == 3: 
            self._handle_fin_segment(orig)

    def _handle_data_segment(self, seqno, data, orig, file):
        if seqno == self.waited_seqno:
            self._write_data_and_advance_seqno(data, file)
        elif seqno > self.waited_seqno:
            self._handle_future_segment(seqno, data)
        else:  # Duplicate segment
            self.logger.dup_data_segments_received += 1

        self._send_ack(orig)

    def _handle_future_segment(self, seqno, data):
        if seqno in self.unordered_seg:
            self.logger.dup_data_segments_received += 1
        else:
            self.logger.original_data_received += len(data)
            self.logger.original_segments_received += 1
            self.unordered_seg[seqno] = data

    def _write_data_and_advance_seqno(self, data, file):
        self.logger.original_data_received += len(data)
        self.logger.original_segments_received += 1
        file.write(data)
        self.waited_seqno = calc_new_seqno(self.waited_seqno, data)

        while self.waited_seqno in self.unordered_seg:
            data = self.unordered_seg.pop(self.waited_seqno)
            file.write(data)
            self.waited_seqno = calc_new_seqno(self.waited_seqno, data)

    def _handle_fin_segment(self, orig):
        self.waited_seqno = calc_rcv_syn_fin_seqno(self.waited_seqno)
        self.handle_fin(orig)

    def _send_ack(self, orig):
        snd_ack(self, orig)


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
    txt_file_received = sys.argv[3]

    stp_receiver = STPReceiver(receiver_port, txt_file_received)
    stp_receiver.rcv_syn()
    stp_receiver.rcv_dat()
    stp_receiver.logger.summary()