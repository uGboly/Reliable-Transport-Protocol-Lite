from segment import MSS, Segment, SEGMENT_TYPE_DATA
from sender_utils.utils import send_segment
from sender_utils.tear_down import tear_down

def data_transfer(filename, control_block, sender_socket, receiver_address):
    try:
        with open(filename, 'rb') as file:
            file_data = file.read()

        total_length = len(file_data)
        sent_length = 0

        # Data sending loop
        while sent_length < total_length or control_block.unack_segments:
            # Calculate the window space taking into account the unacknowledged segments
            with control_block.lock:
                window_space = calculate_window_space(control_block)

                # Check if there is window space to send more data
                if window_space > 0 and sent_length < total_length:
                    # Determine the size of the data to send in this segment
                    segment_size = min(MSS, total_length -
                                    sent_length, window_space)
                    segment_data = file_data[sent_length:sent_length+segment_size]
                    new_segment = Segment(
                        SEGMENT_TYPE_DATA, control_block.seqno, data=segment_data)

                    # Send the new data segment
                    send_segment(sender_socket, receiver_address,
                                new_segment, control_block)

                    # Update control block information for the sent segment
                    update_control_block_for_sent_segment(
                        control_block, segment_size, new_segment)

                    sent_length += segment_size
        
        tear_down(sender_socket, receiver_address, control_block)
    except IOError as e:
        print(f"Error reading file {filename}: {e}")


def calculate_window_space(control_block):
    return control_block.window_size - (len(control_block.unack_segments) * MSS)


def update_control_block_for_sent_segment(control_block, segment_size, segment):
    if not control_block.unack_segments:
        control_block.start_timer()  # Start the timer for the first unacknowledged segment
    control_block.unack_segments.append(segment)
    control_block.seqno = (control_block.seqno + segment_size) % (2 ** 16 - 1)