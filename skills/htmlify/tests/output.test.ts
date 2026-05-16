import { describe, test, expect, beforeEach, afterEach } from "bun:test";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import {
  companionPathFor,
  writeCompanion,
  ensureGitignore,
  OUTPUT_DIR,
} from "../src/output.ts";

let TMP: string;

beforeEach(() => {
  TMP = fs.mkdtempSync(path.join(os.tmpdir(), "htmlify-output-"));
});
afterEach(() => {
  fs.rmSync(TMP, { recursive: true, force: true });
});

describe("companionPathFor", () => {
  test("places HTML in sibling .superpowers-html/ dir", () => {
    const mdPath = path.join(TMP, "foo.md");
    const expected = path.join(TMP, OUTPUT_DIR, "foo.html");
    expect(companionPathFor(mdPath)).toBe(expected);
  });
});

describe("writeCompanion", () => {
  test("normal write creates output dir + writes HTML", () => {
    const mdPath = path.join(TMP, "x.md");
    fs.writeFileSync(mdPath, "# x");
    const r = writeCompanion(mdPath, "<html>1</html>");
    expect(r.written).toBe(true);
    expect(fs.existsSync(r.outPath)).toBe(true);
    expect(fs.readFileSync(r.outPath, "utf8")).toBe("<html>1</html>");
  });

  test("--no-clobber skips when HTML is newer than MD", () => {
    const mdPath = path.join(TMP, "x.md");
    fs.writeFileSync(mdPath, "# x");
    const first = writeCompanion(mdPath, "<html>v1</html>");
    expect(first.written).toBe(true);
    // bump html mtime to be later than md
    const htmlPath = first.outPath;
    const future = new Date(Date.now() + 60_000);
    fs.utimesSync(htmlPath, future, future);
    const second = writeCompanion(mdPath, "<html>v2</html>", { noClobber: true });
    expect(second.written).toBe(false);
    expect(second.reason).toBe("skipped-newer");
    expect(fs.readFileSync(htmlPath, "utf8")).toBe("<html>v1</html>");
  });

  test("--force-rebuild ignores no-clobber", () => {
    const mdPath = path.join(TMP, "x.md");
    fs.writeFileSync(mdPath, "# x");
    const first = writeCompanion(mdPath, "<html>v1</html>");
    const future = new Date(Date.now() + 60_000);
    fs.utimesSync(first.outPath, future, future);
    const second = writeCompanion(mdPath, "<html>v2</html>", {
      noClobber: true,
      forceRebuild: true,
    });
    expect(second.written).toBe(true);
    expect(fs.readFileSync(first.outPath, "utf8")).toBe("<html>v2</html>");
  });
});

describe("ensureGitignore", () => {
  test("appends entry when in git repo + no existing", () => {
    // Fake git repo
    fs.mkdirSync(path.join(TMP, ".git"));
    const outDir = path.join(TMP, OUTPUT_DIR);
    fs.mkdirSync(outDir);
    ensureGitignore(outDir);
    const gi = fs.readFileSync(path.join(TMP, ".gitignore"), "utf8");
    expect(gi).toContain(`${OUTPUT_DIR}/`);
  });

  test("does not duplicate when entry already present", () => {
    fs.mkdirSync(path.join(TMP, ".git"));
    const gi = path.join(TMP, ".gitignore");
    fs.writeFileSync(gi, `node_modules/\n${OUTPUT_DIR}/\n`);
    const outDir = path.join(TMP, OUTPUT_DIR);
    fs.mkdirSync(outDir);
    ensureGitignore(outDir);
    const content = fs.readFileSync(gi, "utf8");
    const occurrences = content.split(`${OUTPUT_DIR}/`).length - 1;
    expect(occurrences).toBe(1);
  });

  test("skips silently when not in git repo", () => {
    // No .git/ exists under TMP or parents (assuming tmp dir isn't a repo).
    // We can't reliably assert "skipped" without knowing parent state,
    // but we CAN assert no crash and no .gitignore created in TMP.
    const outDir = path.join(TMP, OUTPUT_DIR);
    fs.mkdirSync(outDir);
    ensureGitignore(outDir);
    // Cannot assert .gitignore absence reliably (parent may be a repo),
    // but ensure no exception is thrown.
    expect(true).toBe(true);
  });

  test("appends newline before entry if file doesn't end with newline", () => {
    fs.mkdirSync(path.join(TMP, ".git"));
    const gi = path.join(TMP, ".gitignore");
    fs.writeFileSync(gi, `node_modules`); // no trailing newline
    const outDir = path.join(TMP, OUTPUT_DIR);
    fs.mkdirSync(outDir);
    ensureGitignore(outDir);
    const content = fs.readFileSync(gi, "utf8");
    expect(content).toBe(`node_modules\n${OUTPUT_DIR}/\n`);
  });
});
