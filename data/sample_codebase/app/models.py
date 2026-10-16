from dataclasses import asdict, dataclass
from sqlite3 import Row


@dataclass
class Todo:
    id: int
    title: str
    done: bool
    created_at: str

    @classmethod
    def from_row(cls, row: Row) -> "Todo":
        return cls(
            id=row["id"],
            title=row["title"],
            done=bool(row["done"]),
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        return asdict(self)
