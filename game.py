# -*- coding: utf-8 -*-
"""
منطق بازی مار و پله:
- ساخت تصادفی و معتبرِ مار و نردبان برای هر اندازه زمین
- کلاس‌های Player و Game
- نمایش زمین به‌صورت «جدول متنی خانه‌به‌خانه» (بدون تصویر)
"""

import random

from config import DIFFICULTIES, MAX_PLAYERS, ROLL_AGAIN_ON_SIX


def generate_board(size, num_snakes, num_ladders):
    """
    ساخت تصادفیِ مار و نردبان بدون تداخل.
    - نردبان: از خانهٔ پایین به خانهٔ بالاتر
    - مار: از خانهٔ بالا به خانهٔ پایین‌تر
    خانه‌های ۱ و آخر همیشه خالی می‌مانند.
    """
    occupied = {1, size}
    ladders = {}
    snakes = {}
    min_gap = max(3, size // 20)

    tries = 0
    while len(ladders) < num_ladders and tries < 3000:
        tries += 1
        bottom = random.randint(2, size - 2)
        top = random.randint(bottom + 1, size - 1)
        if bottom in occupied or top in occupied:
            continue
        if top - bottom < min_gap:
            continue
        ladders[bottom] = top
        occupied.add(bottom)
        occupied.add(top)

    tries = 0
    while len(snakes) < num_snakes and tries < 3000:
        tries += 1
        head = random.randint(3, size - 1)
        tail = random.randint(1, head - 1)
        if head in occupied or tail in occupied:
            continue
        if head - tail < min_gap:
            continue
        snakes[head] = tail
        occupied.add(head)
        occupied.add(tail)

    return snakes, ladders


class Player:
    def __init__(self, user_id, name, color_index, is_bot=False):
        self.user_id = user_id
        self.name = name
        self.color_index = color_index
        self.is_bot = is_bot
        self.pos = 0          # ۰ یعنی هنوز وارد زمین نشده
        self.finished = False


class Game:
    def __init__(self, chat_id, difficulty, creator_id):
        cfg = DIFFICULTIES[difficulty]
        self.chat_id = chat_id
        self.difficulty = difficulty
        self.cols = cfg["cols"]
        self.rows = cfg["rows"]
        self.size = self.cols * self.rows
        self.snakes, self.ladders = generate_board(
            self.size, cfg["snakes"], cfg["ladders"]
        )
        self.players = []
        self.turn_index = 0
        self.state = "lobby"        # lobby | playing | finished
        self.creator_id = creator_id
        self.winner = None
        self.vs_bot = False
        self.message_id = None      # شناسهٔ پیام زمین برای حذف/ارسال دوباره

    # ── مدیریت بازیکنان ──────────────────────────────────────
    def has_player(self, user_id):
        return any(p.user_id == user_id for p in self.players)

    def add_player(self, user_id, name, is_bot=False):
        if self.has_player(user_id):
            return False
        if len(self.players) >= MAX_PLAYERS:
            return False
        color_index = len(self.players) % 6
        self.players.append(Player(user_id, name, color_index, is_bot))
        return True

    def current_player(self):
        if not self.players:
            return None
        return self.players[self.turn_index % len(self.players)]

    # ── منطق حرکت ───────────────────────────────────────────
    def _apply_move(self, pos, steps):
        new = pos + steps
        event = None
        if new > self.size:
            new = self.size - (new - self.size)   # برخورد به انتها و برگشت
        if new in self.ladders:
            new = self.ladders[new]
            event = "ladder"
        elif new in self.snakes:
            new = self.snakes[new]
            event = "snake"
        return new, event

    def roll_and_move(self, dice=None):
        """
        تاس می‌اندازد و مهرهٔ بازیکن فعلی را حرکت می‌دهد.
        خروجی یک دیکشنری شامل جزئیات نوبت است.
        """
        player = self.current_player()
        if dice is None:
            dice = random.randint(1, 6)
        old = player.pos
        new, event = self._apply_move(player.pos, dice)
        player.pos = new

        won = (new == self.size)
        if won:
            player.finished = True
            self.state = "finished"
            self.winner = player

        again = (ROLL_AGAIN_ON_SIX and dice == 6 and not won)
        if not again and not won:
            self.turn_index = (self.turn_index + 1) % len(self.players)

        return {
            "player": player,
            "dice": dice,
            "old": old,
            "new": new,
            "event": event,
            "won": won,
            "again": again,
        }


# ── نمایش متنیِ زمین (خانه‌به‌خانه) ───────────────────────────
def board_grid(game):
    """
    صفحهٔ بازی به‌صورت جدول ایموجی (مارپیچی، خانهٔ ۱ پایین-چپ):
      • عددِ فارسیِ خانه‌های معمولی
      • 🪜 پای نردبان، 🐍 سرِ مار، 🏁 خانهٔ پایان
      • 🔴🔵🟢🟠🟣🟤 جای بازیکن‌ها (👥 اگر چند نفر روی یک خانه)
    کاراکتر LRM (\u200e) ابتدای هر خط، چینش را چپ‌به‌راست نگه می‌دارد.
    """
    from texts import fa_num
    player_emojis = ["🔴", "🔵", "🟢", "🟠", "🟣", "🟤"]
    cols, rows, size = game.cols, game.rows, game.size

    occ = {}
    for i, p in enumerate(game.players):
        if p.pos >= 1:
            occ.setdefault(p.pos, []).append(i)
    ladder_bottoms = set(game.ladders.keys())
    snake_heads = set(game.snakes.keys())

    width = max(2, len(fa_num(size)))
    out = []
    for r in range(rows - 1, -1, -1):       # از بالا به پایین چاپ می‌کنیم
        cells = []
        for c in range(cols):
            cc = c if r % 2 == 0 else (cols - 1 - c)
            n = r * cols + cc + 1
            if n in occ:                                   # بازیکن (اولویت اول)
                idxs = occ[n]
                if len(idxs) == 1:
                    tok = player_emojis[game.players[idxs[0]].color_index % 6]
                else:
                    tok = "👥"
            elif n == size:                                # خانهٔ پایان
                tok = "🏁"
            elif n in ladder_bottoms:                      # پای نردبان
                tok = "🪜"
            elif n in snake_heads:                         # سرِ مار
                tok = "🐍"
            else:
                tok = fa_num(n)
            cells.append(tok.rjust(width))
        out.append("\u200e" + " ".join(cells))
    return "\n".join(out)
