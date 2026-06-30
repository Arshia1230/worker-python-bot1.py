# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎲 جستجوی حریف / شروع بازی", callback_data="find_match")]])

def get_game_keyboard(game_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎲 ریختن تاس", callback_data=f"roll_{game_id}")]])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 مدیریت اسپانسرها", callback_data="admin_sponsors"),
         InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="admin_users")],
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")]
    ])

def get_admin_sponsors_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن اسپانسر", callback_data="add_sponsor_req"),
         InlineKeyboardButton("❌ حذف اسپانسر", callback_data="remove_sponsor_req")],
        [InlineKeyboardButton("📜 لیست اسپانسرها", callback_data="list_sponsors")],
        [InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="back_to_admin")]
    ])

def get_admin_users_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن ادمین جدید", callback_data="add_admin_req"),
         InlineKeyboardButton("❌ حذف ادمین", callback_data="remove_admin_req")],
        [InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="back_to_admin")]
    ])

def get_sponsor_keyboard(sponsors):
    keyboard = []
    for chan_id, link, name in sponsors:
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در {name}", url=link)])
    keyboard.append([InlineKeyboardButton("✅ تایید عضویت", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)
