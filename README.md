# Network Programming Integrated Application

This repository contains a modular network programming project that combines several smaller
assignments into a single interactive command-line application.  The program exposes the following
modules through a main menu:

1. **Machine Information** – inspect local host/network interface details.
2. **Echo Test** – spin up an in-process echo server/client pair to validate connectivity while
   respecting configurable socket parameters.
3. **SNTP Time Check** – query an NTP server and compare the response with the local system clock.
4. **Socket Settings** – adjust the socket options (timeouts, buffer sizes, blocking mode) that are
   reused by other modules.
5. **Chat** – launch a threaded chat server, connect clients, and inspect chat logs.
6. **Error Management** – centralised log viewer that aggregates diagnostic information from the
   other modules with NTP-synchronised timestamps when available.

The project deadline described in the assignment brief is **24.10.2025 23:59**.

## Requirements

* Python 3.9 or later.
* No third-party installation is required because a copy of `ntplib` is bundled with the project.

## Running the application

```bash
python integrated_app.py
```

The program presents an interactive main menu.  Choose an option by entering the associated number.
Most modules return to the menu when they finish; the chat client keeps control until you exit with
`/quit`.

## Module overview

### Machine Information
Displays the system host name, best-effort primary IP address, and enumerates discovered interfaces
with friendly labels (Wi-Fi/LAN, VPN, Localhost, Docker/internal, IPv6, or unknown).

### Echo Test
Starts an echo server in a background thread, connects with a client socket configured according to
the current socket settings, and measures the round-trip time for a message.  Results are recorded in
the error log for traceability.

### SNTP Time Check
Uses the bundled `ntplib` client to query `pool.ntp.org`, shows the server time, local time, and the
calculated difference.  If the NTP request fails the module falls back to the local clock and reports
the error.

### Socket Settings
Stores reusable socket options (timeout, receive/send buffer sizes, blocking mode).  These settings
are applied to the echo test and chat module sockets so that experiments can be performed under
consistent conditions.

### Chat Module
Provides a submenu that can start/stop the threaded chat server, connect a client, and display the
chat log file (`chat_log.txt`).  The server accepts multiple clients, broadcasts messages, and logs
activity to both the chat log and the central error log.  Run multiple client sessions (even from
external terminals) to simulate a chat room.

### Error Management
Reads `logs/error_log.jsonl` and summarises the recorded events.  Each log entry contains the module
name, severity level, message, and an NTP-synchronised timestamp when available.  The menu can show
recent entries, display an aggregated summary, or clear the log file.

## Test outputs

Because the application is interactive, automated test scripts are not bundled.  Instead, run the
modules manually from the menu and inspect the console output as well as the generated log files
(`logs/error_log.jsonl` and `chat_log.txt`) to verify correct operation.

## Repository layout

```
integrated_app.py      # Integrated application with the menu and modules
proje-a.py             # Original machine information helper script
client-b.py            # Standalone echo client used during development
server-b.py            # Standalone echo server used during development
proje-c.py             # Original SNTP check script
proje-d.py             # Original chat application script
ntplib.py              # Bundled SNTP client library
chat_log.txt           # Chat transcript (also reused by the new chat module)
logs/                  # Created automatically for aggregated error logs
```

Feel free to explore the legacy scripts for reference; the integrated application replicates and
extends their functionality inside one cohesive program.
