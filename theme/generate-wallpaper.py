#!/usr/bin/env python3
"""Navigator duvar kâğıdını üretir (stdlib-only, bağımlılıksız).

Neden ikili bir görsel değil de üretici bir betik:

- Depoda ikili bir varlık taşımak yerine kaynağı taşıyoruz; palet
  değişirse duvar kâğıdı da değişir, elle yeniden çizilmesi gerekmez.
- `theme/palette.json` marka renklerinin tek kaynağı; buradaki renkler
  ELLE tekrarlanmıyor, o dosyadan OKUNUYOR. (hyprland.conf ve Theme.qml
  hâlâ elle tekrarlıyor ve CI onları karşılaştırıyor — burada o sapma
  riski hiç doğmuyor.)
- Çıktı deterministik: sabit tohumlu bir PRNG kullanılıyor, aynı girdi
  aynı baytları üretiyor. Böylece imaj build'i tekrarlanabilir kalıyor.

Kimlik: gece göğü (lacivert taban), Orion takımyıldızı ve Kuzey Yıldızı
— `theme/palette.json`'daki nautical/gökyüzü temasının doğrudan görsel
karşılığı. Bilinçli olarak KOYU ve SAKİN: üstünde bar, pencereler ve
asistan paneli okunacak, duvar kâğıdı onlarla yarışmamalı.

Kullanım:
    generate-wallpaper.py <çıktı.png> [--width 2560] [--height 1440]
"""
import json
import math
import os
import random
import struct
import sys
import zlib

SEED = 20260804  # deterministik çıktı için sabit

# Orion'un yıldızları — kutu içinde normalize konumlar (0..1).
# Betelgeuse sol üst omuz, Bellatrix sağ üst omuz, kuşak ortada,
# Saiph sol alt diz, Rigel sağ alt ayak.
ORION = {
    "betelgeuse": (0.28, 0.13, 2.6),
    "bellatrix": (0.71, 0.19, 2.2),
    "alnitak": (0.44, 0.49, 2.0),
    "alnilam": (0.52, 0.51, 2.2),
    "mintaka": (0.60, 0.53, 2.0),
    "saiph": (0.36, 0.86, 2.0),
    "rigel": (0.74, 0.89, 2.6),
}
ORION_LINES = [
    ("betelgeuse", "bellatrix"),
    ("betelgeuse", "alnitak"),
    ("bellatrix", "mintaka"),
    ("alnitak", "alnilam"),
    ("alnilam", "mintaka"),
    ("alnitak", "saiph"),
    ("mintaka", "rigel"),
]


def load_palette(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: hex_to_rgb(v["hex"]) for k, v in data["colors"].items()}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class Canvas:
    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.buf = bytearray(width * height * 3)

    def fill_gradient(self, top: tuple, bottom: tuple) -> None:
        """Dikey gradyan. Satır başına tek hesap + tekrar — hızlı."""
        for y in range(self.h):
            t = y / max(1, self.h - 1)
            # ease-in: üst yarı uzun süre koyu kalsın, ışıma alta toplansın
            e = t * t
            row = bytes(
                int(round(top[i] + (bottom[i] - top[i]) * e)) for i in range(3)
            ) * self.w
            self.buf[y * self.w * 3 : (y + 1) * self.w * 3] = row

    def add(self, x: int, y: int, color: tuple, alpha: float) -> None:
        """Toplamalı karıştırma (yıldız ışığı zemine EKLENİR)."""
        if not (0 <= x < self.w and 0 <= y < self.h) or alpha <= 0:
            return
        i = (y * self.w + x) * 3
        for k in range(3):
            v = self.buf[i + k] + color[k] * alpha
            self.buf[i + k] = 255 if v > 255 else int(v)

    def glow(self, cx: float, cy: float, radius: float, color: tuple, strength: float) -> None:
        """Yumuşak dairesel ışıma — yıldızlar ve ufuk parıltısı için."""
        x0, x1 = int(cx - radius) - 1, int(cx + radius) + 2
        y0, y1 = int(cy - radius) - 1, int(cy + radius) + 2
        r2 = radius * radius
        for y in range(max(0, y0), min(self.h, y1)):
            dy = y - cy
            for x in range(max(0, x0), min(self.w, x1)):
                dx = x - cx
                d2 = dx * dx + dy * dy
                if d2 > r2:
                    continue
                falloff = (1.0 - math.sqrt(d2) / radius) ** 2
                self.add(x, y, color, strength * falloff)

    def line(self, p0: tuple, p1: tuple, color: tuple, strength: float) -> None:
        """Takımyıldız çizgisi — kasıtlı olarak çok sönük."""
        x0, y0 = p0
        x1, y1 = p1
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / steps
            self.add(int(round(x0 + (x1 - x0) * t)), int(round(y0 + (y1 - y0) * t)),
                     color, strength)

    def to_png(self, path: str) -> None:
        raw = b"".join(
            b"\x00" + bytes(self.buf[y * self.w * 3 : (y + 1) * self.w * 3])
            for y in range(self.h)
        )

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (struct.pack(">I", len(payload)) + tag + payload
                    + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw, 9))
        png += chunk(b"IEND", b"")
        with open(path, "wb") as fh:
            fh.write(png)


def build(width: int, height: int, palette: dict) -> Canvas:
    navy = palette["navy"]
    teal = palette["teal"]
    purple = palette["purple"]
    gold = palette["gold"]
    rng = random.Random(SEED)

    c = Canvas(width, height)
    # Taban: tepede saf lacivert, altta hafifçe mor-teal'e çalan bir ufuk.
    horizon = tuple(min(255, navy[i] + (purple[i] - navy[i]) * 0.22) for i in range(3))
    c.fill_gradient(navy, tuple(int(v) for v in horizon))

    # Ufuk parıltısı — deniz feneri çağrışımı, çok sönük ve geniş.
    c.glow(width * 0.5, height * 1.02, height * 0.55, teal, 0.10)

    # Yıldız alanı. Çoğunluk küçük ve sönük; birkaçı belirgin.
    star_count = int(width * height / 5200)
    for _ in range(star_count):
        x = rng.randrange(width)
        y = rng.randrange(height)
        # üst tarafta daha yoğun (gökyüzü), altta seyrek
        if rng.random() < (y / height) * 0.65:
            continue
        b = rng.random()
        if b > 0.985:
            c.glow(x, y, 2.6, gold, 0.55)
        elif b > 0.93:
            c.glow(x, y, 1.7, (255, 255, 255), 0.35)
        else:
            c.add(x, y, (255, 255, 255), 0.10 + b * 0.30)

    # Orion — sağ üstte, ölçülü bir kutu içinde.
    box_w = width * 0.26
    box_h = height * 0.34
    box_x = width * 0.66
    box_y = height * 0.12
    pts = {
        name: (box_x + nx * box_w, box_y + ny * box_h)
        for name, (nx, ny, _) in ORION.items()
    }
    for a, b in ORION_LINES:
        c.line(pts[a], pts[b], teal, 0.05)
    for name, (nx, ny, mag) in ORION.items():
        px, py = pts[name]
        c.glow(px, py, mag * 1.6, (255, 255, 255), 0.30)
        c.glow(px, py, mag * 0.7, gold, 0.55)

    # Kuzey Yıldızı — tek ve en parlak nokta, dört uçlu hafif bir parıltıyla.
    nx, ny = width * 0.845, height * 0.075
    c.glow(nx, ny, 16.0, teal, 0.10)
    c.glow(nx, ny, 7.0, gold, 0.45)
    c.glow(nx, ny, 2.6, (255, 255, 255), 0.95)
    for d in range(1, 22):
        f = (1.0 - d / 22.0) ** 2 * 0.5
        c.add(int(nx + d), int(ny), gold, f)
        c.add(int(nx - d), int(ny), gold, f)
        c.add(int(nx), int(ny + d), gold, f)
        c.add(int(nx), int(ny - d), gold, f)
    return c


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    out = args[0]
    width, height = 2560, 1440
    for a in sys.argv[1:]:
        if a.startswith("--width="):
            width = int(a.split("=", 1)[1])
        elif a.startswith("--height="):
            height = int(a.split("=", 1)[1])

    palette_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "palette.json")
    if not os.path.exists(palette_path):
        print(f"HATA: palet bulunamadı: {palette_path}")
        return 1
    palette = load_palette(palette_path)

    canvas = build(width, height, palette)
    canvas.to_png(out)
    print(f"duvar kâğıdı yazıldı: {out} ({width}x{height}, {os.path.getsize(out)} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
