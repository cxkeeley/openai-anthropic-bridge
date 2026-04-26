---
name: feedback
description: User feedback and preferences
type: feedback
---

**Rule**: Don't add error handling or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs).

**Why:** The user prefers clean, minimal code without unnecessary validation. This helps me write more concise, production-ready code.

**How to apply:** Only add error handling for actual failure cases (user input, external API calls). Don't add validation for internal state that can't be corrupted by the code itself.

**Rule**: Prefer one bundled PR over many small ones for refactors.

**Why:** The user has confirmed that bundled PRs are the right approach for refactors.

**How to apply:** For refactors, create one PR with all changes rather than splitting into multiple small PRs.
