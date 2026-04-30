---
name: rewrite
description: Rewrite a module, service, or component in a different language or framework
argument-hint: "<target> in <language/framework>"
user-invocable: true
---

# Rewrite in Different Language or Framework

Port or rewrite a module, service, or component into a new language or framework while ensuring feature parity.

## Input

The user provides: `$ARGUMENTS` (e.g., "auth module in Go", "API in FastAPI", "frontend in Next.js")

## The Contract

A rewrite is a high-risk operation. You MUST:
1. Build a complete feature specification before writing any new code
2. Get Lead Dev approval on the spec and migration strategy
3. Verify feature parity before declaring done

---

## Phase 1: Map the Existing System

Read and document the existing implementation thoroughly:

1. **Entry points** — what functions, endpoints, or components are public API?
2. **Behavior spec** — for each entry point, document:
   - Input types and validation rules
   - Business logic and transformations
   - Output format (return values, side effects, events emitted)
   - Error cases and how they're handled
   - Edge cases (empty inputs, nulls, concurrency)
3. **Dependencies** — what external systems does this call? (databases, APIs, queues)
4. **Existing tests** — what tests exist? They define the behavioral contract.
5. **Known issues** — any bugs or limitations in the current implementation that the rewrite should fix (or deliberately preserve)?

Produce a **Feature Specification**:
```markdown
## Feature Specification: [Module Name]

### Public API
| Endpoint/Function | Input | Output | Errors |
|---|---|---|---|

### Business Rules
1. [Rule description]
2. ...

### External Dependencies
- [System]: [how it's used]

### Known Issues to Fix in Rewrite
- [Issue]: [how it should behave in the new version]

### Out of Scope
- [Explicitly what this rewrite does NOT include]
```

**STOP HERE.** Present the spec. Get Lead Dev approval before Phase 2.

---

## Phase 2: Migration Strategy

Design how the cutover will work:

1. **Build strategy**: Strangler Fig (gradual) vs. Big Bang (all at once)?
   - Strangler Fig: run old and new side-by-side, migrate traffic incrementally
   - Big Bang: build complete replacement, switch over in one step

2. **Compatibility layer**: Does anything need to call both old and new during transition?

3. **Data migration**: Any schema changes needed? How will data be migrated?

4. **Rollback plan**: If the new version has a critical bug in production, how do we revert?

Present the strategy. Get Lead Dev approval before Phase 3.

---

## Phase 3: Build the New Implementation

With approved spec and strategy, build the new version:

1. Set up the new project/module structure in the target language/framework
2. Implement each feature from the spec, one at a time:
   - Write a test that verifies spec compliance
   - Implement until the test passes
   - Commit: `~/.claude/bin/git-commit.sh "feat: implement [feature] in [lang]"`
3. Follow the target language's idioms and conventions — do not port old patterns blindly
4. Implement the agreed migration/compatibility strategy

---

## Phase 4: Feature Parity Verification

For every item in the Feature Specification, provide evidence of parity:

| Spec Item | Old Behavior | New Behavior | Evidence |
|---|---|---|---|
| POST /users returns 201 | ✅ | ✅ | `test_create_user` passes |
| Validates email format | ✅ | ✅ | `test_invalid_email` passes |
| Returns 409 on duplicate | ✅ | ✅ | `test_duplicate_user` passes |

Any gaps must be discussed with the Lead Dev before proceeding.

---

## Phase 5: Migration Execution

Execute the agreed migration strategy:

1. If Strangler Fig: route a portion of traffic, monitor, expand
2. If Big Bang: final end-to-end test, then switch
3. Monitor logs and error rates after cutover
4. Keep old code available for rollback until stability is confirmed

---

## Phase 6: Report

```markdown
## Rewrite Complete: [Module] → [Target Language/Framework]

**Scope:** [what was rewritten]
**Strategy:** [Strangler Fig / Big Bang]
**Migration status:** [complete / in progress]

### Feature Parity
- Total spec items: X
- Verified: X ✅
- Gaps: X ⚠️ (list them)

### What improved in the rewrite
- [Performance, maintainability, correctness improvements]

### Rollback procedure
[How to revert if needed]
```
