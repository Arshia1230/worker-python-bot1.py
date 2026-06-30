# game.py
import asyncio
import random
from telegram.error import BadRequest
from database import get_game, update_game, end_game
from keyboards import get_game_keyboard

SNAKES_AND_LADDERS = {
    3: 21, 8: 30, 28: 84, 58: 77, 75: 86, 80: 99,   # نردبان‌ها
    17: 4, 52: 29, 57: 38, 62: 22, 88: 18, 95: 51, 97: 79  # مارها
}

def render_board(p1_pos, p2_pos):
    board_str = "🧱 <b>صفحه بازی آنلاین مار و پله</b> 🧱\n\n"
    
    for row in range(9, -1, -1):
        row_str = ""
        for col in range(1, 11):
            if row % 2 == 1:
                cell = (row * 10) + (11 - col)
            else:
                cell = (row * 10) + col
                
            if cell == p1_pos and cell == p2_pos:
                row_str += "🟣"  # هر دو در یک خانه
            elif cell == p1_pos:
                row_str += "🔴"  # بازیکن اول
            elif cell == p2_pos:
                row_str += "🟠"  # بازیکن دوم
            elif cell in SNAKES_AND_LADDERS:
                row_str += "🪜" if SNAKES_AND_LADDERS[cell] > cell else "🐍"
            else:
                row_str += "⬜"
        board_str += row_str + "\n"
        
    board_str += f"\n🔴 بازیکن اول: خانه {p1_pos}"
    board_str += f"\n🟠 بازیکن دوم: خانه {p2_pos}\n"
    return board_str

async def handle_player_move(context, game_id, player_id):
    game = get_game(game_id)
    if not game:
        return
        
    p1_id, p2_id, p1_pos, p2_pos, turn, p1_msg_id, p2_msg_id = game
    
    if player_id != turn:
        return
        
    dice = random.randint(1, 6)
    is_p1 = (player_id == p1_id)
    current_pos = p1_pos if is_p1 else p2_pos
    target_pos = current_pos + dice
    
    if target_pos > 100:
        next_turn = p2_id if is_p1 else p1_id
        update_game(game_id, p1_pos, p2_pos, next_turn)
        msg_text = render_board(p1_pos, p2_pos) + f"\n🎲 تاس ریخته شده: {dice}\n⚠️ عدد تاس بیشتر از خانه 100 است! تعویض نوبت."
        for c_id, m_id in [(p1_id, p1_msg_id), (p2_id, p2_msg_id)]:
            try:
                await context.bot.edit_message_text(chat_id=c_id, message_id=m_id, text=msg_text, reply_markup=get_game_keyboard(game_id), parse_mode="HTML")
            except BadRequest: pass
        return

    # انیمیشن حرکت پله به پله (فریم به فریم) روی ال سی دی تلگرام
    for step in range(current_pos + 1, target_pos + 1):
        t_p1, t_p2 = (step, p2_pos) if is_p1 else (p1_pos, step)
        board_html = render_board(t_p1, t_p2) + f"\n🎲 تاس ریخته شده: {dice}\n🏃‍♂️ مهره شما در حال حرکت پله‌به‌پله است... (خانه {step})"
        
        for c_id, m_id in [(p1_id, p1_msg_id), (p2_id, p2_msg_id)]:
            try:
                await context.bot.edit_message_text(chat_id=c_id, message_id=m_id, text=board_html, parse_mode="HTML")
            except BadRequest: pass
        await asyncio.sleep(0.5)

    # بررسی برخورد با مار یا نردبان
    final_pos = target_pos
    if final_pos in SNAKES_AND_LADDERS:
        land_pos = SNAKES_AND_LADDERS[final_pos]
        event_str = f"\n🪜 نردبان شانس! از خانه {final_pos} پرتاب شدید به خانه {land_pos}!" if land_pos > final_pos else f"\n🐍 نیش مار تلخ! از خانه {final_pos} سقوط کردید به خانه {land_pos}!"
        final_pos = land_pos
        p1_pos, p2_pos = (final_pos, p2_pos) if is_p1 else (p1_pos, final_pos)
        
        await asyncio.sleep(0.4)
        board_html = render_board(p1_pos, p2_pos) + event_str
        for c_id, m_id in [(p1_id, p1_msg_id), (p2_id, p2_msg_id)]:
            try:
                await context.bot.edit_message_text(chat_id=c_id, message_id=m_id, text=board_html, parse_mode="HTML")
            except BadRequest: pass
    else:
        p1_pos, p2_pos = (final_pos, p2_pos) if is_p1 else (p1_pos, final_pos)

    # بررسی برنده شدن مسابقه
    if final_pos == 100:
        end_game(game_id, player_id, p2_id if is_p1 else p1_id)
        win_text = f"🎉 <b>تبریک! بازیکن {player_id} به خانه 100 رسید و برنده نهایی بازی شد!</b>"
        for c_id in [p1_id, p2_id]:
            try:
                await context.bot.send_message(chat_id=c_id, text=win_text, parse_mode="HTML")
            except BadRequest: pass
        return

    # جابجایی نوبت بازیکنان
    next_turn = p2_id if is_p1 else p1_id
    update_game(game_id, p1_pos, p2_pos, next_turn)
    turn_msg = render_board(p1_pos, p2_pos) + f"\n🎲 آخرین تاس: {dice}\n🎯 اکنون نوبت بازیکن <a href='tg://user?id={next_turn}'>{next_turn}</a> است."
    
    for c_id, m_id in [(p1_id, p1_msg_id), (p2_id, p2_msg_id)]:
        try:
            await context.bot.edit_message_text(chat_id=c_id, message_id=m_id, text=turn_msg, reply_markup=get_game_keyboard(game_id), parse_mode="HTML")
        except BadRequest: pass
