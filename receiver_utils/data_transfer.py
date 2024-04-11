from segment import Segment, SEGMENT_TYPE_DATA, SEGMENT_TYPE_ACK, SEGMENT_TYPE_SYN, SEGMENT_TYPE_FIN
from receiver_utils.utils import log_actions, send_segment, receive_segment, ReceiveError
from receiver_utils.tear_down import tear_down

def data_transfer(control_block):
    buffer = {}  # 使用字典作为缓冲区，键为序列号，值为数据
    with open(control_block.file_to_save, 'wb') as file:
        while True:
            try:
                segment, sender_address = receive_segment(control_block)

                if segment.segment_type == SEGMENT_TYPE_SYN:
                    log_actions(control_block, "rcv", segment, 0)
                    ack_segment = Segment(
                        SEGMENT_TYPE_ACK, control_block.expected_seqno)
                    send_segment(control_block,
                                 ack_segment, sender_address)
                    control_block.total_ack_segments_sent += 1
                    log_actions(control_block, "snd", ack_segment, 0)

                if segment.segment_type == SEGMENT_TYPE_DATA:
                    log_actions(control_block, "rcv",
                                segment, len(segment.data))
                    # 如果数据段按序到达，直接写入文件，并检查缓冲区中是否有连续的后续数据
                    if segment.seqno == control_block.expected_seqno:
                        control_block.original_data_received += len(
                            segment.data)
                        control_block.original_segments_received += 1
                        file.write(segment.data)
                        control_block.expected_seqno += len(segment.data)

                        # 检查并写入缓冲区中按序的数据
                        while control_block.expected_seqno in buffer:
                            data = buffer.pop(control_block.expected_seqno)
                            file.write(data)
                            control_block.expected_seqno += len(data)
                    elif segment.seqno > control_block.expected_seqno:  # 到达了乱序数据
                        if segment.seqno in buffer:
                            control_block.dup_data_segments_received += 1
                        else:
                            control_block.original_data_received += len(
                                segment.data)
                            control_block.original_segments_received += 1
                            buffer[segment.seqno] = segment.data
                    else:  # 到达的数据段已经写入文件
                        control_block.dup_data_segments_received += 1

                    # 发送ACK
                    control_block.total_ack_segments_sent += 1
                    ack_segment = Segment(
                        SEGMENT_TYPE_ACK, control_block.expected_seqno)
                    send_segment(control_block,
                                 ack_segment, sender_address)
                    log_actions(control_block, "snd", ack_segment, 0)

                if segment.segment_type == SEGMENT_TYPE_FIN:
                    log_actions(control_block, "rcv", segment, 0)
                    tear_down(control_block, sender_address)
                    break
            except ReceiveError:
                continue