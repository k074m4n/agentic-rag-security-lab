# Deployment

## Configuration

Tasky is configured entirely through environment variables:

| Variable              | Default          | Purpose                                  |
|-----------------------|------------------|------------------------------------------|
| `TASKY_DATABASE_PATH` | `tasky.sqlite3`  | Path to the SQLite database file         |
| `TASKY_API_TOKEN`     | *(empty)*        | Bearer token for write endpoints         |

If `TASKY_API_TOKEN` is empty, every write request is rejected with `401`.

## Database configuration and connections

Tasky uses SQLite. A connection is opened lazily per request in `app/db.py`
(`get_db`) and closed in the app-context teardown (`close_db`). The schema is
created on startup by `init_db()`.

For production, put the database file on a persistent volume and back it up
with `sqlite3 tasky.sqlite3 ".backup tasky.bak"`.

## Running behind a WSGI server

```bash
gunicorn --workers 2 --bind 0.0.0.0:8000 "app:create_app()"
```
