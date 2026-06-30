# -*- coding: utf-8 -*-
"""
ربات تلگرام «مار و پله»
- بازی گروهی نوبتی داخل گروه‌ها (بازی با دوستان، بدون لینک)
- بازی با کامپیوتر در پیوی
- تاس انیمیشنیِ واقعی تلگرام (send_dice)
- سه سطح: آسان / متوسط / حرفه‌ای (تفاوت فقط در اندازهٔ زمین)
- نمایش زمین به‌صورت جدول متنی خانه‌به‌خانه (بدون تصویر)
- عضویت اجباری در کانال (Force Join)
- پنل ادمین: آمار، برترین‌ها، پیام همگانی، حالت تعمیر
- سازگار با Render (وب‌سرور سلامت برای جلوگیری از خواب)
"""

import re
import random
import asyncio
import logging
from html import escape as h

from telegram import Update
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import config
import database as db
import texts as T
import keyboards as kb
import keep_alive
from game import Game, board_grid

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("snake_ladder")

# بازی‌های فعال در حافظه: کلید = chat_id
games = {}

# چت‌هایی که در حال پردازش یک پرتاب هستند (برای جلوگیری از تپ پشت‌سرهم)
busy = set()

# ادمین‌هایی که منتظر دریافت متن پیام همگانی هستند
awaiting_broadcast = set()

# شناسهٔ مجازی برای بازیکنِ کامپیوتر
BOT_PLAYER_ID = -1

PLAYER_EMOJIS = ["🔴", "🔵", "🟢", "🟠", "🟣", "🟤"]

# مدت انتظار تا انیمیشن تاس تمام شود
DICE_ANIM_DELAY = 3.0


# ── توابع کمکی عمومی ─────────────────────────────────────────
def is_admin(user_id):
    return user_id in config.ADMIN_IDS


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


def safe_name(p):
    if p.is_bot:
        return "🤖 کامپیوتر"
    return h(p.name or "بازیکن")


def bot_username(context):
    return getattr(context.bot, "username", None)


# ── عضویت اجباری در کانال ────────────────────────────────────
async def is_member(context, user_id):
    """آیا کاربر عضو کانال اجباری هست؟ (ادمین‌ها معاف‌اند)."""
    ch = config.REQUIRED_CHANNEL
    if not ch:
        return True
    if is_admin(user_id):
        return True
    try:
        m = await context.bot.get_chat_member(ch, user_id)
    except Exception as e:
        log.warning("بررسی عضویت ناموفق بود (آیا ربات در کانال ادمین است؟): %s", e)
        return False
    status = getattr(m, "status", "")
    if status in ("creator", "administrator", "member", "owner"):
        return True
    if status == "restricted" and getattr(m, "is_member", False):
        return True
    return False


async def require_membership_msg(update, context):
    user = update.effective_user
    if await is_member(context, user.id):
        return True
    await update.effective_message.reply_text(
        T.join_gate_text(), parse_mode=ParseMode.HTML,
        reply_markup=kb.join_gate_keyboard(),
    )
    return False


async def require_membership_cb(update, context):
    q = update.callback_query
    if await is_member(context, q.from_user.id):
        return True
    await q.answer("اول باید عضو کانال شوید.", show_alert=True)
    try:
        await q.message.reply_text(
            T.join_gate_text(), parse_mode=ParseMode.HTML,
            reply_markup=kb.join_gate_keyboard(),
        )
    except Exception:
        pass
    return False


# ── تاس انیمیشنی ─────────────────────────────────────────────
async def animate_dice(context, chat_id):
    """
    استیکر تاسِ انیمیشنیِ تلگرام را می‌فرستد، صبر می‌کند تا انیمیشن تمام شود،
    و عددِ نهایی (۱ تا ۶) را برمی‌گرداند. اگر ارسال ممکن نشد، عدد تصادفی می‌دهد.
    """
    try:
        m = await context.bot.send_dice(chat_id=chat_id, emoji="🎲")
        value = m.dice.value
    except Exception as e:
        log.warning("ارسال تاس انیمیشنی ممکن نشد: %s", e)
        return random.randint(1, 6)
    await asyncio.sleep(DICE_ANIM_DELAY)
    return value


# ── ساخت متن‌ها ──────────────────────────────────────────────
def lobby_text(game):
    names = "\n".join(
        f"{PLAYER_EMOJIS[p.color_index % 6]} {T.fa_num(i + 1)}- {h(p.name or 'بازیکن')}"
        for i, p in enumerate(game.players)
    ) or "—"
    cfg = config.DIFFICULTIES[game.difficulty]
    size = cfg["cols"] * cfg["rows"]
    return (
        "🎮 <b>بازی مار و پله</b>\n"
        f"{T.LINE}\n"
        f"🎚 سطح: {cfg['title']} ({T.fa_num(size)} خانه)\n"
        f"👥 بازیکنان ({T.fa_num(len(game.players))}/"
        f"{T.fa_num(config.MAX_PLAYERS)}):\n{names}\n"
        f"{T.LINE}\n"
        f"برای پیوستن دکمهٔ «➕ پیوستن» را بزنید. "
        f"حداقل {T.fa_num(config.MIN_PLAYERS)} نفر لازم است."
    )


def board_message_text(game, header=""):
    """متن کامل پیامِ زمین: صفحهٔ بازیِ ایموجی + بازیکنان + نوبت."""
    cfg = config.DIFFICULTIES[game.difficulty]
    size = cfg["cols"] * cfg["rows"]
    parts = []
    if header:
        parts.append(header)
        parts.append("")
    parts.append(f"🎚 سطح: {cfg['title']} ({T.fa_num(size)} خانه)")
    parts.append("")
    parts.append("<pre>" + board_grid(game) + "</pre>")
    parts.append("🪜 نردبان • 🐍 مار • 🏁 پایان")
    parts.append("")
    for i, p in enumerate(game.players):
        em = PLAYER_EMOJIS[p.color_index % 6]
        pos = T.fa_num(p.pos) if p.pos > 0 else "شروع"
        parts.append(f"{em} {safe_name(p)} — خانه {pos}")
    cur = game.current_player()
    if game.state == "playing" and cur:
        parts.append("")
        parts.append(f"👉 نوبت: <b>{safe_name(cur)}</b>")
    text = "\n".join(parts)
    if len(text) > 4000:
        text = text[:3990] + "…"
    return text


def roll_line(res):
    p = res["player"]
    name = safe_name(p)
    line = f"🎲 {name} عدد {T.fa_num(res['dice'])} آورد"
    if res["event"] == "ladder":
        line += f" 🪜 و با نردبان به خانه {T.fa_num(res['new'])} رفت!"
    elif res["event"] == "snake":
        line += f" 🐍 و مار او را به خانه {T.fa_num(res['new'])} برد!"
    else:
        line += f" و به خانه {T.fa_num(res['new'])} رسید."
    if res["won"]:
        line += " 🏆"
    elif res["again"]:
        line += " (۶ آورد، دوباره می‌اندازد!)"
    return line


def join_log(lines):
    if len(lines) > 8:
        lines = ["…"] + lines[-8:]
    return "\n".join(lines)


# ── به‌روزرسانی زمین (پیام تازه بعد از تاس، حذف پیام قبلی) ────
async def push_board(context, chat_id, game, header="", with_roll=True):
    text = board_message_text(game, header)
    markup = kb.roll_keyboard() if (with_roll and game.state == "playing") else None
    # پیام زمینِ قبلی را حذف کن تا زمینِ تازه زیر تاس‌ها دیده شود
    if game.message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id,
                                             message_id=game.message_id)
        except Exception:
            pass
        game.message_id = None
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode=ParseMode.HTML, reply_markup=markup,
        )
    except Exception:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=strip_tags(text), reply_markup=markup,
        )
    game.message_id = msg.message_id


async def finish_game(context, chat, game, header):
    winner = game.winner
    human_ids = [p.user_id for p in game.players if not p.is_bot]
    db.add_played(human_ids)
    if winner and not winner.is_bot:
        db.add_win(winner.user_id)
    db.record_game(
        chat.id, chat.type, game.difficulty, len(game.players),
        None if (winner and winner.is_bot) else (winner.user_id if winner else None),
    )
    win_line = f"🏁🎉 <b>{safe_name(winner)}</b> برنده شد! تبریک 🎊"
    full_header = (header + "\n\n" + win_line) if header else win_line
    await push_board(context, chat.id, game, header=full_header, with_roll=False)
    games.pop(chat.id, None)


# ── دستورها ─────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    db.upsert_user(user)
    if not await require_membership_msg(update, context):
        return
    if chat.type == ChatType.PRIVATE:
        text = T.welcome_private()
        if is_admin(user.id):
            text += "\n\n🛠 شما ادمین هستید؛ برای پنل مدیریت /admin را بزنید."
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML,
            reply_markup=kb.private_menu_keyboard(bot_username(context)),
        )
    else:
        await update.message.reply_text(T.WELCOME_GROUP, parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(T.help_text(), parse_mode=ParseMode.HTML)


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db.upsert_user(user)
    if chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "این دستور مخصوص گروه‌هاست 👥\n"
            "برای بازی با دوستان، ربات را به یک گروه اضافه کنید و آنجا /newgame بزنید.\n"
            "برای بازی با کامپیوتر همین‌جا /play را بزنید."
        )
        return
    if db.is_maintenance() and not is_admin(user.id):
        await update.message.reply_text(T.MAINTENANCE_MSG)
        return
    if not await require_membership_msg(update, context):
        return
    existing = games.get(chat.id)
    if existing and existing.state != "finished":
        await update.message.reply_text(
            "یک بازی در این گروه در جریان است. ابتدا آن را تمام کنید "
            "یا با /endgame پایان دهید."
        )
        return
    await update.message.reply_text(
        T.CHOOSE_DIFFICULTY, parse_mode=ParseMode.HTML,
        reply_markup=kb.difficulty_keyboard("newdiff"),
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    db.upsert_user(user)
    if chat.type != ChatType.PRIVATE:
        await update.message.reply_text("برای بازی با دوستان از /newgame استفاده کنید.")
        return
    if db.is_maintenance() and not is_admin(user.id):
        await update.message.reply_text(T.MAINTENANCE_MSG)
        return
    if not await require_membership_msg(update, context):
        return
    await update.message.reply_text(
        T.CHOOSE_DIFFICULTY, parse_mode=ParseMode.HTML,
        reply_markup=kb.difficulty_keyboard("botdiff"),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user)
    played, won = db.get_user_stats(user.id)
    await update.message.reply_text(
        "📊 <b>آمار شما</b>\n"
        f"{T.LINE}\n"
        f"🎮 تعداد بازی‌ها: {T.fa_num(played)}\n"
        f"🏆 تعداد بردها: {T.fa_num(won)}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game = games.get(chat.id)
    if not game:
        await update.message.reply_text("بازی فعالی در این چت نیست.")
        return
    if user.id != game.creator_id and not is_admin(user.id):
        await update.message.reply_text(
            "فقط سازندهٔ بازی یا ادمین می‌تواند بازی را پایان دهد."
        )
        return
    games.pop(chat.id, None)
    busy.discard(chat.id)
    await update.message.reply_text("⛔️ بازی پایان یافت.")


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text(
        T.ADMIN_PANEL_TITLE, parse_mode=ParseMode.HTML,
        reply_markup=kb.admin_keyboard(db.is_maintenance()),
    )


async def cmd_cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in awaiting_broadcast:
        awaiting_broadcast.discard(user.id)
        await update.message.reply_text("پیام همگانی لغو شد.")


# ── کال‌بک: عضویت ────────────────────────────────────────────
async def cb_checkjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    if await is_member(context, user.id):
        await q.answer("عضویت تأیید شد ✅")
        if q.message.chat.type == ChatType.PRIVATE:
            text = T.welcome_private()
            if is_admin(user.id):
                text += "\n\n🛠 شما ادمین هستید؛ برای پنل مدیریت /admin را بزنید."
            try:
                await q.edit_message_text(
                    text, parse_mode=ParseMode.HTML,
                    reply_markup=kb.private_menu_keyboard(bot_username(context)),
                )
            except Exception:
                pass
        else:
            try:
                await q.edit_message_text(
                    "✅ عضویت تأیید شد. حالا می‌توانید با /newgame بازی بسازید."
                )
            except Exception:
                pass
    else:
        await q.answer(
            "هنوز عضو نشده‌اید. اول در کانال عضو شوید، بعد دوباره بزنید.",
            show_alert=True,
        )


# ── کال‌بک‌ها: ساخت و اجرای بازی ─────────────────────────────
async def cb_newdiff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not await require_membership_cb(update, context):
        return
    await q.answer()
    user = q.from_user
    chat = q.message.chat
    diff = q.data.split(":")[1]
    if diff not in config.DIFFICULTIES:
        return
    db.upsert_user(user)
    game = Game(chat.id, diff, creator_id=user.id)
    game.add_player(user.id, user.first_name)
    games[chat.id] = game
    try:
        await q.edit_message_text(
            lobby_text(game), parse_mode=ParseMode.HTML,
            reply_markup=kb.lobby_keyboard(),
        )
    except Exception:
        pass
    game.message_id = q.message.message_id


async def cb_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not await require_membership_cb(update, context):
        return
    user = q.from_user
    chat = q.message.chat
    game = games.get(chat.id)
    if not game or game.state != "lobby":
        await q.answer("بازی فعالی برای پیوستن نیست.", show_alert=True)
        return
    db.upsert_user(user)
    if game.has_player(user.id):
        await q.answer("شما قبلاً در بازی هستید.")
        return
    if not game.add_player(user.id, user.first_name):
        await q.answer("ظرفیت بازی پر است.", show_alert=True)
        return
    await q.answer("به بازی پیوستید ✅")
    try:
        await q.edit_message_text(
            lobby_text(game), parse_mode=ParseMode.HTML,
            reply_markup=kb.lobby_keyboard(),
        )
    except Exception:
        pass


async def cb_startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    chat = q.message.chat
    game = games.get(chat.id)
    if not game or game.state != "lobby":
        await q.answer("بازی فعالی نیست.", show_alert=True)
        return
    if not game.has_player(user.id):
        await q.answer("فقط بازیکنان می‌توانند بازی را شروع کنند.", show_alert=True)
        return
    if len(game.players) < config.MIN_PLAYERS:
        await q.answer(
            f"حداقل {config.MIN_PLAYERS} بازیکن لازم است.", show_alert=True
        )
        return
    await q.answer()
    game.state = "playing"
    game.turn_index = 0
    game.message_id = q.message.message_id
    await push_board(context, chat.id, game, header="🚀 بازی شروع شد!")


async def cb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    chat = q.message.chat
    game = games.get(chat.id)
    if not game:
        await q.answer()
        return
    if user.id != game.creator_id and not is_admin(user.id):
        await q.answer("فقط سازندهٔ بازی می‌تواند لغو کند.", show_alert=True)
        return
    games.pop(chat.id, None)
    busy.discard(chat.id)
    await q.answer("بازی لغو شد.")
    try:
        await q.edit_message_text("❌ بازی لغو شد.")
    except Exception:
        pass


async def cb_vsbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not await require_membership_cb(update, context):
        return
    await q.answer()
    try:
        await q.edit_message_text(
            T.CHOOSE_DIFFICULTY, parse_mode=ParseMode.HTML,
            reply_markup=kb.difficulty_keyboard("botdiff"),
        )
    except Exception:
        pass


async def cb_botdiff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not await require_membership_cb(update, context):
        return
    await q.answer()
    user = q.from_user
    chat = q.message.chat
    diff = q.data.split(":")[1]
    if diff not in config.DIFFICULTIES:
        return
    db.upsert_user(user)
    game = Game(chat.id, diff, creator_id=user.id)
    game.vs_bot = True
    game.add_player(user.id, user.first_name)
    game.add_player(BOT_PLAYER_ID, "کامپیوتر", is_bot=True)
    game.state = "playing"
    games[chat.id] = game
    game.message_id = q.message.message_id
    await push_board(context, chat.id, game,
                     header="🤖 بازی با کامپیوتر شروع شد! نوبت شماست.")


async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.edit_message_text(
            T.help_text(), parse_mode=ParseMode.HTML,
            reply_markup=kb.private_menu_keyboard(bot_username(context)),
        )
    except Exception:
        pass


async def cb_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    chat = q.message.chat
    game = games.get(chat.id)
    if not game or game.state != "playing":
        await q.answer("بازی فعالی نیست.", show_alert=True)
        return
    cur = game.current_player()
    if cur.is_bot:
        await q.answer("نوبت کامپیوتر است؛ کمی صبر کنید.")
        return
    if cur.user_id != user.id:
        await q.answer("نوبت شما نیست ⏳", show_alert=True)
        return
    if chat.id in busy:
        await q.answer("⏳ صبر کنید، تاس در حال چرخیدن است...")
        return
    await q.answer()

    busy.add(chat.id)
    try:
        log_lines = []
        guard = 0
        # نوبت بازیکن انسانی (با ۶ ممکن است چند بار باشد)
        while True:
            guard += 1
            value = await animate_dice(context, chat.id)
            res = game.roll_and_move(dice=value)
            log_lines.append(roll_line(res))
            if res["won"]:
                await finish_game(context, chat, game, join_log(log_lines))
                return
            if res["again"] and guard < 20:
                await push_board(context, chat.id, game, header=join_log(log_lines))
                continue
            break

        # نوبت‌های کامپیوتر (در حالت تک‌نفره)
        while game.state == "playing" and game.current_player() \
                and game.current_player().is_bot:
            await push_board(context, chat.id, game, header=join_log(log_lines))
            guard = 0
            while True:
                guard += 1
                value = await animate_dice(context, chat.id)
                res = game.roll_and_move(dice=value)
                log_lines.append(roll_line(res))
                if res["won"]:
                    await finish_game(context, chat, game, join_log(log_lines))
                    return
                if res["again"] and guard < 20:
                    await push_board(context, chat.id, game,
                                     header=join_log(log_lines))
                    continue
                break

        await push_board(context, chat.id, game, header=join_log(log_lines))
    finally:
        busy.discard(chat.id)


# ── کال‌بک‌های پنل ادمین ─────────────────────────────────────
async def cb_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    if not is_admin(user.id):
        await q.answer("دسترسی ندارید.", show_alert=True)
        return
    action = q.data.split(":")[1]

    if action == "stats":
        s = db.get_stats()
        diff_lines = "\n".join(
            f"• {config.DIFFICULTIES.get(k, {}).get('title', k)}: {T.fa_num(v)}"
            for k, v in s["by_diff"].items()
        ) or "—"
        txt = (
            "📊 <b>آمار ربات</b>\n"
            f"{T.LINE}\n"
            f"👥 کاربران: {T.fa_num(s['users'])}\n"
            f"🎮 کل بازی‌ها: {T.fa_num(s['games'])}\n\n"
            f"بازی‌ها بر اساس سطح:\n{diff_lines}"
        )
        await q.answer()
        await q.edit_message_text(
            txt, parse_mode=ParseMode.HTML,
            reply_markup=kb.admin_keyboard(db.is_maintenance()),
        )

    elif action == "top":
        rows_ = db.get_leaderboard(10)
        if rows_:
            lines = []
            for i, r in enumerate(rows_):
                nm = r["first_name"] or (
                    ("@" + r["username"]) if r["username"] else "ناشناس"
                )
                lines.append(
                    f"{T.fa_num(i + 1)}. {h(nm)} — 🏆 {T.fa_num(r['games_won'])} "
                    f"برد / 🎮 {T.fa_num(r['games_played'])}"
                )
            txt = "🏆 <b>برترین بازیکنان</b>\n" + T.LINE + "\n" + "\n".join(lines)
        else:
            txt = "هنوز بازی‌ای ثبت نشده است."
        await q.answer()
        await q.edit_message_text(
            txt, parse_mode=ParseMode.HTML,
            reply_markup=kb.admin_keyboard(db.is_maintenance()),
        )

    elif action == "maint":
        new_state = not db.is_maintenance()
        db.set_maintenance(new_state)
        await q.answer("حالت تعمیر تغییر کرد.")
        status = ("🔧 حالت تعمیر: <b>روشن</b>" if new_state
                  else "🟢 حالت تعمیر: <b>خاموش</b>")
        await q.edit_message_text(
            T.ADMIN_PANEL_TITLE + "\n\n" + status,
            parse_mode=ParseMode.HTML,
            reply_markup=kb.admin_keyboard(new_state),
        )

    elif action == "broadcast":
        awaiting_broadcast.add(user.id)
        await q.answer()
        await q.edit_message_text(
            "📢 <b>پیام همگانی</b>\n\n"
            "حالا پیامی که می‌خواهید برای همهٔ کاربران ارسال شود را بفرستید "
            "(متن، عکس، و …).\n"
            "برای لغو، دستور /cancel_broadcast را بزنید.",
            parse_mode=ParseMode.HTML,
        )

    elif action == "refresh":
        await q.answer("بروزرسانی شد.")
        await q.edit_message_text(
            T.ADMIN_PANEL_TITLE, parse_mode=ParseMode.HTML,
            reply_markup=kb.admin_keyboard(db.is_maintenance()),
        )


async def on_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or user.id not in awaiting_broadcast:
        return
    awaiting_broadcast.discard(user.id)
    msg = update.message
    user_ids = db.get_all_user_ids()
    sent, failed = 0, 0
    await msg.reply_text(f"در حال ارسال به {T.fa_num(len(user_ids))} کاربر...")
    for uid in user_ids:
        try:
            await context.bot.copy_message(
                chat_id=uid, from_chat_id=msg.chat_id, message_id=msg.message_id
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await msg.reply_text(
        f"✅ ارسال شد به {T.fa_num(sent)} نفر.\n❌ ناموفق: {T.fa_num(failed)}"
    )


# ── راه‌اندازی ───────────────────────────────────────────────
def main():
    if not config.BOT_TOKEN or config.BOT_TOKEN.startswith("اینجا"):
        raise SystemExit(
            "لطفاً ابتدا BOT_TOKEN را در فایل config.py یا متغیر محیطی قرار دهید "
            "(آن را از @BotFather بگیرید)."
        )

    keep_alive.start()  # وب‌سرور سلامت برای Render

    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    # دستورها
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("endgame", cmd_endgame))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("cancel_broadcast", cmd_cancel_broadcast))

    # کال‌بک‌ها
    app.add_handler(CallbackQueryHandler(cb_checkjoin, pattern=r"^checkjoin$"))
    app.add_handler(CallbackQueryHandler(cb_newdiff, pattern=r"^newdiff:"))
    app.add_handler(CallbackQueryHandler(cb_botdiff, pattern=r"^botdiff:"))
    app.add_handler(CallbackQueryHandler(cb_join, pattern=r"^join$"))
    app.add_handler(CallbackQueryHandler(cb_startgame, pattern=r"^startgame$"))
    app.add_handler(CallbackQueryHandler(cb_cancel, pattern=r"^cancel$"))
    app.add_handler(CallbackQueryHandler(cb_roll, pattern=r"^roll$"))
    app.add_handler(CallbackQueryHandler(cb_vsbot, pattern=r"^vsbot$"))
    app.add_handler(CallbackQueryHandler(cb_help, pattern=r"^help$"))
    app.add_handler(CallbackQueryHandler(cb_admin, pattern=r"^admin:"))

    # دریافت پیامِ پیام‌همگانی (فقط در پیوی و غیر دستوری)
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND, on_admin_message
        )
    )

    log.info("ربات مار و پله شروع به کار کرد...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
