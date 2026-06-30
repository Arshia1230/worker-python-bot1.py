# database.py
import sqlite3
from config import DB_NAME, OWNER_ID

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0
        )
    ''')
    
    # جدول ادمین‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # جدول اسپانسرها (جوین اجباری)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sponsors (
            channel_id INTEGER PRIMARY KEY,
            invite_link TEXT,
            name TEXT
        )
    ''')
    
    # جدول بازی‌های فعال
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            p1_id INTEGER,
            p2_id INTEGER,
            p1_pos INTEGER DEFAULT 1,
            p2_pos INTEGER DEFAULT 1,
            turn INTEGER,
            message_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

# دستورات مدیریت کاربران
def register_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

# دستورات مدیریت ادمین‌ها
def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def add_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# دستورات مدیریت اسپانسرها
def get_sponsors():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, invite_link, name FROM sponsors')
    sponsors = cursor.fetchall()
    conn.close()
    return sponsors

def add_sponsor(channel_id, invite_link, name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO sponsors (channel_id, invite_link, name) VALUES (?, ?, ?)', (channel_id, invite_link, name))
    conn.commit()
    conn.close()

def remove_sponsor(channel_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sponsors WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

# مدیریت منطق بازی در دیتابیس
def create_game(p1_id, p2_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO active_games (p1_id, p2_id, turn) VALUES (?, ?, ?)', (p1_id, p2_id, p1_id))
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return game_id

def get_game(game_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT p1_id, p2_id, p1_pos, p2_pos, turn, message_id FROM active_games WHERE game_id = ?', (game_id,))
    game = cursor.fetchone()
    conn.close()
    return game

def update_game(game_id, p1_pos, p2_pos, turn, message_id=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if message_id:
        cursor.execute('UPDATE active_games SET p1_pos = ?, p2_pos = ?, turn = ?, message_id = ? WHERE game_id = ?', (p1_pos, p2_pos, turn, message_id, game_id))
    else:
        cursor.execute('UPDATE active_games SET p1_pos = ?, p2_pos = ?, turn = ? WHERE game_id = ?', (p1_pos, p2_pos, turn, game_id))
    conn.commit()
    conn.close()

def end_game(game_id, winner_id, loser_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET wins = wins + 1, games_played = games_played + 1 WHERE user_id = ?', (winner_id,))
    cursor.execute('UPDATE users SET losses = losses + 1, games_played = games_played + 1 WHERE user_id = ?', (loser_id,))
    cursor.execute('DELETE FROM active_games WHERE game_id = ?', (game_id,))
    conn.commit()
    conn.close()
