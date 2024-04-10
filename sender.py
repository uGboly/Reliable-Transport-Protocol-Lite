import socket
import sys
import threading
from sender_utils.control_block import ControlBlock
from sender_utils.handshake import handshake
from sender_utils.tear_down import tear_down
from sender_utils.ack_handler import ack_handler
from sender_utils.timer_handler import timer_handler
from sender_utils.file_sender import file_sender


def main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp):

    control_block = ControlBlock(max_win, rto, flp, rlp)
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.bind(('', sender_port))
    receiver_address = ('localhost', receiver_port)

    try:
        handshake(sender_socket, receiver_address, control_block)

        ack_thread = threading.Thread(target=ack_handler, args=(
            control_block, sender_socket, receiver_address))
        timer_thread = threading.Thread(target=timer_handler, args=(
            control_block, sender_socket, receiver_address))
        ack_thread.start()
        timer_thread.start()

        file_sender(txt_file_to_send, control_block,
                    sender_socket, receiver_address)

        tear_down(sender_socket, receiver_address, control_block)

        ack_thread.join()
        timer_thread.join()

    finally:
        sender_socket.close()
        control_block.print_statistics()


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

    main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp)
