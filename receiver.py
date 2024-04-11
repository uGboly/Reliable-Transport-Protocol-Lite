import sys
import threading
from segment import Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
from receiver_utils.control_block import ControlBlock
from receiver_utils.handshake import handshake
from receiver_utils.data_transfer import data_transfer
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(
            "Usage: python3 receiver.py receiver_port sender_port txt_file_received max_win")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]
    max_win = int(sys.argv[4])

    control_block = ControlBlock(receiver_port, sender_port,
                                 txt_file_received, max_win)
    handshake(control_block)
    data_transfer(control_block)
