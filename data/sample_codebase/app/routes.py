from flask import Blueprint, current_app, jsonify, request

from .auth import require_token
from .db import get_db
from .models import Todo
from .utils import ValidationError, parse_page, validate_title

bp = Blueprint("todos", __name__)


@bp.errorhandler(ValidationError)
def handle_validation_error(exc: ValidationError):
    return jsonify(error=str(exc)), 400


@bp.get("/todos")
def list_todos():
    page = parse_page(request.args.get("page"))
    size = current_app.config["PAGE_SIZE"]
    rows = get_db().execute(
        "SELECT * FROM todos ORDER BY id LIMIT ? OFFSET ?",
        (size, (page - 1) * size),
    ).fetchall()
    return jsonify(items=[Todo.from_row(r).to_dict() for r in rows], page=page)


@bp.get("/todos/<int:todo_id>")
def get_todo(todo_id: int):
    row = get_db().execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        return jsonify(error="not found"), 404
    return jsonify(Todo.from_row(row).to_dict())


@bp.post("/todos")
@require_token
def create_todo():
    title = validate_title((request.get_json(silent=True) or {}).get("title"))
    db = get_db()
    cur = db.execute("INSERT INTO todos (title) VALUES (?)", (title,))
    db.commit()
    row = db.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(Todo.from_row(row).to_dict()), 201


@bp.patch("/todos/<int:todo_id>")
@require_token
def update_todo(todo_id: int):
    payload = request.get_json(silent=True) or {}
    db = get_db()
    if "title" in payload:
        db.execute("UPDATE todos SET title = ? WHERE id = ?", (validate_title(payload["title"]), todo_id))
    if "done" in payload:
        db.execute("UPDATE todos SET done = ? WHERE id = ?", (int(bool(payload["done"])), todo_id))
    db.commit()
    return get_todo(todo_id)


@bp.delete("/todos/<int:todo_id>")
@require_token
def delete_todo(todo_id: int):
    db = get_db()
    cur = db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="not found"), 404
    return "", 204
