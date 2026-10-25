---
type: llm
focus: last_message
---

PASS if the final reply states that the root cause is that `median` never sorts its input (it indexes the list as given), and says the fix sorts the values (a copy or in place) before picking the middle.
FAIL if the reply names a different cause, blames the test, or does not say what the cause was.
