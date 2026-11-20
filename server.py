from collections import deque
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
from threading import BoundedSemaphore, Lock
import time
from urllib.parse import unquote, urlsplit

import learning
import mail_delivery
import settings
import store


STATIC = settings.ROOT / "dist"
COOKIE = "practice_session"
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)
mimetypes.add_type("font/woff", ".woff")

login_lock = Lock()
active_logins = BoundedSemaphore(4)
attempts = {}


def check_login_rate(address):
    key = settings.normalize_address(address) or ""
    moment = time.monotonic()
    with login_lock:
        for saved_key, queue in list(attempts.items()):
            while queue and moment - queue[0] > 60:
                queue.popleft()
            if not queue:
                del attempts[saved_key]
        if key not in attempts and len(attempts) >= 512:
            raise store.Problem(429, "Слишком много попыток. Повторите через минуту.")
        queue = attempts.setdefault(key, deque())
        if len(queue) >= 8:
            raise store.Problem(429, "Слишком много попыток. Повторите через минуту.")
        queue.append(moment)


def keys(data, *names):
    if not isinstance(data, dict) or data.keys() != set(names):
        raise store.Problem(400, "Проверьте поля запроса.")


def cookie(token, age):
    attributes = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}"
    return attributes + ("; Secure" if settings.SECURE_COOKIE else "")


class Handler(BaseHTTPRequestHandler):
    server_version = "Practika"
    sys_version = ""

    def setup(self):
        self.request.settimeout(12)
        super().setup()

    def log_message(self, format, *args):
        # Не записываем URL, заголовки, тела запросов и содержимое приглашений.
        return

    def respond(self, status, payload, content_type, set_cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        if settings.SECURE_COOKIE:
            self.send_header("Strict-Transport-Security", "max-age=86400")
        if set_cookie is not None:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def json(self, status, payload, set_cookie=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.respond(status, body, "application/json; charset=utf-8", set_cookie)

    def verify_host(self):
        if self.headers.get("Host", "").lower() != settings.AUTHORITY:
            raise store.Problem(421, "Откройте портал по настроенному адресу.")

    def token(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return ""
        value = cookies[COOKIE].value if COOKIE in cookies else ""
        return value if len(value) == 43 and value.isascii() else ""

    def role(self, role):
        account = store.session(self.token())
        if not account:
            raise store.Problem(401, "Войдите в портал.")
        if account["role"] != role:
            raise store.Problem(403, "У этой учётной записи нет доступа.")
        return account

    def json_body(self):
        origin = self.headers.get("Origin")
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if (origin and origin != settings.ORIGIN) or (fetch_site and fetch_site != "same-origin"):
            raise store.Problem(403, "Откройте приложение напрямую.")
        if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
            raise store.Problem(400, "Ожидается запрос JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError
            return json.loads(raw.decode("utf-8"))
        except (ValueError, RecursionError, TimeoutError):
            raise store.Problem(400, "Проверьте формат и размер запроса.") from None

    def run(self, method):
        try:
            method()
        except store.Problem as error:
            self.json(error.code, {"error": error.message})
        except sqlite3.Error:
            self.json(503, {"error": "Отчёты временно недоступны. Попробуйте позже."})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return

    def do_HEAD(self):
        self.run(self.read_request)

    def do_GET(self):
        self.run(self.read_request)

    def do_POST(self):
        self.run(self.write_request)

    def read_request(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            with store.database() as database:
                database.execute("SELECT 1 FROM accounts LIMIT 1")
            return self.json(200, {"status": "ok"})
        self.verify_host()
        if path == "/api/session":
            return self.json(200, {"user": store.session(self.token())})
        if path == "/api/admin":
            self.role("admin")
            return self.json(200, {
                **store.admin_data(), "scenarios": learning.catalogue(),
                "mail": mail_delivery.info(), "domain": settings.DOMAIN_NAME,
            })
        if path == "/api/lessons":
            account = self.role("participant")
            return self.json(200, {"lessons": store.participant_data(account["id"])})
        if path not in {"/", "/styles.css", "/app.js"} and not path.startswith("/assets/"):
            raise store.Problem(404, "Страница не найдена.")
        asset = (STATIC / ("index.html" if path == "/" else unquote(path).lstrip("/"))).resolve()
        if not asset.is_relative_to(STATIC) or not asset.is_file():
            raise store.Problem(404, "Страница не найдена.")
        content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        self.respond(HTTPStatus.OK, asset.read_bytes(), content_type)

    def write_request(self):
        self.verify_host()
        path = self.path
        data = self.json_body()
        if path == "/api/login":
            keys(data, "email", "password")
            check_login_rate(data["email"])
            if not active_logins.acquire(blocking=False):
                raise store.Problem(429, "Подождите немного и попробуйте снова.")
            try:
                token = store.login(data["email"], data["password"])
            finally:
                active_logins.release()
            return self.json(200, {"user": store.session(token)}, cookie(token, store.SESSION_SECONDS))
        if path == "/api/logout":
            keys(data)
            store.end_session(self.token())
            return self.json(200, {"user": None}, cookie("", 0))
        if path == "/api/admin/participants":
            self.role("admin")
            keys(data, "name", "email", "department")
            return self.json(201, store.create_participant(data))
        if path == "/api/admin/campaigns":
            self.role("admin")
            keys(data, "name", "scenario", "participants")
            return self.json(201, store.create_campaign(data))
        if path == "/api/admin/invitation":
            self.role("admin")
            keys(data, "assignment_id")
            if not mail_delivery.CONFIGURED:
                raise store.Problem(503, "Подключение к почтовому серверу ещё не настроено.")
            assignment_id = store.id_field(data["assignment_id"])
            recipient, message_id = store.claim_invitation(assignment_id)
            outcome = mail_delivery.send_invitation(recipient, message_id)
            return self.json(200, store.close_invitation(assignment_id, message_id, outcome))
        if path == "/api/lesson/start":
            account = self.role("participant")
            keys(data, "assignment_id")
            return self.json(200, store.record_practice(account["id"], store.id_field(data["assignment_id"])))
        if path == "/api/lesson/answer":
            account = self.role("participant")
            keys(data, "assignment_id", "answer")
            if type(data["answer"]) is not int:
                raise store.Problem(400, "Выберите один ответ.")
            return self.json(200, store.record_practice(account["id"], store.id_field(data["assignment_id"]), data["answer"]))
        raise store.Problem(404, "Действие не найдено.")


if __name__ == "__main__":
    store.initialize()
    bind = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    with ThreadingHTTPServer((bind, port), Handler) as server:
        print(f"Практика ИБ слушает порт {port}", flush=True)
        server.serve_forever()
