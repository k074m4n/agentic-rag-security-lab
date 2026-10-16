"""Tasky: a small todo-list HTTP API."""

from flask import Flask

from .config import Config
from .db import close_db, init_db
from .routes import bp


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    app.register_blueprint(bp, url_prefix="/api/v1")
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    return app
