# -*- coding: utf-8 -*-
"""کیبوردهای این‌لاین (دکمه‌های شیشه‌ای)."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from texts import fa_num


def difficulty_keyboard(prefix):
    """
    دکمه‌های انتخاب سطح.
    prefix مشخص می‌کند: بازی گروهی (newdiff) یا با کامپیوتر (botdiff).
    """
    rows = []
    for key, cfg in config.DIFFICULTIES.items():
        size = cfg["cols"] * cfg["rows"]
        rows.append([
            InlineKeyboardButton(
                f"{cfg['title']} ({fa_num(size)} خانه)",
                callback_data=f"{prefix}:{key}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def lobby_keyboard():
    """لابی بازی گروهی (داخل گروه)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ پیوستن به بازی", callback_data="join")],
        [
            InlineKeyboardButton("▶️ شروع بازی", callback_data="startgame"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel"),
        ],
    ])


def roll_keyboard():
    """دکمهٔ تاس."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 پرتاب تاس", callback_data="roll")]
    ])


def private_menu_keyboard(bot_username=None):
    rows = [
        [InlineKeyboardButton("🤖 بازی با کامپیوتر", callback_data="vsbot")],
    ]
    if bot_username:
        rows.append([InlineKeyboardButton(
            "👥 بازی با دوستان (افزودن به گروه)",
            url=f"https://t.me/{bot_username}?startgroup=new",
        )])
    rows.append([InlineKeyboardButton("📖 راهنما", callback_data="help")])
    if config.REQUIRED_CHANNEL_URL:
        rows.append([InlineKeyboardButton("📢 چنل اسپانسر ما",
                                          url=config.REQUIRED_CHANNEL_URL)])
    return InlineKeyboardMarkup(rows)


def join_gate_keyboard():
    """دکمه‌های صفحهٔ عضویت اجباری."""
    url = config.REQUIRED_CHANNEL_URL or "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در چنل اسپانسر ما", url=url)],
        [InlineKeyboardButton("✅ عضو شدم", callback_data="checkjoin")],
    ])


def admin_keyboard(maintenance):
    maint_label = "🟢 خروج از حالت تعمیر" if maintenance else "🔧 ورود به حالت تعمیر"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 آمار", callback_data="admin:stats"),
            InlineKeyboardButton("🏆 برترین‌ها", callback_data="admin:top"),
        ],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin:broadcast")],
        [InlineKeyboardButton(maint_label, callback_data="admin:maint")],
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin:refresh")],
    ])
