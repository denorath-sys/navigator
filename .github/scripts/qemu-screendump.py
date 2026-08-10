#!/usr/bin/env python3
"""Connect to QEMU's HMP monitor socket and run `screendump` (stdlib-only).

No VNC client needs to be installed: QEMU's own monitor can write the screen's
current contents to the HOST filesystem as a raw PPM. Nothing is run inside the
VM, so the screenshot is independent of the guest — exactly the answer to the
question "what is the user seeing".

Usage:
    qemu-screendump.py <monitor.sock> <output.ppm>
"""
import os
import socket
import sys
import time

PROMPT = b"(qemu) "


def read_until_prompt(sock: socket.socket, timeout: float = 15.0) -> bytes:
    """Read until the monitor's command prompt appears.

    HMP is line-based and every response ends with a `(qemu) ` prompt; waiting
    for the prompt rather than using a fixed number of `recv` calls keeps us
    from truncating the response on a slow screendump.
    """
    sock.settimeout(timeout)
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        if buf.rstrip().endswith(PROMPT.strip()) or PROMPT in buf.split(b"\n")[-1]:
            break
    return buf


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    sock_path, out_path = sys.argv[1], sys.argv[2]
    out_path = os.path.abspath(out_path)

    if os.path.exists(out_path):
        os.unlink(out_path)

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(sock_path)
    except OSError as e:
        print(f"ERROR: could not connect to the monitor socket ({sock_path}): {e}")
        return 1

    with sock:
        banner = read_until_prompt(sock, timeout=10.0)
        first = banner.decode("utf-8", "replace").strip().splitlines()
        print(f"monitor: {first[0] if first else '(no banner)'}")

        sock.sendall(f"screendump {out_path}\n".encode())
        resp = read_until_prompt(sock, timeout=30.0).decode("utf-8", "replace")

    # HMP errors are printed to the output as plain text; don't let them pass
    # silently.
    lowered = resp.lower()
    if "error" in lowered or "unknown command" in lowered or "invalid" in lowered:
        print(f"ERROR: screendump was refused:\n{resp.strip()}")
        return 1

    # The file can be written asynchronously: wait until its size stabilises.
    stable_size = -1
    for _ in range(30):
        if os.path.exists(out_path):
            size = os.path.getsize(out_path)
            if size > 0 and size == stable_size:
                print(f"screenshot written: {out_path} ({size} bytes)")
                return 0
            stable_size = size
        time.sleep(0.5)

    print(f"ERROR: {out_path} was not created/did not stabilise in 15 seconds (last size: {stable_size}).")
    print(f"monitor response: {resp.strip()!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
