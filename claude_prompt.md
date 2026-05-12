# Prompt for Claude to Build the Test Backend

Copy and paste the following prompt to Claude to test its capability in building a full backend from scratch.

---

**PROMPT:**

"Create a production-grade FastAPI backend in a new folder named `test_backend/`. The backend must implement a full user management system including registration, login with JWT authentication, and CRUD operations (Update, Delete) for the authenticated user.

**Technical Requirements:**
1. **Architecture**: Use a 1-layer architecture without any ORM (No SQLAlchemy, No Tortoise, etc.). Use raw SQL queries only.
2. **Database**: Use PostgreSQL. Use the `psycopg2-binary` or `asyncpg` library for connections.
3. **Database Credentials**:
   - Host: `localhost`
   - Port: `5432`
   - User: `admin`
   - Password: `secret`
   - Database: `postgres`
4. **Authentication**: Implement JWT-based authentication (HS256). Use `passlib` with `bcrypt` for password hashing and `python-jose` for JWT handling.
5. **API Endpoints**:
   - `POST /register`: Create a new user.
   - `POST /token`: Login and return a JWT token.
   - `GET /me`: Return the current user's profile.
   - `PUT /me`: Update the current user's profile (email, full name, password).
   - `DELETE /me`: Delete the current user's account.
6. **Validation**: Use Pydantic models for all request and response bodies.
7. **Initialization**: Include a script to initialize the `users` table on startup.
8. **Structure**: Organize the code logically (e.g., `app/main.py`, `app/database.py`, `app/auth.py`, `app/models.py`, `app/routes/users.py`).
9. **Documentation**: Provide a `requirements.txt` and a basic `README.md` in the `test_backend/` folder.

Please generate all necessary files and ensure they are saved inside the `test_backend/` directory."

---
