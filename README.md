# FastAPI Authentication System Architecture

## Project Goal

Build a clean, beginner-friendly, production-style FastAPI authentication system using PostgreSQL, SQLAlchemy, and JWT.

The objective is to learn the architecture while following industry best practices.

---

# Project Structure

myproject/

    app/

        main.py

        core/

            config.py

            security.py

        db/

            base.py

            session.py

        models/

            user.py

        schemas/

            user.py

            token.py

        crud/

            user.py

        api/

            deps.py

            routes/

                auth.py

                users.py

---

# Architecture Rules

Every folder has only ONE responsibility.

## core/

Contains application configuration.

config.py

- Read .env
- Load environment variables
- Application settings

security.py

- Hash Password
- Verify Password
- Create JWT
- Decode JWT

No SQLAlchemy code.

No Routes.

No CRUD.

---

## db/

Contains database configuration only.

session.py

Responsibilities

- Create Engine
- Create SessionLocal
- get_db()

base.py

Responsibilities

- Create DeclarativeBase

No Models.

No CRUD.

No API.

---

## models/

Contains SQLAlchemy Models.

One file = One table.

Example

User

Product

Order

Each model inherits from Base.

Models should never contain business logic.

---

## schemas/

Contains Pydantic Models.

Used for

Request Validation

Response Serialization

Never store passwords in Response Schemas.

Schemas should never inherit from SQLAlchemy Base.

---

## crud/

Contains database logic.

Examples

create_user()

get_user_by_email()

get_user_by_id()

update_user()

delete_user()

CRUD should only communicate with SQLAlchemy Session and Models.

CRUD should never return HTTP responses.

CRUD should never contain Route decorators.

---

## api/routes/

Contains API endpoints.

Responsibilities

- Receive Request
- Validate Schema
- Call CRUD
- Return Response

Routes should never directly write SQL.

---

## api/deps.py

Contains reusable dependencies.

Examples

get_current_user()

get_current_active_user()

get_db()

---

# Request Flow

Client

↓

Route

↓

Schema

↓

CRUD

↓

SQLAlchemy Session

↓

Database

↓

CRUD

↓

Schema

↓

Client

---

# Authentication Flow

Registration

Client

↓

POST /register

↓

UserRegister Schema

↓

Hash Password

↓

CRUD

↓

Database

↓

UserResponse

↓

Client

---

Login

Client

↓

POST /login

↓

UserLogin

↓

Verify Password

↓

Create JWT

↓

Token Schema

↓

Client

---

Protected Route

Client

↓

Authorization Header

↓

JWT

↓

Decode JWT

↓

Current User

↓

Route

↓

Response

---

# Database Rules

Use SQLAlchemy 2.0 style.

Use

Mapped

mapped_column

DeclarativeBase

Do NOT use deprecated SQLAlchemy syntax.

---

# Password Rules

Never store plain text passwords.

Always hash passwords using bcrypt.

Always verify passwords using Passlib.

---

# JWT Rules

Access Token only.

No Refresh Token.

Algorithm

HS256

Expiration

30 Minutes

---

# Dependency Rules

Routes

↓

CRUD

↓

Models

↓

Session

↓

Engine

↓

Database

Never reverse this dependency.

Models should not import CRUD.

CRUD should not import Routes.

Schemas should not import Routes.

---

# Code Style

Use

Type hints

Docstrings where appropriate

Clear variable names

One responsibility per file

Explain code with comments where useful.

Avoid unnecessary complexity.

Keep the implementation beginner-friendly while following professional architecture.
