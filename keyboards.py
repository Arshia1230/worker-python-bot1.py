# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    keyboard = [[InlineKeyboardButton("🎲 جستجوی حریف / شروع بازی", callback_data="find_match")]]
    return InlineKeyboardMarkup(keyboard)

def get_game_keyboard(game_id):
    keyboard = [[InlineKeyboardButton("🎲 ریختن تاس", callback_data=f"roll_{game_id}")]]
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 مدیریت اسپانسرها", callback_data="manage_sponsors")],
        [InlineKeyboardButton("👤 مدیریت ادمین‌ها", callback_data="manage_admins")],
        [InlineKeyboardButton("📊 آمار ربات", callback_data="bot_stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sponsor_keyboard(sponsors):
    keyboard = []
    for chan_id, link, name in sponsors:
        keyboard.append([InlineKeyboardButton(f"📢 عضویت در {name}", url=link)])
    keyboard.append([InlineKeyboardButton("✅ تایید عضویت", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)
