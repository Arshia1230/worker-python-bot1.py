# -*- coding: utf-8 -*-
"""
وب‌سرور کوچک برای Render.

سرویس‌های رایگان Render اگر پورتی باز نباشد یا ترافیکی نیاید، بعد از حدود
۱۵ دقیقه به خواب می‌روند. این ماژول:
  ۱) یک وب‌سرور سبک روی پورت $PORT باز می‌کند (تا Render سرویس را «وب» ببیند).
  ۲) هر چند دقیقه به آدرس خود ربات یک درخواست می‌زند (Self-Ping).

برای بیدار ماندن قطعی، بهتر است یک سرویس بیرونی مثل UptimeRobot هم هر
۵ تا ۱۰ دقیقه آدرس سرویس را صدا بزند (در README توضیح داده شده).
"""

import os
import time
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from urllib.request import urlopen
except Exception:
    urlopen = None

log = logging.getLogger("keep_alive")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("ربات مار و پله فعال است ✅".encode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        # خاموش‌کردن لاگ پرحجمِ درخواست‌ها
        pass


def _serve():
    port = int(os.environ.get("PORT", "10000"))
    try:
        srv = HTTPServer(("0.0.0.0", port), _Handler)
    except Exception as e:
        log.warning("اجرای وب‌سرور سلامت ممکن نشد: %s", e)
        return
    log.info("وب‌سرور سلامت روی پورت %s بالا آمد.", port)
    srv.serve_forever()


def _self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("SELF_URL")
    if not url or urlopen is None:
        return
    while True:
        time.sleep(600)  # هر ۱۰ دقیقه
        try:
            urlopen(url, timeout=20)
            log.info("Self-ping انجام شد.")
        except Exception:
            pass


def start():
    """راه‌اندازی وب‌سرور و Self-Ping در نخ‌های جداگانه."""
    threading.Thread(target=_serve, daemon=True).start()
    threading.Thread(target=_self_ping, daemon=True).start()
