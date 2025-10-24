import socket
import sys
import argparse

host = 'localhost'

def echo_client(port):
    """ A simple echo client """
    # 1) create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 2) connect to server
    server_address = (host, port)
    print("Connecting to %s port %s" % server_address)
    sock.connect(server_address)

    try:
        # 3) send message to server
        message = "Test message. This will be echoed"
        print("Sending %s" % message)
        sock.sendall(message.encode('utf-8'))

        # 4) receive echo back
        # important: server sends bytes, so we should count bytes, not characters
        amount_received = 0
        amount_expected = len(message.encode('utf-8'))  # bytes to expect
        recv_buf = bytearray()

        # collect until we got back what we sent (or socket closes)
        while amount_received < amount_expected:
            chunk = sock.recv(16)
            if not chunk:  # server closed
                break
            recv_buf += chunk
            amount_received += len(chunk)

        received_text = recv_buf.decode('utf-8')
        print("Received:", received_text)

        # 5) compare and print required output
        if received_text == message:
            print("Connection successful, data matches")
        else:
            print("Data mismatch")

    except socket.error as e:
        print("Socket error: %s" % str(e))
    except Exception as e:
        print("Other exception: %s" % str(e))
    finally:
        print("Closing connection to the server")
        sock.close()

if __name__ == '__main__':
    # run: python 13-client-tcp.py --port=9900
    parser = argparse.ArgumentParser(description='Socket Client Example')
    parser.add_argument('--port', action="store", dest="port", type=int, required=True)
    given_args = parser.parse_args()
    port = given_args.port
    echo_client(port)
