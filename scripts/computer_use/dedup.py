RETAIN_STATUSES = {"rejected", "failed", "unsupported", "timeout", "app_left_foreground"}


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
