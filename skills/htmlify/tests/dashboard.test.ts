import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { renderDashboard, writeDashboard } from "../src/renderDashboard.ts";
import { OUTPUT_DIR } from "../src/output.ts";

let TMP: string;

beforeEach(() => {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), "htmlify-dashboard-"));
});
afterEach(() => {
  fs.rmSync(TMP, { recursive: true, force: true });
});

describe("renderDashboard", () => {
  test("empty dir shows 'no companions yet'", () => {
    const html = renderDashboard(TMP, "companion.css");
    expect(html).toContain("No companions yet");
  });

  test("lists artifacts sorted by mtime desc", () => {
    // Three MDs with different mtimes
    fs.writeFileSync(
      path.join(TMP, "older.md"),
      `---\ntype: design-doc\ntitle: Older\nstatus: APPROVED\n---\n`
    );
    fs.writeFileSync(
      path.join(TMP, "newer.md"),
      `---\ntype: plan\ntitle: Newer\nstatus: DRAFT\n---\n`
    );
    fs.writeFileSync(
      path.join(TMP, "middle.md"),
      `---\ntype: design-doc\ntitle: Middle\nstatus: SHIPPED\n---\n`
    );
    // Set mtimes explicitly so order is deterministic
    const t0 = new Date(2026, 0, 1).getTime() / 1000;
    fs.utimesSync(path.join(TMP, "older.md"), t0, t0);
    fs.utimesSync(path.join(TMP, "middle.md"), t0 + 100, t0 + 100);
    fs.utimesSync(path.join(TMP, "newer.md"), t0 + 200, t0 + 200);

    const html = renderDashboard(TMP, "companion.css");
    expect(html).toContain("Older");
    expect(html).toContain("Middle");
    expect(html).toContain("Newer");
    // Newer must appear before Older
    const newerIdx = html.indexOf("Newer");
    const olderIdx = html.indexOf("Older");
    expect(newerIdx).toBeGreaterThan(0);
    expect(olderIdx).toBeGreaterThan(0);
    expect(newerIdx).toBeLessThan(olderIdx);
  });

  test("dashboard skips broken MD files silently", () => {
    fs.writeFileSync(
      path.join(TMP, "good.md"),
      `---\ntype: design-doc\ntitle: Good\n---\n`
    );
    // Broken: malformed YAML
    fs.writeFileSync(path.join(TMP, "broken.md"), `---\nthis is: not [valid yaml\n---\n`);
    const html = renderDashboard(TMP, "companion.css");
    expect(html).toContain("Good");
    // Broken file should be skipped silently — no crash, no broken entry
  });

  test("renders source-MD link relative path", () => {
    fs.writeFileSync(
      path.join(TMP, "x.md"),
      `---\ntype: design-doc\ntitle: X\n---\n`
    );
    const html = renderDashboard(TMP, "companion.css");
    expect(html).toContain(`href="../x.md"`);
    expect(html).toContain(`href="x.html"`); // companion is in same dir as index
  });

  test("generic artifacts also appear", () => {
    fs.writeFileSync(path.join(TMP, "plain.md"), `# Plain MD without frontmatter`);
    const html = renderDashboard(TMP, "companion.css");
    expect(html).toContain("plain");
    expect(html).toContain("type-generic");
  });

  test("escapes title with HTML entities", () => {
    fs.writeFileSync(
      path.join(TMP, "x.md"),
      `---\ntype: design-doc\ntitle: "<script>alert(1)</script>"\n---\n`
    );
    const html = renderDashboard(TMP, "companion.css");
    // The shell legitimately includes inline scripts for theme handling;
    // assert that the user-supplied payload appears escaped, never as an
    // executable tag.
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
  });
});

describe("writeDashboard", () => {
  test("writes index.html to .superpowers-html/", () => {
    fs.writeFileSync(
      path.join(TMP, "x.md"),
      `---\ntype: design-doc\ntitle: X\n---\n`
    );
    const indexPath = writeDashboard(TMP, "companion.css");
    expect(indexPath).toBe(path.join(TMP, OUTPUT_DIR, "index.html"));
    expect(fs.existsSync(indexPath)).toBe(true);
  });
});
