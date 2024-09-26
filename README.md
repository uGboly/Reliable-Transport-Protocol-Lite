# Reliable Transport Protocol Lite

This project implements a simple unidirectional reliable data transfer protocol over UDP. The protocol is designed to handle packet loss and ensure reliable delivery using a sliding window, fast retransmission, and simulated packet loss. It also features basic connection establishment and termination, as well as logging of key events.

## Features

1. **Handshake and Termination:**
   - A single exchange handshake is implemented to establish a connection between the sender and receiver, using a SYN segment followed by an ACK segment.
   - A simplified termination process is used, where the sender sends a FIN segment and waits for an ACK from the receiver.

2. **Sliding Window Protocol:**
   - The sender uses a sliding window mechanism to manage the flow of data packets, ensuring that multiple packets can be in transit simultaneously to optimize throughput.

3. **Fast Retransmission:**
   - The sender implements a fast retransmission mechanism. If three duplicate ACKs are received, the sender immediately retransmits the unacknowledged segment without waiting for a timeout.

4. **Packet Loss Simulation:**
   - The system simulates packet loss for both data and ACK segments using user-specified probabilities. Forward loss probability (`flp`) simulates data packet loss, while reverse loss probability (`rlp`) simulates ACK packet loss.

5. **Event Logging:**
   - Both the sender and receiver log significant events (such as sending, receiving, and dropping of packets) to `sender_log.txt` and `receiver_log.txt`. These logs also include statistical information about original data sent, retransmissions, and dropped packets.

## Requirements

- Python 3.x

## Usage

### Running the Sender

To run the sender, use the following command:

```bash
python3 sender.py sender_port receiver_port txt_file_to_send max_win rto flp rlp
```

Where:

- `sender_port`: The UDP port the sender binds to.
- `receiver_port`: The port of the receiver.
- `txt_file_to_send`: The file path of the text file to send.
- `max_win`: The maximum sliding window size in bytes.
- `rto`: The retransmission timeout (in milliseconds).
- `flp`: Forward loss probability (for simulating data packet loss, 0 ≤ flp ≤ 1).
- `rlp`: Reverse loss probability (for simulating ACK packet loss, 0 ≤ rlp ≤ 1).

Example:

```bash
python3 sender.py 5000 6000 data.txt 4096 200 0.1 0.05
```

This sends the `data.txt` file from the sender on port 5000 to the receiver on port 6000, using a sliding window of 4096 bytes, a retransmission timeout of 200 milliseconds, and packet loss probabilities of 10% for data and 5% for ACK packets.

### Running the Receiver

To run the receiver, use the following command:

```bash
python3 receiver.py receiver_port sender_port txt_file_received max_win
```

Where:

- `receiver_port`: The UDP port the receiver listens on.
- `sender_port`: The port of the sender.
- `txt_file_received`: The file name to save the received text.
- `max_win`: The maximum sliding window size in bytes.

Example:

```bash
python3 receiver.py 6000 5000 received_data.txt 4096
```

This saves the received data from the sender into the file `received_data.txt`.

## Log Files

- **Sender Log (`sender_log.txt`)**: Logs all major events such as sending, receiving, dropping, retransmitting packets, and summarizes statistics like original data sent, retransmitted segments, duplicate ACKs, etc.
- **Receiver Log (`receiver_log.txt`)**: Logs events such as receiving data packets, duplicate packets, and final statistics on the data received and duplicate segments.

## Protocol Details

1. **Connection Establishment**:
   - The sender initiates the connection by sending a SYN segment.
   - The receiver acknowledges the SYN by sending an ACK segment.
   - The connection is established after this single SYN-ACK exchange.

2. **Data Transmission**:
   - The sender transmits data using a sliding window.
   - The receiver acknowledges the successfully received segments. If a segment is out of order, it will be buffered until the expected segment is received.
   - If the sender receives three duplicate ACKs for the same data, it triggers a fast retransmission of the lost segment.

3. **Connection Termination**:
   - The sender initiates the termination by sending a FIN segment once all data has been sent.
   - The receiver responds with an ACK to confirm the connection termination.
   - If the FIN or ACK is lost, retransmissions are handled until confirmation is received.

## Error Handling and Packet Loss Simulation

- **Timeouts**: If the sender doesn't receive an ACK within the specified retransmission timeout (RTO), the oldest unacknowledged segment is retransmitted.
- **Simulated Packet Loss**: You can configure the forward loss probability (`flp`) and reverse loss probability (`rlp`) to simulate packet loss in the network. This feature helps test the protocol's behavior under unreliable conditions.