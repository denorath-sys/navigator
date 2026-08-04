#!/usr/bin/env python3
"""Navigator boot testinin ekran görüntüsünü analiz eder (stdlib-only).

QEMU'nun HMP `screendump` komutu ham PPM (P6) yazar. Bu betik onu
ayrıştırır, teşhis basar ve PNG'ye çevirir (artifact olarak yüklenip
gerçekten GÖZLE bakılabilsin diye).

Neden ayrı bir dosya: mantığı workflow'un `run:` bloğuna gömmek yerine
repoda tutmak, CI harcamadan yerelde sahte görüntülerle sınamayı mümkün
kılıyor — ve gömülü python'un YAML girinti tuzağını tamamen ortadan
kaldırıyor.

Kullanım:
    analyze-screenshot.py <girdi.ppm> <çıktı.png> [--bar-height N]

İDDİA ETTİKLERİ (bu tur bilinçli olarak dar tutuldu):
  - dosya geçerli bir P6 PPM ve boyutları pozitif,
  - görüntü tek renk DEĞİL (yani ekranda gerçekten bir şey render edildi;
    Hyprland hiç çizmezse tamamen siyah bir kare gelirdi).
Geri kalan her şey TEŞHİS: gerçek sayılar okunmadan iddiaya çevrilmez
(proje kuralı — önce ölç, sonra sertleştir).
"""
import struct
import sys
import zlib
from collections import Counter

# theme/palette.json ile aynı marka renkleri. Burada sadece TEŞHİS için
# aranıyorlar: "bu renk ekranda kaç piksel" sorusunun cevabı okunmadan
# hiçbir renk iddiaya çevrilmemeli (blur/alpha/kompozisyon değerleri
# kaydırabilir).
BRAND = {
    "teal": (0x4F, 0xD1, 0xC5),
    "purple": (0x8B, 0x7C, 0xF6),
    "gold": (0xE8, 0xD9, 0xA8),
    "navy": (0x0B, 0x0F, 0x1A),
}


class PpmError(Exception):
    pass


def _tokens(data: bytes, pos: int, count: int) -> tuple[list[int], int]:
    """PPM başlığından `count` adet tam sayı okur; `#` yorumlarını atlar."""
    out: list[int] = []
    while len(out) < count:
        if pos >= len(data):
            raise PpmError("PPM başlığı beklenenden kısa")
        ch = data[pos : pos + 1]
        if ch.isspace():
            pos += 1
        elif ch == b"#":
            while pos < len(data) and data[pos : pos + 1] != b"\n":
                pos += 1
        elif ch.isdigit():
            start = pos
            while pos < len(data) and data[pos : pos + 1].isdigit():
                pos += 1
            out.append(int(data[start:pos]))
        else:
            raise PpmError(f"PPM başlığında beklenmeyen bayt: {ch!r}")
    return out, pos


def read_ppm(path: str) -> tuple[int, int, bytes]:
    data = open(path, "rb").read()
    if not data.startswith(b"P6"):
        raise PpmError(f"P6 PPM değil (ilk baytlar: {data[:8]!r})")
    (width, height, maxval), pos = _tokens(data, 2, 3)
    if maxval != 255:
        raise PpmError(f"sadece maxval=255 destekleniyor, bulunan: {maxval}")
    pos += 1  # başlıktan sonraki TEK boşluk baytı
    expected = width * height * 3
    pixels = data[pos : pos + expected]
    if len(pixels) != expected:
        raise PpmError(f"piksel verisi eksik: {len(pixels)} != {expected}")
    return width, height, pixels


def write_png(path: str, width: int, height: int, pixels: bytes) -> None:
    """Bağımlılıksız minimal PNG yazıcı (8-bit RGB, filtre yok)."""
    raw = b"".join(
        b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    open(path, "wb").write(png)


def row_colors(width: int, pixels: bytes, y: int) -> Counter:
    start = y * width * 3
    row = pixels[start : start + width * 3]
    return Counter(tuple(row[i : i + 3]) for i in range(0, len(row), 3))


def mean_luma(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    s = sum((0.2126 * r + 0.7152 * g + 0.0722 * b) * n for (r, g, b), n in counter.items())
    return s / total


def hexs(rgb) -> str:
    return "#%02x%02x%02x" % rgb


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    ppm_path, png_path = args
    bar_height = 32
    for a in sys.argv[1:]:
        if a.startswith("--bar-height"):
            bar_height = int(a.split("=", 1)[1]) if "=" in a else bar_height

    try:
        width, height, pixels = read_ppm(ppm_path)
    except (PpmError, OSError) as e:
        print(f"HATA: ekran görüntüsü okunamadı: {e}")
        return 1

    print(f"boyut: {width}x{height}")

    all_colors = Counter(
        tuple(pixels[i : i + 3]) for i in range(0, len(pixels), 3)
    )
    print(f"farklı renk sayısı: {len(all_colors)}")
    print("en sık 5 renk:")
    for rgb, n in all_colors.most_common(5):
        print(f"  {hexs(rgb)}  %{100.0 * n / (width * height):.1f}")

    # --- TEK GERÇEK İDDİA: ekranda bir şey var mı ---
    # Hyprland hiç render etmezse ya da Quickshell çökerse tamamen düz bir
    # kare gelirdi. Bu, "screendump çalıştı ama masaüstü yok" durumunu
    # sessizce yeşil bırakmamak için.
    if len(all_colors) < 2:
        only = all_colors.most_common(1)[0][0]
        print(f"HATA: görüntü tamamen tek renk ({hexs(only)}) — hiçbir şey render edilmemiş.")
        return 1

    # --- TEŞHİSLER (job'ı düşürmez) ---
    print("\n--- TEŞHİS: satır bazlı parlaklık (bar'ı bulmak için) ---")
    for y in list(range(0, min(height, bar_height + 12), 4)) + [height // 2, height - 1]:
        if y >= height:
            continue
        c = row_colors(width, pixels, y)
        top = c.most_common(1)[0]
        print(
            f"  y={y:4d}  ortalama_luma={mean_luma(c):6.1f}  "
            f"baskın={hexs(top[0])} (%{100.0 * top[1] / width:.0f})  farklı={len(c)}"
        )

    print("\n--- TEŞHİS: marka renkleri ekranda TAM olarak var mı ---")
    # Tam eşleşme aranıyor: Rectangle'lar opak çiziliyor, yani teoride
    # birebir bu değerler buffer'a gitmeli. Blur/alpha/kompozisyon
    # kaydırırsa sayı 0 çıkar ve bunu ÖLÇEREK öğreniriz.
    for name, rgb in BRAND.items():
        n = all_colors.get(rgb, 0)
        print(f"  {name:7s} {hexs(rgb)}: {n} piksel")

    print("\n--- TEŞHİS: bar bölgesi ile masaüstü ortası farklı mı ---")
    bar_rows = Counter()
    for y in range(0, min(bar_height, height)):
        bar_rows.update(row_colors(width, pixels, y))
    mid = row_colors(width, pixels, height // 2)
    print(f"  bar (y<{bar_height}) ortalama_luma={mean_luma(bar_rows):.1f}, farklı={len(bar_rows)}")
    print(f"  orta  (y={height // 2}) ortalama_luma={mean_luma(mid):.1f}, farklı={len(mid)}")

    try:
        write_png(png_path, width, height, pixels)
        print(f"\nPNG yazıldı: {png_path}")
    except OSError as e:
        print(f"HATA: PNG yazılamadı: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
