import socket
import random
import sys
import time
import threading
from sender_components.segment_handler import snd_seg, rcv_seg
from sender_components.logger import ActionLogger


class STPSender:
    def __init__(self):
        self.state = "CLOSE"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.lock = threading.Lock()
        self.window_size = max_win
        self.rto = rto
        self.parameters = dict(rto=rto, flp=flp, rlp=rlp)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', sender_port))
        self.sock.settimeout(rto / 1000.0)
        self.dest = ('localhost', receiver_port)
        self.unack_segments = []
        self.timer = None
        self.dup_ack_count = {}
        self.action_logger = ActionLogger()


def establish_connection(stp_sender):
    snd_seg(stp_sender, 2, stp_sender.isn)

    while True:
        try:
            ack_seqno = rcv_seg(stp_sender)

            if ack_seqno == stp_sender.isn + 1:
                stp_sender.state = "ESTABLISHED"
                break
        except socket.timeout:
            snd_seg(stp_sender, 2, stp_sender.isn)


def ack_receiver(stp_sender):
    while True:

        try:
            ack_seqno = rcv_seg(stp_sender)

            with stp_sender.lock:
                if stp_sender.state == "FIN_WAIT" and ack_seqno == stp_sender.seqno + 1:
                    stp_sender.state = "CLOSE"
                    break

                elif ack_seqno in [(seg[0] + len(seg[1])) % 2 ** 16 for seg in stp_sender.unack_segments]:

                    index_ack_seg = [i for i, seg in enumerate(
                        stp_sender.unack_segments) if (seg[0] + len(seg[1])) % 2 ** 16 == ack_seqno][0]
                    for seg in stp_sender.unack_segments[:index_ack_seg + 1]:
                        stp_sender.action_logger.original_data_acked += len(
                            seg[1])

                    stp_sender.unack_segments = stp_sender.unack_segments[index_ack_seg + 1:]

                    if stp_sender.unack_segments:
                        stp_sender.timer = time.time() * 1000 + stp_sender.rto
                    else:
                        stp_sender.timer = None

                    stp_sender.dup_ack_count = {}

                else:

                    stp_sender.action_logger.dup_acks_received += 1
                    if ack_seqno in stp_sender.dup_ack_count:
                        stp_sender.dup_ack_count[ack_seqno] += 1
                    else:
                        stp_sender.dup_ack_count[ack_seqno] = 1

                    if stp_sender.dup_ack_count[ack_seqno] == 3:
                        oldest_unack_segment = stp_sender.unack_segments[0]
                        snd_seg(
                            stp_sender, 0, oldest_unack_segment[0], oldest_unack_segment[1], True)

                        stp_sender.timer = time.time() * 1000 + stp_sender.rto

        except socket.timeout:
            continue


def timer_thread(stp_sender):
    while True:
        with stp_sender.lock:
            if stp_sender.state == "CLOSE":

                break
            if stp_sender.timer is not None:
                current_time = time.time() * 1000
                if current_time >= stp_sender.timer:

                    if stp_sender.unack_segments:
                        oldest_unack_segment = stp_sender.unack_segments[0]
                        snd_seg(
                            stp_sender, 0, oldest_unack_segment[0], oldest_unack_segment[1], True)

                        stp_sender.timer = current_time + stp_sender.rto

                        stp_sender.dup_ack_count = {}
                    elif stp_sender.state == "FIN_WAIT":

                        snd_seg(stp_sender, 3,
                                stp_sender.seqno, b'', True)
                        stp_sender.timer = current_time + stp_sender.rto


def send_file(filename, stp_sender):
    with open(filename, 'rb') as file:
        file_data = file.read()
        total_length = len(file_data)
        sent_length = 0

        while sent_length < total_length or stp_sender.unack_segments:
            with stp_sender.lock:
                window_space = stp_sender.window_size - \
                    (len(stp_sender.unack_segments) * 1000)

                if window_space > 0 and sent_length < total_length:

                    segment_size = min(1000, total_length -
                                       sent_length, window_space)
                    segment_data = file_data[sent_length:sent_length+segment_size]

                    snd_seg(stp_sender, 0,
                            stp_sender.seqno, segment_data)

                    if not stp_sender.unack_segments:
                        stp_sender.timer = time.time() * 1000 + stp_sender.rto
                    stp_sender.unack_segments.append(
                        [stp_sender.seqno, segment_data])
                    stp_sender.seqno = (
                        stp_sender.seqno + segment_size) % (2 ** 16)

                    sent_length += segment_size


def close_connection(stp_sender):
    while True:
        with stp_sender.lock:
            if not stp_sender.unack_segments:

                stp_sender.state = "FIN_WAIT"

                snd_seg(stp_sender, 3, stp_sender.seqno)
                stp_sender.timer = time.time() * 1000 + stp_sender.rto
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

    establish_connection(stp_sender)

    if stp_sender.state != "ESTABLISHED":
        print("Failed to establish connection.")
        sys.exit(1)

    ack_thread = threading.Thread(
        target=ack_receiver, args=[stp_sender])
    timer_thread = threading.Thread(
        target=timer_thread, args=[stp_sender])
    ack_thread.start()
    timer_thread.start()

    send_file(txt_file_to_send, stp_sender)

    close_connection(stp_sender)

    ack_thread.join()
    timer_thread.join()

    stp_sender.sock.close()

    stp_sender.action_logger.summary()
