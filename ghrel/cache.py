from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests


def _cache_path(name):  # type: (str) -> pathlib.Path
    from pathlib import Path

    if sys.platform == "win32":
        return Path(os.getenv("LOCALAPPDATA")) / name
    else:
        xdg_cache_dir = os.getenv("XDG_CACHE_DIR")
        if xdg_cache_dir:
            return Path(xdg_cache_dir) / name
        return Path.home() / ".cache" / name


@dataclass
class Entry:
    url: str
    checksum: str
    size: int
    etag: str
    last_modified: datetime | None
    expire: datetime | None

    def expired(self):
        if self.expire:
            now = datetime.utcnow()
            return self.expire <= now
        return False


def from_http_date(date):  # type: (str) -> datetime
    return datetime.strptime(date, "%a, %d %b %Y %H:%M:%S GMT")


class Cache:
    def __init__(self, name="gh-releases"):
        self._path = _cache_path(name) / "cache.db"
        self._loaded = False
        self._modified = False
        self._con = None

    @property
    def path(self):
        return self._path

    def _create_table(self):
        """create a database table if it does not exist already"""
        self._con.executescript(
            """
BEGIN;
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS url(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS cache(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    urlID INTEGER,
    checksum TEXT,
    size INTEGER,
    etag TEXT NOT NULL,
    lastModifiedDate TIMESTAMP,
    expireDate TIMESTAMP,
    FOREIGN KEY(urlID) REFERENCES url(id),
    UNIQUE(urlID));
COMMIT;
"""
        )

    def _connect(self):
        self._con = sqlite3.connect(
            self._path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )

    def _load(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()
        self._create_table()
        self._loaded = True

    def _find_entry(self, url):  # type: (str) -> Entry | None
        cur = self._con.cursor()
        try:
            cur.execute(
                """
SELECT u.url, c.checksum, c.size, c.etag, c.lastModifiedDate, c.expireDate
FROM cache c
JOIN url u ON c.urlID = u.id
WHERE u.url = ?;
""",
                (url,),
            )
            records = cur.fetchall()
            for row in records:
                return Entry(*row[:6])
        finally:
            cur.close()

    def _update_entry(self, entry: Entry):
        cur = self._con.cursor()
        try:
            cur.execute("INSERT OR IGNORE INTO url (url) VALUES (?);", (entry.url,))
            cur.execute(
                """
    INSERT INTO cache (urlID, checksum, size, etag, lastModifiedDate, expireDate)
    VALUES ((SELECT id FROM url WHERE url = ?), ?, ?, ?, ?, ?)
    ON CONFLICT(urlID) DO UPDATE SET
    checksum = EXCLUDED.checksum,
    etag = EXCLUDED.etag,
    size = EXCLUDED.size,
    lastModifiedDate = EXCLUDED.lastModifiedDate,
    expireDate = EXCLUDED.expireDate;
    """,
                (
                    entry.url,
                    entry.checksum,
                    entry.size,
                    entry.etag,
                    entry.last_modified,
                    entry.expire,
                ),
            )
        finally:
            cur.close()
            self._con.commit()

    def get(self, url):  # type: (str) -> Entry | None
        if not self._loaded:
            self._load()
        return self._find_entry(url)

    def insert(
        self, url, size, response, checksum
    ):  # type: (str, int, requests.Response, str) -> bool
        if not self._loaded:
            self._load()
        etag = response.headers.get("Etag")
        last_modified = response.headers.get("Last-Modified")
        if etag:
            modified_time = (
                None if last_modified is None else from_http_date(last_modified)
            )
            expire = guess_expire(response)
            entry = Entry(url, checksum, size, etag, modified_time, expire)
            self._update_entry(entry)
            return True
        return False

    def commit(self):
        if self._modified and self._con:
            self._con.commit()
            self._modified = False

    def close(self):
        if self._con is not None:
            self._con.commit()
            self._con.close()
            self._con = None


def guess_expire(response):  # type: (requests.Response) -> datetime | None
    expire = None  # type: datetime | None
    try:
        expire_date = response.headers.get("Expire")
        if expire_date:
            print(f"Expire: {expire}")
            expire = from_http_date(expire_date)
        if expire is None:
            # force an expiration of one month
            expire = datetime.utcnow() + timedelta(weeks=4)
        cache_control = response.headers.get("Cache-Control")
        if cache_control:
            print(f"Cache-Control: {cache_control}")
            for field in cache_control.split(","):
                name, value = field.split("=", 1)
                name = name.strip().lower()
                if name == "max-age":
                    seconds = max(0, int(value.strip()))
                    limit = datetime.utcnow() + timedelta(seconds=seconds)
                    expire = min(expire, limit)
                elif name == "no-cache":
                    expire = min(expire, datetime.utcnow())
    except ValueError:
        pass
    return expire
