"""Persistent SQLite storage and minimal security helpers for FlowSCM."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.getenv('FLOWSCM_DB_PATH', str(Path(__file__).resolve().parent.parent / 'data' / 'flowscm.sqlite3')))
COOKIE_NAME = 'flowscm_session'
COOKIE_SECURE = os.getenv('FLOWSCM_COOKIE_SECURE', '0') == '1' or bool(os.getenv('VERCEL'))
SESSION_DAYS = 7


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def connect():
    if os.getenv('DATABASE_URL'):
        return PgConnection(os.environ['DATABASE_URL'])
    if os.getenv('VERCEL'):
        raise RuntimeError('Neon DATABASE_URL is required on Vercel; refusing ephemeral SQLite storage')
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=5000')
    return con


def setup():
    if os.getenv('DATABASE_URL'):
        setup_postgres()
        return
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            car_model TEXT NOT NULL,
            period TEXT NOT NULL,
            sales INTEGER NOT NULL CHECK(sales>=0),
            dealer_orders INTEGER NOT NULL CHECK(dealer_orders>=0),
            created_at TEXT NOT NULL,
            UNIQUE(user_id, car_model, period)
        );
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            max_gap_pct REAL NOT NULL DEFAULT 10.0,
            auto_approve INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            car_model TEXT NOT NULL,
            target_period TEXT NOT NULL,
            method TEXT NOT NULL,
            forecast_units INTEGER NOT NULL,
            confirmed_orders INTEGER NOT NULL,
            gap_pct REAL NOT NULL,
            threshold_pct REAL NOT NULL,
            capacity_limit INTEGER,
            supply_risk INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            approved_units INTEGER,
            review_note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_records_user ON records(user_id, car_model, period);
        CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_user ON audit(user_id, created_at);
        ''')


def hash_password(password):
    salt = secrets.token_bytes(16)
    rounds = 310000
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, rounds)
    return f'pbkdf2_sha256${rounds}${salt.hex()}${key.hex()}'


def verify_password(password, value):
    try:
        algo, n, salt, expected = value.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(n))
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(db, user_id):
    raw = secrets.token_urlsafe(36)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(timespec='seconds')
    db.execute('INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)', (hash_token(raw), user_id, expires, utcnow()))
    return raw


def user_from_token(raw):
    if not raw:
        return None
    with connect() as db:
        row = db.execute('''SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON s.user_id=u.id
                            WHERE s.token_hash=? AND s.expires_at>?''', (hash_token(raw), utcnow())).fetchone()
        return dict(row) if row else None


def write_audit(db, user_id, event, detail):
    db.execute('INSERT INTO audit(user_id,event,detail,created_at) VALUES (?,?,?,?)', (user_id, event, detail[:350], utcnow()))


def validate_email(email):
    return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)) and len(email) <= 254


# Neon Postgres: Keep SQLite support for offline local development.
# DATABASE_URL is required in Vercel and must be set as a secret environment variable.
def setup_postgres():
    statements = [
        "CREATE TABLE IF NOT EXISTS users (id BIGSERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS records (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, car_model TEXT NOT NULL, period TEXT NOT NULL, sales INTEGER NOT NULL CHECK(sales>=0), dealer_orders INTEGER NOT NULL CHECK(dealer_orders>=0), created_at TEXT NOT NULL, UNIQUE(user_id, car_model, period))",
        "CREATE TABLE IF NOT EXISTS settings (user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, max_gap_pct DOUBLE PRECISION NOT NULL DEFAULT 10, auto_approve INTEGER NOT NULL DEFAULT 1)",
        "CREATE TABLE IF NOT EXISTS plans (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, car_model TEXT NOT NULL, target_period TEXT NOT NULL, method TEXT NOT NULL, forecast_units INTEGER NOT NULL, confirmed_orders INTEGER NOT NULL, gap_pct DOUBLE PRECISION NOT NULL, threshold_pct DOUBLE PRECISION NOT NULL, capacity_limit INTEGER, supply_risk INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, reason TEXT NOT NULL, approved_units INTEGER, review_note TEXT, created_at TEXT NOT NULL, reviewed_at TEXT)",
        "CREATE TABLE IF NOT EXISTS audit (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE INDEX IF NOT EXISTS idx_records_user ON records(user_id, car_model, period)",
        "CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit(user_id, created_at)",
    ]
    with PgConnection(os.environ['DATABASE_URL']) as db:
        for statement in statements:
            db.execute(statement)


class PgRow(dict):
    # Support row['name'] and csv.writer(list(row)) as in sqlite3.Row.
    def __iter__(self):
        return iter(self.values())


class PgCursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return PgRow(row) if row is not None else None

    def fetchall(self):
        return [PgRow(row) for row in self.cursor.fetchall()]


class PgConnection:
    def __init__(self, dsn):
        import psycopg
        from psycopg.rows import dict_row
        self.raw = psycopg.connect(dsn, row_factory=dict_row, connect_timeout=8)

    def __enter__(self):
        return self

    def __exit__(self, typ, val, tb):
        if typ is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()
        return False

    def execute(self, sql, params=()):
        # App source uses SQLite's '?'; psycopg needs '%s'.
        # No question-mark characters appear in static SQL string literals.
        sql = sql.replace('?', '%s')
        generating_id = sql.lstrip().upper().startswith(('INSERT INTO USERS(', 'INSERT INTO PLANS('))
        if generating_id:
            sql += ' RETURNING id'
        cursor = self.raw.execute(sql, params)
        lastrowid = None
        if generating_id:
            lastrowid = cursor.fetchone()['id']
        return PgCursor(cursor, lastrowid=lastrowid)

try:
    from psycopg.errors import UniqueViolation
except ImportError:
    class UniqueViolation(Exception):
        pass
