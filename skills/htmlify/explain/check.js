// Layout check for an explainer page, run inside the page by bin/explain-check.
// Returns a JSON array of findings; an empty array means nothing was cut or overlapped.
// Kinds: page-overflow, clipped, runs-out, svg-cut, svg-overlap, svg-out-of-box.
(() => {
  const out = [];
  const label = (el) => {
    const t = (el.textContent || "").trim().replace(/\s+/g, " ");
    return t.length > 60 ? t.slice(0, 57) + "…" : t;
  };
  const section = (el) => {
    const s = el.closest("section, .top, footer");
    const tag = s && s.querySelector(".tag");
    return tag ? label(tag) : (s && s.tagName.toLowerCase()) || "page";
  };
  const add = (kind, el, detail) => out.push({ kind, section: section(el), text: label(el), detail });

  // 1. The page itself must not scroll sideways (wide diagrams scroll inside .scroll).
  const vw = document.documentElement.clientWidth;
  const sw = document.documentElement.scrollWidth;
  if (sw > vw + 1) out.push({ kind: "page-overflow", section: "page", text: "", detail: `page is ${sw}px wide in a ${vw}px viewport` });

  // 2. HTML text that is clipped, or runs past the box it sits in.
  for (const el of document.body.querySelectorAll("*")) {
    if (el.closest("svg") || el.closest(".scroll") || el.tagName === "SCRIPT" || el.tagName === "STYLE") continue;
    if (!el.clientWidth || !(el.textContent || "").trim()) continue;
    const cs = getComputedStyle(el);
    const overX = el.scrollWidth > el.clientWidth + 1;
    const overY = el.scrollHeight > el.clientHeight + 1;
    const clipsX = /hidden|clip/.test(cs.overflowX), clipsY = /hidden|clip/.test(cs.overflowY);
    if ((clipsX && overX) || (clipsY && overY) || cs.textOverflow === "ellipsis" && overX) {
      add("clipped", el, `content ${el.scrollWidth}×${el.scrollHeight} in a ${el.clientWidth}×${el.clientHeight} box`);
    } else if (overX && cs.overflowX === "visible" && cs.display !== "inline") {
      // Only report the innermost box: a parent overflows because its child does.
      const childOver = [...el.children].some((c) => c.clientWidth && c.scrollWidth > c.clientWidth + 1);
      if (!childOver) add("runs-out", el, `text is ${el.scrollWidth}px wide in a ${el.clientWidth}px box`);
    }
  }

  // 3. SVG text: cut by the drawing's edge, overlapping other text, or wider than its box.
  const inter = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) *
                          Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  const area = (r) => r.width * r.height;
  for (const svg of document.querySelectorAll("svg")) {
    const sb = svg.getBoundingClientRect();
    if (!sb.width) continue;
    const texts = [...svg.querySelectorAll("text")].filter((t) => t.textContent.trim())
      .map((t) => ({ t, r: t.getBoundingClientRect() }));
    const shapes = [...svg.querySelectorAll("rect, circle, ellipse")]
      .map((s) => ({ s, r: s.getBoundingClientRect() }))
      .filter(({ r }) => area(r) > 0 && area(r) < area(sb) * 0.9);
    for (const { t, r } of texts) {
      if (r.left < sb.left - 1 || r.right > sb.right + 1 || r.top < sb.top - 1 || r.bottom > sb.bottom + 1) {
        add("svg-cut", t, "text crosses the edge of the drawing");
        continue;
      }
      // Its box is the smallest shape holding the text's anchor point (start, middle or
      // end): a label too long for its box still starts inside it, its centre may not.
      const anchor = getComputedStyle(t).textAnchor;
      const cx = anchor === "middle" ? (r.left + r.right) / 2 : anchor === "end" ? r.right - 2 : r.left + 2;
      const cy = (r.top + r.bottom) / 2;
      const box = shapes.filter(({ r: b }) => cx >= b.left && cx <= b.right && cy >= b.top && cy <= b.bottom)
        .sort((a, b) => area(a.r) - area(b.r))[0];
      if (box && (r.left < box.r.left - 2 || r.right > box.r.right + 2)) {
        add("svg-out-of-box", t, `text ${Math.round(r.width)}px wide, its box ${Math.round(box.r.width)}px`);
      }
    }
    // A line or curve drawn through text: sample each stroke every 4 px in page
    // coordinates and test the points against the text boxes, shrunk so that an arrow
    // ending next to a label does not count.
    const strokes = [...svg.querySelectorAll("path, line, polyline")]
      .filter((p) => getComputedStyle(p).stroke !== "none" && !p.closest("marker, defs"));
    for (const p of strokes) {
      let len = 0;
      try { len = p.getTotalLength(); } catch (e) { continue; }
      const m = p.getScreenCTM();
      if (!m || !len) continue;
      const hit = new Set();
      for (let d = 0; d <= len; d += 4) {
        const q = p.getPointAtLength(d);
        const pt = new DOMPoint(q.x, q.y).matrixTransform(m);
        texts.forEach(({ t, r }, k) => {
          if (pt.x > r.left + 3 && pt.x < r.right - 3 && pt.y > r.top + 3 && pt.y < r.bottom - 3) hit.add(k);
        });
      }
      for (const k of hit) add("svg-line-through-text", texts[k].t, "a line or arrow is drawn through this text");
    }
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        const a = texts[i].r, b = texts[j].r;
        const ov = inter(a, b);
        if (ov > 0.2 * Math.min(area(a), area(b))) {
          add("svg-overlap", texts[i].t, `overlaps «${label(texts[j].t)}»`);
        }
      }
    }
  }
  return JSON.stringify(out);
})()
