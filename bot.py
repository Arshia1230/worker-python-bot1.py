# bot.py
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from config import TOKEN
import database
import keyboards
import texts
import game

# صَف انتظار برای بازیکنان تصادفی
matchmaking_queue = []

async def check_user_sponsors(bot, user_id):
    """بررسی وضعیت عضویت کاربر در کانال‌های اسپانسر"""
    sponsors = database.get_sponsors()
    for channel_id, invite_link, name in sponsors:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False # در صورت وجود خطا فرض بر عدم عضویت است
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username)
    
    if not await check_user_sponsors(context.bot, user.id):
        sponsors = database.get_sponsors()
        await update.message.reply_text(texts.NOT_SUBSCRIBED, reply_markup=keyboards.get_sponsor_keyboard(sponsors))
        return
        
    await update.message.reply_text(texts.START_MESSAGE, reply_markup=keyboards.get_start_keyboard())

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not database.is_admin(user_id):
        return
    await update.message.reply_text(texts.ADMIN_WELCOME, reply_markup=keyboards.get_admin_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data == "check_join":
        if await check_user_sponsors(context.bot, user_id):
            await query.message.edit_text(texts.JOIN_CONFIRMATION, reply_markup=keyboards.get_start_keyboard())
        else:
            await query.answer("❌ شما هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)
            
    elif query.data == "find_match":
        if user_id in matchmaking_queue:
            return
            
        if matchmaking_queue:
            opponent_id = matchmaking_queue.pop(0)
            if opponent_id == user_id:
                matchmaking_queue.append(user_id)
                return
                
            # شروع بازی دو نفره
            game_id = database.create_game(user_id, opponent_id)
            initial_board = game.render_board(1, 1) + "\n🎮 بازی آغاز شد! نوبت بازیکن اول است."
            
            msg1 = await context.bot.send_message(chat_id=user_id, text=initial_board, reply_markup=keyboards.get_game_keyboard(game_id), parse_mode="HTML")
            msg2 = await context.bot.send_message(chat_id=opponent_id, text=initial_board, reply_markup=keyboards.get_game_keyboard(game_id), parse_mode="HTML")
            
            database.update_game(game_id, 1, 1, user_id, msg1.message_id)
        else:
            matchmaking_queue.append(user_id)
            await query.message.edit_text("⏳ در حال جستجوی حریف... لطفاً منتظر بمانید.")
            
    elif query.data.startswith("roll_"):
        game_id = int(query.data.split("_")[1])
        await game.handle_player_move(context, game_id, user_id)

def main():
    database.init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("ربات مار و پله با موفقیت روشن شد و در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
