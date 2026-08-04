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
    analyze-screenshot.py <girdi.ppm> <çıktı.png> [--bar-height=N]
                          [--reference=<duvar-kagidi.png>]

İDDİA ETTİKLERİ (bu tur bilinçli olarak dar tutuldu):
  - dosya geçerli bir P6 PPM ve boyutları pozitif,
  - görüntü tek renk DEĞİL (yani ekranda gerçekten bir şey render edildi;
    Hyprland hiç çizmezse tamamen siyah bir kare gelirdi),
  - `--reference` verilirse: masaüstü GERÇEKTEN o duvar kâğıdını
    gösteriyor (blok bazlı karşılaştırma, bkz. MAX_BLOCK_DISTANCE).
Geri kalan her şey TEŞHİS: gerçek sayılar okunmadan iddiaya çevrilmez
(proje kuralı — önce ölç, sonra sertleştir).
"""
import math
import struct
import sys
import zlib
from collections import Counter

# Ekrandaki masaüstünün, olması gereken duvar kâğıdıyla ne kadar
# örtüştüğü. Blok bazlı ortalama renk farkının MEDYANI kullanılıyor;
# medyan, üst bar ve asistan paneli gibi kaplayan pencerelere karşı
# dayanıklı (onlar blokların azınlığını bozar).
#
# Eşik tahmin değil, gerçek ölçüm: aynı duvar kâğıdının gerçek bir
# ekran görüntüsüyle karşılaştırması medyan 0.1 verdi; farklı duvar
# kâğıtlarında 43.9 ve 68.7 çıktı. 15 ikisinin arasında, her iki yana
# da yüz katın üzerinde pay bırakıyor.
#
# NEDEN PARLAKLIK DEĞİL: önceki sürüm "masaüstü koyu mu" diye
# soruyordu (stok Hyprland 85.3, o zamanki üretilmiş duvar kâğıdı 21.6).
# Gerçek marka duvar kâğıdı gelince o ölçü çöktü — ortasında parlak bir
# dalga var ve aynı bandın luma'sı 73.0, yani stok'un 85.3'üne komşu.
# Parlaklık duvar kâğıdının KİMLİĞİNİ değil sadece bir özetini ölçüyordu.
MAX_BLOCK_DISTANCE = 15.0

# Karşılaştırma ızgarası. Kaba olması kasıtlı: hyprpaper'ın ölçekleme
# algoritmasını taklit etmeye çalışmıyoruz, kompozisyonun aynı olup
# olmadığına bakıyoruz.
GRID_X, GRID_Y = 24, 15

# theme/palette.json ile aynı marka renkleri. Burada sadece TEŞHİS için
# aranıyorlar: "bu renk ekranda kaç piksel" sorusunun cevabı okunmadan
# hiçbir renk iddiaya çevrilmemeli (blur/alpha/kompozisyon kaydırabilir).
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


def read_png(path: str) -> tuple[int, int, bytearray]:
    """8-bit RGB PNG okur (filtreleri çözerek). Referans duvar kâğıdı için."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PpmError(f"PNG değil: {path}")
    width, height, depth, ctype = struct.unpack(">IIBB", data[16:26])
    if depth != 8 or ctype != 2:
        raise PpmError(f"sadece 8-bit RGB PNG destekleniyor (depth={depth}, type={ctype})")
    idat = b""
    i = 8
    while i < len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        if data[i + 4 : i + 8] == b"IDAT":
            idat += data[i + 8 : i + 8 + length]
        i += 12 + length
    raw = zlib.decompress(idat)

    out = bytearray(width * height * 3)
    prev = bytearray(width * 3)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + width * 3])
        pos += width * 3
        if ftype == 1:
            for x in range(3, len(line)):
                line[x] = (line[x] + line[x - 3]) & 255
        elif ftype == 2:
            for x in range(len(line)):
                line[x] = (line[x] + prev[x]) & 255
        elif ftype == 3:
            for x in range(len(line)):
                a = line[x - 3] if x >= 3 else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif ftype == 4:
            for x in range(len(line)):
                a = line[x - 3] if x >= 3 else 0
                b = prev[x]
                c = prev[x - 3] if x >= 3 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out[y * width * 3 : (y + 1) * width * 3] = line
        prev = line
    return width, height, out


def block_means(width, height, pixels, win=(0.0, 1.0, 0.0, 1.0)) -> list:
    """Verilen alt-dikdörtgeni GRID_X×GRID_Y bloğa bölüp ortalama renkleri verir."""
    x0, x1, y0, y1 = win
    bx0, bx1 = int(width * x0), int(width * x1)
    by0, by1 = int(height * y0), int(height * y1)
    bw, bh = (bx1 - bx0) / GRID_X, (by1 - by0) / GRID_Y
    result = []
    for gy in range(GRID_Y):
        for gx in range(GRID_X):
            xs, xe = int(bx0 + gx * bw), int(bx0 + (gx + 1) * bw)
            ys, ye = int(by0 + gy * bh), int(by0 + (gy + 1) * bh)
            r = g = b = n = 0
            for y in range(ys, ye, max(1, (ye - ys) // 6)):
                for x in range(xs, xe, max(1, (xe - xs) // 6)):
                    j = (y * width + x) * 3
                    r += pixels[j]
                    g += pixels[j + 1]
                    b += pixels[j + 2]
                    n += 1
            result.append((r / n, g / n, b / n))
    return result


def cover_window(sw: int, sh: int, rw: int, rh: int) -> tuple:
    """hyprpaper'ın 'cover' ölçeklemesinde referansın GÖRÜNEN alt-dikdörtgeni.

    Ekranla referansın en-boy oranı farklıysa taşan kenarlar kırpılır;
    karşılaştırmanın anlamlı olması için aynı kırpmayı burada da yapmak
    gerekiyor.
    """
    screen_aspect, ref_aspect = sw / sh, rw / rh
    if ref_aspect > screen_aspect:  # referans daha geniş → yanlar kırpılır
        f = screen_aspect / ref_aspect
        return ((1 - f) / 2, (1 + f) / 2, 0.0, 1.0)
    f = ref_aspect / screen_aspect  # referans daha dar → alt/üst kırpılır
    return (0.0, 1.0, (1 - f) / 2, (1 + f) / 2)


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
    reference = None
    for a in sys.argv[1:]:
        if a.startswith("--bar-height="):
            bar_height = int(a.split("=", 1)[1])
        elif a.startswith("--reference="):
            reference = a.split("=", 1)[1]

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

    band_y0, band_y1 = int(height * 0.45), int(height * 0.70)
    band = Counter()
    for y in range(band_y0, band_y1):
        band.update(row_colors(width, pixels, y))
    print(f"\nmasaüstü bandı (y={band_y0}..{band_y1}) ortalama luma: {mean_luma(band):.1f} (teşhis)")

    # --- İDDİA: ekrandaki masaüstü GERÇEKTEN Navigator duvar kâğıdı mı ---
    if reference:
        try:
            rw, rh, rpix = read_png(reference)
        except (PpmError, OSError, zlib.error) as e:
            print(f"HATA: referans duvar kâğıdı okunamadı ({reference}): {e}")
            return 1
        win = cover_window(width, height, rw, rh)
        shot_blocks = block_means(width, height, pixels)
        ref_blocks = block_means(rw, rh, rpix, win)
        dists = sorted(
            math.dist(shot_blocks[i], ref_blocks[i]) for i in range(len(shot_blocks))
        )
        median = dists[len(dists) // 2]
        print(f"\nreferans duvar kâğıdı: {reference} ({rw}x{rh})")
        print(f"  görünen alan (cover kırpması): x %{win[0]*100:.1f}..%{win[1]*100:.1f}, "
              f"y %{win[2]*100:.1f}..%{win[3]*100:.1f}")
        print(f"  blok farkı — medyan={median:.1f}  ortalama={sum(dists)/len(dists):.1f}  "
              f"max={dists[-1]:.1f}")
        if median > MAX_BLOCK_DISTANCE:
            print(
                f"HATA: masaüstü referans duvar kâğıdıyla örtüşmüyor "
                f"({median:.1f} > {MAX_BLOCK_DISTANCE}) — hyprpaper duvar kâğıdını "
                "yüklememiş ya da başka bir görsel gösteriliyor olabilir."
            )
            return 1
        print(f"  OK: masaüstü referans duvar kâğıdıyla örtüşüyor "
              f"({median:.1f} <= {MAX_BLOCK_DISTANCE}).")

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
