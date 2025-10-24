"""Integrated menu that reuses the original project modules."""
from __future__ import annotations

import importlib.util
import multiprocessing
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
ERROR_LOG = LOG_DIR / "error_log.txt"


def load_module(module_name: str, file_name: str):
    """Load a module from a file that contains dashes in its name."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = BASE_DIR / file_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Unable to load module from {file_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_echo_server_process(
    port: int,
    timeout: float,
    rcvbuf: int,
    sndbuf: int,
    nonblock: bool,
    logpath: str,
) -> None:
    server_module = load_module("server_b", "server-b.py")
    server_module.echo_server(port, timeout, rcvbuf, sndbuf, nonblock, logpath)


def run_chat_server_process(
    host: str,
    port: int,
    timeout: float,
    rcvbuf: int,
    sndbuf: int,
    nonblock: bool,
) -> None:
    chat_module = load_module("proje_d", "proje-d.py")
    chat_module.chat_server(host, port, timeout, rcvbuf, sndbuf, nonblock)


class IntegratedNetworkApp:
    """Main menu that orchestrates the existing standalone scripts."""

    def __init__(self) -> None:
        self.machine_module = load_module("proje_a", "proje-a.py")
        self.ntp_module = load_module("proje_c", "proje-c.py")
        self.echo_client_module = load_module("client_b", "client-b.py")
        self.chat_module = load_module("proje_d", "proje-d.py")

        self.echo_server_process: Optional[multiprocessing.Process] = None
        self.chat_server_process: Optional[multiprocessing.Process] = None

        self.echo_port = 9900
        self.socket_timeout = 0.0
        self.socket_rcvbuf = 0
        self.socket_sndbuf = 0
        self.socket_nonblock = False

    # ------------------------------------------------------------------
    # Logging helpers
    def append_log(self, module: str, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with ERROR_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] [{level}] {module}: {message}\n")

    def show_log(self) -> None:
        if not ERROR_LOG.exists():
            print("No log entries available.")
            return
        content = ERROR_LOG.read_text(encoding="utf-8").strip()
        if not content:
            print("No log entries available.")
            return
        print("\n--- Log Entries ---")
        print(content)

    def clear_log(self) -> None:
        ERROR_LOG.write_text("", encoding="utf-8")
        print("Log cleared.")

    # ------------------------------------------------------------------
    # Module wrappers
    def show_machine_info(self) -> None:
        try:
            self.machine_module.print_machine_info()
            self.append_log("Machine Information", "Displayed machine network information")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.append_log("Machine Information", f"Failed to display info: {exc}", level="ERROR")

    def show_sntp_time(self) -> None:
        try:
            self.ntp_module.print_time()
            self.append_log("SNTP", "Fetched SNTP time information")
        except Exception as exc:
            self.append_log("SNTP", f"Failed to fetch time: {exc}", level="ERROR")

    def _start_process(self, description: str, target, args: tuple, attr_name: str) -> None:
        process: Optional[multiprocessing.Process] = getattr(self, attr_name)
        if process is not None and process.is_alive():
            print(f"{description} server already running.")
            return
        process = multiprocessing.Process(target=target, args=args, daemon=True)
        process.start()
        setattr(self, attr_name, process)
        self.append_log(description, "Server started")
        time.sleep(0.5)

    def _stop_process(self, description: str, attr_name: str) -> None:
        process: Optional[multiprocessing.Process] = getattr(self, attr_name)
        if process is None:
            print(f"{description} server is not running.")
            return
        process.terminate()
        process.join(timeout=1)
        setattr(self, attr_name, None)
        self.append_log(description, "Server stopped")
        print(f"{description} server stopped.")

    def start_echo_server(self) -> None:
        args = (
            self.echo_port,
            self.socket_timeout,
            self.socket_rcvbuf,
            self.socket_sndbuf,
            self.socket_nonblock,
            str(LOG_DIR / "echo_server.log"),
        )
        self._start_process("Echo", run_echo_server_process, args, "echo_server_process")
        print(f"Echo server listening on localhost:{self.echo_port}")

    def stop_echo_server(self) -> None:
        self._stop_process("Echo", "echo_server_process")

    def run_echo_client(self) -> None:
        try:
            self.echo_client_module.echo_client(
                self.echo_port,
                self.socket_timeout,
                self.socket_rcvbuf,
                self.socket_sndbuf,
                self.socket_nonblock,
                str(LOG_DIR / "echo_client.log"),
            )
            self.append_log("Echo", "Client test executed")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.append_log("Echo", f"Client test failed: {exc}", level="ERROR")

    def configure_socket_settings(self) -> None:
        print("\nCurrent settings:")
        print(f"  Port           : {self.echo_port}")
        print(f"  Timeout        : {self.socket_timeout}")
        print(f"  Receive buffer : {self.socket_rcvbuf}")
        print(f"  Send buffer    : {self.socket_sndbuf}")
        print(f"  Non-blocking   : {self.socket_nonblock}")

        def prompt_int(prompt: str, current: int) -> int:
            value = input(f"{prompt} [{current}]: ").strip()
            if value == "":
                return current
            try:
                return int(value)
            except ValueError:
                print("Invalid integer, keeping previous value.")
                return current

        def prompt_float(prompt: str, current: float) -> float:
            value = input(f"{prompt} [{current}]: ").strip()
            if value == "":
                return current
            try:
                return float(value)
            except ValueError:
                print("Invalid number, keeping previous value.")
                return current

        def prompt_bool(prompt: str, current: bool) -> bool:
            value = input(f"{prompt} (y/n) [{'y' if current else 'n'}]: ").strip().lower()
            if value == "":
                return current
            return value in {"y", "yes", "1"}

        self.echo_port = prompt_int("Port", self.echo_port)
        self.socket_timeout = prompt_float("Timeout", self.socket_timeout)
        self.socket_rcvbuf = prompt_int("Receive buffer", self.socket_rcvbuf)
        self.socket_sndbuf = prompt_int("Send buffer", self.socket_sndbuf)
        self.socket_nonblock = prompt_bool("Non-blocking mode", self.socket_nonblock)
        self.append_log("Socket Settings", "Socket settings updated")

    def show_socket_settings(self) -> None:
        print("\nSocket Settings:")
        print(f"  Port           : {self.echo_port}")
        print(f"  Timeout        : {self.socket_timeout}")
        print(f"  Receive buffer : {self.socket_rcvbuf}")
        print(f"  Send buffer    : {self.socket_sndbuf}")
        print(f"  Non-blocking   : {self.socket_nonblock}")

    def chat_menu(self) -> None:
        while True:
            print("\nChat Module")
            print("1. Start chat server")
            print("2. Stop chat server")
            print("3. Start chat client")
            print("0. Back to main menu")
            choice = input("Select an option: ").strip()
            if choice == "1":
                host = input("Server host [127.0.0.1]: ").strip() or "127.0.0.1"
                port_str = input("Server port [9900]: ").strip()
                try:
                    port = int(port_str) if port_str else 9900
                except ValueError:
                    print("Invalid port.")
                    continue
                timeout_str = input("Socket timeout [0]: ").strip()
                try:
                    timeout = float(timeout_str) if timeout_str else 0.0
                except ValueError:
                    print("Invalid timeout.")
                    continue
                rcvbuf = input("Receive buffer (0 for default) [0]: ").strip()
                sndbuf = input("Send buffer (0 for default) [0]: ").strip()
                nonblock = input("Non-blocking mode? (y/n) [n]: ").strip().lower() in {"y", "yes", "1"}
                try:
                    args = (
                        host,
                        port,
                        timeout,
                        int(rcvbuf) if rcvbuf else 0,
                        int(sndbuf) if sndbuf else 0,
                        nonblock,
                    )
                except ValueError:
                    print("Buffer sizes must be integers.")
                    continue
                self._start_process("Chat", run_chat_server_process, args, "chat_server_process")
                print(f"Chat server listening on {host}:{port}")
            elif choice == "2":
                self.stop_chat_server()
            elif choice == "3":
                host = input("Server host [127.0.0.1]: ").strip() or "127.0.0.1"
                port_str = input("Server port [9900]: ").strip()
                try:
                    port = int(port_str) if port_str else 9900
                except ValueError:
                    print("Invalid port.")
                    continue
                name = input("Nickname [guest]: ").strip() or "guest"
                try:
                    self.chat_module.chat_client(host, port, name)
                    self.append_log("Chat", f"Client session completed for {name}")
                except Exception as exc:  # pragma: no cover - runtime safeguard
                    self.append_log("Chat", f"Client error: {exc}", level="ERROR")
            elif choice == "0":
                break
            else:
                print("Invalid option.")

    def echo_menu(self) -> None:
        while True:
            print("\nEcho Test Module")
            print("1. Show current socket settings")
            print("2. Update socket settings")
            print("3. Start echo server")
            print("4. Stop echo server")
            print("5. Run echo client test")
            print("0. Back to main menu")
            choice = input("Select an option: ").strip()
            if choice == "1":
                self.show_socket_settings()
            elif choice == "2":
                self.configure_socket_settings()
            elif choice == "3":
                self.start_echo_server()
            elif choice == "4":
                self.stop_echo_server()
            elif choice == "5":
                if self.echo_server_process is None or not self.echo_server_process.is_alive():
                    print("Echo server not running. Starting server automatically...")
                    self.start_echo_server()
                self.run_echo_client()
            elif choice == "0":
                break
            else:
                print("Invalid option.")

    def error_management_menu(self) -> None:
        while True:
            print("\nError Management")
            print("1. Show log entries")
            print("2. Clear log")
            print("0. Back to main menu")
            choice = input("Select an option: ").strip()
            if choice == "1":
                self.show_log()
            elif choice == "2":
                self.clear_log()
            elif choice == "0":
                break
            else:
                print("Invalid option.")

    def shutdown(self) -> None:
        if self.echo_server_process is not None and self.echo_server_process.is_alive():
            self.stop_echo_server()
        if self.chat_server_process is not None and self.chat_server_process.is_alive():
            self.stop_chat_server()

    def stop_chat_server(self) -> None:
        self._stop_process("Chat", "chat_server_process")

    def run(self) -> None:
        try:
            while True:
                print("\nIntegrated Network Programming Project")
                print("1. Machine Information")
                print("2. Echo Test")
                print("3. SNTP Time Check")
                print("4. Socket Settings")
                print("5. Chat")
                print("6. Error Management")
                print("0. Exit")
                choice = input("Select an option: ").strip()
                if choice == "1":
                    self.show_machine_info()
                elif choice == "2":
                    self.echo_menu()
                elif choice == "3":
                    self.show_sntp_time()
                elif choice == "4":
                    self.configure_socket_settings()
                elif choice == "5":
                    self.chat_menu()
                elif choice == "6":
                    self.error_management_menu()
                elif choice == "0":
                    break
                else:
                    print("Invalid option. Please select again.")
        finally:
            self.shutdown()


def main() -> None:
    app = IntegratedNetworkApp()
    app.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
