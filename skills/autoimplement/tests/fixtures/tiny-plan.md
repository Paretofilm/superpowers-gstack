# tiny-plan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Verify autoimplement orchestration end-to-end. Two phases, each appends one line to `skills/autoimplement/tests/fixtures/sample.txt` and commits.

**Architecture:** Trivial. Each phase has one task that runs `echo ... >> sample.txt && git add && git commit`. Exercises the real commit + review chain — not a /tmp fake.

**Tech Stack:** Bash + a tracked text file.

---

## Phase 1: Append "phase1"

### Task 1.1: Append and commit

**Files:**
- Modify: `skills/autoimplement/tests/fixtures/sample.txt`

- [ ] **Step 1: Append the line**

```bash
echo "phase1" >> skills/autoimplement/tests/fixtures/sample.txt
```

- [ ] **Step 2: Verify**

```bash
grep -c '^phase1$' skills/autoimplement/tests/fixtures/sample.txt
```

Expected: `1`

- [ ] **Step 3: Commit**

```bash
git add skills/autoimplement/tests/fixtures/sample.txt
git commit -m "test(autoimplement): tiny-plan phase 1 (e2e fixture)"
```

---

## Phase 2: Append "phase2"

### Task 2.1: Append and commit

**Files:**
- Modify: `skills/autoimplement/tests/fixtures/sample.txt`

- [ ] **Step 1: Append the line**

```bash
echo "phase2" >> skills/autoimplement/tests/fixtures/sample.txt
```

- [ ] **Step 2: Verify**

```bash
grep -c '^phase2$' skills/autoimplement/tests/fixtures/sample.txt
```

Expected: `1`

- [ ] **Step 3: Commit**

```bash
git add skills/autoimplement/tests/fixtures/sample.txt
git commit -m "test(autoimplement): tiny-plan phase 2 (e2e fixture)"
```
