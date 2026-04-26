---
name: karpathy-guidelines
description: 5 coding principles for quality work — think before code, simplicity, surgical edits, goal-oriented execution, full-scope tracing.
---

# Karpathy Coding Guidelines

Principles based on Andrey Karpathy's observations about typical LLM mistakes when writing code. These rules are MANDATORY when working with the project codebase.

---

## 1. Think Before You Code

Explicitly state your assumptions, propose multiple interpretations for ambiguous tasks, and stop when something is unclear.

- **State assumptions explicitly** — before starting, list what you assume. If unsure — ask, don't guess
- **Propose multiple interpretations** — if a task is ambiguous, show 2–3 ways to understand it and ask which is correct
- **Push back when needed** — if there's a simpler solution or the request conflicts with architecture, say so
- **Stop when confused** — name exactly what's unclear and request clarification. Don't continue hoping "it'll be fine"

**Test:** If you're making an assumption you haven't stated — you're violating this rule.

---

## 2. Simplicity Above All

Minimum code to solve the task. No abstractions for one-time use and no "future-proofing" features.

- No features beyond what was requested
- No abstractions for code used only once
- No "flexibility", "configurability" or "extensibility" that wasn't asked for
- No error handling for impossible scenarios
- If 200 lines can be replaced with 50 — rewrite

**Test:** Would a senior developer say this is over-engineered? If yes — simplify.

---

## 3. Surgical Edits

Change only what was requested. Don't touch neighboring code and don't delete existing dead code without being asked.

When editing existing code:
- **Don't "improve"** neighboring code, comments, or formatting
- **Don't refactor** what isn't broken
- **Don't delete** dead code that existed before you — if you notice it, mention it but don't touch it
- **Follow existing style**, even if you'd write it differently

When your changes create "orphans":
- Delete imports/variables/functions that YOUR changes made unused
- Don't delete previously existing dead code without explicit request

**Test:** Every changed line must directly follow from the user's request.

---

## 4. Goal-Oriented Execution

Instead of vague instructions, formulate the task as a specific goal with verification.

Instead of vague "fix the bug" → "write a test that reproduces the bug, then make it pass".

For each task:
1. **Define the goal** — what exactly should the outcome be
2. **Define success criteria** — how to verify the goal is achieved
3. **Create a plan with checks at each step:**

```
1. [Step] → check: [what to verify]
2. [Step] → check: [what to verify]
3. [Step] → check: [what to verify]
```

Examples of correct formulation:
- ❌ "Fix auth" → ✅ "Login with valid creds must return 200 + token, invalid — 401"
- ❌ "Optimize the query" → ✅ "Query to orders table must execute < 100ms on 10K records"
- ❌ "Fix the bug" → ✅ "Write a test reproducing the bug. Make it pass"

**Test:** Can you definitively say "done" or "not done"? If not — clarify criteria.

---

## 5. Full-Scope Tracing

Before making any change, trace the ENTIRE flow of the affected function across all related files: API handler → business logic → client-side JS → templates. Never change only one part of a feature without understanding the full chain.

- **Trace callers and callees** — before editing a function, find all places that call it and all functions it calls. Use grep/search across the entire codebase
- **Follow data flow end-to-end** — if changing a server response, check how the client parses and uses it. If changing client logic, check what the server expects
- **Check both sides of the contract** — API response format must match client parsing. DB schema must match ORM models. WS broadcast must match WS listener
- **Look at neighboring files in the same module** — when editing `scan_api.py`, also check `scan.html`, `workflow.py`, and any templates that consume the API
- **Verify side-effects** — if you change a timer value, check: where is it read? where is it validated? where is it displayed? where is it stored? Does the server enforce it independently of the client?

Common mistakes this rule prevents:
- Changing a server response field without updating client-side parsing
- Adding a UI timer without adding server-side cooldown enforcement
- Modifying a WS broadcast format without updating all WS listeners
- Changing model fields without updating all queries that use them

**Test:** Can you draw the full data flow from user action to database and back? If not — you haven't traced enough.

---

## When to Apply

These principles are mandatory for **any non-trivial work** with code:
- Adding new features
- Refactoring
- Bug fixing
- DB migrations
- Architecture changes

For trivial tasks (typos, obvious one-liners) — use common sense.

---

## Note

The goal is to reduce the number of expensive mistakes on complex tasks, not to slow down simple ones.
