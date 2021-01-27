import datetime
import dateutil.tz
import sqlite3
import os
from typing import Optional


DB_FILE = os.environ['DB_FILE']
db = sqlite3.connect(DB_FILE)
db.row_factory = sqlite3.Row


def _update_schema(db):
    cur = db.execute('pragma user_version')
    user_version = next(cur)[0]
    if user_version < 1:
        db.executescript("""
CREATE TABLE guild_settings (
    guild_id BIGINT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE guild_memes (
    guild_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    last_posted DATETIME,
    PRIMARY KEY (guild_id, url)
);
PRAGMA user_version=1;
        """)
        db.commit()
        user_version = 1
    if user_version < 2:
        db.executescript("""
CREATE TABLE global_memes (
    url TEXT NOT NULL,
    approved BOOLEAN NOT NULL DEFAULT 0,
    submitter BIGINT
);
ALTER TABLE guild_memes ADD COLUMN submitter BIGINT;
PRAGMA user_version=2;
        """)
        db.commit()
        user_version = 2
    if user_version < 3:
        db.executescript("""
DROP TABLE guild_memes;
CREATE TABLE guild_memes (
    guild_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    last_posted DATETIME,
    submitter BIGINT,
    PRIMARY KEY (guild_id, url)
);
DROP TABLE global_memes;
CREATE TABLE global_memes (
    url TEXT NOT NULL PRIMARY KEY,
    approved BOOLEAN NOT NULL DEFAULT 0,
    submitter BIGINT
);
PRAGMA user_version=3;
        """)
        db.commit()
        user_version = 3


_update_schema(db)


def get_setting(guild_id: int, key: str, default = None) -> Optional[str]:
    cur = db.execute('SELECT * FROM guild_settings WHERE guild_id=? AND key=? LIMIT 1', (guild_id, key))
    for row in cur:
        value = row['value']
        return value if value is not None else default
    return default


def set_setting(guild_id: int, key: str, value: str):
    cur = db.execute('INSERT OR REPLACE INTO guild_settings VALUES (?, ?, ?)', (guild_id, key, value))
    db.commit()

def get_schedule(guild_id: int, from_dt = None) -> datetime.datetime:
    tz = dateutil.tz.gettz(get_setting(guild_id, 'timezone', 'America/New_York'))
    if not tz:
        tz = dateutil.tz.gettz('America/New_York')
    time = datetime.time.fromisoformat(get_setting(guild_id, 'time', '09:30'))
    ts = datetime.datetime.now(tz=tz).replace(hour=time.hour, minute=time.minute)
    days_until_wednesday = (2 - ts.weekday()) % 7
    ts += datetime.timedelta(days=days_until_wednesday)
    if not from_dt:
        from_dt = datetime.datetime.now(tz=tz)
    while ts > from_dt:
        ts -= datetime.timedelta(days=7)
    if ts < from_dt:
        ts += datetime.timedelta(days=7)
    return ts

def get_queue_depth(guild_id: int):
    cur = db.execute('SELECT COUNT(*) FROM guild_memes WHERE guild_id=? AND last_posted IS NULL', (guild_id,))
    return next(cur)[0]

def get_global_queue_depth(guild_id: int):
    cur = db.execute('SELECT COUNT(*) FROM global_memes WHERE approved=1 AND NOT EXISTS (SELECT 1 FROM guild_memes WHERE guild_id=? AND url=global_memes.url AND last_posted IS NULL)', (guild_id,))
    return next(cur)[0]

def get_guild_meme(guild_id: int) -> Optional[str]:
    cur = db.execute('SELECT * FROM guild_memes WHERE guild_id=? AND last_posted IS NULL ORDER BY RANDOM() LIMIT 1', (guild_id,))
    for row in cur:
        return row['url']
    cur = db.execute('SELECT * FROM global_memes WHERE NOT EXISTS (SELECT 1 FROM guild_memes WHERE guild_id=? AND url=global_memes.url AND last_posted IS NOT NULL) ORDER BY RANDOM() LIMIT 1', (guild_id,))
    for row in cur:
        return row['url']
    print('no unused memes found')

def mark_guild_meme(guild_id: int, url: str):
    cur = db.execute("INSERT OR REPLACE INTO guild_memes (guild_id, url, last_posted) VALUES (?, ?, datetime('now'))", (guild_id, url))
    db.commit()

def add_guild_meme(guild_id: int, url: str, submitter: Optional[int] = None):
    cur = db.execute('INSERT INTO guild_memes (guild_id, url, submitter) VALUES (?, ?, ?)', (guild_id, url, submitter))
    db.commit()

def add_global_meme(url: str, approved: Optional[bool] = False, submitter: Optional[int] = None):
    if approved is None:
        approved = 0
    cur = db.execute('INSERT INTO global_memes (url, approved, submitter) VALUES (?, ?, ?)', (url, approved, submitter))
    db.commit()
