---
description: TDD discipline on a small new function (no shell in this environment)
tags: [process]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Skill, Read, Glob, Grep, TodoWrite]
---

Legg til en funksjon `slugify(text)` i en ny Python-modul `textutil.py` i denne mappen. Den skal gjøre om tekst til en URL-slug: små bokstaver, ord skilt med én bindestrek, tegnsetting fjernet, og æ, ø og å beholdt. Lag tester med `unittest` i `test_textutil.py`. Du har ikke skall i dette miljøet, så testene kan ikke kjøres her. Jobb selvstendig, det er ingen som kan svare på spørsmål underveis.
