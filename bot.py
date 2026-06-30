# bot.py
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from config import TOKEN
import database
import keyboards
import texts
import game

matchmaking_queue = []

async def check_user_sponsors(bot, user_id):
    sponsors = database.get_sponsors()
    for channel_id, invite_link, name in sponsors:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username)
    
    if not await check_user_sponsors(context.bot, user.id):
        sponsors = database.get_sponsors()
        await update.message.reply_text(texts.NOT_SUBSCRIBED, reply_markup=keyboards.get_sponsor_keyboard(sponsors), parse_mode="HTML")
        return
        
    await update.message.reply_text(texts.START_MESSAGE, reply_markup=keyboards.get_start_keyboard(), parse_mode="HTML")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not database.is_admin(user_id):
        return
    context.user_data.clear()
    await update.message.reply_text(texts.ADMIN_WELCOME, reply_markup=keyboards.get_admin_keyboard(), parse_mode="HTML")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data.startswith("admin_") or query.data.endswith("_req") or query.data in ["list_sponsors", "back_to_admin"]:
        if not database.is_admin(user_id):
            return
            
    if query.data == "check_join":
        if await check_user_sponsors(context.bot, user_id):
            await query.message.edit_text(texts.JOIN_CONFIRMATION, reply_markup=keyboards.get_start_keyboard())
        else:
            await query.answer("❌ شما هنوز عضو کانال‌های اسپانسر نشده‌اید!", show_alert=True)
            
    elif query.data == "find_match":
        if user_id in matchmaking_queue:
            return
        if matchmaking_queue:
            opponent_id = matchmaking_queue.pop(0)
            if opponent_id == user_id:
                matchmaking_queue.append(user_id)
                return
                
            game_id = database.create_game(user_id, opponent_id)
            initial_board = game.render_board(1, 1) + "\n🎮 بازی آغاز شد! نوبت بازیکن اول است."
            
            msg1 = await context.bot.send_message(chat_id=user_id, text=initial_board, reply_markup=keyboards.get_game_keyboard(game_id), parse_mode="HTML")
            msg2 = await context.bot.send_message(chat_id=opponent_id, text=initial_board, reply_markup=keyboards.get_game_keyboard(game_id), parse_mode="HTML")
            
            database.update_game(game_id, 1, 1, user_id, msg1.message_id, msg2.message_id)
        else:
            matchmaking_queue.append(user_id)
            await query.message.edit_text("⏳ در حال جستجوی حریف آنلاین... لطفاً منتظر بمانید.")
            
    elif query.data.startswith("roll_"):
        game_id = int(query.data.split("_")[1])
        await game.handle_player_move(context, game_id, user_id)
        
    elif query.data == "back_to_admin":
        context.user_data.clear()
        await query.message.edit_text(texts.ADMIN_WELCOME, reply_markup=keyboards.get_admin_keyboard(), parse_mode="HTML")
        
    elif query.data == "admin_sponsors":
        await query.message.edit_text("📢 بخش مدیریت اسپانسرها (جوین اجباری):", reply_markup=keyboards.get_admin_sponsors_keyboard())
        
    elif query.data == "admin_users":
        await query.message.edit_text("👤 بخش مدیریت ادمین‌های ربات:", reply_markup=keyboards.get_admin_users_keyboard())
        
    elif query.data == "admin_stats":
        total_users = database.get_total_users_count()
        await query.message.edit_text(f"📊 <b>آمار کلی ربات مار و پله:</b>\n\n👥 تعداد کل کاربران ثبت‌شده: {total_users}", reply_markup=keyboards.get_admin_keyboard(), parse_mode="HTML")
        
    elif query.data == "add_sponsor_req":
        context.user_data['state'] = 'awaiting_sponsor_data'
        await query.message.edit_text("📥 لطفاً اطلاعات کانال اسپانسر را با فرمت زیر ارسال کنید:\n\n<code>آیدی_عددی_کانال|لینک_جوین|نام_کانال</code>\n\nمثال:\n<code>-10012345678|https://t.me/joinchat/...|کانال اصلی</code>", parse_mode="HTML")
        
    elif query.data == "remove_sponsor_req":
        context.user_data['state'] = 'awaiting_sponsor_remove'
        await query.message.edit_text("🗑 لطفاً آیدی عددی کانال اسپانسری که می‌خواهید حذف کنید را بفرستید:")
        
    elif query.data == "list_sponsors":
        sponsors = database.get_sponsors()
        if not sponsors:
            await query.message.edit_text("📜 هیچ کانال اسپانسری تنظیم نشده است.", reply_markup=keyboards.get_admin_sponsors_keyboard())
            return
        text = "📜 <b>لیست اسپانسرهای فعلی:</b>\n\n"
        for c_id, link, name in sponsors:
            text += f"🔹 <b>{name}</b>\nآیدی: <code>{c_id}</code>\nلینک: {link}\n\n"
        await query.message.edit_text(text, reply_markup=keyboards.get_admin_sponsors_keyboard(), parse_mode="HTML")
        
    elif query.data == "add_admin_req":
        context.user_data['state'] = 'awaiting_admin_add'
        await query.message.edit_text("📥 لطفاً آیدی عددی کاربر مورد نظر را جهت ارتقا به ادمین ارسال کنید:")
        
    elif query.data == "remove_admin_req":
        context.user_data['state'] = 'awaiting_admin_remove'
        await query.message.edit_text("🗑 لطفاً آیدی عددی ادمینی که می‌خواهید عزل کنید را ارسال کنید:")

async def handle_admin_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not database.is_admin(user_id) or 'state' not in context.user_data:
        return
        
    state = context.user_data['state']
    text = update.message.text.strip()
    
    if state == 'awaiting_sponsor_data':
        try:
            parts = text.split('|')
            if len(parts) != 3:
                await update.message.reply_text("❌ فرمت ارسالی اشتباه است! باید شامل دو خط عمودی باشد. مجدداً تلاش کنید.")
                return
            chan_id = int(parts[0].strip())
            link = parts[1].strip()
            name = parts[2].strip()
            
            database.add_sponsor(chan_id, link, name)
            context.user_data.clear()
            await update.message.reply_text("✅ کانال اسپانسر با موفقیت اضافه/بروزرسانی شد.", reply_markup=keyboards.get_admin_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ خطایی رخ داد: {str(e)}")
            
    elif state == 'awaiting_sponsor_remove':
        try:
            chan_id = int(text)
            database.remove_sponsor(chan_id)
            context.user_data.clear()
            await update.message.reply_text("✅ کانال اسپانسر مورد نظر حذف شد.", reply_markup=keyboards.get_admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک آیدی عددی معتبر وارد کنید.")
            
    elif state == 'awaiting_admin_add':
        try:
            target_id = int(text)
            database.add_admin(target_id)
            context.user_data.clear()
            await update.message.reply_text(f"✅ کاربر {target_id} به لیست ادمین‌ها اضافه شد.", reply_markup=keyboards.get_admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ لطفاً آیدی عددی معتبر وارد کنید.")
            
    elif state == 'awaiting_admin_remove':
        try:
            target_id = int(text)
            database.remove_admin(target_id)
            context.user_data.clear()
            await update.message.reply_text(f"✅ کاربر {target_id} از لیست ادمین‌ها حذف شد.", reply_markup=keyboards.get_admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ لطفاً آیدی عددی معتبر وارد کنید.")

def main():
    database.init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text_inputs))
    
    print("ربات مار و پله با موفقیت روشن شد و در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
