---
description: Root cause of a failing test (no shell in this environment)
tags: [process]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep, TodoWrite]
---

En av testene i dette prosjektet feiler. Slik så kjøringen ut:

```
$ python3 -m unittest
..F
======================================================================
FAIL: test_unsorted (test_stats.MedianTest.test_unsorted)
----------------------------------------------------------------------
AssertionError: 1 != 5
----------------------------------------------------------------------
Ran 3 tests in 0.000s

FAILED (failures=1)
```

Fiks det, og si i svaret hva rotårsaken var. Du har ikke skall i dette miljøet. Jobb selvstendig, det er ingen som kan svare på spørsmål underveis.
