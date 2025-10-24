import socket, sys, argparse

host = 'localhost'

def echo_client(port, timeout, rcvbuf, sndbuf, nonblock, logpath):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)              
    if rcvbuf > 0: sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    if sndbuf > 0: sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
    if timeout > 0: sock.settimeout(timeout)
    if nonblock: sock.setblocking(False)

    server_address = (host, port)
    print(f"[client] connect to {server_address}  (timeout={timeout}, rcvbuf={rcvbuf}, sndbuf={sndbuf}, nonblock={nonblock})")
    try:
        sock.connect(server_address)                                      
    except BlockingIOError:
        print("[client] connect in progress (non-blocking)")
    except socket.timeout:
        print("[client] connect timeout")
        sock.close()
        return
    except ConnectionRefusedError:
        print("[client] connection refused")
        sock.close()
        return

    try:
        message = "Test message. This will be echoed"                     
        sent = 0
        while sent < len(message):
            try:
                n = sock.send(message[sent:].encode('utf-8'))             
                sent += n
            except BlockingIOError:
                print("[client] send would block, retry...")
            except socket.timeout:
                print("[client] send timeout")
                break

        recv_buf = bytearray()
        expected = len(message.encode('utf-8'))
        while len(recv_buf) < expected:
            try:
                chunk = sock.recv(16)                                    
                if not chunk:
                    print("[client] server closed early")
                    break
                recv_buf += chunk
            except BlockingIOError:
                print("[client] recv would block, retry...")
            except socket.timeout:
                print("[client] recv timeout")
                break

        received_text = recv_buf.decode('utf-8')
        print("Received:", received_text)
        if received_text == message:
            print("Connection successful, data matches")
        else:
            print("Data mismatch")

    except OSError as e:
        print(f"[client] OS error: {e}")
    finally:
        print("[client] closing")
        sock.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Socket Client Example')
    p.add_argument('--port', type=int, required=True)
    # NEW flags for Module E
    p.add_argument('--timeout', type=float, default=0.0)
    p.add_argument('--rcvbuf', type=int, default=0)
    p.add_argument('--sndbuf', type=int, default=0)
    p.add_argument('--nonblock', action='store_true')
    p.add_argument('--log', default='')
    a = p.parse_args()
    echo_client(a.port, a.timeout, a.rcvbuf, a.sndbuf, a.nonblock, a.log)
