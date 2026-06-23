"""Seed a persistent SQLite database for deployment."""
import sys

from app.generator import generate
from app.storage.db import Database


def main(path: str = "career.db", n: int = 2000, seed: int = 0) -> None:
    db = Database(path)
    db.init_schema()
    db.insert_jobs(generate(n, seed=seed))
    print(f"Seeded {n} jobs into {path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(*(args[:1]), **({"n": int(args[1])} if len(args) > 1 else {}))
