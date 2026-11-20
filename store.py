from contextlib import closing, contextmanager
from datetime import datetime, timezone
from email.utils import make_msgid
import hashlib
import hmac
import secrets
import sqlite3
import time

from learning import BY_ID, exercise
from settings import DATABASE, DOMAIN_NAME, normalize_address


SESSION_SECONDS = 8 * 60 * 60
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  department TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin', 'participant')),
  password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  digest TEXT PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY,
  campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  scenario_id TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  correct INTEGER CHECK(correct IN (0, 1)),
  mail_status TEXT NOT NULL DEFAULT 'pending',
  mail_attempt_at INTEGER,
  accepted_at TEXT,
  mail_id TEXT,
  UNIQUE(campaign_id, account_id)
);
"""
ASSIGNMENT_COLUMNS = """
  a.id, a.campaign_id, a.account_id, a.scenario_id,
  a.started_at, a.completed_at, a.correct, a.mail_status, a.mail_attempt_at,
  a.accepted_at, a.mail_id
"""


class Problem(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@contextmanager
def database(write=False):
    with closing(sqlite3.connect(DATABASE, timeout=5)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db


def initialize():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)


def text_field(value, label, maximum, minimum=1):
    value = value.strip() if isinstance(value, str) else ""
    if not minimum <= len(value) <= maximum or not value.isprintable():
        raise Problem(400, f"Проверьте поле «{label}».")
    return value


def address_field(value):
    address = normalize_address(value)
    if not address:
        raise Problem(400, "Введите адрес внутреннего почтового домена.")
    return address


def id_field(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise Problem(400, "Выберите запись из списка.")
    return value


def derive_password(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32).hex()


def password_hash(password):
    salt = secrets.token_bytes(16)
    return f"{salt.hex()}:{derive_password(password, salt)}"


def valid_password(password, hash_value):
    salt, expected = hash_value.split(":")
    return hmac.compare_digest(expected, derive_password(password, bytes.fromhex(salt)))


def session_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_admin(raw_address):
    address = address_field(raw_address)
    password = secrets.token_urlsafe(18)
    encoded = password_hash(password)
    with database(write=True) as db:
        account = db.execute("SELECT id, role FROM accounts WHERE email = ?", (address,)).fetchone()
        if account and account["role"] != "admin":
            raise Problem(409, "Этот адрес уже занимает учётная запись сотрудника.")
        if account:
            db.execute("UPDATE accounts SET password_hash = ? WHERE id = ?", (encoded, account["id"]))
            db.execute("DELETE FROM sessions WHERE account_id = ?", (account["id"],))
        else:
            db.execute("""
                INSERT INTO accounts (email, name, department, role, password_hash)
                VALUES (?, 'Администратор', 'ИБ', 'admin', ?)
            """, (address, encoded))
    return password


def create_participant(data):
    name = text_field(data["name"], "ФИО", 90)
    address = address_field(data["email"])
    department = text_field(data["department"], "Подразделение", 70)
    password = secrets.token_urlsafe(15)
    encoded = password_hash(password)
    try:
        with database(write=True) as db:
            result = db.execute("""
                INSERT INTO accounts (email, name, department, role, password_hash)
                VALUES (?, ?, ?, 'participant', ?)
            """, (address, name, department, encoded))
            return {"id": result.lastrowid, "email": address, "password": password}
    except sqlite3.IntegrityError:
        raise Problem(409, "На этот адрес уже создана учётная запись.") from None


def login(address, password):
    if not isinstance(password, str) or not 1 <= len(password) <= 128 or not password.isascii():
        raise Problem(401, "Проверьте адрес и пароль портала.")
    with database() as db:
        account = db.execute(
            "SELECT id, password_hash FROM accounts WHERE email = ?", (normalize_address(address),)
        ).fetchone()
    stored = account["password_hash"] if account else f"{'0' * 32}:{'0' * 64}"
    if not valid_password(password, stored) or not account:
        raise Problem(401, "Проверьте адрес и пароль портала.")
    token = secrets.token_urlsafe(32)
    timestamp = int(time.time())
    with database(write=True) as db:
        # A password rotation may have happened while the hash was being checked.
        current = db.execute("SELECT password_hash FROM accounts WHERE id = ?", (account["id"],)).fetchone()
        if not current or current["password_hash"] != stored:
            raise Problem(401, "Проверьте адрес и пароль портала.")
        db.execute("DELETE FROM sessions WHERE expires <= ?", (timestamp,))
        db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session_hash(token), account["id"], timestamp + SESSION_SECONDS))
    return token


def session(token):
    if not token:
        return None
    with database() as db:
        account = db.execute("""
            SELECT a.id, a.name, a.email, a.role
            FROM sessions AS s JOIN accounts AS a ON a.id = s.account_id
            WHERE s.digest = ? AND s.expires > ?
        """, (session_hash(token), int(time.time()))).fetchone()
    return dict(account) if account else None


def end_session(token):
    if token:
        with database(write=True) as db:
            db.execute("DELETE FROM sessions WHERE digest = ?", (session_hash(token),))


def admin_data():
    with database() as db:
        db.execute("BEGIN")
        people = db.execute("""
            SELECT id, name, email, department FROM accounts WHERE role = 'participant' ORDER BY name, id
        """).fetchall()
        campaigns = {
            row["id"]: {**dict(row), "assignments": []}
            for row in db.execute("SELECT id, name, created_at FROM campaigns ORDER BY id DESC")
        }
        epoch = int(time.time())
        for row in db.execute(f"SELECT {ASSIGNMENT_COLUMNS} FROM assignments AS a ORDER BY a.id"):
            assignment = dict(row)
            if assignment["mail_status"] == "sending" and assignment["mail_attempt_at"] < epoch - 120:
                assignment["mail_status"] = "unknown"
            campaigns[assignment["campaign_id"]]["assignments"].append(assignment)
    return {"people": [dict(row) for row in people], "campaigns": list(campaigns.values())}


def create_campaign(data):
    name = text_field(data["name"], "Название кампании", 90)
    scenario = data["scenario"]
    members = data["participants"]
    if not isinstance(scenario, str) or scenario not in BY_ID:
        raise Problem(400, "Выберите сценарий из каталога.")
    if not isinstance(members, list) or not 1 <= len(members) <= 500:
        raise Problem(400, "Выберите от одного до 500 сотрудников.")
    ids = list(dict.fromkeys(id_field(member) for member in members))
    with database(write=True) as db:
        placeholders = ",".join("?" for _ in ids)
        count = db.execute(
            f"SELECT count(*) FROM accounts WHERE role = 'participant' AND id IN ({placeholders})", ids
        ).fetchone()[0]
        if count != len(ids):
            raise Problem(400, "Проверьте список сотрудников.")
        campaign_id = db.execute("INSERT INTO campaigns (name, created_at) VALUES (?, ?)", (name, now())).lastrowid
        db.executemany("""
            INSERT INTO assignments (campaign_id, account_id, scenario_id)
            VALUES (?, ?, ?)
        """, ((campaign_id, member, scenario) for member in ids))
    return {"id": campaign_id}


def participant_data(account_id):
    with database() as db:
        rows = db.execute(f"""
            SELECT {ASSIGNMENT_COLUMNS}, c.name AS campaign_name
            FROM assignments AS a JOIN campaigns AS c ON c.id = a.campaign_id
            WHERE a.account_id = ? ORDER BY a.id DESC
        """, (account_id,)).fetchall()
    return [{
        "id": row["id"], "campaign": row["campaign_name"], "started_at": row["started_at"],
        "completed_at": row["completed_at"], "correct": row["correct"],
        "exercise": exercise(row["scenario_id"]),
        "feedback": BY_ID[row["scenario_id"]]["feedback"] if row["completed_at"] else None,
    } for row in rows]


def record_practice(account_id, assignment_id, answer=None):
    with database(write=True) as db:
        row = db.execute("""
            SELECT scenario_id, started_at, completed_at, correct FROM assignments
            WHERE id = ? AND account_id = ?
        """, (assignment_id, account_id)).fetchone()
        if not row:
            raise Problem(404, "Задание не найдено.")
        if answer is None:
            db.execute("UPDATE assignments SET started_at = coalesce(started_at, ?) WHERE id = ?", (now(), assignment_id))
            return {"started": True}
        if not row["started_at"]:
            raise Problem(409, "Сначала откройте упражнение.")
        scenario = BY_ID[row["scenario_id"]]
        if not 0 <= answer < len(scenario["choices"]):
            raise Problem(400, "Выберите один ответ.")
        if row["completed_at"]:
            return {"correct": bool(row["correct"]), "feedback": scenario["feedback"]}
        correct = answer == scenario["answer"]
        db.execute("UPDATE assignments SET completed_at = ?, correct = ? WHERE id = ?", (now(), int(correct), assignment_id))
        return {"correct": correct, "feedback": scenario["feedback"]}


def claim_invitation(assignment_id):
    with database(write=True) as db:
        row = db.execute("""
            SELECT a.mail_status, p.email FROM assignments AS a JOIN accounts AS p ON p.id = a.account_id
            WHERE a.id = ?
        """, (assignment_id,)).fetchone()
        if not row:
            raise Problem(404, "Назначение не найдено.")
        if row["mail_status"] not in {"pending", "rejected"}:
            raise Problem(409, "Приглашение уже обработано. Проверьте статус в отчёте.")
        message_id = make_msgid(domain=DOMAIN_NAME)
        db.execute(
            "UPDATE assignments SET mail_status = 'sending', mail_attempt_at = ?, mail_id = ? WHERE id = ?",
            (int(time.time()), message_id, assignment_id),
        )
        return row["email"], message_id


def close_invitation(assignment_id, message_id, outcome):
    accepted_at = now() if outcome == "accepted" else None
    with database(write=True) as db:
        db.execute("UPDATE assignments SET mail_status = ?, accepted_at = ? WHERE id = ? AND mail_id = ?",
                   (outcome, accepted_at, assignment_id, message_id))
    return {"status": outcome, "accepted_at": accepted_at, "message_id": message_id}
