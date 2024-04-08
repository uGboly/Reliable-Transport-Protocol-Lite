import socket
from STPSegment import STPSegment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
import time
import sys

# MSS 定义
MSS = 1000


def receive_file(receiver_port, sender_port, txt_file_received):
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_socket.bind(('', receiver_port))
    state = "LISTEN"

    with open(txt_file_received, 'wb') as file:
        while True:
            packet, sender_address = receiver_socket.recvfrom(1024 + 4)  # 接收数据和头部
            segment = STPSegment.unpack(packet)

            if state == "LISTEN" and segment.segment_type == SEGMENT_TYPE_SYN:
                # 发送 ACK
                ack_segment = STPSegment(SEGMENT_TYPE_ACK, segment.seqno + 1)
                receiver_socket.sendto(ack_segment.pack(), ('localhost', sender_port))
                state = "ESTABLISHED"

            elif state == "ESTABLISHED":
                if segment.segment_type == SEGMENT_TYPE_DATA:
                    # 处理数据段
                    file.write(segment.data)
                    # 发送 ACK
                    ack_segment = STPSegment(SEGMENT_TYPE_ACK, segment.seqno + len(segment.data))
                    receiver_socket.sendto(ack_segment.pack(), ('localhost', sender_port))
                elif segment.segment_type == SEGMENT_TYPE_FIN:
                    # 发送 FIN ACK
                    ack_segment = STPSegment(SEGMENT_TYPE_ACK, segment.seqno + 1)
                    receiver_socket.sendto(ack_segment.pack(), ('localhost', sender_port))
                    state = "TIME_WAIT"
                    time.sleep(2)
                    break  # 结束循环，关闭文件和socket

    receiver_socket.close()

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python3 receiver.py receiver_port sender_port txt_file_received")
        sys.exit(1)

    receiver_port = int(sys.argv[1])
    sender_port = int(sys.argv[2])
    txt_file_received = sys.argv[3]

    receive_file(receiver_port, sender_port, txt_file_received)
