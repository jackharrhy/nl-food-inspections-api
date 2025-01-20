import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass

DB_PATH = Path("data/nl-food-inspections.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
PDF_TTL = timedelta(days=7)


@dataclass
class Row:
    name: str
    location: str
    region: str

    pdf_url: str

    pdf: bytes | None = None
    time_since_scraped: datetime | None = None

    def composite_key(self) -> str:
        return f"{self.name}-{self.location}-{self.region}"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pdfs (
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                region TEXT NOT NULL,
                pdf_url TEXT NOT NULL,
                pdf BLOB,
                time_since_scraped TIMESTAMP,
                PRIMARY KEY (name, location, region)
            )
        """)
        conn.commit()


def store_pdf(row: Row):
    if row.pdf is None:
        raise ValueError("PDF is required to store in the database")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO pdfs 
            (name, location, region, pdf_url, pdf, time_since_scraped)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (row.name, row.location, row.region, row.pdf_url, row.pdf, datetime.now()),
        )
        conn.commit()


def get_pdf(row: Row) -> Row | None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM pdfs
            WHERE name = ? AND location = ? AND region = ?
        """,
            (row.name, row.location, row.region),
        )
        result = cur.fetchone()

        if result is None:
            return None

        return Row(
            name=result[0],
            location=result[1],
            region=result[2],
            pdf_url=result[3],
            pdf=result[4],
            time_since_scraped=datetime.fromisoformat(result[5]),
        )


init_db()
