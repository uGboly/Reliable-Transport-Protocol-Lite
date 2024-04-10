import socket
import sys
import threading
from sender_utils.control_block import ControlBlock
from sender_utils.handshake import handshake
from sender_utils.ack_handler import ack_handler
from sender_utils.timer_handler import timer_handler
from sender_utils.data_transfer import data_transfer


def main(sender_port, receiver_port, txt_file_to_send, max_win, rto, flp, rlp):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind(('', sender_port))
    control_block = ControlBlock(max_win, rto, flp, rlp)

    try:
        handshake(control_block, udp_socket, ('localhost', receiver_port))

        ack_event_thread = threading.Thread(target=ack_handler, args=(
            control_block, udp_socket, ('localhost', receiver_port)))
        timer_event_thread = threading.Thread(target=timer_handler, args=(
            control_block, udp_socket, ('localhost', receiver_port)))
        
        ack_event_thread.start()
        timer_event_thread.start()

        data_transfer(txt_file_to_send, control_block,
                    udp_socket, ('localhost', receiver_port))

        ack_event_thread.join()
        timer_event_thread.join()

    finally:
        udp_socket.close()
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
