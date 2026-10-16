import os


class Config:
    DATABASE_PATH = os.getenv("TASKY_DATABASE_PATH", "tasky.sqlite3")
    API_TOKEN = os.getenv("TASKY_API_TOKEN", "")
    MAX_TITLE_LENGTH = 200
    PAGE_SIZE = 20


class TestConfig(Config):
    API_TOKEN = "test-token"
    TESTING = True
