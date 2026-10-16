# Tasky

A small todo-list HTTP API built with Flask and SQLite.

## Getting started

```bash
pip install -r requirements.txt
export TASKY_API_TOKEN=change-me
flask --app "app:create_app()" run
```

## Endpoints

| Method | Path                   | Auth  |
|--------|------------------------|-------|
| GET    | /api/v1/todos?page=N   | no    |
| GET    | /api/v1/todos/<id>     | no    |
| POST   | /api/v1/todos          | token |
| PATCH  | /api/v1/todos/<id>     | token |
| DELETE | /api/v1/todos/<id>     | token |

Write endpoints require `Authorization: Bearer $TASKY_API_TOKEN`.

## Tests

```bash
pytest
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production configuration.
