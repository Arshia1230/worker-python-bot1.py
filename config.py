# -*- coding: utf-8 -*-
"""
تنظیمات ربات مار و پله.
توکن و آیدی ادمین از متغیرهای محیطی خوانده می‌شوند.
"""

import os

# توکن ربات - از Environment Variables روی Render تنظیم کنید
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# آیدی ادمین‌ها - از Environment Variables خوانده می‌شود
# مثال: ADMIN_IDS=123456789,987654321
_admin_raw = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

# مسیر فایل دیتابیس
DB_PATH = os.environ.get("DB_PATH", "snake_ladder.db")

# ────────────────────────────────────────────────────────────
# سه سطح بازی
# ────────────────────────────────────────────────────────────
DIFFICULTIES = {
    "easy": {
        "title": "آسان",
        "cols": 6,
        "rows": 6,
        "snakes": 4,
        "ladders": 5,
    },
    "medium": {
        "title": "متوسط",
        "cols": 10,
        "rows": 10,
        "snakes": 8,
        "ladders": 9,
    },
    "professional": {
        "title": "حرفه‌ای",
        "cols": 12,
        "rows": 12,
        "snakes": 14,
        "ladders": 14,
    },
}

MIN_PLAYERS = 2
MAX_PLAYERS = 6
ROLL_AGAIN_ON_SIX = True
