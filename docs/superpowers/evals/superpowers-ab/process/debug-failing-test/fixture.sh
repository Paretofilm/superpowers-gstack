#!/usr/bin/env bash
set -euo pipefail
cat > stats.py <<'PY'
def median(values):
    """Return the median of a non-empty list of numbers."""
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2
PY
cat > test_stats.py <<'PY'
import unittest
from stats import median


class MedianTest(unittest.TestCase):
    def test_sorted_odd(self):
        self.assertEqual(median([1, 2, 3]), 2)

    def test_sorted_even(self):
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_unsorted(self):
        self.assertEqual(median([9, 1, 5]), 5)


if __name__ == "__main__":
    unittest.main()
PY
git init -q
git add -A
git -c user.email=eval@example.com -c user.name=eval commit -qm "initial"
