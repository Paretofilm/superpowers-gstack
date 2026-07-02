# H1: a visual-issue finder must critique every screen the run REACHED. A successful step lands on
# a newly-navigated screen — exactly what to inspect — so "success" is retained alongside problem
# steps and endpoints. Visually-identical successive screens (e.g. a scroll that hit the end, a
# rejected tap that changed nothing) are then collapsed by perceptual_dedup below so the critic is
# not billed for redundant pixels.
RETAIN_STATUSES = {"success", "rejected", "failed", "unsupported", "timeout", "app_left_foreground"}
import os
import struct
import subprocess
import tempfile


def ahash(gray_pixels, side: int = 8) -> int:
    """Gjennomsnitts-hash over en side*side nedskalert gråtoneliste."""
    avg = sum(gray_pixels) / len(gray_pixels)
    bits = 0
    for i, p in enumerate(gray_pixels):
        if p >= avg:
            bits |= (1 << i)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def should_retain(status: str, is_first: bool, is_last: bool) -> bool:
    return status in RETAIN_STATUSES or is_first or is_last


def is_critic_dup(new_hash: int, prev_hash, threshold: int = 5) -> bool:
    if prev_hash is None:
        return False
    return hamming(new_hash, prev_hash) <= threshold


def perceptual_dedup(items, hashes, threshold: int = 5):
    """Collapse visually near-identical successive screens, keeping the first of each group.
    items/hashes are parallel; a None hash (decode failed) is always kept and never becomes the
    comparison anchor, so a later real dupe still collapses against the last real hash."""
    kept = []
    last_hash = None
    for item, h in zip(items, hashes):
        if h is None or last_hash is None or hamming(h, last_hash) > threshold:
            kept.append(item)
            if h is not None:
                last_hash = h
    return kept


def ahash_png(path, side: int = 8):
    """Perceptual average-hash of a PNG, decoded via `sips` downscale → BMP (stdlib parse, no Pillow).
    sips is already in the tool chain (used for landscape rotation). Returns int, or None on any error
    so callers degrade to keeping the screen rather than crashing."""
    fd, bmp = tempfile.mkstemp(suffix=".bmp")
    os.close(fd)
    try:
        subprocess.run(["sips", "-z", str(side), str(side), "-s", "format", "bmp", path, "--out", bmp],
                       capture_output=True, check=True, timeout=15)
        with open(bmp, "rb") as f:
            data = f.read()
    except Exception:
        return None
    finally:
        try:
            os.unlink(bmp)
        except OSError:
            pass
    try:
        pixoff = struct.unpack("<I", data[10:14])[0]
        w = struct.unpack("<i", data[18:22])[0]
        h = abs(struct.unpack("<i", data[22:26])[0])
        bpp = struct.unpack("<H", data[28:30])[0]
        stride = ((w * bpp // 8 + 3) // 4) * 4  # BMP rows are padded to 4 bytes
        step = bpp // 8
        grays = []
        for r in range(h):
            base = pixoff + r * stride
            for c in range(w):
                px = base + c * step
                grays.append((data[px] + data[px + 1] + data[px + 2]) // 3)  # BGR(A) → gray
        if len(grays) != side * side:
            return None
        return ahash(grays, side)
    except Exception:
        return None
