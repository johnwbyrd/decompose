#!/usr/bin/env python3
"""Persistent Python REPL server over a Unix domain socket.

Maintains a single namespace across all code executions. State lives
in-memory in the running process — no serialization needed.

Usage:
    repl_server.py <socket_path>

Protocol: 4-byte big-endian length prefix + UTF-8 JSON payload.
Request:  {"code": "x = 42"}
Response: {"stdout": "", "stderr": "", "locals": ["x"]}
"""

import io
import json
import os
import signal
import socket
import struct
import sys
import threading


_SAFE_BUILTINS = {
    "print": print, "len": len, "str": str, "int": int, "float": float,
    "list": list, "dict": dict, "set": set, "tuple": tuple, "bool": bool,
    "type": type, "isinstance": isinstance, "enumerate": enumerate,
    "zip": zip, "map": map, "filter": filter, "sorted": sorted,
    "reversed": reversed, "range": range, "min": min, "max": max,
    "sum": sum, "abs": abs, "round": round, "any": any, "all": all,
    "pow": pow, "divmod": divmod, "chr": chr, "ord": ord, "hex": hex,
    "bin": bin, "oct": oct, "repr": repr, "format": format, "hash": hash,
    "id": id, "iter": iter, "next": next, "slice": slice,
    "callable": callable, "hasattr": hasattr, "getattr": getattr,
    "setattr": setattr, "dir": dir, "vars": vars,
    "bytes": bytes, "bytearray": bytearray, "complex": complex,
    "object": object, "super": super, "property": property,
    "__import__": __import__, "open": open,
    "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
    "KeyError": KeyError, "IndexError": IndexError, "RuntimeError": RuntimeError,
    "FileNotFoundError": FileNotFoundError, "OSError": OSError,
    "StopIteration": StopIteration, "AssertionError": AssertionError,
    "ImportError": ImportError, "AttributeError": AttributeError,
    "NotImplementedError": NotImplementedError,
    "input": None, "eval": None, "exec": None, "compile": None,
    "globals": None, "locals": None,
}


class PersistentREPL:
    def __init__(self):
        self.globals = {"__builtins__": _SAFE_BUILTINS.copy(), "__name__": "__main__"}
        self.user_locals = {}
        self._lock = threading.Lock()

    def execute(self, code):
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr

        with self._lock:
            try:
                sys.stdout, sys.stderr = stdout_buf, stderr_buf
                combined = {**self.globals, **self.user_locals}
                exec(code, combined, combined)
                for key, value in combined.items():
                    if key not in self.globals and not key.startswith("_"):
                        self.user_locals[key] = value
            except Exception as e:
                stderr_buf.write(f"\n{type(e).__name__}: {e}")
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr

        visible_locals = [k for k in self.user_locals if not k.startswith("_")]
        return {
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "locals": visible_locals,
        }


def recv_msg(conn):
    raw_len = conn.recv(4)
    if not raw_len:
        return None
    length = struct.unpack(">I", raw_len)[0]
    payload = b""
    while len(payload) < length:
        chunk = conn.recv(length - len(payload))
        if not chunk:
            return None
        payload += chunk
    return json.loads(payload.decode("utf-8"))


def send_msg(conn, data):
    payload = json.dumps(data).encode("utf-8")
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def handle_client(conn, repl):
    try:
        msg = recv_msg(conn)
        if msg is None:
            return
        if "code" in msg:
            result = repl.execute(msg["code"])
            send_msg(conn, result)
        elif msg.get("command") == "show_vars":
            visible = {k: type(v).__name__ for k, v in repl.user_locals.items()
                        if not k.startswith("_")}
            send_msg(conn, {"locals": visible})
        elif msg.get("command") == "shutdown":
            send_msg(conn, {"status": "shutting down"})
            os._exit(0)
        else:
            send_msg(conn, {"stderr": "Unknown request"})
    except Exception as e:
        try:
            send_msg(conn, {"stderr": f"Server error: {e}"})
        except Exception:
            pass
    finally:
        conn.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: repl_server.py <socket_path>", file=sys.stderr)
        sys.exit(1)

    sock_path = sys.argv[1]

    # Clean up stale socket
    if os.path.exists(sock_path):
        os.unlink(sock_path)

    repl = PersistentREPL()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(5)

    def cleanup(signum, frame):
        server.close()
        if os.path.exists(sock_path):
            os.unlink(sock_path)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    print(f"REPL server listening on {sock_path}", file=sys.stderr)

    while True:
        conn, _ = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, repl), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
