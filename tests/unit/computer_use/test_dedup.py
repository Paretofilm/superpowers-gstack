from test_smoke import load
dedup = load("dedup")


def test_hamming():
    assert dedup.hamming(0b1010, 0b1000) == 1


def test_retain_keeps_every_explored_screen():
    # H1: the critic must see EVERY screen the run reached, not just endpoints + problem steps.
    # A successful mid-run navigation lands on a new screen whose post-action shot is exactly what
    # a visual-issue finder should critique — so a plain successful step is retained too.
    assert dedup.should_retain("rejected", False, False) is True
    assert dedup.should_retain("app_left_foreground", False, False) is True
    assert dedup.should_retain("success", True, False) is True    # første
    assert dedup.should_retain("success", False, True) is True    # siste
    assert dedup.should_retain("success", False, False) is True   # mellomsteg → utforsket skjerm, kritiseres


def test_critic_dup_threshold():
    assert dedup.is_critic_dup(0b1111, 0b1111, threshold=2) is True
    assert dedup.is_critic_dup(0b1111, 0b0000, threshold=2) is False
    assert dedup.is_critic_dup(0b1111, None) is False  # ingen forrige


def test_perceptual_dedup_collapses_near_duplicates():
    # three screens where #2 is a near-dupe of #1 (Hamming 1) and #3 is distinct.
    items = ["a", "b", "c"]
    hashes = [0b0000, 0b0001, 0b1111]
    kept = dedup.perceptual_dedup(items, hashes, threshold=2)
    assert kept == ["a", "c"], "near-dupe 'b' should be collapsed, distinct 'c' kept"


def test_perceptual_dedup_keeps_first_of_each_group():
    # a long identical run collapses to a single representative (the first)
    items = list("abcd")
    hashes = [0b0000, 0b0000, 0b0000, 0b0000]
    assert dedup.perceptual_dedup(items, hashes, threshold=2) == ["a"]


def test_perceptual_dedup_keeps_unhashable():
    # a None hash (decode failed) can't be compared -> always keep, and it must not become the
    # comparison anchor (so a later real dupe of the previous real hash still collapses).
    items = ["a", "x", "b"]
    hashes = [0b0000, None, 0b0001]
    kept = dedup.perceptual_dedup(items, hashes, threshold=2)
    assert kept == ["a", "x"], "None kept; 'b' collapses against 'a' not against None"


def test_ahash_png_identical_and_different(tmp_path):
    # ahash_png decodes via sips; identical images hash equal, a very different one differs.
    import subprocess, shutil
    if not shutil.which("sips"):
        import pytest
        pytest.skip("sips not available")
    white = tmp_path / "white.png"
    black = tmp_path / "black.png"
    # sips can synthesize solid images from a padded canvas; build via a tiny known PNG instead.
    # Use sips to create solids by cropping a generated gradient is overkill — write raw via python.
    _write_solid_png(white, 255)
    _write_solid_png(black, 0)
    hw = dedup.ahash_png(str(white))
    hb = dedup.ahash_png(str(black))
    hw2 = dedup.ahash_png(str(white))
    assert hw is not None and hb is not None
    assert hw == hw2, "identical image must hash identically"


def _write_solid_png(path, level):
    # minimal solid-gray 16x16 PNG, stdlib only (zlib), so the test needs no image lib
    import struct, zlib
    w = h = 16
    raw = b""
    for _ in range(h):
        raw += b"\x00" + bytes([level, level, level]) * w  # filter byte + RGB row
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))  # 8-bit RGB
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
