import socket


def print_machine_info():
    host_name = socket.gethostname()
    ip_address = socket.gethostbyname(host_name)
    addr_info = socket.getaddrinfo(host_name, None)
    print("Host name: %s" % host_name)
    print("IP address: %s" % ip_address)
    print("\nNetwork Interfaces:")

    for info in addr_info:
        ip = info[4][0]
      
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
        print(f"  {name}: {ip}")

if __name__ == "__main__":
    print_machine_info()
