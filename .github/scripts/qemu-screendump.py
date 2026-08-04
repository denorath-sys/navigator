#!/usr/bin/env python3
"""QEMU'nun HMP monitor soketine bağlanıp `screendump` çalıştırır (stdlib-only).

VNC istemcisi kurmaya gerek yok: QEMU'nun kendi monitörü ekranın o anki
içeriğini ham PPM olarak HOST dosya sistemine yazabiliyor. VM'in içinde
hiçbir şey çalıştırılmıyor, yani ekran görüntüsü misafirden bağımsız —
tam olarak "kullanıcı ne görüyor" sorusunun cevabı.

Kullanım:
    qemu-screendump.py <monitor.sock> <çıktı.ppm>
"""
import os
import socket
import sys
import time

PROMPT = b"(qemu) "


def read_until_prompt(sock: socket.socket, timeout: float = 15.0) -> bytes:
    """Monitör komut istemini görene kadar okur.

    HMP satır tabanlı ve her yanıtın sonunda `(qemu) ` istemi geliyor;
    sabit bir `recv` sayısı yerine istemi beklemek, yavaş bir screendump'ta
    yanıtı yarıda kesmemizi engelliyor.
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
        print(f"HATA: monitor soketine bağlanılamadı ({sock_path}): {e}")
        return 1

    with sock:
        banner = read_until_prompt(sock, timeout=10.0)
        first = banner.decode("utf-8", "replace").strip().splitlines()
        print(f"monitor: {first[0] if first else '(banner yok)'}")

        sock.sendall(f"screendump {out_path}\n".encode())
        resp = read_until_prompt(sock, timeout=30.0).decode("utf-8", "replace")

    # HMP hataları çıkışa düz metin olarak basılıyor; sessizce geçmesin.
    lowered = resp.lower()
    if "error" in lowered or "unknown command" in lowered or "invalid" in lowered:
        print(f"HATA: screendump reddedildi:\n{resp.strip()}")
        return 1

    # Dosya asenkron yazılabiliyor: boyut sabitlenene kadar bekle.
    stable_size = -1
    for _ in range(30):
        if os.path.exists(out_path):
            size = os.path.getsize(out_path)
            if size > 0 and size == stable_size:
                print(f"ekran görüntüsü yazıldı: {out_path} ({size} bayt)")
                return 0
            stable_size = size
        time.sleep(0.5)

    print(f"HATA: {out_path} 15 saniyede oluşmadı/sabitlenmedi (son boyut: {stable_size}).")
    print(f"monitor yanıtı: {resp.strip()!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
