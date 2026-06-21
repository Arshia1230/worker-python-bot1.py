# -*- coding: utf-8 -*-
"""
منطق بازی مار و پله:
- ساخت تصادفی و معتبرِ مار و نردبان برای هر اندازه زمین
- کلاس‌های Player و Game
- رسم تصویر زمین با Pillow (در صورت نبودِ Pillow، نمایش متنی)
"""

import io
import math
import random
from collections import defaultdict

from config import DIFFICULTIES, MAX_PLAYERS, ROLL_AGAIN_ON_SIX

# رنگ مهرهٔ بازیکن‌ها (تا ۶ نفر)
PLAYER_COLORS = [
    (220, 50, 50),    # قرمز
    (40, 110, 220),   # آبی
    (40, 170, 80),    # سبز
    (240, 150, 30),   # نارنجی
    (150, 60, 200),   # بنفش
    (120, 80, 40),    # قهوه‌ای
]


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
    min_gap = max(3, size // 20)  # حداقل اختلاف برای جلوگیری از مار/نردبان خیلی کوتاه

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
        color_index = len(self.players) % len(PLAYER_COLORS)
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


# ── رسم تصویر زمین ───────────────────────────────────────────
def render_board_image(game):
    """
    رسم زمین به‌صورت تصویر PNG و بازگرداندن بایت‌ها.
    اگر Pillow نصب نباشد None برمی‌گرداند تا از نمایش متنی استفاده شود.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    cols, rows, size = game.cols, game.rows, game.size
    cell = 64
    margin = 12
    W = cols * cell + margin * 2
    H = rows * cell + margin * 2

    img = Image.new("RGB", (W, H), (250, 248, 240))
    d = ImageDraw.Draw(img)

    def load_font(sz):
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(path, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    token_font = load_font(max(12, cell // 4))
    num_font = load_font(max(9, cell // 6))

    def cell_center(n):
        """مرکز خانه با شماره‌گذاری مارپیچی (۱ پایین-چپ، به سمت بالا)."""
        idx = n - 1
        r = idx // cols
        c = idx % cols
        if r % 2 == 1:
            c = cols - 1 - c
        x = margin + c * cell + cell / 2
        y = margin + (rows - 1 - r) * cell + cell / 2
        return x, y

    # خانه‌ها
    for n in range(1, size + 1):
        cx, cy = cell_center(n)
        x0, y0 = cx - cell / 2, cy - cell / 2
        x1, y1 = cx + cell / 2, cy + cell / 2
        light = ((n + (n - 1) // cols) % 2 == 0)
        base = (236, 231, 216) if light else (214, 224, 205)
        d.rectangle([x0, y0, x1, y1], fill=base, outline=(185, 180, 165))
        d.text((x0 + 4, y0 + 3), str(n), fill=(120, 115, 105), font=num_font)

    # خانهٔ آخر را برجسته کن
    cx, cy = cell_center(size)
    d.rectangle(
        [cx - cell / 2, cy - cell / 2, cx + cell / 2, cy + cell / 2],
        outline=(210, 170, 30), width=3,
    )

    # نردبان‌ها (سبز)
    for bottom, top in game.ladders.items():
        x0, y0 = cell_center(bottom)
        x1, y1 = cell_center(top)
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1
        ox, oy = -dy / length * 7, dx / length * 7
        d.line([x0 + ox, y0 + oy, x1 + ox, y1 + oy], fill=(60, 160, 70), width=4)
        d.line([x0 - ox, y0 - oy, x1 - ox, y1 - oy], fill=(60, 160, 70), width=4)
        steps = max(2, int(length // 22))
        for i in range(1, steps):
            t = i / steps
            rx, ry = x0 + dx * t, y0 + dy * t
            d.line([rx + ox, ry + oy, rx - ox, ry - oy], fill=(95, 195, 105), width=3)

    # مارها (قرمز)
    for head, tail in game.snakes.items():
        x0, y0 = cell_center(head)
        x1, y1 = cell_center(tail)
        d.line([x0, y0, x1, y1], fill=(205, 65, 65), width=6)
        d.ellipse([x0 - 9, y0 - 9, x0 + 9, y0 + 9], fill=(175, 40, 40))      # سر مار
        d.ellipse([x1 - 5, y1 - 5, x1 + 5, y1 + 5], fill=(225, 125, 125))    # دم مار

    # مهره‌ها (اگر چند بازیکن روی یک خانه باشند کنار هم می‌نشینند)
    groups = defaultdict(list)
    for i, p in enumerate(game.players):
        if p.pos >= 1:
            groups[p.pos].append((i, p))
    for pos, plist in groups.items():
        cx, cy = cell_center(pos)
        k = len(plist)
        for j, (i, p) in enumerate(plist):
            offx = (j - (k - 1) / 2) * 13
            color = PLAYER_COLORS[p.color_index % len(PLAYER_COLORS)]
            r = 11
            d.ellipse(
                [cx + offx - r, cy - r, cx + offx + r, cy + r],
                fill=color, outline=(255, 255, 255), width=2,
            )
            label = str(i + 1)
            try:
                bbox = d.textbbox((0, 0), label, font=token_font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = 6, 8
            d.text((cx + offx - tw / 2, cy - th / 2 - 1), label,
                   fill=(255, 255, 255), font=token_font)

    bio = io.BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return bio.getvalue()


def board_text(game):
    """نمایش متنی زمین (وقتی Pillow در دسترس نیست)."""
    from texts import fa_num
    lines = ["🎲 وضعیت زمین:"]
    for i, p in enumerate(game.players):
        pos = fa_num(p.pos) if p.pos > 0 else "شروع"
        name = "🤖 کامپیوتر" if p.is_bot else p.name
        lines.append(f"{fa_num(i + 1)}- {name} → خانه {pos}")
    lines.append("")
    if game.ladders:
        ll = "، ".join(f"{fa_num(b)}→{fa_num(t)}"
                       for b, t in sorted(game.ladders.items()))
        lines.append(f"🪜 نردبان‌ها: {ll}")
    if game.snakes:
        ss = "، ".join(f"{fa_num(h)}→{fa_num(t)}"
                       for h, t in sorted(game.snakes.items()))
        lines.append(f"🐍 مارها: {ss}")
    return "\n".join(lines)
