# -*- coding: utf-8 -*-
"""دیتابیس SQLite برای کاربران، بازی‌ها، آمار و تنظیمات (حالت تعمیر)."""

import sqlite3
import datetime

from config import DB_PATH


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_db():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id      INTEGER PRIMARY KEY,
                username     TEXT,
                first_name   TEXT,
                joined_at    TEXT,
                last_active  TEXT,
                games_played INTEGER DEFAULT 0,
                games_won    INTEGER DEFAULT 0,
                banned       INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS games (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER,
                chat_type     TEXT,
                difficulty    TEXT,
                players_count INTEGER,
                winner_id     INTEGER,
                created_at    TEXT,
                finished_at   TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )


def upsert_user(user):
    """ثبت یا به‌روزرسانی کاربر هنگام تعامل با ربات."""
    with _conn() as c:
        row = c.execute(
            "SELECT user_id FROM users WHERE user_id=?", (user.id,)
        ).fetchone()
        if row:
            c.execute(
                "UPDATE users SET username=?, first_name=?, last_active=? "
                "WHERE user_id=?",
                (user.username, user.first_name, now(), user.id),
            )
        else:
            c.execute(
                "INSERT INTO users(user_id, username, first_name, joined_at, "
                "last_active) VALUES(?,?,?,?,?)",
                (user.id, user.username, user.first_name, now(), now()),
            )


def is_banned(user_id):
    with _conn() as c:
        r = c.execute(
            "SELECT banned FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        return bool(r and r["banned"])


def set_ban(user_id, banned=True):
    with _conn() as c:
        c.execute(
            "UPDATE users SET banned=? WHERE user_id=?",
            (1 if banned else 0, user_id),
        )


def record_game(chat_id, chat_type, difficulty, players_count, winner_id):
    with _conn() as c:
        c.execute(
            "INSERT INTO games(chat_id, chat_type, difficulty, players_count, "
            "winner_id, created_at, finished_at) VALUES(?,?,?,?,?,?,?)",
            (chat_id, str(chat_type), difficulty, players_count,
             winner_id, now(), now()),
        )


def add_played(user_ids):
    with _conn() as c:
        for uid in user_ids:
            c.execute(
                "UPDATE users SET games_played = games_played + 1 "
                "WHERE user_id=?",
                (uid,),
            )


def add_win(user_id):
    with _conn() as c:
        c.execute(
            "UPDATE users SET games_won = games_won + 1 WHERE user_id=?",
            (user_id,),
        )


def get_user_stats(user_id):
    with _conn() as c:
        r = c.execute(
            "SELECT games_played, games_won FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if not r:
        return 0, 0
    return r["games_played"], r["games_won"]


def get_stats():
    with _conn() as c:
        users = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        games = c.execute("SELECT COUNT(*) AS n FROM games").fetchone()["n"]
        by_diff = c.execute(
            "SELECT difficulty, COUNT(*) AS n FROM games GROUP BY difficulty"
        ).fetchall()
    return {
        "users": users,
        "games": games,
        "by_diff": {r["difficulty"]: r["n"] for r in by_diff},
    }


def get_leaderboard(limit=10):
    with _conn() as c:
        return c.execute(
            "SELECT first_name, username, games_won, games_played "
            "FROM users ORDER BY games_won DESC, games_played DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_all_user_ids():
    with _conn() as c:
        return [
            r["user_id"]
            for r in c.execute(
                "SELECT user_id FROM users WHERE banned=0"
            ).fetchall()
        ]


def get_setting(key, default=None):
    with _conn() as c:
        r = c.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
    return r["value"] if r else default


def set_setting(key, value):
    with _conn() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def is_maintenance():
    return get_setting("maintenance", "0") == "1"


def set_maintenance(on):
    set_setting("maintenance", "1" if on else "0")
