import socket
import random
import sys
import time
import threading
from sender_components.segment_handler import snd_seg, rcv_seg
from sender_components.logger import ActionLogger
from utils import calc_new_seqno

CLOSE = 0
ESTABLISHED = 1
FIN_WAIT = 2


class STPSender:
    def __init__(self):
        self.state = CLOSE
        self.syn_seqno = random.randint(0, 65535)
        self.seqno = self.syn_seqno + 1
        self.lock = threading.Lock()
        self.parameters = dict(max_win=max_win, rto=rto, flp=flp, rlp=rlp)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', sender_port))
        self.sock.settimeout(rto / 1000.0)
        self.dest = ('localhost', receiver_port)
        self.action_logger = ActionLogger()
        self.buffered_seg = []
        self.stp_timer = None
        self.ack_cnt = {}

    def send_syn(self):
        snd_seg(self, 2, self.syn_seqno)
        while True:
            try:
                ack_seqno = rcv_seg(self)

                if ack_seqno == self.syn_seqno + 1:
                    self.state = ESTABLISHED
                    break
            except socket.timeout:
                snd_seg(self, 2, self.syn_seqno)

    def ack_listener(self):
        while True:
            try:
                ack_seqno = rcv_seg(self)

                with self.lock:
                    if self._is_final_ack_in_fin_wait(ack_seqno):
                        break
                    elif self._is_ack_for_buffered_segment(ack_seqno):
                        self._handle_ack_for_buffered_segment(ack_seqno)
                    else:
                        self._handle_duplicate_ack(ack_seqno)

            except socket.timeout:
                continue

    def _is_final_ack_in_fin_wait(self, ack_seqno):
        final_ack_received = self.state == FIN_WAIT and ack_seqno == self.seqno + 1
        if final_ack_received:
            self.state = CLOSE
        return final_ack_received

    def _is_ack_for_buffered_segment(self, ack_seqno):
        return ack_seqno in [calc_new_seqno(old_seqno, data) for old_seqno, data in self.buffered_seg]

    def _handle_ack_for_buffered_segment(self, ack_seqno):
        index_ack_seg = next(i for i, [old_seqno, data] in enumerate(self.buffered_seg) if calc_new_seqno(old_seqno, data) == ack_seqno)
        acknowledged_segments = self.buffered_seg[:index_ack_seg + 1]
        self.action_logger.original_data_acked += sum(len(data) for _, data in acknowledged_segments)
        self.buffered_seg = self.buffered_seg[index_ack_seg + 1:]
        self._update_timer_based_on_buffer()

    def _handle_duplicate_ack(self, ack_seqno):
        self.action_logger.dup_acks_received += 1
        self.ack_cnt[ack_seqno] = self.ack_cnt.get(ack_seqno, 0) + 1
        if self.ack_cnt[ack_seqno] == 3:
            self._retransmit_first_buffered_segment()

    def _update_timer_based_on_buffer(self):
        if self.buffered_seg:
            self.stp_timer = time.time() * 1000 + self.parameters['rto']
        else:
            self.stp_timer = None

    def _retransmit_first_buffered_segment(self):
        first_buffered_seg = self.buffered_seg[0]
        snd_seg(self, 0, first_buffered_seg[0], first_buffered_seg[1], True)
        self.stp_timer = time.time() * 1000 + self.parameters['rto']


    def timer_thread(self):
        while True:
            with self.lock:
                if self.state == CLOSE:
                    break
                if self.stp_timer is not None:
                    current_time = time.time() * 1000
                    if current_time >= self.stp_timer:

                        if self.buffered_seg:
                            first_buffered_seg = self.buffered_seg[0]
                            snd_seg(
                                self, 0, first_buffered_seg[0], first_buffered_seg[1], True)

                            self.stp_timer = current_time + \
                                self.parameters['rto']
                            self.ack_cnt = {}

                        elif self.state == FIN_WAIT:
                            snd_seg(self, 3,
                                    self.seqno, b'', True)
                            self.stp_timer = current_time + \
                                self.parameters['rto']

    def send_file(self, filename):
        with open(filename, 'rb') as file:
            file_data = file.read()
            total_length = len(file_data)
            sent_length = 0

            while sent_length < total_length or self.buffered_seg:
                with self.lock:
                    window_space = self.parameters['max_win'] - \
                        (len(self.buffered_seg) * 1000)

                    if window_space > 0 and sent_length < total_length:

                        segment_size = min(1000, total_length -
                                           sent_length, window_space)
                        segment_data = file_data[sent_length:sent_length+segment_size]

                        snd_seg(self, 0,
                                self.seqno, segment_data)

                        if not self.buffered_seg:
                            self.stp_timer = time.time() * 1000 + \
                                self.parameters['rto']
                        self.buffered_seg.append(
                            [self.seqno, segment_data])
                        self.seqno = calc_new_seqno(self.seqno, segment_data)

                        sent_length += segment_size

    def send_fin(self):
        while True:
            with self.lock:
                if self.buffered_seg:
                    continue
                else:
                    self.state = FIN_WAIT
                    snd_seg(self, 3, self.seqno)
                    self.stp_timer = time.time() * 1000 + \
                        self.parameters['rto']
                    break


if __name__ == '__main__':
    if len(sys.argv) != 8:
        print("Usage: python3 sender.py sender_port receiver_port txt_file_to_send max_win rto flp rlp")
        sys.exit(1)

    sender_port = int(sys.argv[1])
    receiver_port = int(sys.argv[2])
    txt_file_to_send = sys.argv[3]
    max_win = int(sys.argv[4])
    rto = int(sys.argv[5])
    flp = float(sys.argv[6])
    rlp = float(sys.argv[7])

    random.seed()

    stp_sender = STPSender()

    stp_sender.send_syn()

    ack_listener_thread = threading.Thread(
        target=stp_sender.ack_listener)
    timer_thread = threading.Thread(
        target=stp_sender.timer_thread)
    ack_listener_thread.start()
    timer_thread.start()

    stp_sender.send_file(txt_file_to_send)

    stp_sender.send_fin()

    ack_listener_thread.join()
    timer_thread.join()

    stp_sender.sock.close()

    stp_sender.action_logger.summary()
