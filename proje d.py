# chat.py
# terminal 1
#python chat.py --mode server --host 127.0.0.1 --port 9900

# terminal 2
#python chat.py --mode client --host 127.0.0.1 --port 9900 --name ali

# terminal 3 (another client)
#python chat.py --mode client --host 127.0.0.1 --port 9900 --name veli

import socket
import threading
import argparse
import sys
from datetime import datetime

DATA_PAYLOAD = 2048
BACKLOG = 10

def log_line(path, text):
    #  timestamp
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def chat_server(host, port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(BACKLOG)
    print(f"[server] listening on {host}:{port}")

    clients = []               # list of (conn, addr, name)
    clients_lock = threading.Lock()
    log_file = "chat_log.txt"

    def broadcast(sender_conn, msg_bytes):
        # send to all except the sender
        with clients_lock:
            dead = []
            for (c, a, n) in clients:
                if c is not sender_conn:
                    try:
                        c.sendall(msg_bytes)
                    except:
                        dead.append(c)
            # purge dead
            for d in dead:
                for i, (c,a,n) in enumerate(clients):
                    if c is d:
                        try: c.close()
                        except: pass
                        clients.pop(i)
                        break

    def handle_client(conn, addr):
        # first line from client is its nickname
        try:
            name = conn.recv(DATA_PAYLOAD).decode("utf-8", errors="ignore").strip()
            if not name:
                name = f"{addr[0]}:{addr[1]}"
        except:
            name = f"{addr[0]}:{addr[1]}"

        join_msg = f"* {name} joined from {addr}"
        print(join_msg)
        log_line(log_file, join_msg)
        broadcast(conn, f"{join_msg}\n".encode("utf-8"))

        # message loop
        try:
            while True:
                data = conn.recv(DATA_PAYLOAD)
                if not data:
                    break
                text = data.decode("utf-8", errors="ignore").rstrip("\n")
                if text == "/quit":
                    break
                line = f"{name}: {text}"
                print(line)
                log_line(log_file, line)
                broadcast(conn, (line + "\n").encode("utf-8"))
        finally:
            leave_msg = f"* {name} left"
            print(leave_msg)
            log_line(log_file, leave_msg)
            broadcast(conn, f"{leave_msg}\n".encode("utf-8"))
            with clients_lock:
                # remove connection
                for i, (c,a,n) in enumerate(clients):
                    if c is conn:
                        clients.pop(i)
                        break
            try: conn.close()
            except: pass

    while True:
        try:
            conn, addr = srv.accept()
        except KeyboardInterrupt:
            print("\n[server] shutting down")
            with clients_lock:
                for c,_,_ in clients:
                    try: c.close()
                    except: pass
            srv.close()
            break

        # add client and start its thread
        with clients_lock:
            clients.append((conn, addr, None))
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


def chat_client(host, port, name):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    log_file = "chat_log.txt"

    
    sock.sendall((name + "\n").encode("utf-8"))
    print(f"[client] connected to {host}:{port} as '{name}'")
    print("type messages. '/quit' to exit.")

   
    def reader():
        while True:
            try:
                data = sock.recv(DATA_PAYLOAD)
                if not data:
                    print("[client] server closed")
                    break
                text = data.decode("utf-8", errors="ignore")
                print(text, end="")      
               
                for line in text.splitlines():
                    if line.strip():
                        log_line(log_file, f"[recv] {line}")
            except:
                break

    rt = threading.Thread(target=reader, daemon=True)
    rt.start()

   
    try:
        for line in sys.stdin:
            msg = line.rstrip("\n")
            if not msg:
                continue
            if msg == "/quit":
                sock.sendall(b"/quit\n")
                break
            # log our own message locally
            log_line(log_file, f"[send] {name}: {msg}")
            sock.sendall((msg + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        pass
    finally:
        try: sock.close()
        except: pass
        print("[client] bye")


def main():
    parser = argparse.ArgumentParser(description="Simple Chat (server or client)")
    parser.add_argument("--mode", required=True, choices=["server", "client"])
    parser.add_argument("--host", default="127.0.0.1")   #  127.0.0.1 for local tests
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--name", default="guest")       # client nickname
    args = parser.parse_args()

    if args.mode == "server":
        chat_server(args.host, args.port)
    else:
        chat_client(args.host, args.port, args.name)

if __name__ == "__main__":
    main()
