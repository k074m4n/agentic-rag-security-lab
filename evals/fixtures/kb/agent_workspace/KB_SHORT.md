# Short Knowledge Base

_This is an automatically generated compressed summary of the full KB index. For full details, see KB_INDEX.md._


## Table of Contents
- [sub_agent_0/OVERVIEW.md](#sub-agent-0-overview-md)
- [sub_agent_1/ARCHITECTURE.md](#sub-agent-1-architecture-md)
- [sub_agent_2/API_REFERENCE.md](#sub-agent-2-api-reference-md)
- [sub_agent_3/DATA_MODELS.md](#sub-agent-3-data-models-md)
- [sub_agent_4/BUILD_AND_TOOLING.md](#sub-agent-4-build-and-tooling-md)
- [sub_agent_5/TESTING_AND_QA.md](#sub-agent-5-testing-and-qa-md)
---
---

## sub_agent_0/OVERVIEW.md
<a id='sub-agent-0-overview-md'></a>

## Table of Contents
- [Project purpose and high‑level description](#project-purpose-and-high-level-description)
- [Main entry points and how to start the app](#main-entry-points-and-how-to-start-the-app)
- [Top‑level directory overview](#top-level-directory-overview)
- [Getting started](#getting-started)
---

## Project purpose and high‑level description
**Tasky** is a tiny Todo‑list HTTP API built with **Flask** and **SQLite**.  It provides a RESTful interface for creating, reading, updating and deleting todo items.  The API is intentionally lightweight, making it a good reference implementation for learning Flask, Blueprint organization, and simple SQLite persistence.
---

## Main entry points and how the application is started
The application is created by the factory function `create_app` defined in `app/__init__.py`:
```python
from flask import Flask
from .config import Config
from .db import close_db, init_db
from .routes import bp
def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.register_blueprint(bp, url_prefix="/api/v1")

## Top‑level directory overview
```
.
├── README.md            # Project description, usage, and endpoints
├── requirements.txt    # Python dependencies
├── docs/
│   └── DEPLOYMENT.md   # Production deployment notes
├── app/                # Core application package
│   ├── __init__.py      # Flask app factory
│   ├── auth.py          # Token‑based authentication decorator
│   ├── config.py        # Configuration defaults (e.g., PAGE_SIZE)

## Getting started
1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Set the API token** (required for write operations)
   ```bash
   export TASKY_API_TOKEN=change-me
   ```
3. **Run the development server**
   ```bash

## sub_agent_1/ARCHITECTURE.md
<a id='sub-agent-1-architecture-md'></a>

## Table of Contents
- [High-level Architecture](#high-level-architecture)
- [Core Modules & Responsibilities](#core-modules--responsibilities)
- [Dependency Flow](#dependency-flow)
- [External Services & Integrations](#external-services--integrations)
---

## High-level Architecture
The project is a **Flask‑based HTTP API** that provides a simple Todo list service.  It follows a classic **single‑page Flask application** structure with:
- **Application factory** (`app/__init__.py`) that creates the Flask app, registers a Blueprint, and initializes the SQLite database.
- **Blueprint** (`app/routes.py`) that defines the REST endpoints for CRUD operations on Todo items.
- **Database layer** (`app/db.py`) that manages a request‑scoped SQLite connection.
- **Domain model** (`app/models.py`) representing a Todo as a dataclass.
- **Authentication** (`app/auth.py`) and **utility helpers** (`app/utils.py`).
The system can be visualised as:
```
[Flask App] --> [Blueprint (routes)] --> [Auth] & [Validation]
                     |

## Core Modules / Packages and Their Responsibilities
| Module | Purpose |
|--------|---------|
| `app/__init__.py` | Application factory (`create_app`). Sets configuration, registers the `todos` Blueprint, and ensures the DB schema is created on startup. |
| `app/config.py` | Holds configuration values (database path, API token, pagination defaults). Provides a `TestConfig` for the test suite. |
| `app/db.py` | Provides `get_db`, `close_db`, and `init_db`. Manages a per‑request SQLite connection stored in Flask's `g` context. |
| `app/models.py` | Defines the `Todo` dataclass with helpers to convert from SQLite rows and to dictionaries for JSON responses. |
| `app/routes.py` | Implements the REST API (list, retrieve, create, update, delete). Uses the Blueprint `bp` and registers error handling for validation errors. |
| `app/auth.py` | Contains the `require_token` decorator that checks the request's `Authorization` header against the configured API token. |
| `app/utils.py` | Validation utilities (`validate_title`, `parse_page`) and a custom `ValidationError` exception used across the routes. |
---

## Dependency Flow
1. **Application start** – `create_app` loads configuration, registers the Blueprint, and calls `init_db`.
2. **Incoming request** – Flask routes the request to the appropriate view function in `routes.py`.
3. **Authentication** – For mutating endpoints (`POST`, `PATCH`, `DELETE`), the `@require_token` decorator validates the API token.
4. **Validation** – Request payloads are validated via helpers in `utils.py`. Validation errors raise `ValidationError`, caught by the Blueprint error handler.
5. **Database interaction** – View functions call `get_db()` (from `db.py`) to obtain a request‑scoped SQLite connection, execute SQL statements, and commit changes.
6. **Domain conversion** – Rows returned from SQLite are transformed into `Todo` objects (`models.Todo.from_row`) and then to plain dictionaries for JSON serialization.
7. **Response** – Flask returns JSON responses (or status codes) back to the client.
---

## External Services & Integrations
- **SQLite** – The only external data store, accessed via the standard library `sqlite3` module. The database file path is configurable via `Config.DATABASE_PATH`.
- **Environment variables** – `TASKY_DATABASE_PATH` and `TASKY_API_TOKEN` allow external configuration without code changes.
- **HTTP client** – Not part of the codebase, but the API is intended to be consumed over HTTP (e.g., `curl`, Postman, or any HTTP client).
---
*This architecture is intentionally lightweight, suitable for small‑scale deployments or as a teaching example of a Flask‑based CRUD API.*
---


...

(Truncated for brevity. See KB_INDEX.md for full details.)
## sub_agent_2/API_REFERENCE.md

