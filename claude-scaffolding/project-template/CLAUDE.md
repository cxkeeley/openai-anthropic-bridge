# [Project Name] — Project Context

> Copy this file to the root of your project as `CLAUDE.md` and fill in each section.
> The global CLAUDE.md (from the toolkit) defines Claude's role and rules.
> This file provides the project-specific context Claude needs to work effectively.

## Project Overview

<!-- What does this project do? What problem does it solve? Who uses it? -->

## Tech Stack

<!-- List the primary technologies, frameworks, and tools used -->
- **Language**: e.g., Python 3.12, TypeScript 5.x
- **Backend**: e.g., FastAPI, Django, Express, Gin
- **Frontend**: e.g., React, Next.js, Vue, SvelteKit
- **Database**: e.g., PostgreSQL, MySQL, SQLite, MongoDB
- **Infrastructure**: e.g., Docker, Kubernetes, AWS, Railway

## Project Structure

```
/                    ← Project root
├── src/             ← Main source code
├── tests/           ← Test files
├── docs/            ← Documentation
└── ...
```

<!-- Add any non-obvious structural decisions here -->

## Development Commands

```bash
# Install dependencies
<command>

# Run development server
<command>

# Run tests (affected only)
<command>

# Run full test suite
<command>

# Lint / format
<command>

# Build for production
<command>
```

## Key Conventions

<!-- Project-specific patterns Claude must follow -->

### Naming Conventions
<!-- e.g., snake_case for Python, camelCase for JS, kebab-case for files -->

### API Design
<!-- e.g., REST with RFC 9457 error format, versioned at /v1/, auth via Bearer token -->

### Database
<!-- e.g., Alembic migrations, always use transactions, no raw SQL in views -->

### Testing
<!-- e.g., pytest with fixtures in conftest.py, factory_boy for model factories -->

## Environment Variables

<!-- List the key env vars and where they come from -->
| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | JWT signing key | Yes |

## Integration Verification

<!-- Define what to check after significant changes -->
<!-- Claude uses this during /implement and /verify skills -->

**Triggers**: Changes to `docker-compose.yml`, `Dockerfile`, `alembic/`, or `requirements*.txt`

```bash
# Check containers are healthy
docker compose ps

# Check migrations are current
# <migration command>

# Hit health endpoint
curl -f http://localhost:8000/health
```

## Notes for Claude

<!-- Anything else Claude needs to know about this project -->
<!-- e.g., "The frontend lives in a separate repo", "We use a monorepo", -->
<!-- "Always check the OpenAPI spec before modifying endpoints" -->
