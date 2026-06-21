# -*- coding: utf-8 -*-
"""کیبوردهای این‌لاین (دکمه‌های شیشه‌ای)."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import DIFFICULTIES
from texts import fa_num


def difficulty_keyboard(prefix):
    """
    دکمه‌های انتخاب سطح.
    prefix یعنی این انتخاب برای بازی گروهی است (newdiff) یا با کامپیوتر (botdiff).
    """
    rows = []
    for key, cfg in DIFFICULTIES.items():
        size = cfg["cols"] * cfg["rows"]
        rows.append([
            InlineKeyboardButton(
                f"{cfg['title']} ({fa_num(size)} خانه)",
                callback_data=f"{prefix}:{key}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def lobby_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ پیوستن به بازی", callback_data="join")],
        [
            InlineKeyboardButton("▶️ شروع بازی", callback_data="startgame"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel"),
        ],
    ])


def roll_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 پرتاب تاس", callback_data="roll")]
    ])


def private_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 بازی با کامپیوتر", callback_data="vsbot")],
        [InlineKeyboardButton("📖 راهنما", callback_data="help")],
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
