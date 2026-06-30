# game.py
import asyncio
import random
from telegram.error import BadRequest
from database import get_game, update_game, end_game
from keyboards import get_game_keyboard

# نقشه مارها و پله‌ها
SNAKES_AND_LADDERS = {
    # پله‌ها (صعود)
    3: 21, 8: 30, 28: 84, 58: 77, 75: 86, 80: 99,
    # مارها (سقوط)
    17: 4, 52: 29, 57: 38, 62: 22, 88: 18, 95: 51, 97: 79
}

def render_board(p1_pos, p2_pos):
    """ساخت یک صفحه نمایشی تمیز و مینیمال بر اساس تم سفید و نارنجی"""
    board_str = "🧱 <b>صفحه بازی مار و پله</b> 🧱\n\n"
    
    # ساخت یک گرید ساده بصورت ردیفی برای نمایش جذاب‌تر موقعیت‌ها
    for row in range(9, -1, -1):
        row_str = ""
        for col in range(1, 11):
            cell = row * 10 + col
            if cell == p1_pos and cell == p2_pos:
                row_str += "🟣"  # هردو مهره در یک خانه
            elif cell == p1_pos:
                row_str += "🔴"  # بازیکن اول
            elif cell == p2_pos:
                row_str += "🟠"  # بازیکن دوم (اسپانسر/رقیب)
            elif cell in SNAKES_AND_LADDERS:
                row_str += "🪜" if SNAKES_AND_LADDERS[cell] > cell else "🐍"
            else:
                row_str += "⬜"
        board_str += row_str + "\n"
        
    board_str += f"\n🔴 موقعیت بازیکن اول: {p1_pos}"
    board_str += f"\n🟠 موقعیت بازیکن دوم: {p2_pos}\n"
    return board_str

async def handle_player_move(context, game_id, player_id):
    game = get_game(game_id)
    if not game:
        return
        
    p1_id, p2_id, p1_pos, p2_pos, turn, message_id = game
    
    if player_id != turn:
        return # نوبت این بازیکن نیست
        
    dice = random.randint(1, 6)
    is_p1 = (player_id == p1_id)
    current_pos = p1_pos if is_p1 else p2_pos
    target_pos = current_pos + dice
    
    if target_pos > 100:
        # تاس بیشتر از خانه ۱۰۰ آمده و بازیکن نمی‌تواند حرکت کند
        next_turn = p2_id if is_p1 else p1_id
        update_game(game_id, p1_pos, p2_pos, next_turn)
        await context.bot.edit_message_text(
            chat_id=player_id,
            message_id=message_id,
            text=render_board(p1_pos, p2_pos) + f"\n🎲 تاس: {dice}\n⚠️ عدد تاس بیش از حد نیاز بود! نوبت بازیکن بعدی.",
            reply_markup=get_game_keyboard(game_id),
            parse_mode="HTML"
        )
        return

    # انیمیشن حرکت پله‌به‌پله مهره
    for step in range(current_pos + 1, target_pos + 1):
        if is_p1:
            temp_p1, temp_p2 = step, p2_pos
        else:
            temp_p1, temp_p2 = p1_pos, step
            
        board_html = render_board(temp_p1, temp_p2) + f"\n🎲 تاس ریخته شد: {dice}\n🏃‍♂️ مهره در حال حرکت است..."
        try:
            await context.bot.edit_message_text(
                chat_id=p1_id, message_id=message_id, text=board_html, parse_mode="HTML"
            )
            await context.bot.edit_message_text(
                chat_id=p2_id, message_id=message_id, text=board_html, parse_mode="HTML"
            )
        except BadRequest:
            pass
        await asyncio.sleep(0.5) # تاخیر نیم‌ثانیه‌ای انیمیشن

    # بررسی برخورد با مار یا پله در خانه نهایی
    final_pos = target_pos
    event_text = ""
    if final_pos in SNAKES_AND_LADDERS:
        land_pos = SNAKES_AND_LADDERS[final_pos]
        if land_pos > final_pos:
            event_text = f"\n🪜 فوق‌العاده بود! از نردبان بالا رفتی به خانه {land_pos}!"
        else:
            event_text = f"\n🐍 اوه نه! مار تو را نیش زد و به خانه {land_pos} سقوط کردی!"
        final_pos = land_pos
        
        # نمایش موقعیت نهایی پس از مار یا پله
        if is_p1:
            p1_pos = final_pos
        else:
            p2_pos = final_pos
            
        await asyncio.sleep(0.6)
        board_html = render_board(p1_pos, p2_pos) + event_text
        try:
            await context.bot.edit_message_text(chat_id=p1_id, message_id=message_id, text=board_html, parse_mode="HTML")
            await context.bot.edit_message_text(chat_id=p2_id, message_id=message_id, text=board_html, parse_mode="HTML")
        except BadRequest:
            pass
    else:
        if is_p1:
            p1_pos = final_pos
        else:
            p2_pos = final_pos

    # بررسی شرایط برد
    if final_pos == 100:
        winner = player_id
        loser = p2_id if is_p1 else p1_id
        end_game(game_id, winner, loser)
        win_msg = f"🎉 تبریک! بازیکن <a href='tg://user?id={winner}'>{winner}</a> بازی را برد و به خانه ۱00 رسید!"
        try:
            await context.bot.send_message(chat_id=p1_id, text=win_msg, parse_mode="HTML")
            await context.bot.send_message(chat_id=p2_id, text=win_msg, parse_mode="HTML")
        except BadRequest:
            pass
        return

    # تعویض نوبت
    next_turn = p2_id if is_p1 else p1_id
    update_game(game_id, p1_pos, p2_pos, next_turn)
    
    turn_msg = f"\n🎲 تاس: {dice}\n🎯 اکنون نوبت بازیکن بعدی است."
    try:
        await context.bot.edit_message_text(
            chat_id=p1_id, message_id=message_id, text=render_board(p1_pos, p2_pos) + turn_msg,
            reply_markup=get_game_keyboard(game_id), parse_mode="HTML"
        )
        await context.bot.edit_message_text(
            chat_id=p2_id, message_id=message_id, text=render_board(p1_pos, p2_pos) + turn_msg,
            reply_markup=get_game_keyboard(game_id), parse_mode="HTML"
        )
    except BadRequest:
        pass
