#!/usr/bin/env python3
"""Analyse the screenshot from the Navigator boot test (stdlib-only).

QEMU'nun HMP `screendump` komutu ham PPM (P6) yazar. Bu betik onu
parses it, prints diagnostics and converts it to PNG (so it can be uploaded
as an artifact and genuinely LOOKED AT).

Why a separate file: keeping the logic in the repository rather than embedding
it in the workflow's `run:` block makes it possible to exercise it locally
against fake images without spending CI — and removes the YAML indentation trap
of embedded python entirely.

Usage:
    analyze-screenshot.py <input.ppm> <output.png> [--bar-height=N]
                          [--reference=<duvar-kagidi.png>]

WHAT IT ASSERTS (deliberately kept narrow this round):
  - the file is a valid P6 PPM with positive dimensions,
  - the image is NOT a single colour (i.e. something was genuinely rendered on
    screen; if Hyprland drew nothing at all a completely black frame would
    arrive),
  - if `--reference` is given: the desktop is GENUINELY showing that wallpaper
    (a block-based comparison, see MAX_BLOCK_DISTANCE).
Everything else is a DIAGNOSTIC: nothing is promoted to an assertion before the
real numbers have been read (a project rule — measure first, harden second).
"""
import math
import struct
import sys
import zlib
from collections import Counter

# How closely the on-screen desktop matches the wallpaper it should be showing.
# The MEDIAN of the block-based average colour difference is used; the median is
# robust against covering windows such as the top bar and the assistant panel
# (those spoil a minority of the blocks).
#
# The threshold is not a guess but a real measurement: comparing the same
# wallpaper against a real screenshot gave a median of 0.1; different wallpapers
# gave 43.9 and 68.7. 15 sits between them, leaving over a hundredfold margin on
# both sides.
#
# WHY NOT BRIGHTNESS: the previous version asked "is the desktop dark?" (stock
# Hyprland 85.3, the generated wallpaper of the time 21.6). When the real brand
# wallpaper arrived that measure collapsed — it has a bright wave in the middle
# and the same band's luma is 73.0, i.e. adjacent to stock's 85.3. Brightness was
# measuring only a summary of the wallpaper, not its IDENTITY.
MAX_BLOCK_DISTANCE = 15.0

# The comparison grid. Being coarse is deliberate: we are not trying to imitate
# hyprpaper's scaling algorithm, we are checking whether the composition is the
# same.
GRID_X, GRID_Y = 24, 15

# The same brand colours as theme/palette.json. They are looked for here only as
# a DIAGNOSTIC: no colour should be promoted to an assertion before the answer to
# "how many pixels of this colour are on screen" has been read (blur/alpha/
# compositing can shift it).
BRAND = {
    "teal": (0x4F, 0xD1, 0xC5),
    "purple": (0x8B, 0x7C, 0xF6),
    "gold": (0xE8, 0xD9, 0xA8),
    "navy": (0x0B, 0x0F, 0x1A),
}


class PpmError(Exception):
    pass


def _tokens(data: bytes, pos: int, count: int) -> tuple[list[int], int]:
    """Read `count` integers from the PPM header, skipping `#` comments."""
    out: list[int] = []
    while len(out) < count:
        if pos >= len(data):
            raise PpmError("PPM header is shorter than expected")
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
            raise PpmError(f"Unexpected byte in PPM header: {ch!r}")
    return out, pos


def read_ppm(path: str) -> tuple[int, int, bytes]:
    data = open(path, "rb").read()
    if not data.startswith(b"P6"):
        raise PpmError(f"Not a P6 PPM (first bytes: {data[:8]!r})")
    (width, height, maxval), pos = _tokens(data, 2, 3)
    if maxval != 255:
        raise PpmError(f"sadece maxval=255 destekleniyor, bulunan: {maxval}")
    pos += 1  # the SINGLE whitespace byte after the header
    expected = width * height * 3
    pixels = data[pos : pos + expected]
    if len(pixels) != expected:
        raise PpmError(f"piksel verisi eksik: {len(pixels)} != {expected}")
    return width, height, pixels


def read_png(path: str) -> tuple[int, int, bytearray]:
    """Read an 8-bit RGB PNG (undoing the filters). For the reference wallpaper."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PpmError(f"Not a PNG: {path}")
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
    """Split the given sub-rectangle into GRID_X×GRID_Y blocks and give the average colours."""
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
    """The VISIBLE sub-rectangle of the reference under hyprpaper's 'cover' scaling.

    If the screen and the reference have different aspect ratios the overflowing
    edges are cropped; applying the same cropping here is what makes the
    gerekiyor.
    """
    screen_aspect, ref_aspect = sw / sh, rw / rh
    if ref_aspect > screen_aspect:  # reference is wider → the sides are cropped
        f = screen_aspect / ref_aspect
        return ((1 - f) / 2, (1 + f) / 2, 0.0, 1.0)
    f = ref_aspect / screen_aspect  # reference is narrower → top/bottom are cropped
    return (0.0, 1.0, (1 - f) / 2, (1 + f) / 2)


def write_png(path: str, width: int, height: int, pixels: bytes) -> None:
    """A minimal, dependency-free PNG writer (8-bit RGB, no filtering)."""
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
        print(f"ERROR: could not read the screenshot: {e}")
        return 1

    print(f"size: {width}x{height}")

    all_colors = Counter(
        tuple(pixels[i : i + 3]) for i in range(0, len(pixels), 3)
    )
    print(f"distinct colour count: {len(all_colors)}")
    print("5 most frequent colours:")
    for rgb, n in all_colors.most_common(5):
        print(f"  {hexs(rgb)}  {100.0 * n / (width * height):.1f}%")

    # --- THE ONE REAL ASSERTION: is there anything on screen ---
    # If Hyprland rendered nothing at all, or Quickshell crashed, a completely
    # flat frame would arrive. This exists so that "screendump worked but there
    # is no desktop" is not left silently green.
    if len(all_colors) < 2:
        only = all_colors.most_common(1)[0][0]
        print(f"ERROR: the image is a single colour throughout ({hexs(only)}) — nothing was rendered.")
        return 1

    # --- DIAGNOSTICS (these do not fail the job) ---
    print("\n--- DIAGNOSTIC: row-wise brightness (to locate the bar) ---")
    for y in list(range(0, min(height, bar_height + 12), 4)) + [height // 2, height - 1]:
        if y >= height:
            continue
        c = row_colors(width, pixels, y)
        top = c.most_common(1)[0]
        print(
            f"  y={y:4d}  mean_luma={mean_luma(c):6.1f}  "
            f"dominant={hexs(top[0])} ({100.0 * top[1] / width:.0f}%)  distinct={len(c)}"
        )

    print("\n--- DIAGNOSTIC: are the brand colours EXACTLY present on screen ---")
    # An exact match is looked for: the Rectangles are drawn opaque, so in theory
    # these exact values should reach the buffer. If blur/alpha/compositing
    # shifts them the count comes out 0, and we learn that BY MEASURING.
    for name, rgb in BRAND.items():
        n = all_colors.get(rgb, 0)
        print(f"  {name:7s} {hexs(rgb)}: {n} piksel")

    band_y0, band_y1 = int(height * 0.45), int(height * 0.70)
    band = Counter()
    for y in range(band_y0, band_y1):
        band.update(row_colors(width, pixels, y))
    print(f"\ndesktop band (y={band_y0}..{band_y1}) mean luma: {mean_luma(band):.1f} (diagnostic)")

    # --- ASSERTION: is the on-screen desktop GENUINELY the Navigator wallpaper ---
    if reference:
        try:
            rw, rh, rpix = read_png(reference)
        except (PpmError, OSError, zlib.error) as e:
            print(f"ERROR: could not read the reference wallpaper ({reference}): {e}")
            return 1
        win = cover_window(width, height, rw, rh)
        shot_blocks = block_means(width, height, pixels)
        ref_blocks = block_means(rw, rh, rpix, win)
        dists = sorted(
            math.dist(shot_blocks[i], ref_blocks[i]) for i in range(len(shot_blocks))
        )
        median = dists[len(dists) // 2]
        print(f"\nreference wallpaper: {reference} ({rw}x{rh})")
        print(f"  visible area (cover cropping): x {win[0]*100:.1f}%..{win[1]*100:.1f}%, "
              f"y %{win[2]*100:.1f}..%{win[3]*100:.1f}")
        print(f"  block difference — median={median:.1f}  mean={sum(dists)/len(dists):.1f}  "
              f"max={dists[-1]:.1f}")
        if median > MAX_BLOCK_DISTANCE:
            print(
                f"ERROR: the desktop does not match the reference wallpaper "
                f"({median:.1f} > {MAX_BLOCK_DISTANCE}) — hyprpaper may not have "
                "loaded the wallpaper, or a different image is being shown."
            )
            return 1
        print(f"  OK: the desktop matches the reference wallpaper "
              f"({median:.1f} <= {MAX_BLOCK_DISTANCE}).")

    print("\n--- DIAGNOSTIC: does the bar region differ from the middle of the desktop ---")
    bar_rows = Counter()
    for y in range(0, min(bar_height, height)):
        bar_rows.update(row_colors(width, pixels, y))
    mid = row_colors(width, pixels, height // 2)
    print(f"  bar (y<{bar_height}) mean_luma={mean_luma(bar_rows):.1f}, distinct={len(bar_rows)}")
    print(f"  middle (y={height // 2}) mean_luma={mean_luma(mid):.1f}, distinct={len(mid)}")

    try:
        write_png(png_path, width, height, pixels)
        print(f"\nPNG written: {png_path}")
    except OSError as e:
        print(f"ERROR: could not write PNG: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
