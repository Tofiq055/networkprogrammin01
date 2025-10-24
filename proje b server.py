
import socket, sys, argparse

host = 'localhost'
data_payload = 2048
backlog = 5

def echo_server(port, timeout, rcvbuf, sndbuf, nonblock, logpath):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)              
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)            

    # settings for Module E
    if rcvbuf > 0: sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    if sndbuf > 0: sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, sndbuf)
    if timeout > 0: sock.settimeout(timeout)
    if nonblock: sock.setblocking(False)

    server_address = (host, port)
    print(f"[server] bind {server_address}  (timeout={timeout}, rcvbuf={rcvbuf}, sndbuf={sndbuf}, nonblock={nonblock})")
    if logpath: open(logpath, "a", encoding="utf-8").write("[server] settings applied\n")

    try:
        sock.bind(server_address)                                         
        sock.listen(backlog)                                              
        while True:
            print("[server] waiting for client...")
            try:
                client, address = sock.accept()                           
            except socket.timeout:
                print("[server] accept timeout")
                continue
            except BlockingIOError:
                print("[server] accept would block (non-blocking). retrying...")
                continue

            print(f"[server] client connected: {address}")
            try:
                data = client.recv(data_payload)                          
                print(f"[server] recv bytes={len(data) if data else 0}")
                if data:
                    client.send(data)                                     
                    print(f"[server] sent echo to {address}")
            except socket.timeout:
                print("[server] recv/send timeout")
            except ConnectionResetError:
                print("[server] client reset connection")
            except BlockingIOError:
                print("[server] recv/send would block (non-blocking)")
            finally:
                client.close()                                           
    except OSError as e:
        print(f"[server] OS error: {e}")
    finally:
        sock.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Socket Server Example')
    p.add_argument('--port', type=int, required=True)
    # NEW flags for Module E
    p.add_argument('--timeout', type=float, default=0.0)
    p.add_argument('--rcvbuf', type=int, default=0)
    p.add_argument('--sndbuf', type=int, default=0)
    p.add_argument('--nonblock', action='store_true')
    p.add_argument('--log', default='')
    a = p.parse_args()
    echo_server(a.port, a.timeout, a.rcvbuf, a.sndbuf, a.nonblock, a.log)
