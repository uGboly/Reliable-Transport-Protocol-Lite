import socket
import random
import sys
import time
import threading
from sender_components.segment_handler import send_segment, receive_segment


class STPControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.isn = random.randint(0, 65535)
        self.seqno = self.isn + 1
        self.lock = threading.Lock()
        self.window_size = max_win
        self.rto = rto
        self.parameters = dict(rto=rto, flp=flp, rlp=rlp)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', sender_port))
        self.dest = ('localhost', receiver_port)
        self.unack_segments = []
        self.timer = None
        self.dup_ack_count = {}
        self.start_time = 0
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0


def establish_connection(control_block):

    send_segment(control_block, 2, control_block.isn)

    control_block.sock.settimeout(control_block.rto / 1000.0)

    while True:
        try:
            ack_seqno = receive_segment(control_block)

            if ack_seqno == control_block.isn + 1:
                control_block.state = "ESTABLISHED"
                break
        except socket.timeout:
            send_segment(control_block, 2, control_block.isn)
        except AttributeError:
            continue


def ack_receiver(control_block):
    while True:

        try:
            ack_seqno = receive_segment(control_block)

            with control_block.lock:
                if control_block.state == "FIN_WAIT" and ack_seqno == control_block.seqno + 1:
                    control_block.state = "CLOSE"
                    break

                elif ack_seqno in [(seg[0] + len(seg[1])) % 2 ** 16 for seg in control_block.unack_segments]:

                    index_ack_seg = [i for i, seg in enumerate(
                        control_block.unack_segments) if (seg[0] + len(seg[1])) % 2 ** 16 == ack_seqno][0]
                    for seg in control_block.unack_segments[:index_ack_seg + 1]:
                        control_block.original_data_acked += len(seg[1])

                    control_block.unack_segments = control_block.unack_segments[index_ack_seg + 1:]

                    if control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto
                    else:
                        control_block.timer = None

                    control_block.dup_ack_count = {}

                else:

                    control_block.dup_acks_received += 1
                    if ack_seqno in control_block.dup_ack_count:
                        control_block.dup_ack_count[ack_seqno] += 1
                    else:
                        control_block.dup_ack_count[ack_seqno] = 1

                    if control_block.dup_ack_count[ack_seqno] == 3:
                        oldest_unack_segment = control_block.unack_segments[0]
                        send_segment(
                            control_block, 0, oldest_unack_segment[0], oldest_unack_segment[1], True)

                        control_block.timer = time.time() * 1000 + control_block.rto

        except socket.timeout:
            continue
        except AttributeError:
            continue


def timer_thread(control_block):
    while True:
        with control_block.lock:
            if control_block.state == "CLOSE":

                break
            if control_block.timer is not None:
                current_time = time.time() * 1000
                if current_time >= control_block.timer:

                    if control_block.unack_segments:
                        oldest_unack_segment = control_block.unack_segments[0]
                        send_segment(
                            control_block, 0, oldest_unack_segment[0], oldest_unack_segment[1], True)

                        control_block.timer = current_time + control_block.rto

                        control_block.dup_ack_count = {}
                    elif control_block.state == "FIN_WAIT":

                        send_segment(control_block, 3,
                                     control_block.seqno, b'', True)
                        control_block.timer = current_time + control_block.rto


def send_file(filename, control_block):
    with open(filename, 'rb') as file:
        file_data = file.read()
        total_length = len(file_data)
        sent_length = 0

        while sent_length < total_length or control_block.unack_segments:
            with control_block.lock:
                window_space = control_block.window_size - \
                    (len(control_block.unack_segments) * 1000)

                if window_space > 0 and sent_length < total_length:

                    segment_size = min(1000, total_length -
                                       sent_length, window_space)
                    segment_data = file_data[sent_length:sent_length+segment_size]

                    send_segment(control_block, 0,
                                 control_block.seqno, segment_data)

                    if not control_block.unack_segments:
                        control_block.timer = time.time() * 1000 + control_block.rto
                    control_block.unack_segments.append(
                        [control_block.seqno, segment_data])
                    control_block.seqno = (
                        control_block.seqno + segment_size) % (2 ** 16)

                    sent_length += segment_size


def close_connection(control_block):
    while True:
        with control_block.lock:
            if not control_block.unack_segments:

                control_block.state = "FIN_WAIT"

                send_segment(control_block, 3, control_block.seqno)
                control_block.timer = time.time() * 1000 + control_block.rto
                break


def finalize_log(control_block):
    with open("sender_log.txt", "a") as log_file:
        log_file.write(
            f"Original data sent: {control_block.original_data_sent}\n")
        log_file.write(
            f"Original data acked: {control_block.original_data_acked}\n")
        log_file.write(
            f"Original segments sent: {control_block.original_segments_sent}\n")
        log_file.write(
            f"Retransmitted segments: {control_block.retransmitted_segments}\n")
        log_file.write(
            f"Dup acks received: {control_block.dup_acks_received}\n")
        log_file.write(
            f"Data segments dropped: {control_block.data_segments_dropped}\n")
        log_file.write(
            f"Ack segments dropped: {control_block.ack_segments_dropped}\n")


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

    with open("sender_log.txt", "w"):
        pass

    random.seed()

    control_block = STPControlBlock()

    establish_connection(control_block)

    if control_block.state != "ESTABLISHED":
        print("Failed to establish connection.")
        sys.exit(1)

    ack_thread = threading.Thread(
        target=ack_receiver, args=[control_block])
    timer_thread = threading.Thread(
        target=timer_thread, args=[control_block])
    ack_thread.start()
    timer_thread.start()

    send_file(txt_file_to_send, control_block)

    close_connection(control_block)

    ack_thread.join()
    timer_thread.join()

    control_block.sock.close()

    with control_block.lock:
        finalize_log(control_block)
