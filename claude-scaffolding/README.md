# Claude Scaffolding Toolkit

A reusable Claude Code toolkit that configures Claude as a **Senior Software Engineer** under your lead as the **Lead Developer**.

## Philosophy

You define WHAT to build and WHY. Claude defines HOW — and always presents a plan before writing a single line of code.

### Four Layers

| Layer | What it is | Purpose |
|---|---|---|
| `CLAUDE.md` | Global identity & rules | Defines the Lead Dev / Senior SWE contract |
| `skills/` | Skill procedures | Step-by-step workflows for each dev task |
| `rules/` | Contextual standards | Architectural policies loaded automatically |
| `bin/` | Helper scripts | Safe git, tests, audits, hooks |

## Installation

```bash
git clone <this-repo> ~/projects/claude-scaffolding
cd ~/projects/claude-scaffolding
./install.sh
```

Restart Claude Code after installation.

## Per-Project Setup

For each new project:

```bash
cp ~/projects/claude-scaffolding/project-template/CLAUDE.md /path/to/your/project/CLAUDE.md
# Fill in the project-specific sections
```

## Skills

| Skill | Invocation | When to Use |
|---|---|---|
| Build | `/build <description>` | Build a new feature from scratch |
| Implement | `/implement <issue>` | Implement a GitHub issue (TDD + PR) |
| Debug | `/debug <description>` | Systematic root-cause debugging |
| Refactor | `/refactor [target]` | Safe, incremental refactoring |
| Rewrite | `/rewrite <target> in <lang>` | Rewrite in different language/framework |
| Review | `/review [--staged\|--branch\|--file]` | Code review |
| Test | `/test [--all\|--affected]` | Smart test runner |
| Audit | `/audit [env\|deps\|docker\|all]` | Project health audits |
| Security Audit | `/security-audit` | OWASP-guided security review |
| Cleanup | `/cleanup` | Post-PR branch cleanup |

## Rules (Auto-Loaded by Claude Code)

| Rule | What it Enforces |
|---|---|
| `error-handling.md` | Never swallow errors, RFC 9457 format, translate at boundaries |
| `api-design.md` | HTTP status codes, pagination, rate limiting |
| `data-integrity.md` | Transactions, idempotency, migration safety |
| `structured-logging.md` | Structured fields, no secrets in logs |
| `testing.md` | Real behavior over mocks, realistic fixtures |
| `code-review.md` | No performative agreement, push back when right |
| `documentation.md` | Purpose-first docs |

## Safety Hooks (Always Active)

- **`hook-auto-approve-bash.sh`**: Auto-approves safe compound commands (`&&` chains, pipes, redirects to `/tmp/`) that permission matching would otherwise block.
- **`hook-block-destructive.sh`**: Blocks dangerous operations — `rm -rf /`, `git push --force`, `DROP TABLE`, `git reset --hard`, and more.
- **`hook-post-edit-lint.sh`**: Runs `ruff` on Python files after edits (advisory, non-blocking).

## Structure

```
claude-scaffolding/
├── CLAUDE.md                          ← Global identity + rules → ~/.claude/CLAUDE.md
├── settings.json                      ← Permissions + hooks → ~/.claude/settings.json
├── install.sh                         ← Installer
├── project-template/
│   └── CLAUDE.md                      ← Per-project template
├── skills/
│   ├── build/SKILL.md
│   ├── implement/SKILL.md
│   ├── debug/SKILL.md
│   ├── refactor/SKILL.md
│   ├── rewrite/SKILL.md
│   ├── review/SKILL.md
│   ├── test/SKILL.md
│   ├── audit/SKILL.md
│   ├── security-audit/SKILL.md
│   └── cleanup/SKILL.md
├── rules/
│   ├── error-handling.md
│   ├── api-design.md
│   ├── data-integrity.md
│   ├── structured-logging.md
│   ├── testing.md
│   ├── code-review.md
│   └── documentation.md
└── bin/
    ├── hook-auto-approve-bash.sh
    ├── hook-block-destructive.sh
    ├── hook-post-edit-lint.sh
    ├── git-commit.sh
    ├── git-cleanup-merged-branch.sh
    ├── git-find-base-branch
    ├── git-push-pr-merge.sh
    ├── project-test.sh
    ├── venv-run.sh
    ├── smoke-test.sh
    ├── env-audit.sh
    ├── deps-audit.sh
    ├── docker-health-check.sh
    ├── docker-audit.sh
    ├── secret-scan.sh
    └── security-headers-check.sh
```
