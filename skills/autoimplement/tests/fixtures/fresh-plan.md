# fresh-plan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** A deliberately fresh fixture for testing autoimplement's active pre-flight review chain (Step 6b). This plan starts WITHOUT a pre-flight marker in its commit history — so autoimplement's Check 6a should trigger pre-flight on first invocation. After pre-flight commits its sentinel marker, subsequent runs should skip pre-flight via Check 6a.

**Architecture:** Two phases, each appends a line to `skills/autoimplement/tests/fixtures/fresh-sample.txt` and commits. Same structural pattern as tiny-plan.md but a different file pair so the two fixtures can coexist without interfering with each other's review-history state.

**Tech Stack:** Bash + a tracked text file.

**Idempotency:** Verify steps use `grep -q` (presence check, same fix as tiny-plan.md v2.13.2). Safe to re-run on a branch that already ran it once.

---

## Phase 1: Append "alpha"

### Task 1.1: Append and commit

**Files:**
- Modify: `skills/autoimplement/tests/fixtures/fresh-sample.txt`

- [ ] **Step 1: Append the line**

```bash
echo "alpha" >> skills/autoimplement/tests/fixtures/fresh-sample.txt
```

- [ ] **Step 2: Verify (idempotent — presence-check, not count)**

```bash
grep -q '^alpha$' skills/autoimplement/tests/fixtures/fresh-sample.txt && echo "alpha present"
```

Expected: `alpha present`

- [ ] **Step 3: Commit**

```bash
git add skills/autoimplement/tests/fixtures/fresh-sample.txt
git commit -m "test(autoimplement): fresh-plan phase 1 (preflight fixture)"
```

---

## Phase 2: Append "beta"

### Task 2.1: Append and commit

**Files:**
- Modify: `skills/autoimplement/tests/fixtures/fresh-sample.txt`

- [ ] **Step 1: Append the line**

```bash
echo "beta" >> skills/autoimplement/tests/fixtures/fresh-sample.txt
```

- [ ] **Step 2: Verify (idempotent — presence-check, not count)**

```bash
grep -q '^beta$' skills/autoimplement/tests/fixtures/fresh-sample.txt && echo "beta present"
```

Expected: `beta present`

- [ ] **Step 3: Commit**

```bash
git add skills/autoimplement/tests/fixtures/fresh-sample.txt
git commit -m "test(autoimplement): fresh-plan phase 2 (preflight fixture)"
```
