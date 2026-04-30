---
name: refactor
description: Safe, incremental refactoring with zero regression tolerance
argument-hint: "[file, module, or description of what to refactor]"
user-invocable: true
---

# Safe Refactoring

Refactor code without breaking anything. This skill enforces a strict "lock behavior first, change structure second" workflow.

## Input

Target to refactor: `$ARGUMENTS`
If no argument is given, ask the user what they want to refactor.

## The Iron Law

```
DO NOT CHANGE BEHAVIOR AND STRUCTURE AT THE SAME TIME.
```

Every refactoring step changes structure only. Behavior is locked by tests before the first line of production code changes.

---

## Phase 1: Understand What You're Refactoring

1. **Read everything** — read the target file(s) and all files that import/use the target
2. **Understand the current behavior** — document what the code does, not what it's supposed to do
3. **Identify the problem** — why is this being refactored? (readability, duplication, performance, new requirement, language migration)
4. **Define the end state** — what will the code look like when done?

Present your understanding to the Lead Dev. Confirm before proceeding.

---

## Phase 2: Write Characterization Tests

Before changing anything, write tests that document the current behavior:

1. For each public function/endpoint/method in scope:
   - Write a test with realistic input
   - Assert the exact current output (even if it's "wrong")
   - These tests define what must NOT change

2. Run all characterization tests — they must ALL pass now (before any refactoring)

3. Commit the tests:
   ```bash
   ~/.claude/bin/git-commit.sh "test: add characterization tests before refactor of [target]"
   ```

> These tests are your safety net. If any fail during refactoring, you broke behavior.

---

## Phase 3: Refactoring Plan

Create a numbered plan of small, self-contained steps. Each step must:
- Change structure only (not behavior)
- Leave all characterization tests passing
- Be committed separately

**STOP HERE.** Present the plan. Wait for Lead Dev approval.

---

## Phase 4: Execute (Step by Step)

For each step in the plan:

1. **Make the structural change** — rename, extract, consolidate, simplify
2. **Run ALL tests** (characterization + existing test suite):
   ```bash
   ~/.claude/bin/project-test.sh -v
   ```
3. **All tests must pass** — if any fail:
   - STOP
   - Identify what behavior changed (not what structure changed)
   - Fix or revert
   - Do NOT proceed until green
4. **Commit the step**:
   ```bash
   ~/.claude/bin/git-commit.sh "refactor: [what was changed]"
   ```

---

## Phase 5: Final Review

After all steps are complete:

1. Run the full test suite one final time — must be 100% green
2. Run `/review --branch` on all refactoring changes:
   - Fix HIGH/CRITICAL findings
   - Flag MEDIUM for Lead Dev review
3. Clean up characterization tests if they are now covered by better tests (confirm with Lead Dev)

---

## Phase 6: Report

```markdown
## Refactor Complete: [Target]

**Problem solved:** [why this was refactored]
**What changed:** [structural changes made]
**What didn't change:** [behavior is identical]

### Steps taken
1. [Step] — [commit hash]
2. ...

### Test results
- Characterization tests: X/X passing ✅
- Full suite: X/X passing ✅

### Code health improvement
[Before/after: lines of code, duplication removed, complexity reduced]
```
