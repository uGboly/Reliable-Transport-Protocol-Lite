import socket
import random
import sys
import threading
from sender_utils import SenderLogger, ConnectionManager, DataTransmissionManager, AckReceiver, TimerManager


class SenderControlBlock:
    def __init__(self):
        self.state = "CLOSED"
        self.init_seqno = random.randint(0, 65535)
        self.seqno = self.init_seqno + 1
        self.ackno = 0
        self.lock = threading.Lock()
        self.max_win = max_win
        self.rto = rto
        self.sliding_window = []
        self.timer = None
        self.ack_counter = {}
        self.original_data_sent = 0
        self.original_data_acked = 0
        self.original_segments_sent = 0
        self.retransmitted_segments = 0
        self.dup_acks_received = 0
        self.data_segments_dropped = 0
        self.ack_segments_dropped = 0


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
    logger = SenderLogger("sender_log.txt")

    control_block = SenderControlBlock()
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    sender_address = ('localhost', receiver_port)
    receiver_address = ('localhost', receiver_port)

    connection_manager = ConnectionManager(
        sender_socket, receiver_address, control_block, logger, rto, flp, rlp)
    connection_manager.setup()

    ack_receiver_instance = AckReceiver(control_block, connection_manager)
    ack_receiver = threading.Thread(target=ack_receiver_instance.run)

    timer_manager_instance = TimerManager(control_block, connection_manager)
    timer_manager = threading.Thread(target=timer_manager_instance.run)

    ack_receiver.start()
    timer_manager.start()

    with open(txt_file_to_send, 'rb') as file:
        data = file.read()
        DataTransmissionManager(control_block, connection_manager, data)
        control_block.state = "FIN_WAIT"

    ack_receiver.join()
    timer_manager.join()
    connection_manager.finish()
