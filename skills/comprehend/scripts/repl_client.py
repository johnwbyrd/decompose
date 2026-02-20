#!/usr/bin/env python3
"""Send code to the persistent REPL server and print results.

Connects via AF_UNIX where available (Linux, macOS). On platforms without
Unix domain sockets (Windows), reads the TCP address from the given path.

Usage:
    echo 'x = 42' | repl_client.py <address_path>
    repl_client.py <address_path> 'print(x + 1)'
    repl_client.py <address_path> --vars
    repl_client.py <address_path> --shutdown

Protocol: 4-byte big-endian length prefix + UTF-8 JSON payload.
"""

import json
import os
import socket
import struct
import sys

_HAS_UNIX = hasattr(socket, 'AF_UNIX')


def send_msg(sock, data):
    payload = json.dumps(data).encode("utf-8")
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_msg(sock):
    raw_len = sock.recv(4)
    if not raw_len:
        return None
    length = struct.unpack(">I", raw_len)[0]
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            return None
        payload += chunk
    return json.loads(payload.decode("utf-8"))


def connect(addr_path):
    """Connect to the REPL server, auto-detecting Unix socket vs TCP."""
    if _HAS_UNIX:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(addr_path)
    else:
        with open(addr_path) as f:
            addr = f.read().strip()
        host, port = addr.rsplit(':', 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
    return sock


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    addr_path = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == "--vars":
        msg = {"command": "show_vars"}
    elif len(sys.argv) > 2 and sys.argv[2] == "--shutdown":
        msg = {"command": "shutdown"}
    elif len(sys.argv) > 2:
        msg = {"code": " ".join(sys.argv[2:])}
    else:
        msg = {"code": sys.stdin.read()}

    try:
        sock = connect(addr_path)
    except (ConnectionRefusedError, FileNotFoundError):
        print(f"Error: Cannot connect to REPL server at {addr_path}", file=sys.stderr)
        print("Start the server first: python3 repl_server.py " + addr_path, file=sys.stderr)
        sys.exit(1)

    send_msg(sock, msg)
    result = recv_msg(sock)
    sock.close()

    if result is None:
        print("Error: No response from server", file=sys.stderr)
        sys.exit(1)

    if result.get("stdout"):
        print(result["stdout"], end="")
    if result.get("stderr"):
        print(result["stderr"], file=sys.stderr, end="")
    if "locals" in result and not result.get("stdout") and not result.get("stderr"):
        print(json.dumps(result["locals"], indent=2))


if __name__ == "__main__":
    main()
