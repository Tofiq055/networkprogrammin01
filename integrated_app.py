"""Integrated network programming application with modular menu."""
from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ntplib


class TimeService:
    """Retrieve time information from an NTP server with graceful fallbacks."""

    def __init__(self, server: str = "pool.ntp.org", refresh_interval: int = 300) -> None:
        self.server = server
        self.refresh_interval = refresh_interval
        self._client = ntplib.NTPClient()
        self._last_sync: Optional[datetime] = None
        self._last_ntp: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    def _fetch_time(self) -> Tuple[Optional[datetime], Optional[str]]:
        try:
            response = self._client.request(self.server, version=3, timeout=5)
            ntp_time = datetime.fromtimestamp(response.tx_time)
            self._last_sync = datetime.utcnow()
            self._last_ntp = ntp_time
            self._last_error = None
            return ntp_time, None
        except Exception as exc:  # pragma: no cover - network issues should not crash the app
            self._last_error = str(exc)
            return None, str(exc)

    def get_current_times(self, force_refresh: bool = False) -> Tuple[Optional[datetime], datetime, Optional[str]]:
        """Return (ntp_time, local_time, error)."""
        with self._lock:
            local_now = datetime.now()
            needs_refresh = (
                force_refresh
                or self._last_sync is None
                or self._last_ntp is None
                or (datetime.utcnow() - self._last_sync) > timedelta(seconds=self.refresh_interval)
            )
            if needs_refresh:
                ntp_time, error = self._fetch_time()
                if ntp_time is None:
                    return None, local_now, error

            if self._last_ntp is None or self._last_sync is None:
                return None, local_now, self._last_error

            drift = datetime.utcnow() - self._last_sync
            current_ntp = self._last_ntp + drift
            return current_ntp, local_now, None

    def timestamp_for_log(self) -> Tuple[str, str]:
        ntp_time, local_time, error = self.get_current_times()
        if ntp_time is not None:
            return ntp_time.strftime("%Y-%m-%d %H:%M:%S"), "NTP"
        return local_time.strftime("%Y-%m-%d %H:%M:%S"), "Local"

    def display_time_information(self) -> None:
        ntp_time, local_time, error = self.get_current_times(force_refresh=True)
        print("\nSNTP Time Check")
        print("----------------")
        if ntp_time is not None:
            print(f"NTP server ({self.server}) time : {ntp_time:%Y-%m-%d %H:%M:%S}")
            print(f"Local system time           : {local_time:%Y-%m-%d %H:%M:%S}")
            delta = ntp_time - local_time
            print(f"Clock difference            : {delta.total_seconds():.3f} seconds")
        else:
            print("Unable to reach NTP server; showing local time only.")
            print(f"Local system time           : {local_time:%Y-%m-%d %H:%M:%S}")
            if error:
                print(f"Reason: {error}")


class ErrorManager:
    """Centralised error/log management with optional NTP timestamps."""

    def __init__(self, time_service: TimeService, log_path: Path = Path("logs/error_log.jsonl")) -> None:
        self.time_service = time_service
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()
        self._lock = threading.Lock()

    def log(self, module: str, message: str, level: str = "INFO", extra: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        timestamp, source = self.time_service.timestamp_for_log()
        entry: Dict[str, object] = {
            "timestamp": timestamp,
            "time_source": source,
            "module": module,
            "level": level,
            "message": message,
        }
        if extra:
            entry.update(extra)
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry

    def _read_entries(self) -> List[Dict[str, object]]:
        with self._lock:
            content = self.log_path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        entries: List[Dict[str, object]] = []
        for line in content.splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def show_recent(self, limit: int = 10) -> None:
        entries = self._read_entries()
        if not entries:
            print("No log entries available.")
            return
        print(f"\nShowing the last {min(limit, len(entries))} log entries:")
        for entry in entries[-limit:]:
            print(
                f"[{entry.get('timestamp')} | {entry.get('time_source')} | {entry.get('level', 'INFO')}] "
                f"{entry.get('module', 'Unknown')}: {entry.get('message')}"
            )

    def show_summary(self) -> None:
        entries = self._read_entries()
        if not entries:
            print("No log entries to summarise.")
            return
        summary: Dict[str, int] = {}
        for entry in entries:
            level = str(entry.get("level", "INFO")).upper()
            summary[level] = summary.get(level, 0) + 1
        print("\nLog Summary by Level:")
        for level, count in sorted(summary.items()):
            print(f"  {level:<7} : {count}")

    def clear(self) -> None:
        with self._lock:
            self.log_path.write_text("", encoding="utf-8")
        print("Log cleared successfully.")


@dataclass
class SocketSettings:
    timeout: float = 0.0
    recv_buffer: int = 0
    send_buffer: int = 0
    nonblocking: bool = False

    def apply(self, sock: socket.socket, *, allow_nonblocking: bool = True) -> None:
        if self.recv_buffer > 0:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.recv_buffer)
        if self.send_buffer > 0:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.send_buffer)
        if self.timeout > 0:
            sock.settimeout(self.timeout)
        else:
            # None resets to system default blocking behaviour
            sock.settimeout(None)
        if allow_nonblocking and self.nonblocking:
            sock.setblocking(False)
        else:
            sock.setblocking(True)

    def describe(self) -> str:
        return (
            f"timeout={self.timeout}s, recv_buffer={self.recv_buffer} bytes, "
            f"send_buffer={self.send_buffer} bytes, nonblocking={self.nonblocking}"
        )


def machine_information_module() -> None:
    print("\nMachine Information")
    print("-------------------")
    host_name = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(host_name)
    except socket.gaierror:
        ip_address = "Unknown"
    print(f"Host name : {host_name}")
    print(f"IP address: {ip_address}")
    try:
        addr_info = socket.getaddrinfo(host_name, None)
    except socket.gaierror:
        print("Unable to enumerate interfaces.")
        return

    seen = set()
    for info in addr_info:
        ip = info[4][0]
        if ip in seen:
            continue
        seen.add(ip)
        if ip.startswith("192.168."):
            name = "Wi-Fi / LAN"
        elif ip.startswith("10."):
            name = "VPN"
        elif ip.startswith("127."):
            name = "Localhost"
        elif ip.startswith("172."):
            name = "Docker or Internal Network"
        elif ":" in ip:
            name = "IPv6 Interface"
        else:
            name = "Unknown Interface"
        print(f"  {name:<24}: {ip}")


class EchoTester:
    def __init__(self, settings: SocketSettings, error_manager: ErrorManager, host: str = "127.0.0.1") -> None:
        self.settings = settings
        self.error_manager = error_manager
        self.host = host

    def _accept_connection(self, srv: socket.socket) -> Tuple[socket.socket, Tuple[str, int]]:
        deadline = time.time() + self.settings.timeout if self.settings.timeout > 0 else None
        while True:
            try:
                return srv.accept()
            except BlockingIOError:
                if deadline and time.time() > deadline:
                    raise TimeoutError("accept timed out")
                time.sleep(0.05)
            except socket.timeout:
                raise

    def _recv_all(self, conn: socket.socket) -> bytes:
        chunks = bytearray()
        deadline = time.time() + self.settings.timeout if self.settings.timeout > 0 else None
        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                chunks.extend(data)
            except BlockingIOError:
                if deadline and time.time() > deadline:
                    raise TimeoutError("receive timed out")
                time.sleep(0.05)
            except socket.timeout:
                raise
        return bytes(chunks)

    def _send_all(self, conn: socket.socket, data: bytes) -> None:
        view = memoryview(data)
        sent = 0
        deadline = time.time() + self.settings.timeout if self.settings.timeout > 0 else None
        while sent < len(view):
            try:
                nbytes = conn.send(view[sent:])
                if nbytes == 0:
                    raise ConnectionError("socket connection broken")
                sent += nbytes
            except BlockingIOError:
                if deadline and time.time() > deadline:
                    raise TimeoutError("send timed out")
                time.sleep(0.05)
            except socket.timeout:
                raise

    def _server_thread(self, ready: threading.Event, port_holder: Dict[str, int], result: Dict[str, object]) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.settings.apply(srv)
                srv.bind((self.host, 0))
                srv.listen(1)
                port_holder["port"] = srv.getsockname()[1]
                ready.set()
                conn, addr = self._accept_connection(srv)
                with conn:
                    payload = self._recv_all(conn)
                    if payload:
                        self._send_all(conn, payload)
                        result["payload"] = payload
                    result["client"] = addr
        except Exception as exc:  # pragma: no cover - defensive: avoid crashing background thread
            result["error"] = str(exc)
            ready.set()
            self.error_manager.log("Echo Test", f"Server error: {exc}", level="ERROR")

    def run(self) -> None:
        message = input("Enter a message for the echo test (default: 'Hello from Echo Test'): ").strip() or "Hello from Echo Test"
        ready = threading.Event()
        port_holder: Dict[str, int] = {}
        result: Dict[str, object] = {}
        thread = threading.Thread(target=self._server_thread, args=(ready, port_holder, result), daemon=True)
        thread.start()
        if not ready.wait(timeout=2):
            print("Echo server failed to start.")
            self.error_manager.log("Echo Test", "Server failed to start", level="ERROR")
            return

        if "error" in result:
            print(f"Server error: {result['error']}")
            return

        port = port_holder.get("port")
        if not port:
            print("Unable to determine server port.")
            self.error_manager.log("Echo Test", "Server did not provide a port", level="ERROR")
            return

        client_result: Dict[str, object] = {}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cli:
                self.settings.apply(cli)
                start_time = time.time()
                cli.connect((self.host, port))
                self._send_all(cli, message.encode("utf-8"))
                try:
                    cli.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                echoed = self._recv_all(cli)
                duration = time.time() - start_time
                client_result = {
                    "sent": message,
                    "received": echoed.decode("utf-8", errors="replace"),
                    "matched": echoed.decode("utf-8", errors="replace") == message,
                    "round_trip_ms": duration * 1000.0,
                }
        except Exception as exc:
            client_result = {"error": str(exc)}

        thread.join(timeout=2)

        if "error" in client_result:
            print(f"Echo test failed: {client_result['error']}")
            self.error_manager.log("Echo Test", f"Client error: {client_result['error']}", level="ERROR")
            return

        print("\nEcho Test Result")
        print("----------------")
        print(f"Message sent    : {client_result['sent']}")
        print(f"Message received: {client_result['received']}")
        print(f"Round trip time : {client_result['round_trip_ms']:.2f} ms")
        if client_result["matched"]:
            print("Status          : SUCCESS (messages match)")
            self.error_manager.log(
                "Echo Test",
                "Echo successful",
                level="INFO",
                extra={"round_trip_ms": round(client_result["round_trip_ms"], 2)},
            )
        else:
            print("Status          : WARNING (messages differ)")
            self.error_manager.log("Echo Test", "Echo response mismatch", level="WARNING")


class ChatModule:
    def __init__(
        self,
        settings: SocketSettings,
        error_manager: ErrorManager,
        host: str = "127.0.0.1",
        port: int = 9900,
        log_path: Path = Path("chat_log.txt"),
    ) -> None:
        self.settings = settings
        self.error_manager = error_manager
        self.host = host
        self.port = port
        self.log_path = log_path
        self.log_path.touch(exist_ok=True)
        self._server_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._server_ready = threading.Event()
        self._clients: List[socket.socket] = []
        self._clients_lock = threading.Lock()

    def _log_chat_line(self, text: str) -> None:
        timestamp, _ = self.error_manager.time_service.timestamp_for_log()
        line = f"[{timestamp}] {text}\n"
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _broadcast(self, sender: Optional[socket.socket], payload: bytes) -> None:
        dead: List[socket.socket] = []
        with self._clients_lock:
            for client in self._clients:
                if client is sender:
                    continue
                try:
                    client.sendall(payload)
                except OSError:
                    dead.append(client)
            if dead:
                for client in dead:
                    try:
                        client.close()
                    except OSError:
                        pass
                    if client in self._clients:
                        self._clients.remove(client)

    def _handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        try:
            name_data = conn.recv(1024)
            name = name_data.decode("utf-8", errors="ignore").strip() or f"{addr[0]}:{addr[1]}"
        except Exception:
            name = f"{addr[0]}:{addr[1]}"
        join_msg = f"* {name} joined from {addr}"
        print(join_msg)
        self.error_manager.log("Chat", join_msg)
        self._log_chat_line(join_msg)
        self._broadcast(conn, f"{join_msg}\n".encode("utf-8"))
        try:
            while not self._stop_event.is_set():
                try:
                    data = conn.recv(2048)
                except socket.timeout:
                    continue
                if not data:
                    break
                text = data.decode("utf-8", errors="ignore").rstrip("\n")
                if text == "/quit":
                    break
                line = f"{name}: {text}"
                print(line)
                self.error_manager.log("Chat", line)
                self._log_chat_line(line)
                self._broadcast(conn, (line + "\n").encode("utf-8"))
        finally:
            leave_msg = f"* {name} left"
            print(leave_msg)
            self.error_manager.log("Chat", leave_msg)
            self._log_chat_line(leave_msg)
            with self._clients_lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            try:
                conn.close()
            except OSError:
                pass
            self._broadcast(conn, f"{leave_msg}\n".encode("utf-8"))

    def _server_loop(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # For the server we keep blocking behaviour to simplify shutdown handling
                self.settings.apply(srv, allow_nonblocking=False)
                srv.bind((self.host, self.port))
                srv.listen(10)
                srv.settimeout(1.0)
                self._server_ready.set()
                print(f"[chat server] listening on {self.host}:{self.port}")
                self.error_manager.log("Chat", f"Server listening on {self.host}:{self.port}")
                while not self._stop_event.is_set():
                    try:
                        conn, addr = srv.accept()
                    except socket.timeout:
                        continue
                    except OSError as exc:
                        if self._stop_event.is_set():
                            break
                        self.error_manager.log("Chat", f"Server socket error: {exc}", level="ERROR")
                        break
                    with self._clients_lock:
                        self._clients.append(conn)
                    conn.settimeout(1.0)
                    threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        finally:
            with self._clients_lock:
                for client in list(self._clients):
                    try:
                        client.close()
                    except OSError:
                        pass
                self._clients.clear()
            self._server_ready.clear()
            print("[chat server] stopped")
            self.error_manager.log("Chat", "Server stopped")

    def start_server(self) -> None:
        if self._server_thread and self._server_thread.is_alive():
            print("Chat server is already running.")
            return
        self._stop_event.clear()
        self._server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self._server_thread.start()
        if not self._server_ready.wait(timeout=2):
            print("Chat server failed to start.")
            self.error_manager.log("Chat", "Server failed to start", level="ERROR")
        else:
            print("Chat server started successfully.")

    def stop_server(self) -> None:
        if not (self._server_thread and self._server_thread.is_alive()):
            print("Chat server is not running.")
            return
        self._stop_event.set()
        self._server_thread.join(timeout=3)
        if self._server_thread.is_alive():
            print("Chat server did not shut down cleanly.")
            self.error_manager.log("Chat", "Server shutdown timeout", level="WARNING")
        else:
            print("Chat server stopped.")

    def run_client(self) -> None:
        name = input("Enter your chat nickname (default: guest): ").strip() or "guest"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.settings.apply(sock, allow_nonblocking=False)
                sock.connect((self.host, self.port))
                sock.sendall((name + "\n").encode("utf-8"))
                print(f"Connected to chat server at {self.host}:{self.port} as '{name}'.")
                print("Type messages and press Enter to send. Use '/quit' to exit the chat module.")

                stop_reader = threading.Event()

                def reader() -> None:
                    while not stop_reader.is_set():
                        try:
                            data = sock.recv(2048)
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                        if not data:
                            print("\n[chat] server closed the connection")
                            break
                        text = data.decode("utf-8", errors="ignore")
                        if text:
                            print("\r" + text, end="")
                            print("> ", end="", flush=True)
                    stop_reader.set()

                reader_thread = threading.Thread(target=reader, daemon=True)
                reader_thread.start()

                while not stop_reader.is_set():
                    try:
                        msg = input("> ")
                    except EOFError:
                        msg = "/quit"
                    if not msg:
                        continue
                    sock.sendall((msg + "\n").encode("utf-8"))
                    if msg == "/quit":
                        break
                stop_reader.set()
                reader_thread.join(timeout=1)
        except ConnectionRefusedError:
            print("Unable to connect to the chat server. Is it running?")
            self.error_manager.log("Chat", "Client connection refused", level="ERROR")
        except Exception as exc:
            print(f"Chat client error: {exc}")
            self.error_manager.log("Chat", f"Client error: {exc}", level="ERROR")

    def show_chat_log(self, limit: int = 20) -> None:
        if not self.log_path.exists():
            print("No chat log available yet.")
            return
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            print("Chat log is empty.")
            return
        print(f"\nLast {min(limit, len(lines))} chat log entries:")
        for line in lines[-limit:]:
            print(line)

    def menu(self) -> None:
        while True:
            print("\nChat Module")
            print("-----------")
            print("1) Start chat server")
            print("2) Connect as client")
            print("3) Show chat log")
            print("4) Stop chat server")
            print("0) Return to main menu")
            choice = input("Select an option: ").strip()
            if choice == "1":
                self.start_server()
            elif choice == "2":
                self.run_client()
            elif choice == "3":
                self.show_chat_log()
            elif choice == "4":
                self.stop_server()
            elif choice == "0":
                return
            else:
                print("Invalid choice. Please try again.")


def configure_socket_settings(settings: SocketSettings) -> None:
    print("\nSocket Settings")
    print("----------------")
    print(f"Current settings: {settings.describe()}")
    try:
        timeout_str = input("Timeout in seconds (leave blank to keep current): ").strip()
        if timeout_str:
            settings.timeout = max(0.0, float(timeout_str))
        recv_str = input("Receive buffer size in bytes (leave blank to keep current): ").strip()
        if recv_str:
            settings.recv_buffer = max(0, int(recv_str))
        send_str = input("Send buffer size in bytes (leave blank to keep current): ").strip()
        if send_str:
            settings.send_buffer = max(0, int(send_str))
        nonblock_str = input("Use non-blocking sockets? (y/n, blank to keep current): ").strip().lower()
        if nonblock_str in {"y", "yes"}:
            settings.nonblocking = True
        elif nonblock_str in {"n", "no"}:
            settings.nonblocking = False
    except ValueError:
        print("Invalid numeric input. Settings unchanged.")
        return
    print(f"Updated settings: {settings.describe()}")


def error_management_menu(error_manager: ErrorManager) -> None:
    while True:
        print("\nError Management")
        print("-----------------")
        print("1) Show recent log entries")
        print("2) Show log summary")
        print("3) Clear log")
        print("0) Return to main menu")
        choice = input("Select an option: ").strip()
        if choice == "1":
            error_manager.show_recent()
        elif choice == "2":
            error_manager.show_summary()
        elif choice == "3":
            confirm = input("Are you sure you want to clear the log? (y/N): ").strip().lower()
            if confirm in {"y", "yes"}:
                error_manager.clear()
        elif choice == "0":
            return
        else:
            print("Invalid choice. Please try again.")


def main() -> None:
    time_service = TimeService()
    error_manager = ErrorManager(time_service)
    settings = SocketSettings()
    echo_tester = EchoTester(settings, error_manager)
    chat_module = ChatModule(settings, error_manager)

    while True:
        print("\nNetwork Programming Integrated Application")
        print("------------------------------------------")
        print("1) Machine Information")
        print("2) Echo Test")
        print("3) SNTP Time Check")
        print("4) Socket Settings")
        print("5) Chat")
        print("6) Error Management")
        print("0) Exit")
        choice = input("Select an option: ").strip()
        if choice == "1":
            machine_information_module()
        elif choice == "2":
            echo_tester.run()
        elif choice == "3":
            time_service.display_time_information()
        elif choice == "4":
            configure_socket_settings(settings)
        elif choice == "5":
            chat_module.menu()
        elif choice == "6":
            error_management_menu(error_manager)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")
