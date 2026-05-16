// Minimal Levenshtein for typo detection on `type:` field (D12).
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  const prev: number[] = Array.from({ length: b.length + 1 }, (_, i) => i);
  const curr: number[] = new Array(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i++) {
    curr[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    for (let j = 0; j <= b.length; j++) prev[j] = curr[j];
  }
  return prev[b.length];
}

export function closestMatch(input: string, candidates: string[], threshold = 3): string | null {
  let best: { name: string; dist: number } | null = null;
  for (const c of candidates) {
    const d = levenshtein(input, c);
    if (d < threshold && (!best || d < best.dist)) best = { name: c, dist: d };
  }
  return best ? best.name : null;
}
