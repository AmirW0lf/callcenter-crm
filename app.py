#!/usr/bin/env python3
import csv
import hashlib
import hmac
import html
import io
import json
import re
import os
import secrets
import socket
import sqlite3
import sys
import traceback
import urllib.parse
from datetime import datetime, date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "crm.sqlite3")
SESSION_COOKIE = "crm_session"
SESSIONS = {}

# Load flatpickr assets inline (zero external dependencies at runtime)
def _load_asset(filename):
    try:
        p = os.path.join(BASE_DIR, filename)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return ""

_FLATPICKR_CSS = _load_asset("flatpickr.min.css")
_FLATPICKR_JS = _load_asset("flatpickr.min.js")
_FLATPICKR_FA = _load_asset("flatpickr-fa.js")

SOURCES = ["phone_call", "walk_in", "facebook", "instagram", "website", "referral", "old_customer", "other"]
PROJECT_STAGES = ["planning", "permits", "foundation", "structure", "brickwork", "electrical_plumbing", "finishing", "final_inspection", "ready", "delivered", "paused"]
REG_STATUSES = ["open", "closed", "coming_soon", "sold_out"]
CALL_TYPES = ["incoming", "outgoing", "missed", "follow_up"]
PRIORITIES = ["low", "normal", "high", "urgent"]
NOTE_TYPES = ["general", "manager_note", "project_note", "complaint_note", "document_note"]
PROBLEM_TYPES = [
    "registration_question", "project_progress", "payment_question", "documents_question",
    "site_visit", "delay_complaint", "quality_complaint", "wrong_number", "other",
]
FOLLOW_UP_REASONS = [
    "site_visit", "payment_follow_up", "document_follow_up", "call_back",
    "contract_follow_up", "progress_update", "general_follow_up", "other",
]
LOOKUP_DEFS = {
    "sources": ("منبع", SOURCES),
    "problem_types": ("موضوع/دلیل تماس", PROBLEM_TYPES),
    "project_stages": ("مرحله پروژه", PROJECT_STAGES),
    "registration_statuses": ("وضعیت ثبت نام پروژه", REG_STATUSES),
    "follow_up_reasons": ("دلایل پیگیری", FOLLOW_UP_REASONS),
}

FA = {
    "manager": "مدیر", "agent": "اپراتور", "new_lead": "مشتری جدید", "contacted": "تماس گرفته شده",
    "interested": "علاقه مند", "needs_follow_up": "نیاز به پیگیری", "site_visit_scheduled": "بازدید زمان بندی شده",
    "documents_requested": "درخواست مدارک", "documents_received": "مدارک دریافت شد", "registered_signed": "ثبت نام / قرارداد",
    "payment_pending": "در انتظار پرداخت", "active_customer": "مشتری فعال", "project_progress_inquiry": "سوال پیشرفت پروژه",
    "complaint_issue": "شکایت / مشکل", "not_interested": "عدم علاقه", "closed": "بسته شده",
    "phone_call": "تماس تلفنی", "walk_in": "حضوری", "facebook": "فیسبوک", "instagram": "اینستاگرام",
    "website": "وبسایت", "referral": "معرفی", "old_customer": "مشتری قدیمی", "other": "سایر",
    "planning": "برنامه ریزی", "permits": "مجوزها", "foundation": "فونداسیون", "structure": "اسکلت",
    "brickwork": "دیوارچینی", "electrical_plumbing": "برق و لوله کشی", "finishing": "نازک کاری",
    "final_inspection": "بازرسی نهایی", "ready": "آماده", "delivered": "تحویل شده", "paused": "متوقف",
    "open": "باز", "closed": "بسته", "coming_soon": "به زودی", "sold_out": "تکمیل ظرفیت",
    "incoming": "ورودی", "outgoing": "خروجی", "missed": "از دست رفته", "follow_up": "پیگیری",
    "no_answer": "بدون پاسخ", "busy": "مشغول", "call_back_later": "تماس در زمان دیگر",
    "wants_project_details": "جزئیات پروژه", "wants_site_visit": "درخواست بازدید", "wants_payment_details": "جزئیات پرداخت",
    "asked_about_progress": "سوال پیشرفت",    "wrong_number": "شماره اشتباه", "payment_follow_up": "پیگیری پرداخت", "document_follow_up": "پیگیری مدارک",
    "call_back": "تماس مجدد", "contract_follow_up": "پیگیری قرارداد", "progress_update": "به روز رسانی پیشرفت",
    "general_follow_up": "پیگیری عمومی", "pending": "در انتظار", "done": "انجام شد",
    "cancelled": "لغو شد", "low": "کم", "normal": "معمولی", "high": "زیاد", "urgent": "فوری",
    "general": "عمومی", "manager_note": "یادداشت مدیر", "project_note": "یادداشت پروژه", "complaint_note": "یادداشت شکایت",
    "document_note": "یادداشت مدارک", "registration_question": "سوال ثبت نام", "project_progress": "پیشرفت پروژه",
    "payment_question": "سوال پرداخت", "documents_question": "سوال مدارک", "site_visit": "بازدید پروژه",
    "delay_complaint": "شکایت تاخیر", "quality_complaint": "شکایت کیفیت",
}


def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat(sep=" ")


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def label(value):
    return esc(label_text(value))


def label_text(value):
    value = "" if value is None else str(value)
    return FA.get(value, value.replace("_", " ").title())


def money_date(value):
    return esc(to_jalali_display(value) if value else "-")


def datetime_local_value(value=None):
    raw = value or now_iso()
    return esc(str(raw).replace(" ", "T")[:16])


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def to_jalali_display(value):
    text = str(value or "")
    try:
        part = text[:10]
        gy, gm, gd = [int(x) for x in part.split("-")]
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        return f"{jy:04d}/{jm:02d}/{jd:02d}" + (text[10:16] if len(text) > 10 else "")
    except Exception:
        return text


def jalali_to_gregorian(jy, jm, jd):
    if jy > 979:
        gy = 1600
        jy -= 979
    else:
        gy = 621
    days = 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + 78 + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy += 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    kab = gy % 4 == 0 and gy % 100 != 0 or gy % 400 == 0
    sal_a = [0, 31, 29 if kab else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd


def parse_jalali(value, with_time=False):
    text = (value or "").strip().replace("-", "/")
    if not text:
        return None
    try:
        date_part, _, time_part = text.partition(" ")
        if "T" in date_part:
            date_part, time_part = date_part.split("T", 1)
        parts = [int(x) for x in date_part.split("/")]
        if len(parts) != 3:
            return value.replace("T", " ")
        if parts[0] > 1700:
            out = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
        else:
            gy, gm, gd = jalali_to_gregorian(parts[0], parts[1], parts[2])
            out = f"{gy:04d}-{gm:02d}-{gd:02d}"
        if with_time:
            out += " " + (time_part[:5] if time_part else "00:00")
        return out
    except Exception:
        return value.replace("T", " ")


def jalali_input_value(value=None, with_time=False):
    raw = value or now_iso()
    shown = to_jalali_display(raw)
    return esc(shown[:16] if with_time else shown[:10])


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150_000).hex()
    return f"{salt}${digest}"


def check_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt).split("$", 1)[1], digest)


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    ensure_columns(conn)
    users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if users == 0:
        seed(conn)
    conn.close()


def ensure_columns(conn):
    call_cols = {row["name"] for row in conn.execute("PRAGMA table_info(call_logs)").fetchall()}
    if "problem_type" not in call_cols:
        conn.execute("ALTER TABLE call_logs ADD COLUMN problem_type TEXT")
    if "project_id" not in call_cols:
        conn.execute("ALTER TABLE call_logs ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")

    # Migrate existing DBs: drop call_result column (with fallback for older SQLite)
    call_col_info = {r["name"]: r for r in conn.execute("PRAGMA table_info(call_logs)").fetchall()}
    if "call_result" in call_col_info:
        if call_col_info["call_result"]["notnull"]:
            try:
                conn.execute("ALTER TABLE call_logs DROP COLUMN call_result")
                conn.commit()
            except Exception:
                conn.rollback()
                # SQLite <3.35.0: recreate table without call_result
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("""CREATE TABLE call_logs_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                    agent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    call_type TEXT NOT NULL DEFAULT 'outgoing',
                    problem_type TEXT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    call_started_at TEXT,
                    call_duration_seconds INTEGER,
                    notes TEXT,
                    next_action TEXT,
                    follow_up_required INTEGER NOT NULL DEFAULT 0,
                    follow_up_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                old_cols = [r["name"] for r in conn.execute("PRAGMA table_info(call_logs)").fetchall() if r["name"] != "call_result"]
                cols_csv = ",".join(old_cols)
                conn.execute(f"INSERT INTO call_logs_migrated({cols_csv}) SELECT {cols_csv} FROM call_logs")
                conn.execute("DROP TABLE call_logs")
                conn.execute("ALTER TABLE call_logs_migrated RENAME TO call_logs")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_customer ON call_logs(customer_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_agent ON call_logs(agent_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_call_logs_started ON call_logs(call_started_at)")
                conn.execute("PRAGMA foreign_keys=ON")
                conn.commit()
        else:
            # Column exists but is nullable — just drop it
            try:
                conn.execute("ALTER TABLE call_logs DROP COLUMN call_result")
                conn.commit()
            except Exception:
                conn.rollback()

    customer_cols = {row["name"] for row in conn.execute("PRAGMA table_info(customers)").fetchall()}
    if "national_code" not in customer_cols:
        conn.execute("ALTER TABLE customers ADD COLUMN national_code TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_national_code ON customers(national_code) WHERE national_code IS NOT NULL AND national_code != ''")

    conn.execute("""CREATE TABLE IF NOT EXISTS customer_projects (
        customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        PRIMARY KEY(customer_id, project_id)
    )""")
    conn.execute("""INSERT OR IGNORE INTO customer_projects(customer_id, project_id, created_at)
        SELECT id, interested_project_id, COALESCE(created_at, datetime('now'))
        FROM customers WHERE interested_project_id IS NOT NULL""")
    conn.execute("""INSERT OR IGNORE INTO customer_projects(customer_id, project_id, created_at)
        SELECT id, signed_project_id, COALESCE(created_at, datetime('now'))
        FROM customers WHERE signed_project_id IS NOT NULL""")

    conn.execute("""CREATE TABLE IF NOT EXISTS follow_up_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follow_up_id INTEGER NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        comment TEXT NOT NULL,
        created_at TEXT NOT NULL
    );""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_follow_up_comments_follow ON follow_up_comments(follow_up_id)")

    follow_cols = {row["name"] for row in conn.execute("PRAGMA table_info(follow_ups)").fetchall()}
    if "viewed_at" not in follow_cols:
        conn.execute("ALTER TABLE follow_ups ADD COLUMN viewed_at TEXT")

    conn.execute("""CREATE TABLE IF NOT EXISTS lookup_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lookup_type TEXT NOT NULL,
        value TEXT NOT NULL,
        label TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(lookup_type, value)
    )""")
    for lookup_type, (_, values) in LOOKUP_DEFS.items():
        for value in values:
            conn.execute("""INSERT OR IGNORE INTO lookup_items(lookup_type,value,label,is_active,created_at,updated_at)
                VALUES(?,?,?,?,?,?)""", (lookup_type, value, label_text(value), 1, now_iso(), now_iso()))
    conn.commit()


def seed(conn):
    default_password = hash_password("password123")
    people = [
        ("مدیر", "manager@crm.local", "+964000000001", "manager"),
        ("MS.Nasiri اپراتور", "nasiri@crm.local", "+964000000002", "agent"),
        ("MS.Abasi اپراتور", "abasi@crm.local", "+964000000003", "agent"),
        ("MS.Saadati اپراتور", "saadati@crm.local", "+964000000004", "agent"),
    ]
    for name, email, phone, role in people:
        conn.execute("INSERT INTO users(name,email,password,phone,role,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)", (name, email, default_password, phone, role, now_iso(), now_iso()))
    conn.execute("INSERT INTO projects(name,location,description,stage,progress_percentage,expected_completion_date,registration_status,public_update,internal_notes,is_active,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,1,1,?,?)", ("پروژه A", "Erbil", "Main residential construction project.", "structure", 45, "2026-12-30", "open", "Structure work is currently in progress.", "Demo project seeded for first login.", now_iso(), now_iso()))
    conn.execute("INSERT INTO projects(name,location,description,stage,progress_percentage,expected_completion_date,registration_status,public_update,is_active,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,1,1,?,?)", ("پروژه B", "Duhok", "Second residential project.", "finishing", 80, "2026-09-30", "open", "Finishing phase is ongoing.", now_iso(), now_iso()))
    conn.execute("INSERT INTO customers(full_name,national_code,primary_phone,city,source,status,assigned_agent_id,interested_project_id,general_notes,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", ("Ali Hassan", "1000000001", "+964750000001", "Erbil", "phone_call", "interested", 2, 1, "Demo customer interested in پروژه A.", 1, now_iso(), now_iso()))
    conn.execute("INSERT OR IGNORE INTO customer_projects(customer_id,project_id,created_at) VALUES(1,1,?)", (now_iso(),))
    conn.execute("INSERT INTO follow_ups(customer_id,assigned_agent_id,created_by,due_at,status,priority,reason,notes,created_at,updated_at) VALUES(1,2,1,?, 'pending', 'high', 'Schedule site visit', 'Seed follow-up for demo dashboard.', ?, ?)", (now_iso(), now_iso(), now_iso()))
    conn.commit()


SCHEMA = r"""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'agent' CHECK(role IN ('manager','agent')),
    is_active INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    description TEXT,
    stage TEXT NOT NULL DEFAULT 'planning',
    progress_percentage INTEGER NOT NULL DEFAULT 0 CHECK(progress_percentage BETWEEN 0 AND 100),
    expected_completion_date TEXT,
    registration_status TEXT NOT NULL DEFAULT 'open',
    public_update TEXT,
    internal_notes TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_stage ON projects(stage);
CREATE INDEX IF NOT EXISTS idx_projects_registration ON projects(registration_status);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT NOT NULL,
    national_code TEXT UNIQUE,
    primary_phone TEXT NOT NULL,
    secondary_phone TEXT,
    email TEXT,
    city TEXT,
    address TEXT,
    source TEXT NOT NULL DEFAULT 'phone_call',
    status TEXT NOT NULL DEFAULT 'new_lead',
    assigned_agent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    interested_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    signed_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    registration_date TEXT,
    last_contacted_at TEXT,
    next_follow_up_at TEXT,
    general_notes TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(primary_phone);
CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
CREATE INDEX IF NOT EXISTS idx_customers_agent ON customers(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_customers_follow ON customers(next_follow_up_at);

CREATE TABLE IF NOT EXISTS customer_projects (
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(customer_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_customer_projects_project ON customer_projects(project_id);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    agent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    call_type TEXT NOT NULL DEFAULT 'outgoing',
    call_result TEXT,
    problem_type TEXT,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    call_started_at TEXT,
    call_duration_seconds INTEGER,
    notes TEXT,
    next_action TEXT,
    follow_up_required INTEGER NOT NULL DEFAULT 0,
    follow_up_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_call_logs_customer ON call_logs(customer_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_agent ON call_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_started ON call_logs(call_started_at);

CREATE TABLE IF NOT EXISTS follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    assigned_agent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    due_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','done','cancelled')),
    priority TEXT NOT NULL DEFAULT 'normal',
    reason TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    viewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_follow_ups_customer ON follow_ups(customer_id);
CREATE INDEX IF NOT EXISTS idx_follow_ups_agent ON follow_ups(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_follow_ups_due ON follow_ups(due_at);
CREATE INDEX IF NOT EXISTS idx_follow_ups_status ON follow_ups(status);

CREATE TABLE IF NOT EXISTS customer_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    note_type TEXT NOT NULL DEFAULT 'general',
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    update_text TEXT,
    stage TEXT NOT NULL,
    progress_percentage INTEGER NOT NULL DEFAULT 0 CHECK(progress_percentage BETWEEN 0 AND 100),
    update_date TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    action TEXT NOT NULL,
    description TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS follow_up_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    follow_up_id INTEGER NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_follow_up_comments_follow ON follow_up_comments(follow_up_id);

CREATE TABLE IF NOT EXISTS live_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    extension TEXT,
    phone TEXT NOT NULL,
    caller_name TEXT,
    call_id TEXT,
    status TEXT,
    started_at TEXT,
    ended_at TEXT,
    duration_seconds INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_calls_agent ON live_calls(agent_id);
CREATE INDEX IF NOT EXISTS idx_live_calls_extension ON live_calls(extension);
CREATE INDEX IF NOT EXISTS idx_live_calls_call_id ON live_calls(call_id);
"""


def options(values, selected=None, blank=None):
    out = []
    if blank is not None:
        out.append(f'<option value="">{esc(blank)}</option>')
    for v in values:
        sel = " selected" if str(v) == str(selected or "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{label(v)}</option>')
    return "".join(out)


def lookup_values(conn, lookup_type, fallback):
    try:
        rows = conn.execute("SELECT value FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id", (lookup_type,)).fetchall()
        values = [r["value"] for r in rows]
    except sqlite3.OperationalError:
        values = []
    return values or fallback


def lookup_options(conn, lookup_type, selected=None, blank=None):
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    try:
        rows = conn.execute("SELECT value,label FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id", (lookup_type,)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        return options(LOOKUP_DEFS[lookup_type][1], selected, blank)
    for r in rows:
        sel = " selected" if str(r["value"]) == str(selected or "") else ""
        out.append(f'<option value="{esc(r["value"])}"{sel}>{esc(r["label"])}</option>')
    return "".join(out)


def status_key(label_value):
    return (label_value or "").strip() or None


def user_options(conn, selected=None, blank="بدون مسئول"):
    rows = conn.execute("SELECT id,name,role FROM users WHERE is_active=1 ORDER BY role DESC,name").fetchall()
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for r in rows:
        sel = " selected" if str(r["id"]) == str(selected or "") else ""
        out.append(f'<option value="{r["id"]}"{sel}>{esc(r["name"])} ({esc(r["role"])})</option>')
    return "".join(out)


def project_options(conn, selected=None, blank="بدون پروژه"):
    rows = conn.execute("SELECT id,name FROM projects WHERE is_active=1 ORDER BY name").fetchall()
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for r in rows:
        sel = " selected" if str(r["id"]) == str(selected or "") else ""
        out.append(f'<option value="{r["id"]}"{sel}>{esc(r["name"])}</option>')
    return "".join(out)


def customer_project_options(conn, customer_id, selected=None, blank=None):
    rows = conn.execute("""SELECT p.id,p.name FROM projects p
        JOIN customer_projects cp ON cp.project_id=p.id
        WHERE cp.customer_id=? AND p.is_active=1 ORDER BY p.name""", (customer_id,)).fetchall()
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for r in rows:
        sel = " selected" if str(r["id"]) == str(selected or "") else ""
        out.append(f'<option value="{r["id"]}"{sel}>{esc(r["name"])}</option>')
    return "".join(out)


def can_edit_row(user, row, owner_field):
    return user["role"] == "manager" or row[owner_field] == user["id"]


def project_selects(conn, selected_ids=None):
    selected_ids = [str(x) for x in (selected_ids or []) if x]
    if not selected_ids:
        selected_ids = [""]
    return "".join(
        f'<div class="project-pick"><select name="project_ids">{project_options(conn, selected)}</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button></div>'
        for selected in selected_ids
    )


class App(BaseHTTPRequestHandler):
    server_version = "CallCenterCRM/1.0"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        self.query = urllib.parse.parse_qs(parsed.query)
        self.conn = db()
        self.current_user = self.get_current_user()
        try:
            if path == "/static/app.css":
                return self.css()
            if path == "/static/BNazanin.ttf":
                return self.static_file("BNazanin.ttf", "font/ttf")
            if path == "/static/BTitrBd.ttf":
                return self.static_file("BTitrBd.ttf", "font/ttf")

            if path == "/login":
                return self.login(method)
            if path == "/logout":
                return self.logout()
            if not self.current_user:
                return self.redirect("/login")
            if path in ["/", "/dashboard"]:
                return self.dashboard()
            if path == "/customers":
                return self.customers(method)
            if path == "/customers/new":
                return self.customer_form(method)
            if path.startswith("/customers/"):
                return self.customer_routes(path, method)
            if path == "/projects":
                return self.projects(method)
            if path == "/projects/new":
                return self.project_form(method)
            if path.startswith("/projects/"):
                return self.project_routes(path, method)
            if path == "/follow-ups":
                return self.followups()
            if path.startswith("/follow-ups/"):
                return self.followup_action(path, method)
            if path.startswith("/call-logs/"):
                return self.call_log_detail(path, method)
            if path == "/reports":
                return self.reports()
            if path == "/users":
                return self.users(method)
            if path.startswith("/users/"):
                return self.user_action(path, method)
            if path == "/base-tables":
                return self.base_tables(method)
            if path.startswith("/base-tables/"):
                return self.base_table_action(path, method)
            if path == "/api/customers/by-national-code":
                return self.api_customer_by_national_code()
            if path == "/api/customers/by-phone":
                return self.api_customer_by_phone()
            if path == "/api/customers/follow-up-history":
                return self.api_customer_followup_history()
            if path == "/api/live-call":
                return self.api_live_call()
            if path == "/exports/customers":
                return self.export_customers()
            if path == "/exports/daily-report":
                return self.export_daily_report()
            if path == "/exports/project-calls":
                return self.export_project_calls()
            if path == "/exports/project-member-calls":
                return self.export_project_member_calls()
            if path == "/exports/project-detail":
                return self.export_project_detail()
            if path == "/exports/follow-ups":
                return self.export_follow_ups()
            return self.not_found()
        except Exception:
            try:
                self.send_html("<h1>خطای سرور</h1><pre>" + html.escape(traceback.format_exc()) + "</pre>", status=500)
            except Exception:
                pass
        finally:
            self.conn.close()

    def get_current_user(self):
        cookies = self.headers.get("Cookie", "")
        token = None
        for chunk in cookies.split(";"):
            if "=" in chunk:
                k, v = chunk.strip().split("=", 1)
                if k == SESSION_COOKIE:
                    token = v
        uid = SESSIONS.get(token)
        if uid:
            return self.conn.execute("SELECT * FROM users WHERE id=? AND is_active=1", (uid,)).fetchone()
        return None

    def form_all(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length).decode() if length else ""
        return urllib.parse.parse_qs(data, keep_blank_values=True)

    def form(self):
        if not hasattr(self, '_form_data'):
            self._form_data = self.form_all()
        return {k: v[-1] for k, v in self._form_data.items()}

    def form_list(self):
        if not hasattr(self, '_form_data'):
            self._form_data = self.form_all()
        return self._form_data

    def send_html(self, body, title="CRM", status=200):
        user = self.current_user
        nav = ""
        if user:
            unviewed_count = self.count_unviewed_followups()
            badge_html = f'<span class="nav-badge">{unviewed_count}</span>' if unviewed_count > 0 else ''
            badge_hamb = f'<span class="nav-badge">{unviewed_count}</span>' if unviewed_count > 0 else ''
            base_drop = '<div class="nav-drop"><a href="/base-tables">جداول پایه</a><div class="nav-menu"><a href="/base-tables#sources">منبع</a><a href="/users">اپراتور</a><a href="/projects">پروژه ها</a><a href="/base-tables#problem_types">دلیل های تماس</a></div></div>' if user["role"] == "manager" else ""
            report_link = '<a href="/reports">گزارش من</a>' if user["role"] == "agent" else ''
            manager_links = f'{base_drop}<a href="/reports">گزارش ها</a><a href="/users">کاربران</a>' if user["role"] == "manager" else report_link
            nav = f"""
            <nav><div class="hamb">☰<div class="hamb-menu"><a href="/dashboard">داشبورد</a><a href="/customers">مشتریان</a><a href="/projects">پروژه ها</a><a href="/follow-ups">پیگیری ها{badge_hamb}</a>{manager_links}</div></div><a href="/dashboard">داشبورد</a><a href="/customers">مشتریان</a><a href="/projects">پروژه ها</a><a href="/follow-ups">پیگیری ها{badge_html}</a>{manager_links}<span>{esc(user['name'])}</span><a href="/logout">خروج</a></nav>
            """
        jalali_picker_script = '''
        document.addEventListener('DOMContentLoaded',function(){try{
          document.querySelectorAll('.jalali-date').forEach(function(el){if(el._flatpickr)return;el.readOnly=true;flatpickr(el,{locale:'fa',dateFormat:'Y/m/d'})});
          document.querySelectorAll('.jalali-datetime').forEach(function(el){if(el._flatpickr)return;el.readOnly=true;flatpickr(el,{locale:'fa',enableTime:true,dateFormat:'Y/m/d H:i',time_24hr:true})});
          document.querySelectorAll('input[type="time"]').forEach(function(el){if(el._flatpickr)return;el.readOnly=true;flatpickr(el,{noCalendar:true,enableTime:true,dateFormat:'H:i',time_24hr:true})});
        }catch(e){console.error('Jalali picker error:',e)}});
        function filterTable(tableId, query) {
          var q = query.trim().toLowerCase();
          var table = document.getElementById(tableId);
          if (!table) return;
          var rows = table.querySelectorAll('tbody tr');
          for (var i = 0; i < rows.length; i++) {
            var text = rows[i].textContent.toLowerCase();
            rows[i].style.display = q === '' || text.indexOf(q) > -1 ? '' : 'none';
          }
        }
        function filterFollowUps() {
          var q = document.getElementById('fu-search');
          if (!q) return;
          var query = q.value.trim().toLowerCase();
          var dateFrom = document.getElementById('fu-date-from');
          var dateTo = document.getElementById('fu-date-to');
          var fromVal = dateFrom ? dateFrom.value.trim() : '';
          var toVal = dateTo ? dateTo.value.trim() : '';
          var cards = document.querySelectorAll('.fu-card');
          for (var i = 0; i < cards.length; i++) {
            var text = cards[i].textContent.toLowerCase();
            var show = query === '' || text.indexOf(query) > -1;
            if (show && (fromVal || toVal)) {
              var dateMatch = text.match(/(\\d{4}\\/\\d{2}\\/\\d{2})/);
              if (dateMatch) {
                var cardDate = dateMatch[1];
                if (fromVal && cardDate < fromVal) show = false;
                if (toVal && cardDate > toVal) show = false;
              }
            }
            cards[i].style.display = show ? '' : 'none';
          }
        }
        function toggleEditCard(id) {
          var form = document.getElementById('fu-edit-' + id);
          if (!form) return;
          var showing = form.style.display === 'none' || form.style.display === '';
          form.style.display = showing ? 'block' : 'none';
          if (showing) {
            try {
              form.querySelectorAll('.jalali-datetime').forEach(function(el){if(!el._flatpickr){el.readOnly=true;flatpickr(el,{locale:'fa',enableTime:true,dateFormat:'Y/m/d H:i',time_24hr:true})}});
              form.querySelectorAll('.jalali-date').forEach(function(el){if(!el._flatpickr){el.readOnly=true;flatpickr(el,{locale:'fa',dateFormat:'Y/m/d'})}});
            } catch(e) {}
          }
        }
        function filterBaseTables(query) {
          var q = query.trim().toLowerCase();
          var sections = document.querySelectorAll('.bt-section');
          for (var i = 0; i < sections.length; i++) {
            var text = sections[i].textContent.toLowerCase();
            sections[i].style.display = q === '' || text.indexOf(q) > -1 ? '' : 'none';
          }
        }
        function clearDateFilters() {
          var from = document.getElementById('fu-date-from');
          var to = document.getElementById('fu-date-to');
          if (from) from.value = '';
          if (to) to.value = '';
          filterFollowUps();
        }
        '''
        html_doc = f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><link rel="stylesheet" href="/static/app.css"><style>{_FLATPICKR_CSS}</style></head><body>{nav}<main>{body}</main><div class="watermark">تهیه شده در واحد مستند سازی معاونت اجتماعی و اطلاع سازی بتاجا توسط امیرحسین کرمی شماره تماس 09106827218</div><script>{_FLATPICKR_JS}</script><script>{_FLATPICKR_FA}</script><script>{jalali_picker_script}</script></body></html>"""
        data = html_doc.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def not_found(self):
        self.send_html("<h1>Not Found</h1>", status=404)

    def static_file(self, filename, content_type):
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(BASE_DIR), filename)
        if not os.path.exists(path):
            return self.not_found()
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def require_manager(self):
        if self.current_user["role"] != "manager":
            self.send_html("<h1>Forbidden</h1><p>مدیر access required.</p>", status=403)
            return False
        return True

    def login(self, method):
        error = ""
        if method == "POST":
            data = self.form()
            user = self.conn.execute("SELECT * FROM users WHERE email=? AND is_active=1", (data.get("email", "").strip(),)).fetchone()
            if user and check_password(data.get("password", ""), user["password"]):
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = user["id"]
                self.conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_iso(), user["id"]))
                self.conn.commit()
                self.send_response(303)
                self.send_header("Location", "/dashboard")
                self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax")
                self.end_headers()
                return
            error = '<div class="alert">ایمیل یا رمز عبور اشتباه است.</div>'
        body = f"""
        <section class="login"><h1>CRM مرکز تماس شرکت ساختمانی</h1>{error}
        <form method="post"><label>ایمیل<input name="email" value="manager@crm.local"></label><label>رمز عبور<input type="password" name="password" value="password123"></label><button>ورود</button></form>
        <p class="muted">حساب های آزمایشی: manager@crm.local, nasiri@crm.local, abasi@crm.local, saadati@crm.local. رمز عبور: password123</p></section>
        """
        self.send_html(body, "Login")

    def logout(self):
        token = None
        for chunk in self.headers.get("Cookie", "").split(";"):
            if chunk.strip().startswith(SESSION_COOKIE + "="):
                token = chunk.strip().split("=", 1)[1]
        if token:
            SESSIONS.pop(token, None)
        self.send_response(303)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Max-Age=0; Path=/")
        self.end_headers()

    def dashboard(self):
        if self.command == "POST":
            d = self.form()
            data_all = self.form_list()
            customer_id = d.get("customer_id")
            call_project_id = None
            if not customer_id:
                new_name = d.get("new_customer_name", "").strip()
                new_phone = d.get("new_customer_phone", "").strip()
                if new_name and new_phone:
                    national_code = d.get("nc_lookup", "").strip()
                    if national_code and not re.match(r'^\d{10}$', national_code):
                        return self.send_html("<p>کد ملی باید ۱۰ رقم باشد.</p>", status=422)
                    new_city = d.get("new_customer_city", "").strip()
                    new_project_ids = [pid.strip() for pid in data_all.get("new_customer_project_ids", []) if pid.strip()]
                    self.conn.execute("""INSERT INTO customers(full_name,national_code,primary_phone,city,source,status,assigned_agent_id,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (new_name, national_code or None, new_phone, new_city or None, "phone_call", "new_lead", self.current_user["id"], self.current_user["id"], now_iso(), now_iso()))
                    customer_id = str(self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"])
                    for new_pid in new_project_ids:
                        self.conn.execute("INSERT OR IGNORE INTO customer_projects(customer_id,project_id,created_at) VALUES(?,?,?)", (customer_id, new_pid, now_iso()))
                    if new_project_ids:
                        call_project_id = new_project_ids[0]
                else:
                    return self.send_html("<p>لطفا ابتدا مشتری را با کد ملی پیدا کنید یا اطلاعات مشتری جدید را وارد کنید.</p>", status=422)
            # For existing customers, save any new project assignments added by the agent
            existing_proj_ids = [pid.strip() for pid in data_all.get("existing_customer_project_ids", []) if pid.strip()]
            for ep_id in existing_proj_ids:
                self.conn.execute("INSERT OR IGNORE INTO customer_projects(customer_id,project_id,created_at) VALUES(?,?,?)", (customer_id, ep_id, now_iso()))
            call_date = parse_jalali(d.get("call_date"), False) or date.today().isoformat()
            call_time = (d.get("call_time") or datetime.now().strftime("%H:%M")).strip()
            call_started_at = f"{call_date[:10]} {call_time[:5]}"
            dur = d.get("call_duration", "").strip()
            dur_seconds = int(float(dur) * 60) if dur else None
            follow_up = 1 if d.get("follow_up_required") else 0
            self.conn.execute("""INSERT INTO call_logs(customer_id,agent_id,call_type,problem_type,project_id,call_started_at,call_duration_seconds,notes,follow_up_required,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (customer_id, self.current_user["id"], d.get("call_type", "incoming"), d.get("problem_type"), d.get("project_id") or call_project_id, call_started_at, dur_seconds, d.get("notes"), follow_up, now_iso(), now_iso()))
            if follow_up and d.get("follow_up_datetime"):
                fu_due = parse_jalali(d.get("follow_up_datetime"), True) or now_iso()
                fu_agent = d.get("follow_up_agent") or self.current_user["id"]
                fu_reason = d.get("follow_up_reason", "").strip() or "other"
                fu_notes = d.get("follow_up_notes", "").strip() or ""
                self.conn.execute("INSERT INTO follow_ups(customer_id,assigned_agent_id,created_by,due_at,status,priority,reason,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (customer_id, fu_agent, self.current_user["id"], fu_due, "pending", d.get("priority") or "normal", fu_reason, fu_notes, now_iso(), now_iso()))
                # Also add the follow-up note as a follow_up_comment for the assigned agent to see
                if fu_notes:
                    new_fu_id = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
                    self.conn.execute("INSERT INTO follow_up_comments(follow_up_id,user_id,comment,created_at) VALUES(?,?,?,?)",
                        (new_fu_id, self.current_user["id"], fu_notes, now_iso()))
            self.conn.execute("UPDATE customers SET last_contacted_at=?,updated_at=? WHERE id=?", (now_iso(), now_iso(), customer_id))
            self.conn.commit()
            return self.redirect("/dashboard?saved=1")
        uid = self.current_user["id"]
        is_manager = self.current_user["role"] == "manager"
        agent_params = () if is_manager else (uid,)
        total = self.conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        calls_today = self.conn.execute("SELECT COUNT(*) c FROM call_logs WHERE date(created_at)=date('now')" + ("" if is_manager else " AND agent_id=?"), agent_params).fetchone()["c"]
        follow_today = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending' AND date(due_at)=date('now')" + ("" if is_manager else " AND assigned_agent_id=?"), agent_params).fetchone()["c"]
        overdue = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending' AND datetime(due_at)<datetime('now')" + ("" if is_manager else " AND assigned_agent_id=?"), agent_params).fetchone()["c"]
        signed = self.conn.execute("SELECT COUNT(*) c FROM customers WHERE status='registered_signed'").fetchone()["c"]
        rows = self.conn.execute("""SELECT f.*, c.full_name, c.primary_phone, u.name agent FROM follow_ups f JOIN customers c ON c.id=f.customer_id LEFT JOIN users u ON u.id=f.assigned_agent_id WHERE f.status='pending' AND (date(f.due_at)=date('now') OR datetime(f.due_at)<datetime('now')) {} ORDER BY f.due_at LIMIT 10""".format("" if is_manager else "AND f.assigned_agent_id=?"), agent_params).fetchall()
        table = self.follow_table(rows)
        now_ = datetime.now()
        today_jalali = to_jalali_display(date.today().isoformat())[:10]
        current_time = now_.strftime("%H:%M")
        tomorrow_jalali = to_jalali_display((date.today() + timedelta(days=1)).isoformat())[:10]
        problem_opts = lookup_options(self.conn, 'problem_types')
        fu_opts = lookup_options(self.conn, 'follow_up_reasons')
        call_opts = options(CALL_TYPES, 'incoming')
        user_opts = user_options(self.conn, blank='انتخاب اپراتور')
        project_opts = project_options(self.conn, blank='انتخاب پروژه')
        call_form = """
        <div class="call-form-layout">
          <div id="call-logs-sidebar" class="panel call-logs-sidebar" hidden>
            <div class="top"><h2>تماس‌های اخیر</h2></div>
            <div id="call-logs-sidebar-list" class="call-logs-list"></div>
            <hr style="margin:8px 0;border:none;border-top:1px solid var(--line)">
            <div class="top"><h2>پروژه‌های مشتری</h2></div>
            <div id="customer-projects-sidebar-list" class="call-logs-list"></div>
            <hr style="margin:8px 0;border:none;border-top:1px solid var(--line)">
            <div class="top"><h2>پیگیری‌های اخیر</h2></div>
            <div id="follow-up-sidebar-list" class="call-logs-list"></div>
          </div>
          <section class="panel call-save">
            <div class="top"><h2>📞 ثبت تماس جدید</h2></div>
            <form method="post" class="call-form" id="call-save-form">
            <div class="call-form-row">
              <label>تاریخ شمسی<input class="jalali-date" name="call_date" value="{today}"></label>
              <label>ساعت شروع<input type="time" name="call_time" value="{time}"></label>
              <label class="nc-field">کد ملی
              <div id="nc-notification" class="nc-notification" hidden style="font-size:13px;color:#c33;background:#fff0f0;border:1px solid #fcc;border-radius:8px;padding:5px 10px;margin-bottom:6px;display:flex;align-items:center;gap:6px;animation:fadeSlide .35s ease">⚠️ کد ملی باید ۱۰ رقم باشد</div>
              <input type="text" id="nc-lookup" name="nc_lookup" placeholder="شماره ملی ۱۰ رقمی را وارد کنید..." autocomplete="off" maxlength="10" inputmode="numeric" pattern="[0-9]{10}">
              <small class="muted">پس از وارد کردن کد ملی، اطلاعات مشتری نمایش داده می‌شود</small></label>
            </div>
            <div id="customer-info" hidden class="call-form-body">
              <!-- Found customer view -->
              <div id="found-customer" class="call-form-row" hidden>
                <label>نام مشتری<input name="customer_name_display" readonly placeholder="—"></label>
                <label>شماره تماس<input name="customer_phone_display" readonly placeholder="—"></label>
              </div>

              <div id="found-project-row" hidden>
                <div class="call-form-row">
                  <label>پروژه‌های مشتری<button type="button" class="small secondary" onclick="addFoundCustomerProject()" style="margin-right:8px">+ پروژه</button></label>
                  <div id="found-customer-projects"></div>
                </div>
                <div class="call-form-row" style="margin-top:8px">
                  <label>پروژه این تماس<select name="project_id" id="project-select"><option value="">بدون پروژه</option></select></label>
                </div>
              </div>
              <!-- New customer view (when national code not found) -->
              <div id="new-customer" hidden>
                <div class="call-form-row">
                  <label>نام مشتری جدید<input name="new_customer_name" placeholder="نام مشتری"></label>
                  <label>شماره تماس<input name="new_customer_phone" placeholder="شماره تماس"></label>
                  <label>شهر<input name="new_customer_city" placeholder="شهر"></label>
                </div>
                <div style="margin-top:10px">
                  <label>پروژه‌ها<button type="button" class="small secondary" onclick="addNewCustomerProject()" style="margin-right:8px">+ پروژه</button></label>
                  <div id="new-customer-projects"><div class="project-pick"><select name="new_customer_project_ids">{project_opts}</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button></div></div>
                </div>
              </div>
              <!-- Common fields for both -->
              <div class="call-form-row">
                <label>مدت تماس (دقیقه)<input type="number" name="call_duration" min="0" step="1" placeholder="مثلا 5"></label>
                <label>نوع تماس<select name="call_type">{call_opts}</select></label>
                <label>موضوع تماس<select name="problem_type">{opts}</select></label>
                <label class="check"><input type="checkbox" name="follow_up_required" value="1" onclick="toggleFollowUpFields()"> نیاز به پیگیری</label>
              </div>
              <div id="follow-up-fields" class="call-form-row" style="display:none;margin-top:8px">
                <label>دلیل پیگیری<select name="follow_up_reason">{fu_opts}</select></label>
                <label>مهلت پیگیری (تاریخ و ساعت)<input class="jalali-datetime" name="follow_up_datetime" placeholder="1403/01/01 12:30" value="{tomorrow} {time}"></label>
                <label>مسئول پیگیری<select name="follow_up_agent">{user_opts}</select></label>
              </div>
              <div id="follow-up-notes-field" style="display:none">
                <label>یادداشت پیگیری (برای اپراتور مسئول)<textarea name="follow_up_notes" placeholder="یادداشت برای اپراتور مسئول پیگیری..."></textarea></label>
              </div>
              <label>یادداشت‌ها<textarea name="notes" placeholder="توضیحات اضافی (اختیاری)"></textarea></label>
              <input type="hidden" name="customer_id" id="customer-id">
              <button id="save-call-btn" disabled>ذخیره تماس</button>
            </div>
          </form>
        </section>
        </div>
        <script>
        const ncInput = document.getElementById('nc-lookup');
        const customerInfo = document.getElementById('customer-info');
        const foundCustomer = document.getElementById('found-customer');
        const foundProjectRow = document.getElementById('found-project-row');
        const newCustomer = document.getElementById('new-customer');
        let ncTimer;
        ncInput?.addEventListener('input', function(){
          clearTimeout(ncTimer);
          var code = this.value.trim();
          customerInfo.hidden = true;
          foundCustomer.hidden = true;
      foundProjectRow.hidden = true;
      newCustomer.hidden = true;
      document.getElementById('call-logs-sidebar').hidden = true;
          var notif = document.getElementById('nc-notification');
          var saveBtn = document.getElementById('save-call-btn');
          if (code.length > 0 && code.length !== 10) {
            notif.hidden = false;
            saveBtn.disabled = true;
          } else {
            notif.hidden = true;
          }
          if (!/^\\d{10}$/.test(code)) { saveBtn.disabled = true; return; }
          ncTimer = setTimeout(async function(){
            try {
              var res = await fetch('/api/customers/by-national-code?code=' + encodeURIComponent(code));
              var data = await res.json();
              if (data.id) {
                document.getElementById('customer-id').value = data.id;
                document.querySelector('[name="customer_name_display"]').value = data.full_name;
                document.querySelector('[name="customer_phone_display"]').value = data.primary_phone;
                var sel = document.getElementById('project-select');
                var html = '<option value="">بدون پروژه</option>';
                if (data.projects) {
                  for (var i = 0; i < data.projects.length; i++) {
                    html += '<option value="' + data.projects[i].id + '">' + data.projects[i].name + '</option>';
                  }
                }
                sel.innerHTML = html;
                var projList = document.getElementById('found-customer-projects');
                projList.innerHTML = '';
                if (data.projects && data.projects.length > 0) {
                  for (var i = 0; i < data.projects.length; i++) {
                    addFoundCustomerProjectItem(data.projects[i].id, data.projects[i].name);
                  }
                }
                var logsDiv = document.getElementById('call-logs-sidebar-list');
                if (data.recent_calls && data.recent_calls.length > 0) {
                  var logsHtml = '';
                  for (var i = 0; i < data.recent_calls.length; i++) {
                    var c = data.recent_calls[i];
                    logsHtml += '<a href="/call-logs/' + c.id + '" class="call-log-item" style="text-decoration:none;color:inherit;display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 8px;border-radius:6px"><span class="call-log-time">' + (c.call_started_at_display || '—') + '</span><span class="call-log-topic">' + (c.problem_type_label || '—') + '</span></a>';
                  }
                  logsDiv.innerHTML = logsHtml;
                  document.getElementById('call-logs-sidebar').hidden = false;
                }
                saveBtn.disabled = false;
                fetchFollowUpHistory(data.id);
                populateCustomerProjects(data);
                foundCustomer.hidden = false;
                foundProjectRow.hidden = false;
                customerInfo.hidden = false;
              } else {
                saveBtn.disabled = false;
                document.getElementById('customer-id').value = '';
                document.querySelector('[name="new_customer_name"]').value = '';
                document.querySelector('[name="new_customer_phone"]').value = '';
                document.querySelector('[name="new_customer_city"]').value = '';
                document.getElementById('call-logs-sidebar').hidden = true;
                newCustomer.hidden = false;
                customerInfo.hidden = false;
              }
            } catch(e) {
              console.error(e);
            }
          }, 400);
        });
        function populateCustomerProjects(data) {
          var projDiv = document.getElementById('customer-projects-sidebar-list');
          projDiv.innerHTML = '';
          if (data.projects && data.projects.length > 0) {
            var projHtml = '';
            var stageMap = {"planning": "برنامه ریزی", "permits": "مجوزها", "foundation": "فونداسیون", "structure": "اسکلت", "brickwork": "دیوارچینی", "electrical_plumbing": "برق و لوله کشی", "finishing": "نازک کاری", "final_inspection": "بازرسی نهایی", "ready": "آماده", "delivered": "تحویل شده", "paused": "متوقف"};
            var regMap = {"open": "باز", "closed": "بسته", "coming_soon": "به زودی", "sold_out": "تکمیل ظرفیت"};
            for (var i = 0; i < data.projects.length; i++) {
              var p = data.projects[i];
              var stageLabel = stageMap[p.stage] || p.stage;
              var regLabel = regMap[p.registration_status] || p.registration_status;
              projHtml += '<a href="/projects/' + p.id + '" class="call-log-item" style="text-decoration:none;color:inherit;display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 8px;border-radius:6px">';
              projHtml += '<span class="call-log-topic" style="font-weight:600">' + p.name + '</span>';
              projHtml += '<small class="muted" style="font-size:.7rem;width:100%"><span>' + stageLabel + '</span> | <span>' + p.progress_percentage + '%</span> | <span class="pill" style="font-size:.65rem">' + regLabel + '</span></small>';
              projHtml += '</a>';
            }
            projDiv.innerHTML = projHtml;
          } else {
            projDiv.innerHTML = '<small class="muted" style="padding:6px 8px;display:block">هیچ پروژه‌ای ثبت نشده است</small>';
          }
        }
        function addNewCustomerProject() {
          var wrap = document.createElement('div');
          wrap.className = 'project-pick';
          wrap.innerHTML = '<select name="new_customer_project_ids">{project_opts}</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button>';
          document.getElementById('new-customer-projects').appendChild(wrap);
        }
        async function fetchFollowUpHistory(customerId) {
          try {
            var res = await fetch('/api/customers/follow-up-history?customer_id=' + customerId);
            var data = await res.json();
            var fuDiv = document.getElementById('follow-up-sidebar-list');
            var sidebar = document.getElementById('call-logs-sidebar');
            if (data.followups && data.followups.length > 0) {
              var fuHtml = '';
              for (var i = 0; i < data.followups.length; i++) {
                var fu = data.followups[i];
                var statusClass = fu.status === 'done' ? 'status-done' : fu.status === 'cancelled' ? 'status-cancelled' : 'status-pending';
                fuHtml += '<a href="/follow-ups/' + fu.id + '" class="call-log-item" style="text-decoration:none;color:inherit;display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 8px;border-radius:6px">';
                fuHtml += '<span class="call-log-time">' + (fu.due_at_display || '—') + '</span>';
                fuHtml += '<span class="pill ' + statusClass + '">' + (fu.status_label || '—') + '</span>';
                fuHtml += '<span class="call-log-topic">' + (fu.reason || '—') + '</span>';
                if (fu.last_comment) {
                  fuHtml += '<small class="muted" style="display:block;margin-top:2px">نتیجه: ' + fu.last_comment + '</small>';
                }
                fuHtml += '</a>';
              }
              fuDiv.innerHTML = fuHtml;
              if (sidebar.hidden) sidebar.hidden = false;
            }
          } catch(e) {
            console.error('Follow-up fetch error:', e);
          }
        }
        function addFoundCustomerProject() {
          addFoundCustomerProjectItem('', '');
        }
        function addFoundCustomerProjectItem(pid, pname) {
          var wrap = document.createElement('div');
          wrap.className = 'project-pick';
          if (pid) {
            wrap.innerHTML = '<input type="hidden" name="existing_customer_project_ids" value="' + pid + '"><span class="pill">' + pname + '</span>';
          } else {
            wrap.innerHTML = '<select name="existing_customer_project_ids" onchange="syncCallProjectSelect(this)">{project_opts}</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button>';
          }
          document.getElementById('found-customer-projects').appendChild(wrap);
        }
        function toggleFollowUpFields() {
          var fields = document.getElementById('follow-up-fields');
          var notesField = document.getElementById('follow-up-notes-field');
          var cb = document.querySelector('[name="follow_up_required"]');
          fields.style.display = cb.checked ? 'flex' : 'none';
          notesField.style.display = cb.checked ? 'block' : 'none';
        }
        function syncCallProjectSelect(srcSelect) {
          var pid = srcSelect.value;
          var pname = srcSelect.options[srcSelect.selectedIndex].text;
          if (!pid) return;
          var callSel = document.getElementById('project-select');
          for (var i = 0; i < callSel.options.length; i++) {
            if (callSel.options[i].value === pid) return;
          }
          var opt = document.createElement('option');
          opt.value = pid;
          opt.text = pname;
          callSel.appendChild(opt);
          callSel.value = pid;
        }

        var lastLiveId = null;
        var liveFilled = false;
        function fillLiveDuration(seconds) {
          var d = document.querySelector('[name="call_duration"]');
          if (!d || seconds == null) return;
          d.value = Math.max(1, Math.round(seconds / 60));
          liveFilled = true;
        }
        function fillLiveCallForm(lc) {
          var saveBtn = document.getElementById('save-call-btn');
          lastLiveId = lc.id;
          liveFilled = false;
          var phone = (lc.phone || '').trim();
          var name = (lc.caller_name || '').trim();
          fetch('/api/customers/by-phone?phone=' + encodeURIComponent(phone))
            .then(function(r) { return r.json(); })
            .then(function(data) {
              if (data.id) {
                document.getElementById('customer-id').value = data.id;
                document.querySelector('[name="customer_name_display"]').value = data.full_name;
                document.querySelector('[name="customer_phone_display"]').value = data.primary_phone;
                var sel = document.getElementById('project-select');
                var html = '<option value="">بدون پروژه</option>';
                if (data.projects) {
                  for (var i = 0; i < data.projects.length; i++) {
                    html += '<option value="' + data.projects[i].id + '">' + data.projects[i].name + '</option>';
                  }
                }
                sel.innerHTML = html;
                var projList = document.getElementById('found-customer-projects');
                projList.innerHTML = '';
                if (data.projects && data.projects.length > 0) {
                  for (var i = 0; i < data.projects.length; i++) {
                    addFoundCustomerProjectItem(data.projects[i].id, data.projects[i].name);
                  }
                }
                var logsDiv = document.getElementById('call-logs-sidebar-list');
                if (data.recent_calls && data.recent_calls.length > 0) {
                  var logsHtml = '';
                  for (var i = 0; i < data.recent_calls.length; i++) {
                    var c = data.recent_calls[i];
                    logsHtml += '<a href="/call-logs/' + c.id + '" class="call-log-item" style="text-decoration:none;color:inherit;display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 8px;border-radius:6px"><span class="call-log-time">' + (c.call_started_at_display || '—') + '</span><span class="call-log-topic">' + (c.problem_type_label || '—') + '</span></a>';
                  }
                  logsDiv.innerHTML = logsHtml;
                  document.getElementById('call-logs-sidebar').hidden = false;
                }
                fetchFollowUpHistory(data.id);
                populateCustomerProjects(data);
                document.getElementById('found-customer').hidden = false;
                document.getElementById('found-project-row').hidden = false;
              } else {
                document.getElementById('customer-id').value = '';
                document.querySelector('[name="new_customer_name"]').value = name;
                document.querySelector('[name="new_customer_phone"]').value = phone;
                document.querySelector('[name="new_customer_city"]').value = '';
                document.getElementById('call-logs-sidebar').hidden = true;
                document.getElementById('new-customer').hidden = false;
              }
              document.getElementById('customer-info').hidden = false;
              if (saveBtn) saveBtn.disabled = false;
              if (lc.ended && lc.duration_seconds != null) fillLiveDuration(lc.duration_seconds);
            })
            .catch(function(e) { console.error(e); });
        }
        function pollLiveCall() {
          fetch('/api/live-call')
            .then(function(r) { return r.json(); })
            .then(function(lc) {
              if (!lc.found) return;
              if (lc.id !== lastLiveId) { fillLiveCallForm(lc); }
              else if (!liveFilled && lc.ended && lc.duration_seconds != null) { fillLiveDuration(lc.duration_seconds); }
            })
            .catch(function() {});
        }
        setInterval(pollLiveCall, 2000);

        </script>
        """.replace("{today}", today_jalali).replace("{time}", current_time).replace("{tomorrow}", tomorrow_jalali).replace("{opts}", problem_opts).replace("{fu_opts}", fu_opts).replace("{call_opts}", call_opts).replace("{user_opts}", user_opts).replace("{project_opts}", project_opts)

        body = f"""<div class="dashboard">
          <div class="stats">
            <div class="stat"><span>{total}</span><small>مشتریان</small></div>
            <div class="stat"><span>{calls_today}</span><small>تماس‌های امروز</small></div>
            <div class="stat"><span>{follow_today}</span><small>پیگیری امروز</small></div>
            <div class="stat"><span>{overdue}</span><small>پیگیری عقب افتاده</small></div>
            <div class="stat"><span>{signed}</span><small>ثبت نام شده</small></div>
          </div>
          <div class="dash-table">
            <h2>پیگیری‌های امروز / عقب افتاده</h2>
            {table}
          </div>
          {call_form}
        </div>"""
        self.send_html(body, "داشبورد")

    def follow_table(self, rows):
        if not rows:
            return '<p class="muted">هیچ پیگیری فعالی وجود ندارد.</p>'
        out = ['<table><thead><tr><th>مشتری</th><th>موضوع</th><th>اپراتور</th><th>مهلت</th><th>اولویت</th><th>عملیات</th></tr></thead><tbody>']
        for r in rows:
            pid = r["id"]
            pri = label(r["priority"])
            due = to_jalali_display(r["due_at"])[:16]
            out.append(f'<tr><td>{esc(r["full_name"])}</td><td>{esc(r["reason"] or "—")}</td><td>{esc(r["agent"] or "—")}</td><td>{due}</td><td><span class="pill prio-{esc(r["priority"])}">{pri}</span></td><td class="actions"><a href="/follow-ups/{pid}" class="small">مشاهده</a></td></tr>')
        out.append('</tbody></table>')
        return "".join(out)

    def count_unviewed_followups(self):
        if not self.current_user:
            return 0
        row = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE assigned_agent_id=? AND status='pending' AND viewed_at IS NULL",
            (self.current_user['id'],)).fetchone()
        return row['c'] if row else 0

    def followups(self):
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_where = "" if is_manager else " AND (f.assigned_agent_id=? OR f.created_by=?)"
        agent_params = () if is_manager else (uid, uid)
        # Mark all pending follow-ups assigned to current user as viewed
        self.conn.execute("UPDATE follow_ups SET viewed_at=? WHERE assigned_agent_id=? AND status='pending' AND viewed_at IS NULL",
            (now_iso(), uid))
        self.conn.commit()
        # status filter from query string
        status_filter = self.query.get('status', ['pending'])[0]
        if status_filter not in ('pending', 'done', 'cancelled', 'all'):
            status_filter = 'pending'
        status_where = "" if status_filter == 'all' else f" AND f.status='{status_filter}'"
        query = f'''SELECT f.*, c.full_name, c.primary_phone, c.national_code, u.name agent FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            WHERE 1=1{status_where}{agent_where}
            ORDER BY CASE f.status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END, f.due_at ASC'''
        rows = self.conn.execute(query, agent_params).fetchall()
        tabs = ''
        for st, label_fa in [('pending', 'در انتظار'), ('done', 'انجام شده'), ('cancelled', 'لغو شده'), ('all', 'همه')]:
            active = ' active' if st == status_filter else ''
            tabs += f'<a href="/follow-ups?status={st}" class="tab{active}">{label_fa}</a>'
        out = ['<div class="filters"><h2>لیست پیگیری‌ها</h2>'
               '<div style="flex:1;max-width:350px"><input type="text" id="fu-search" class="search-input" placeholder="🔍 جستجو..." oninput="filterFollowUps()"></div>'
               '</div>'
               f'<div class="tab-bar">{tabs}</div>'
               '<div class="filters" style="margin-bottom:12px">'
               '<label style="display:flex;align-items:center;gap:6px;font-size:.8rem">از تاریخ: <input type="text" id="fu-date-from" class="jalali-date search-input" placeholder="از تاریخ..." style="width:140px" onchange="filterFollowUps()"></label>'
               '<label style="display:flex;align-items:center;gap:6px;font-size:.8rem">تا تاریخ: <input type="text" id="fu-date-to" class="jalali-date search-input" placeholder="تا تاریخ..." style="width:140px" onchange="filterFollowUps()"></label>'
               '<button type="button" class="small secondary" onclick="clearDateFilters()">✕ پاک کردن فیلتر</button>'
               '</div>'
               '<div class="follow-up-list" id="follow-up-list">']
        for r in rows:
            due = to_jalali_display(r["due_at"])[:16]
            over = ''
            try:
                if r['status'] == 'pending' and datetime.fromisoformat(r["due_at"]) < datetime.now():
                    over = ' (عقب افتاده)'
            except Exception:
                pass
            notes = esc(r["notes"] or '')
            national_code = esc(r["national_code"] or '')
            completed_display = ''
            if r['completed_at']:
                completed_display = f'<small>تکمیل: {to_jalali_display(r["completed_at"])[:16]}</small>'
            out.append(f'''<div class="follow-up-card fu-card">
                <div class="fu-header"><strong>{esc(r["full_name"])}</strong><span class="pill prio-{esc(r["priority"])} status-{esc(r["status"])}">{label(r["priority"])}</span></div>
                <span aria-hidden="true" style="display:none">{national_code}</span>
                <div class="fu-body"><small>موضوع: {esc(r["reason"] or "—")}</small><small>مهلت: {due}{over}</small><small>اپراتور: {esc(r["agent"] or "—")}</small><small>وضعیت: <span class="pill status-{esc(r["status"])}">{label(r["status"])}</span></small>{completed_display}</div>
                <div class="fu-notes"><p>{notes}</p></div>
                <div class="fu-actions">
                    <form method="post" action="/follow-ups/{r['id']}/reassign" style="display:inline-flex;gap:4px;align-items:center">
                        <select name="agent_id" onchange="this.form.submit()">{user_options(self.conn, r['assigned_agent_id'], blank='انتخاب اپراتور')}</select>
                        <input type="hidden" name="reassign" value="1">
                    </form>''')
            if r['status'] == 'pending':
                out.append(f'''
                    <form method="post" action="/follow-ups/{r['id']}/complete" style="display:inline">
                        <button type="submit" class="small">انجام شد</button>
                    </form>
                    <form method="post" action="/follow-ups/{r['id']}/cancel" style="display:inline">
                        <button type="submit" class="small secondary">لغو</button>
                    </form>
                    <button type="button" class="small secondary" onclick="toggleEditCard('{r['id']}')">✏️</button>''')
            out.append(f'''
                    
                    <a href="/follow-ups/{r['id']}" class="button small secondary">چت / جزئیات</a>
                </div>
            </div>
            <div class="fu-edit-form" id="fu-edit-{r['id']}" style="display:none">
                <form method="post" action="/follow-ups/{r['id']}/edit" style="display:flex;flex-direction:column;gap:8px;padding:12px">
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        <input name="reason" value="{esc(r['reason'] or '')}" placeholder="موضوع" style="flex:1;min-width:120px;padding:4px 8px;font-size:.8rem">
                        <select name="priority" style="width:auto;padding:4px 8px;font-size:.8rem">{options(PRIORITIES, r['priority'])}</select>
                        <input class="jalali-datetime" name="due_at" value="{jalali_input_value(r['due_at'], with_time=True)[:16]}" style="width:180px;padding:4px 8px;font-size:.8rem" placeholder="مهلت جدید">
                    </div>
                    <textarea name="notes" placeholder="یادداشت" style="padding:4px 8px;font-size:.8rem;min-height:40px">{esc(r['notes'] or '')}</textarea>
                    <div style="display:flex;gap:4px">
                        <button type="submit" class="small">ذخیره</button>
                        <button type="button" class="small secondary" onclick="toggleEditCard(\'{r['id']}\')">انصراف</button>
                    </div>
                </form>
            </div>''')
        out.append('</div>')
        return self.send_html("".join(out), "پیگیری‌ها")

    def followup_action(self, path, method):
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return self.not_found()
        fu_id = parts[1]
        action = parts[2] if len(parts) > 2 else ''
        if method == 'POST':
            if action == 'reassign':
                d = self.form()
                agent_id = d.get('agent_id', '').strip()
                if agent_id:
                    self.conn.execute("UPDATE follow_ups SET assigned_agent_id=?, viewed_at=NULL, updated_at=? WHERE id=?",
                        (agent_id, now_iso(), fu_id))
                else:
                    self.conn.execute("UPDATE follow_ups SET assigned_agent_id=NULL, viewed_at=NULL, updated_at=? WHERE id=?",
                        (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'complete':
                self.conn.execute("UPDATE follow_ups SET status='done', completed_at=?, updated_at=? WHERE id=?",
                    (now_iso(), now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'cancel':
                self.conn.execute("UPDATE follow_ups SET status='cancelled', updated_at=? WHERE id=?",
                    (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'comment':
                d = self.form()
                comment = d.get('comment', '').strip()
                if comment:
                    self.conn.execute("INSERT INTO follow_up_comments(follow_up_id,user_id,comment,created_at) VALUES(?,?,?,?)",
                        (fu_id, self.current_user['id'], comment, now_iso()))
                    self.conn.commit()
                return self.redirect(f'/follow-ups/{fu_id}')
            if action == 'edit':
                d = self.form()
                reason = d.get('reason', '').strip()
                priority = d.get('priority', 'normal')
                due_at = parse_jalali(d.get('due_at', ''), True) or now_iso()
                agent_id = d.get('assigned_agent_id', '').strip()
                notes = d.get('notes', '').strip() or None
                # Reset viewed_at if agent changed via edit
                current_agent = self.conn.execute("SELECT assigned_agent_id FROM follow_ups WHERE id=?", (fu_id,)).fetchone()
                new_agent = int(agent_id) if agent_id else None
                if current_agent and str(current_agent['assigned_agent_id'] or '') != str(new_agent or ''):
                    self.conn.execute("UPDATE follow_ups SET viewed_at=NULL, updated_at=? WHERE id=?", (now_iso(), fu_id))
                self.conn.execute("UPDATE follow_ups SET reason=?, priority=?, assigned_agent_id=?, due_at=?, notes=?, updated_at=? WHERE id=?",
                    (reason, priority, agent_id or None, due_at, notes, now_iso(), fu_id))
                self.conn.commit()
                return self.redirect(f'/follow-ups/{fu_id}')
        # GET single follow-up detail with chat and edit capability
        row = self.conn.execute('''SELECT f.*, c.full_name, c.primary_phone, u.name agent, cu.name creator_name
            FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            LEFT JOIN users cu ON cu.id=f.created_by
            WHERE f.id=?''', (fu_id,)).fetchone()
        if not row:
            return self.not_found()
        # Mark this follow-up as viewed by the assigned user
        if row['assigned_agent_id'] == self.current_user['id']:
            self.conn.execute("UPDATE follow_ups SET viewed_at=? WHERE id=? AND viewed_at IS NULL", (now_iso(), fu_id))
            self.conn.commit()
        due = to_jalali_display(row["due_at"])[:16]
        created_display = to_jalali_display(row["created_at"])[:16] if row["created_at"] else ''
        comments = self.conn.execute('''SELECT fc.*, u.name user_name FROM follow_up_comments fc
            LEFT JOIN users u ON u.id=fc.user_id
            WHERE fc.follow_up_id=? ORDER BY fc.created_at ASC''', (fu_id,)).fetchall()
        comments_html = ''
        for c in comments:
            c_time = to_jalali_display(c['created_at'])[:16] if c['created_at'] else ''
            c_name = esc(c['user_name'] or 'سیستم')
            c_text = esc(c['comment'])
            comments_html += f'<div class="chat-msg"><strong>{c_name}</strong> <small class="muted">{c_time}</small><p>{c_text}</p></div>'
        if not comments_html:
            comments_html = '<p class="muted">هنوز پیامی ثبت نشده است.</p>'
        prio_opts = options(PRIORITIES, row['priority'])
        user_opts_all = user_options(self.conn, row['assigned_agent_id'], blank='انتخاب اپراتور')
        edit_form = ''
        if row['status'] == 'pending':
            edit_form = f'''<details class="panel" style="padding:16px;margin-top:12px">
            <summary style="cursor:pointer;font-weight:600;font-size:.9rem">✏️ ویرایش پیگیری</summary>
            <form method="post" action="/follow-ups/{fu_id}/edit" class="form-layout" style="margin-top:8px;box-shadow:none;padding:0">
                <div class="form-row"><label>موضوع (دلیل)<input name="reason" value="{esc(row['reason'] or '')}"></label>
                <label>اولویت<select name="priority">{prio_opts}</select></label></div>
                <div class="form-row"><label>مهلت پیگیری<input class="jalali-datetime" name="due_at" value="{jalali_input_value(row['due_at'], with_time=True)[:16]}"></label>
                <label>مسئول<select name="assigned_agent_id">{user_opts_all}</select></label></div>
                <label>یادداشت‌ها<textarea name="notes">{esc(row['notes'] or '')}</textarea></label>
                <button type="submit" class="small">ذخیره تغییرات</button>
            </form></details>'''
        body = f'''<div class="fu-detail-layout">
          <div class="panel" style="padding:16px">
            <div class="top"><h2>پیگیری: {esc(row["full_name"])}</h2><a href="/follow-ups" class="button small secondary">← بازگشت</a></div>
            <div class="fu-body" style="margin-top:8px">
                <small>مشتری: {esc(row["full_name"])}</small>
                <small>تلفن: {esc(row["primary_phone"])}</small>
                <small>موضوع: {esc(row["reason"] or "—")}</small>
                <small>مهلت: {due}</small>
                <small>اولویت: <span class="pill prio-{esc(row["priority"])}">{label(row["priority"])}</span></small>
                <small>اپراتور: {esc(row["agent"] or "—")}</small>
                <small>ایجادکننده: {esc(row["creator_name"] or "—")}</small>
                <small>تاریخ ایجاد: {created_display}</small>
                <small>وضعیت: <span class="pill status-{esc(row["status"])}">{label(row["status"])}</span></small>
            </div>
          </div>
          {edit_form}
          <div class="panel" style="padding:16px;margin-top:12px">
            <h3>💬 گفتگوی پیگیری</h3>
            <div class="chat-box" id="chat-box">{comments_html}</div>
            <form method="post" action="/follow-ups/{fu_id}/comment" class="chat-form" style="margin-top:8px;display:flex;gap:8px">
                <textarea name="comment" placeholder="پیام خود را بنویسید..." style="flex:1;min-height:44px" required></textarea>
                <button type="submit" class="small" style="align-self:flex-end">ارسال</button>
            </form>
          </div>
          <div class="panel" style="padding:16px;margin-top:12px">
            <h3>یادداشت‌ها</h3>
            <p>{esc(row["notes"] or "—")}</p>
          </div>
        </div>'''
        return self.send_html(body, f"پیگیری: {row['full_name']}")

    def call_log_detail(self, path, method):
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return self.not_found()
        call_id = parts[1]
        if method == 'POST':
            action = parts[2] if len(parts) > 2 else ''
            if action == 'edit':
                d = self.form()
                call_date = parse_jalali(d.get('call_started_date', ''), False) or ''
                call_time = (d.get('call_started_time') or '').strip()
                call_started_at = f"{call_date[:10]} {call_time[:5]}" if call_date and call_time else ''
                dur = d.get('call_duration', '').strip()
                dur_seconds = int(float(dur) * 60) if dur else None
                self.conn.execute('''UPDATE call_logs SET call_type=?, problem_type=?, project_id=?,
                    call_started_at=?, call_duration_seconds=?, notes=?, updated_at=? WHERE id=?''',
                    (d.get('call_type', 'incoming'), d.get('problem_type'),
                     d.get('project_id') or None, call_started_at or None,
                     dur_seconds, d.get('notes', '').strip() or None, now_iso(), call_id))
                self.conn.commit()
                return self.redirect(f'/call-logs/{call_id}')
            if action == 'delete':
                self.conn.execute("DELETE FROM call_logs WHERE id=?", (call_id,))
                self.conn.commit()
                return self.redirect('/reports')
            return self.not_found()
        # GET - show detail page
        row = self.conn.execute('''SELECT cl.*, c.full_name, c.primary_phone, u.name agent,
            p.name project FROM call_logs cl
            JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN users u ON u.id=cl.agent_id
            LEFT JOIN projects p ON p.id=cl.project_id
            WHERE cl.id=?''', (call_id,)).fetchone()
        if not row:
            return self.not_found()
        dur_display = ''
        if row["call_duration_seconds"]:
            d = int(row["call_duration_seconds"])
            dur_display = f'{d // 60}:{d % 60:02d} \u0645\u06cc\u0646'
        date_val = str(row["call_started_at"] or '')[:10]
        time_val = str(row["call_started_at"] or '')[:16]
        can_edit = self.current_user["role"] == "manager" or row["agent_id"] == self.current_user["id"]
        call_type_opts = options(CALL_TYPES, row['call_type'])
        problem_opts = lookup_options(self.conn, 'problem_types', row['problem_type'], blank='\u0627\u0646\u062a\u062e\u0627\u0628 \u06a9\u0646\u06cc\u062f')
        project_opts = project_options(self.conn, row['project_id'], blank='\u0628\u062f\u0648\u0646 \u067e\u0631\u0648\u0698\u0647')
        edit_section = ''
        if can_edit:
            edit_section = f'''<details class="panel" style="padding:16px;margin-top:12px">
            <summary style="cursor:pointer;font-weight:600;font-size:.9rem">\u270f\ufe0f \u0648\u06cc\u0631\u0627\u06cc\u0634 \u062a\u0645\u0627\u0633</summary>
            <form method="post" action="/call-logs/{call_id}/edit" class="form-layout" style="margin-top:8px;box-shadow:none;padding:0">
                <div class="form-row">
                    <label>\u062a\u0627\u0631\u06cc\u062e \u0634\u0631\u0648\u0639<input class="jalali-date" name="call_started_date" value="{jalali_input_value(date_val)}"></label>
                    <label>\u0633\u0627\u0639\u062a \u0634\u0631\u0648\u0639<input type="time" name="call_started_time" value="{esc(time_val[11:16]) if len(time_val) > 10 else ''}"></label>
                </div>
                <div class="form-row">
                    <label>\u0646\u0648\u0639 \u062a\u0645\u0627\u0633<select name="call_type">{call_type_opts}</select></label>
                    <label>\u0645\u0648\u0636\u0648\u0639 \u062a\u0645\u0627\u0633<select name="problem_type">{problem_opts}</select></label>
                    <label>\u0645\u062f\u062a (\u062f\u0642\u06cc\u0642\u0647)<input type="number" name="call_duration" min="0" step="1" value="{int(row["call_duration_seconds"] / 60) if row["call_duration_seconds"] else ''}"></label>
                </div>
                <div class="form-row">
                    <label>\u067e\u0631\u0648\u0698\u0647<select name="project_id">{project_opts}</select></label>
                </div>
                <label>\u06cc\u0627\u062f\u062f\u0627\u0634\u062a\u200c\u0647\u0627<textarea name="notes">{esc(row["notes"] or '')}</textarea></label>
                <div style="display:flex;gap:8px">
                    <button type="submit" class="small">\u0630\u062e\u06cc\u0631\u0647 \u062a\u063a\u06cc\u06cc\u0631\u0627\u062a</button>
                </div>
            </form>
            <form method="post" action="/call-logs/{call_id}/delete" style="margin-top:8px" onsubmit="return confirm('\u0622\u06cc\u0627 \u0627\u0632 \u062d\u0630\u0641 \u0627\u06cc\u0646 \u062a\u0645\u0627\u0633 \u0627\u0637\u0645\u06cc\u0646\u0627\u0646 \u062f\u0627\u0631\u06cc\u062f\u061f')">
                <button type="submit" class="small danger">\U0001F5D1\ufe0f \u062d\u0630\u0641 \u062a\u0645\u0627\u0633</button>
            </form></details>'''
        body = f'''<div class="fu-detail-layout">
          <div class="panel" style="padding:16px">
            <div class="top"><h2>\u062c\u0632\u0626\u06cc\u0627\u062a \u062a\u0645\u0627\u0633 #{call_id}</h2><a href="/reports" class="button small secondary">\u2190 \u0628\u0627\u0632\u06af\u0634\u062a \u0628\u0647 \u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627</a></div>
            <div class="fu-body" style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <small>\u0645\u0634\u062a\u0631\u06cc: <a href="/customers/{row["customer_id"]}"><strong>{esc(row["full_name"])}</strong></a></small>
                <small>\u062a\u0644\u0641\u0646: {esc(row["primary_phone"])}</small>
                <small>\u0646\u0648\u0639 \u062a\u0645\u0627\u0633: <span class="pill">{label(row["call_type"])}</span></small>
                <small>\u0645\u0648\u0636\u0648\u0639: {label(row["problem_type"]) or "\u2014"}</small>
                <small>\u067e\u0631\u0648\u0698\u0647: {esc(row["project"] or "\u2014")}</small>
                <small>\u0627\u067e\u0631\u0627\u062a\u0648\u0631: {esc(row["agent"] or "\u2014")}</small>
                <small>\u062a\u0627\u0631\u06cc\u062e \u0648 \u0633\u0627\u0639\u062a: {money_date(row["call_started_at"])[:16]}</small>
                <small>\u0645\u062f\u062a: {dur_display or "\u2014"}</small>
                <small style="grid-column:1/-1">\u062a\u0627\u0631\u06cc\u062e \u062b\u0628\u062a: {money_date(row["created_at"])[:16]}</small>
            </div>
          </div>
          {edit_section}
          <div class="panel" style="padding:16px;margin-top:12px">
            <h3>\U0001F4DD \u06cc\u0627\u062f\u062f\u0627\u0634\u062a\u200c\u0647\u0627\u06cc \u062a\u0645\u0627\u0633</h3>
            <p>{esc(row["notes"] or "\u2014")}</p>
          </div>
        </div>'''
        return self.send_html(body, f"\u062a\u0645\u0627\u0633 #{call_id}")


    def customers(self, method):
        rows = self.conn.execute('''SELECT c.*, u.name agent_name FROM customers c
            LEFT JOIN users u ON u.id=c.assigned_agent_id
            ORDER BY c.updated_at DESC'''
        ).fetchall()
        out = ['<div class="top"><h2>مشتریان</h2><a href="/customers/new" class="button">+ مشتری جدید</a>'
               '<div style="flex:1;max-width:350px"><input type="text" id="cust-search" class="search-input" placeholder="🔍 جستجو در مشتریان..." oninput="filterTable(\'cust-table\', this.value)"></div>'
               '</div>'
               '<div class="table-wrap"><table id="cust-table"><thead><tr><th>نام</th><th>کد ملی</th><th>تلفن</th><th>وضعیت</th><th>اپراتور</th><th>تاریخ</th><th>عملیات</th></tr></thead><tbody>']
        for r in rows:
            delete_confirm = 'آیا از حذف این مشتری اطمینان دارید؟'
            out.append(f'<tr><td><a href="/customers/{r["id"]}">{esc(r["full_name"])}</a></td><td>{esc(r["national_code"] or "—")}</td><td>{esc(r["primary_phone"])}</td><td>{label(r["status"])}</td><td>{esc(r["agent_name"] or "—")}</td><td>{money_date(r["created_at"])}</td><td class="actions" style="display:flex;gap:4px"><a href="/customers/{r["id"]}" class="small">✏️</a><form method="post" action="/customers/{r["id"]}/delete" style="display:inline" onsubmit="return confirm(\'' + delete_confirm + '\')"><button type="submit" class="small secondary">🗑️</button></form></td></tr>')
        out.append('</tbody></table></div>')
        return self.send_html("".join(out), "مشتریان")

    def customer_form(self, method):
        if method == 'POST':
            d = self.form()
            self.conn.execute('''INSERT INTO customers(full_name,national_code,primary_phone,secondary_phone,email,city,address,source,status,assigned_agent_id,general_notes,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (d.get('full_name','').strip(), d.get('national_code','').strip() or None, d.get('primary_phone','').strip(),
                 d.get('secondary_phone','').strip() or None, d.get('email','').strip() or None, d.get('city','').strip() or None,
                 d.get('address','').strip() or None, d.get('source','phone_call'), d.get('status','new_lead'),
                 d.get('assigned_agent_id') or None, d.get('general_notes','').strip() or None,
                 self.current_user['id'], now_iso(), now_iso()))
            cid = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
            self.conn.commit()
            return self.redirect(f'/customers/{cid}')
        src_opts = lookup_options(self.conn, 'sources', blank='انتخاب منبع')
        agent_opts = user_options(self.conn, blank='بدون اپراتور')
        body = f'''<h2>مشتری جدید</h2>
            <form method="post" class="form-layout">
                <div class="form-row"><label>نام کامل<input name="full_name" required></label><label>کد ملی<input name="national_code" maxlength="10" inputmode="numeric"></label></div>
                <div class="form-row"><label>تلفن اصلی<input name="primary_phone" required></label><label>تلفن دوم<input name="secondary_phone"></label></div>
                <div class="form-row"><label>ایمیل<input name="email" type="email"></label><label>شهر<input name="city"></label></div>
                <div class="form-row"><label>آدرس<input name="address"></label></div>
                <div class="form-row"><label>منبع<select name="source">{src_opts}</select></label><label>اپراتور<select name="assigned_agent_id">{agent_opts}</select></label></div>
                <label>یادداشت‌ها<textarea name="general_notes"></textarea></label>
                <button>ذخیره</button>
            </form>'''
        return self.send_html(body, "مشتری جدید")

    def customer_routes(self, path, method):
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return self.not_found()
        cid = parts[1]
        if method == 'POST' and len(parts) >= 3 and parts[2] == 'delete':
            self.conn.execute("DELETE FROM customers WHERE id=?", (cid,))
            self.conn.commit()
            return self.redirect('/customers')
        if method == 'POST' and len(parts) >= 3 and parts[2] == 'edit':
            d = self.form()
            self.conn.execute('''UPDATE customers SET full_name=?,national_code=?,primary_phone=?,secondary_phone=?,email=?,city=?,address=?,source=?,status=?,assigned_agent_id=?,general_notes=?,updated_at=? WHERE id=?''',
                (d.get('full_name','').strip(), d.get('national_code','').strip() or None, d.get('primary_phone','').strip(),
                 d.get('secondary_phone','').strip() or None, d.get('email','').strip() or None, d.get('city','').strip() or None,
                 d.get('address','').strip() or None, d.get('source','phone_call'), d.get('status','new_lead'),
                 d.get('assigned_agent_id') or None, d.get('general_notes','').strip() or None, now_iso(), cid))
            self.conn.commit()
            return self.redirect(f'/customers/{cid}')
        row = self.conn.execute('''SELECT c.*, u.name agent_name FROM customers c
            LEFT JOIN users u ON u.id=c.assigned_agent_id WHERE c.id=?''', (cid,)).fetchone()
        if not row:
            return self.not_found()
        src_opts = lookup_options(self.conn, 'sources', row['source'])
        agent_opts = user_options(self.conn, row['assigned_agent_id'], blank='بدون اپراتور')
        body = f'''<h2>{esc(row["full_name"])}</h2>
            <form method="post" action="/customers/{cid}/edit" class="form-layout">
                <div class="form-row"><label>نام کامل<input name="full_name" value="{esc(row["full_name"])}" required></label><label>کد ملی<input name="national_code" value="{esc(row["national_code"] or '')}" maxlength="10" inputmode="numeric"></label></div>
                <div class="form-row"><label>تلفن اصلی<input name="primary_phone" value="{esc(row["primary_phone"])}" required></label><label>تلفن دوم<input name="secondary_phone" value="{esc(row["secondary_phone"] or '')}"></label></div>
                <div class="form-row"><label>ایمیل<input name="email" type="email" value="{esc(row['email'] or '')}"></label><label>شهر<input name="city" value="{esc(row['city'] or '')}"></label></div>
                <div class="form-row"><label>آدرس<input name="address" value="{esc(row['address'] or '')}"></label></div>
                <div class="form-row"><label>منبع<select name="source">{src_opts}</select></label><label>اپراتور<select name="assigned_agent_id">{agent_opts}</select></label></div>
                <label>یادداشت‌ها<textarea name="general_notes">{esc(row["general_notes"] or '')}</textarea></label>
                <button>ذخیره</button>
            </form>'''
        return self.send_html(body, f"مشتری: {row['full_name']}")

    def projects(self, method):
        rows = self.conn.execute("SELECT * FROM projects WHERE is_active=1 ORDER BY name").fetchall()
        out = ['<div class="top"><h2>پروژه‌ها</h2><a href="/projects/new" class="button">+ پروژه جدید</a>'
               '<div style="flex:1;max-width:350px"><input type="text" id="proj-search" class="search-input" placeholder="🔍 جستجو در پروژه‌ها..." oninput="filterTable(\'proj-table\', this.value)"></div>'
               '</div>'
               '<div class="table-wrap"><table id="proj-table"><thead><tr><th>نام</th><th>موقعیت</th><th>مرحله</th><th>پیشرفت</th><th>وضعیت</th></tr></thead><tbody>']
        for r in rows:
            out.append(f'<tr><td><a href="/projects/{r["id"]}">{esc(r["name"])}</a></td><td>{esc(r["location"] or "—")}</td><td>{label(r["stage"])}</td><td>{r["progress_percentage"]}%</td><td>{label(r["registration_status"])}</td></tr>')
        out.append('</tbody></table></div>')
        return self.send_html("".join(out), "پروژه‌ها")

    def project_form(self, method):
        if method == 'POST':
            d = self.form()
            self.conn.execute('''INSERT INTO projects(name,location,description,stage,progress_percentage,expected_completion_date,registration_status,public_update,internal_notes,is_active,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?)''',
                (d.get('name','').strip(), d.get('location','').strip() or None, d.get('description','').strip() or None,
                 d.get('stage','planning'), int(d.get('progress_percentage',0)), parse_jalali(d.get('expected_completion_date',''), False) or None,
                 d.get('registration_status','open'), d.get('public_update','').strip() or None, d.get('internal_notes','').strip() or None,
                 self.current_user['id'], now_iso(), now_iso()))
            self.conn.commit()
            return self.redirect('/projects')
        stage_opts = options(PROJECT_STAGES, 'planning')
        reg_opts = options(REG_STATUSES, 'open')
        body = f'''<h2>پروژه جدید</h2>
            <form method="post" class="form-layout">
                <div class="form-row"><label>نام<input name="name" required></label><label>موقعیت<input name="location"></label></div>
                <div class="form-row"><label>مرحله<select name="stage">{stage_opts}</select></label><label>پیشرفت (%)<input name="progress_percentage" type="number" min="0" max="100"></label></div>
                <div class="form-row"><label>وضعیت ثبت نام<select name="registration_status">{reg_opts}</select></label><label>تاریخ تکمیل<input name="expected_completion_date" class="jalali-date"></label></div>
                <label>توضیحات<textarea name="description"></textarea></label>
                <label>به روز رسانی عمومی<textarea name="public_update"></textarea></label>
                <label>یادداشت داخلی<textarea name="internal_notes"></textarea></label>
                <button>ذخیره</button>
            </form>'''
        return self.send_html(body, "پروژه جدید")

    def project_routes(self, path, method):
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return self.not_found()
        pid = parts[1]
        if method == 'POST' and len(parts) >= 3 and parts[2] == 'edit':
            d = self.form()
            self.conn.execute('''UPDATE projects SET name=?,location=?,description=?,stage=?,progress_percentage=?,expected_completion_date=?,registration_status=?,public_update=?,internal_notes=?,updated_at=? WHERE id=?''',
                (d.get('name','').strip(), d.get('location','').strip() or None, d.get('description','').strip() or None,
                 d.get('stage','planning'), int(d.get('progress_percentage',0)), parse_jalali(d.get('expected_completion_date',''), False) or None,
                 d.get('registration_status','open'), d.get('public_update','').strip() or None, d.get('internal_notes','').strip() or None,
                 now_iso(), pid))
            self.conn.commit()
            return self.redirect(f'/projects/{pid}')
        row = self.conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            return self.not_found()
        stage_opts = options(PROJECT_STAGES, row['stage'])
        reg_opts = options(REG_STATUSES, row['registration_status'])
        body = f'''<h2>ویرایش پروژه: {esc(row["name"])}</h2>
            <form method="post" action="/projects/{pid}/edit" class="form-layout">
                <div class="form-row"><label>نام<input name="name" value="{esc(row["name"])}" required></label><label>موقعیت<input name="location" value="{esc(row['location'] or '')}"></label></div>
                <div class="form-row"><label>مرحله<select name="stage">{stage_opts}</select></label><label>پیشرفت (%)<input name="progress_percentage" type="number" min="0" max="100" value="{row['progress_percentage']}"></label></div>
                <div class="form-row"><label>وضعیت ثبت نام<select name="registration_status">{reg_opts}</select></label><label>تاریخ تکمیل<input name="expected_completion_date" class="jalali-date" value="{jalali_input_value(row['expected_completion_date'])}"></label></div>
                <label>توضیحات<textarea name="description">{esc(row['description'] or '')}</textarea></label>
                <label>به روز رسانی عمومی<textarea name="public_update">{esc(row['public_update'] or '')}</textarea></label>
                <label>یادداشت داخلی<textarea name="internal_notes">{esc(row['internal_notes'] or '')}</textarea></label>
                <button>ذخیره</button>
            </form>'''
        return self.send_html(body, f"پروژه: {row['name']}")

    def reports(self):
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        agent_where = "" if is_manager else " WHERE cl.agent_id=?"
        # Project filter for reports
        sel_project_id = self.query.get('project_id', [''])[0].strip()
        project_filter_sql = " AND cl.project_id=?" if sel_project_id else ""
        project_params = (sel_project_id,) if sel_project_id else ()

        # === Summary stats ===
        total_calls = self.conn.execute(f"SELECT COUNT(*) c FROM call_logs cl WHERE 1=1{agent_filter}", agent_params).fetchone()["c"]
        total_customers = self.conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        total_projects = self.conn.execute("SELECT COUNT(*) c FROM projects WHERE is_active=1").fetchone()["c"]
        today_calls = self.conn.execute(f"SELECT COUNT(*) c FROM call_logs cl WHERE date(cl.created_at)=date('now'){agent_filter}", agent_params).fetchone()["c"]
        today_customers = self.conn.execute(f"SELECT COUNT(DISTINCT cl.customer_id) c FROM call_logs cl WHERE date(cl.created_at)=date('now'){agent_filter}", agent_params).fetchone()["c"]
        follow_pending = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending'").fetchone()["c"]
        signed = self.conn.execute("SELECT COUNT(*) c FROM customers WHERE status='registered_signed'").fetchone()["c"]
        
        # === Duration stats ===
        avg_duration_row = self.conn.execute(f"SELECT COALESCE(AVG(cl.call_duration_seconds), 0) avg_sec FROM call_logs cl WHERE cl.call_duration_seconds IS NOT NULL{agent_filter}", agent_params).fetchone()
        avg_duration = round(avg_duration_row["avg_sec"] / 60, 1) if avg_duration_row["avg_sec"] else 0
        total_duration_row = self.conn.execute(f"SELECT COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl{agent_where}", agent_params).fetchone()
        total_duration = round(total_duration_row["total_sec"] / 60, 0) if total_duration_row["total_sec"] else 0

        today_jalali = to_jalali_display(date.today().isoformat())[:10]
        from_date_jalali = today_jalali[:7] + '/01'
        to_date_jalali = today_jalali

        out = ['<h2>گزارش‌ها</h2>']

        # Stats row
        out.append(f'''<div class="stats">
            <div class="stat"><span>{total_calls}</span><small>کل تماس‌ها</small></div>
            <div class="stat"><span>{today_calls}</span><small>تماس‌های امروز</small></div>
            <div class="stat"><span>{today_customers}</span><small>مشتریان امروز</small></div>
            <div class="stat"><span>{total_customers}</span><small>کل مشتریان</small></div>
            <div class="stat"><span>{signed}</span><small>ثبت نام شده</small></div>
            <div class="stat"><span>{follow_pending}</span><small>پیگیری فعال</small></div>
            <div class="stat"><span>{total_projects}</span><small>پروژه‌ها</small></div>
            <div class="stat"><span>{avg_duration}</span><small>میانگین مدت (دقیقه)</small></div>
            <div class="stat"><span>{int(total_duration)}</span><small>مجموع مدت (دقیقه)</small></div>
        </div>''')

        # Export links
        out.append(f'''<div class="top" style="gap:8px">
            <h3>خروجی Excel</h3>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
                <a href="/exports/daily-report" class="button small secondary">📥 گزارش روزانه</a>
                <a href="/exports/project-calls" class="button small secondary">📥 بر اساس پروژه</a>
                <a href="/exports/project-member-calls" class="button small secondary">📥 بر اساس اپراتور</a>
                <a href="/exports/customers" class="button small secondary">📥 لیست مشتریان</a>
                <span class="date-range-export">
                    <input type="text" id="export-date-from" class="jalali-date" placeholder="از تاریخ..." value="{from_date_jalali}" style="width:130px;padding:4px 8px;font-size:.8rem;border:1.5px solid var(--line);border-radius:8px;background:var(--card)">
                    <input type="text" id="export-date-to" class="jalali-date" placeholder="تا تاریخ..." value="{to_date_jalali}" style="width:130px;padding:4px 8px;font-size:.8rem;border:1.5px solid var(--line);border-radius:8px;background:var(--card)">
                    <a href="#" class="button small secondary" onclick="exportWithDateRange();return false">📥 خروجی با بازه تاریخ</a>
                </span>
                <script>
                function exportWithDateRange() {{
                    var from = document.getElementById('export-date-from');
                    var to = document.getElementById('export-date-to');
                    var fromVal = from ? encodeURIComponent(from.value.trim()) : '';
                    var toVal = to ? encodeURIComponent(to.value.trim()) : '';
                    window.location.href = '/exports/daily-report?from_date=' + fromVal + '&to_date=' + toVal;
                }}
                </script>
                <a href="/exports/follow-ups" class="button small secondary">📥 لیست پیگیری‌ها</a>
            </div>
        </div>''')

        # === Project filter ===
        project_opts_rep = project_options(self.conn, sel_project_id, blank="نمایش همه")
        out.append(f'<div class="section" style="margin-bottom:12px">\n            <h3>فیلتر گزارش‌ها بر اساس پروژه</h3>\n            <form method="get" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">\n                <select name="project_id" onchange="this.form.submit()" style="width:250px">{project_opts_rep}</select>\n                <noscript><button type="submit" class="small secondary">اعمال</button></noscript>\n                <a href="/reports" class="small secondary" style="padding:4px 10px;border:1.5px solid var(--line);border-radius:8px;text-decoration:none;color:var(--muted);font-size:.8rem">پاک کردن فیلتر</a>\n            </form>\n        </div>')

        # === Call Type Distribution ===
        type_rows = self.conn.execute(f'''SELECT cl.call_type, COUNT(*) cnt FROM call_logs cl
            WHERE cl.call_type IS NOT NULL AND cl.call_type != ''{agent_filter}{project_filter_sql} GROUP BY cl.call_type ORDER BY cnt DESC''', agent_params + project_params).fetchall()
        if type_rows:
            out.append('<div class="section"><h3>نوع تماس‌ها</h3>')
            out.append('<table><thead><tr><th>نوع تماس</th><th>تعداد</th><th>درصد</th></tr></thead><tbody>')
            type_total = sum(r["cnt"] for r in type_rows)
            for r in type_rows:
                pct = round(r["cnt"] / type_total * 100, 1) if type_total else 0
                out.append(f'<tr><td>{label(r["call_type"])}</td><td>{r["cnt"]}</td><td>{pct}%</td></tr>')
            out.append('</tbody></table></div>')

        # === Daily call log (last 30 days) ===
        if is_manager:
            daily_rows = self.conn.execute(f'''SELECT date(cl.created_at) as d, COUNT(*) as cnt,
                COUNT(DISTINCT cl.customer_id) as cust_cnt FROM call_logs cl WHERE 1=1{project_filter_sql} GROUP BY d ORDER BY d DESC LIMIT 30''', project_params).fetchall()
        else:
            daily_rows = self.conn.execute(f'''SELECT date(cl.created_at) as d, COUNT(*) as cnt,
                COUNT(DISTINCT cl.customer_id) as cust_cnt FROM call_logs cl WHERE cl.agent_id=?{project_filter_sql} GROUP BY d ORDER BY d DESC LIMIT 30''', (uid,) + project_params).fetchall()
        if daily_rows:
            out.append('<div class="section"><h3>تماس‌های روزانه (۳۰ روز اخیر)</h3>')
            out.append('<table><thead><tr><th>تاریخ</th><th>تعداد تماس</th><th>مشتریان منحصر بفرد</th></tr></thead><tbody>')
            for r in daily_rows:
                out.append(f'<tr><td>{to_jalali_display(r["d"])[:10]}</td><td>{r["cnt"]}</td><td>{r["cust_cnt"]}</td></tr>')
            out.append('</tbody></table></div>')
        else:
            out.append('<div class="section muted"><p>هنوز تماسی ثبت نشده است.</p></div>')

        # === Problem type distribution ===
        prob_rows = self.conn.execute(f'''SELECT cl.problem_type, COUNT(*) cnt FROM call_logs cl
            WHERE cl.problem_type IS NOT NULL AND cl.problem_type != ''{agent_filter}{project_filter_sql} GROUP BY cl.problem_type ORDER BY cnt DESC''', agent_params + project_params).fetchall()
        if prob_rows:
            out.append('<div class="section"><h3>موضوعات تماس</h3>')
            out.append('<table><thead><tr><th>موضوع</th><th>تعداد</th><th>درصد</th></tr></thead><tbody>')
            prob_total = sum(r["cnt"] for r in prob_rows)
            for r in prob_rows:
                pct = round(r["cnt"] / prob_total * 100, 1) if prob_total else 0
                out.append(f'<tr><td>{label(r["problem_type"])}</td><td>{r["cnt"]}</td><td>{pct}%</td></tr>')
            out.append('</tbody></table></div>')

        # === Per-agent report (all users can see) ===
        if is_manager:
            agent_rows = self.conn.execute(f'''SELECT u.name agent, COUNT(*) cnt, COUNT(DISTINCT cl.customer_id) cust_cnt,
                COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl 
                JOIN users u ON u.id=cl.agent_id WHERE 1=1{project_filter_sql} GROUP BY cl.agent_id ORDER BY cnt DESC''', project_params).fetchall()
        else:
            agent_rows = self.conn.execute(f'''SELECT u.name agent, COUNT(*) cnt, COUNT(DISTINCT cl.customer_id) cust_cnt,
                COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl
                JOIN users u ON u.id=cl.agent_id WHERE cl.agent_id=?{project_filter_sql} GROUP BY cl.agent_id''', (uid,) + project_params).fetchall()
        if agent_rows:
            out.append('<div class="section"><h3>عملکرد اپراتور</h3>')
            out.append('<table><thead><tr><th>اپراتور</th><th>تعداد تماس</th><th>مشتریان</th><th>مدت کل (دقیقه)</th></tr></thead><tbody>')
            for r in agent_rows:
                mins = round(r["total_sec"] / 60, 0) if r["total_sec"] else 0
                out.append(f'<tr><td>{esc(r["agent"])}</td><td>{r["cnt"]}</td><td>{r["cust_cnt"]}</td><td>{int(mins)}</td></tr>')
            out.append('</tbody></table></div>')

        # === Per-project report (all users can see) ===
        if is_manager:
            proj_rows = self.conn.execute('''SELECT p.name project, COUNT(*) cnt, COUNT(DISTINCT cl.customer_id) cust_cnt,
                COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl
                JOIN projects p ON p.id=cl.project_id GROUP BY cl.project_id ORDER BY cnt DESC''').fetchall()
        else:
            proj_rows = self.conn.execute('''SELECT p.name project, COUNT(*) cnt, COUNT(DISTINCT cl.customer_id) cust_cnt,
                COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl
                JOIN projects p ON p.id=cl.project_id WHERE cl.agent_id=? GROUP BY cl.project_id ORDER BY cnt DESC''', (uid,)).fetchall()
        if proj_rows:
            out.append('<div class="section"><h3>تماس‌ها بر اساس پروژه</h3>')
            out.append('<table><thead><tr><th>پروژه</th><th>تعداد تماس</th><th>مشتریان</th><th>مدت کل (دقیقه)</th></tr></thead><tbody>')
            for r in proj_rows:
                mins = round(r["total_sec"] / 60, 0) if r["total_sec"] else 0
                out.append(f'<tr><td>{esc(r["project"])}</td><td>{r["cnt"]}</td><td>{r["cust_cnt"]}</td><td>{int(mins)}</td></tr>')
            out.append('</tbody></table></div>')

        # === Customer Source Distribution ===
        source_rows = self.conn.execute('''SELECT c.source, COUNT(*) cnt FROM customers c
            WHERE c.source IS NOT NULL AND c.source != '' GROUP BY c.source ORDER BY cnt DESC''').fetchall()
        if source_rows:
            out.append('<div class="section"><h3>منبع مشتریان</h3>')
            out.append('<table><thead><tr><th>منبع</th><th>تعداد</th><th>درصد</th></tr></thead><tbody>')
            src_total = sum(r["cnt"] for r in source_rows)
            for r in source_rows:
                pct = round(r["cnt"] / src_total * 100, 1) if src_total else 0
                out.append(f'<tr><td>{label(r["source"])}</td><td>{r["cnt"]}</td><td>{pct}%</td></tr>')
            out.append('</tbody></table></div>')

        # === Customer Status Distribution ===
        status_rows = self.conn.execute('''SELECT c.status, COUNT(*) cnt FROM customers c
            WHERE c.status IS NOT NULL AND c.status != '' GROUP BY c.status ORDER BY cnt DESC''').fetchall()
        if status_rows:
            out.append('<div class="section"><h3>وضعیت مشتریان</h3>')
            out.append('<table><thead><tr><th>وضعیت</th><th>تعداد</th><th>درصد</th></tr></thead><tbody>')
            st_total = sum(r["cnt"] for r in status_rows)
            for r in status_rows:
                pct = round(r["cnt"] / st_total * 100, 1) if st_total else 0
                out.append(f'<tr><td>{label(r["status"])}</td><td>{r["cnt"]}</td><td>{pct}%</td></tr>')
            out.append('</tbody></table></div>')

        # === Recent calls (last 20) with details ===
        if is_manager:
            recent_rows = self.conn.execute(f'''SELECT cl.*, c.full_name, c.primary_phone, u.name agent, p.name project
                FROM call_logs cl JOIN customers c ON c.id=cl.customer_id
                LEFT JOIN users u ON u.id=cl.agent_id
                LEFT JOIN projects p ON p.id=cl.project_id
                WHERE 1=1{project_filter_sql} ORDER BY cl.created_at DESC LIMIT 20''', project_params).fetchall()
        else:
            recent_rows = self.conn.execute(f'''SELECT cl.*, c.full_name, c.primary_phone, u.name agent, p.name project
                FROM call_logs cl JOIN customers c ON c.id=cl.customer_id
                LEFT JOIN users u ON u.id=cl.agent_id
                LEFT JOIN projects p ON p.id=cl.project_id
                WHERE cl.agent_id=?{project_filter_sql} ORDER BY cl.created_at DESC LIMIT 20''', (uid,) + project_params).fetchall()
        if recent_rows:
            out.append('<div class="section"><h3>تماس‌های اخیر</h3>')
            out.append('<div class="table-wrap"><table><thead><tr><th>تاریخ</th><th>مشتری</th><th>تلفن</th><th>نوع</th><th>موضوع</th><th>مدت</th><th>پروژه</th><th>اپراتور</th></tr></thead><tbody>')
            for r in recent_rows:
                dur = ''
                if r["call_duration_seconds"]:
                    d = int(r["call_duration_seconds"])
                    dur = f'{d // 60}:{d % 60:02d}'
                out.append(f'<tr><td>{money_date(r["call_started_at"])[:16]}</td>')
                out.append(f'<td><a href="/call-logs/{r["id"]}" style="color:var(--primary);text-decoration:none">{esc(r["full_name"])}</a></td>')
                out.append(f'<td>{esc(r["primary_phone"])}</td>')
                out.append(f'<td>{label(r["call_type"])}</td>')
                out.append(f'<td>{label(r["problem_type"])}</td>')
                out.append(f'<td>{dur}</td>')
                out.append(f'<td>{esc(r["project"] or "—")}</td>')
                out.append(f'<td>{esc(r["agent"] or "—")}</td></tr>')
            out.append('</tbody></table></div></div>')

        # === Follow-up status summary ===
        fu_status_rows = self.conn.execute('''SELECT f.status, COUNT(*) cnt FROM follow_ups f GROUP BY f.status''').fetchall()
        if fu_status_rows:
            out.append('<div class="section"><h3>وضعیت پیگیری‌ها</h3>')
            out.append('<table><thead><tr><th>وضعیت</th><th>تعداد</th></tr></thead><tbody>')
            for r in fu_status_rows:
                out.append(f'<tr><td>{label(r["status"])}</td><td>{r["cnt"]}</td></tr>')
            out.append('</tbody></table></div>')

        # === Call reasons by project ===
        if sel_project_id:
            proj_name_row = self.conn.execute("SELECT name FROM projects WHERE id=?", (sel_project_id,)).fetchone()
            proj_name = proj_name_row["name"] if proj_name_row else "پروژه انتخاب شده"
            call_problem_rows = self.conn.execute(f'''SELECT cl.problem_type, COUNT(*) cnt FROM call_logs cl
                WHERE cl.project_id=? AND cl.problem_type IS NOT NULL AND cl.problem_type != \'\'
                GROUP BY cl.problem_type ORDER BY cnt DESC''', (sel_project_id,)).fetchall()
            if call_problem_rows:
                out.append(f'<div class="section"><h3>نتایج تماس‌ها بر اساس پروژه: {esc(proj_name)}</h3>')
                total = sum(r["cnt"] for r in call_problem_rows)
                out.append('<table><thead><tr><th>موضوع/نتیجه تماس</th><th>تعداد</th><th>درصد</th></tr></thead><tbody>')
                for r in call_problem_rows:
                    pct = round(r["cnt"] / total * 100, 1) if total else 0
                    out.append(f'<tr><td>{label(r["problem_type"])}</td><td>{r["cnt"]}</td><td>{pct}%</td></tr>')
                out.append('</tbody></table><p class="muted">مجموع: ' + str(total) + ' تماس</p></div>')
            else:
                out.append(f'<div class="section"><h3>نتایج تماس‌ها بر اساس پروژه: {esc(proj_name)}</h3><p class="muted">هیچ تماسی برای این پروژه یافت نشد.</p></div>')
        else:
            out.append('<div class="section"><h3>نتایج تماس‌ها بر اساس پروژه</h3><p class="muted">برای مشاهده آمار، یک پروژه را از فیلتر بالا انتخاب کنید.</p></div>')
        # Add project detail export link when a project is selected
        if sel_project_id:
            proj_name_row2 = self.conn.execute("SELECT name FROM projects WHERE id=?", (sel_project_id,)).fetchone()
            proj_name2 = proj_name_row2["name"] if proj_name_row2 else ""
            out.append(f'<div style="display:flex;gap:8px;margin-top:8px">')
            out.append(f'<a href="/exports/project-detail?project_id={sel_project_id}" class="button small secondary">📥 خروجی اکسل جزئیات پروژه: {esc(proj_name2)}</a>')
            out.append(f'</div>')

        return self.send_html("".join(out), "گزارش‌ها")

    def users(self, method):
        if method == 'POST':
            d = self.form()
            pw = hash_password(d.get('password','password123'))
            self.conn.execute("INSERT INTO users(name,email,password,phone,role,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
                (d.get('name','').strip(), d.get('email','').strip(), pw, d.get('phone','').strip() or None, d.get('role','agent'), now_iso(), now_iso()))
            self.conn.commit()
            return self.redirect('/users')
        rows = self.conn.execute("SELECT * FROM users ORDER BY role DESC,name").fetchall()
        out = ['<div class="top"><h2>کاربران</h2></div><div class="table-wrap"><table><thead><tr><th>نام</th><th>ایمیل</th><th>نقش</th><th>فعال</th><th>عملیات</th></tr></thead><tbody>']
        for r in rows:
            active = 'فعال' if r['is_active'] else 'غیرفعال'
            confirm_msg = 'آیا از حذف این کاربر اطمینان دارید؟'
            out.append(f'<tr><td>{esc(r["name"])}</td><td>{esc(r["email"])}</td><td>{label(r["role"])}</td><td>{active}</td><td class="actions" style="display:flex;gap:4px"><a href="/users/{r["id"]}/toggle" class="small secondary">{'غیرفعال‌سازی' if r['is_active'] else 'فعال‌سازی'}</a><a href="/users/{r["id"]}/edit" class="small">✏️</a><form method="post" action="/users/{r["id"]}/delete" style="display:inline" onsubmit="return confirm(\'' + confirm_msg + '\')"><button type="submit" class="small secondary">🗑️</button></form></td></tr>')
        out.append('</tbody></table></div>')
        body = f'''{"".join(out)}
            <hr><h3>کاربر جدید</h3>
            <form method="post" class="form-layout">
                <div class="form-row"><label>نام<input name="name" required></label><label>ایمیل<input name="email" type="email" required></label></div>
                <div class="form-row"><label>رمز عبور<input name="password" type="password" value="password123"></label><label>تلفن<input name="phone"></label></div>
                <label>نقش<select name="role">{options(['manager', 'agent'], 'agent')}</select></label>
                <button>ایجاد کاربر</button>
            </form>'''
        return self.send_html(body, "کاربران")

    def user_action(self, path, method):
        parts = path.strip('/').split('/')
        if len(parts) < 2:
            return self.not_found()
        uid = parts[1]
        action = parts[2] if len(parts) > 2 else ''
        if action == 'toggle':
            row = self.conn.execute("SELECT is_active FROM users WHERE id=?", (uid,)).fetchone()
            if row:
                self.conn.execute("UPDATE users SET is_active=? WHERE id=?", (0 if row['is_active'] else 1, uid))
                self.conn.commit()
            return self.redirect('/users')
        if action == 'edit':
            if method == 'POST':
                d = self.form()
                name = d.get('name', '').strip()
                email = d.get('email', '').strip()
                phone = d.get('phone', '').strip() or None
                role = d.get('role', 'agent')
                password = d.get('password', '').strip()
                if name and email:
                    if password:
                        pw = hash_password(password)
                        self.conn.execute("UPDATE users SET name=?, email=?, password=?, phone=?, role=?, updated_at=? WHERE id=?",
                            (name, email, pw, phone, role, now_iso(), uid))
                    else:
                        self.conn.execute("UPDATE users SET name=?, email=?, phone=?, role=?, updated_at=? WHERE id=?",
                            (name, email, phone, role, now_iso(), uid))
                    self.conn.commit()
                return self.redirect('/users')
            # GET - show edit form
            row = self.conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return self.not_found()
            role_opts = options(['manager', 'agent'], row['role'])
            body = f'''<h2>ویرایش کاربر: {esc(row["name"])}</h2>
                <form method="post" action="/users/{uid}/edit" class="form-layout">
                    <div class="form-row"><label>نام<input name="name" value="{esc(row["name"])}" required></label><label>ایمیل<input name="email" type="email" value="{esc(row["email"])}" required></label></div>
                    <div class="form-row"><label>رمز عبور (خالی بگذارید تا بدون تغییر بماند)<input name="password" type="password" placeholder="رمز جدید"></label><label>تلفن<input name="phone" value="{esc(row["phone"] or '')}"></label></div>
                    <label>نقش<select name="role">{role_opts}</select></label>
                    <button>ذخیره</button>
                    <a href="/users" class="button small secondary">انصراف</a>
                </form>'''
            return self.send_html(body, f"ویرایش کاربر: {row['name']}")
        if action == 'delete':
            if method == 'POST':
                if str(uid) != str(self.current_user['id']):
                    self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
                    self.conn.commit()
                return self.redirect('/users')
        return self.not_found()

    def base_tables(self, method):
        if method == 'POST':
            d = self.form()
            action = d.get('action','')
            if action == 'add' and d.get('lookup_type') and d.get('value') and d.get('label'):
                self.conn.execute('''INSERT OR IGNORE INTO lookup_items(lookup_type,value,label,is_active,created_at,updated_at) VALUES(?,?,?,1,?,?)''',
                    (d['lookup_type'], d['value'], d['label'], now_iso(), now_iso()))
                self.conn.commit()
            elif action == 'delete' and d.get('id'):
                self.conn.execute("UPDATE lookup_items SET is_active=0,updated_at=? WHERE id=?", (now_iso(), d['id']))
                self.conn.commit()
            elif action == 'edit' and d.get('id') and d.get('label'):
                val = d.get('value', '')
                if val:
                    self.conn.execute("UPDATE lookup_items SET value=?, label=?, updated_at=? WHERE id=?", (val, d['label'], now_iso(), d['id']))
                else:
                    self.conn.execute("UPDATE lookup_items SET label=?,updated_at=? WHERE id=?", (d['label'], now_iso(), d['id']))
                self.conn.commit()
            return self.redirect('/base-tables')
        out = ['<div class="top"><h2>جداول پایه</h2>'
               '<div style="flex:1;max-width:350px"><input type="text" id="bt-search" class="search-input" placeholder="🔍 جستجو در جداول پایه..." oninput="filterBaseTables(this.value)"></div>'
               '</div>']
        for lookup_type, (title, _) in LOOKUP_DEFS.items():
            items = self.conn.execute("SELECT * FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id", (lookup_type,)).fetchall()
            out.append(f'<div class="section bt-section" id="bt-{esc(lookup_type)}"><h3>{esc(title)}</h3><table><thead><tr><th>مقدار</th><th>برچسب</th><th>عملیات</th></tr></thead><tbody>')
            for it in items:
                out.append(f'<tr><td>{esc(it["value"])}</td><td>{esc(it["label"])}</td>'
                    f'<td class="actions" style="display:flex;gap:4px">'
                    f'<form method="post" style="display:inline-flex;gap:4px;align-items:center">'
                    f'<input type="hidden" name="id" value="{it["id"]}">'
                    f'<input type="hidden" name="action" value="edit">'
                    f'<input type="text" name="value" value="{esc(it["value"])}" style="width:100px;padding:3px 6px;font-size:.78rem" placeholder="مقدار">'
                    f'<input type="text" name="label" value="{esc(it["label"])}" style="width:100px;padding:3px 6px;font-size:.78rem" placeholder="برچسب">'
                    f'<button type="submit" class="small">✓</button>'
                    f'</form>'
                    f'<form method="post" style="display:inline"><input type="hidden" name="action" value="delete">'
                    f'<input type="hidden" name="id" value="{it["id"]}"><button type="submit" class="small secondary">✕</button></form></td></tr>')
            out.append('</tbody></table>')
            out.append(f'''<form method="post" class="form-row">
                <input type="hidden" name="lookup_type" value="{esc(lookup_type)}">
                <input type="hidden" name="action" value="add">
                <label>مقدار<input name="value" placeholder="مقدار انگلیسی" required></label>
                <label>برچسب<input name="label" placeholder="برچسب فارسی" required></label>
                <button type="submit" class="small">افزودن</button>
            </form></div>''')
        return self.send_html("".join(out), "جداول پایه")

    def base_table_action(self, path, method):
        return self.base_tables(method)

    def _customer_payload(self, row):
        projects = self.conn.execute('''SELECT p.id, p.name, p.stage, p.progress_percentage, p.registration_status FROM projects p
            JOIN customer_projects cp ON cp.project_id=p.id WHERE cp.customer_id=?''', (row['id'],)).fetchall()
        recent_calls = self.conn.execute('''SELECT cl.id, cl.call_started_at, cl.problem_type FROM call_logs cl
            WHERE cl.customer_id=? ORDER BY cl.created_at DESC LIMIT 5''', (row['id'],)).fetchall()
        return {'id': row['id'], 'full_name': row['full_name'], 'national_code': row['national_code'],
            'primary_phone': row['primary_phone'],
            'projects': [{'id': p['id'], 'name': p['name'], 'stage': p['stage'], 'progress_percentage': p['progress_percentage'], 'registration_status': p['registration_status']} for p in projects],
            'recent_calls': [{'id': c['id'], 'call_started_at': c['call_started_at'],
                'problem_type': c['problem_type'],
                'call_started_at_display': to_jalali_display(c['call_started_at'])[:16] if c['call_started_at'] else '',
                'problem_type_label': label(c['problem_type']) if c['problem_type'] else ''} for c in recent_calls]}

    def api_customer_by_national_code(self):
        code = self.query.get('code',[''])[0].strip()
        if not re.match(r'^\d{10}$', code):
            self.send_json({})
            return
        row = self.conn.execute('''SELECT c.* FROM customers c WHERE c.national_code=?''', (code,)).fetchone()
        if not row:
            self.send_json({})
            return
        self.send_json(self._customer_payload(row))

    def api_customer_by_phone(self):
        phone = self.query.get('phone', [''])[0].strip()
        if not phone:
            self.send_json({})
            return
        norm = re.sub(r'\D+', '', phone)
        row = self.conn.execute("SELECT * FROM customers WHERE primary_phone=? OR secondary_phone=? ORDER BY id LIMIT 1", (phone, phone)).fetchone()
        if not row and len(norm) >= 7:
            for size in (10, 9, 8, 7):
                tail = norm[-size:]
                row = self.conn.execute(
                    "SELECT * FROM customers WHERE "
                    "replace(replace(replace(replace(replace(primary_phone,'+',''),'-',''),' ',''),'(',''),')','') LIKE ? OR "
                    "replace(replace(replace(replace(replace(secondary_phone,'+',''),'-',''),' ',''),'(',''),')','') LIKE ? "
                    "ORDER BY id LIMIT 1",
                    ("%" + tail, "%" + tail)).fetchone()
                if row:
                    break
        if not row:
            self.send_json({})
            return
        self.send_json(self._customer_payload(row))

    def api_live_call(self):
        uid = self.current_user["id"]
        self.conn.execute("""DELETE FROM live_calls WHERE
            (ended_at IS NOT NULL AND ended_at < datetime('now','-3 hours'))
            OR (ended_at IS NULL AND started_at < datetime('now','-2 hours'))
            OR (ended_at IS NULL AND duration_seconds IS NOT NULL AND updated_at < datetime('now','-30 minutes'))""")
        self.conn.commit()
        row = self.conn.execute("""SELECT * FROM live_calls WHERE
            agent_id=? OR
            (extension IS NOT NULL AND EXISTS (
                SELECT 1 FROM users u WHERE u.id=? AND replace(u.phone,' ','')=live_calls.extension
            ))
            ORDER BY id DESC LIMIT 1""", (uid, uid)).fetchone()
        if not row:
            self.send_json({"found": False})
            return
        self.send_json({
            "found": True,
            "id": row["id"],
            "phone": row["phone"],
            "caller_name": row["caller_name"] or "",
            "status": row["status"] or "",
            "ended": row["ended_at"] is not None or row["duration_seconds"] is not None,
            "duration_seconds": row["duration_seconds"],
            "call_id": row["call_id"] or "",
        })

    def api_customer_followup_history(self):
        customer_id = self.query.get('customer_id',[''])[0].strip()
        if not customer_id:
            self.send_json({'followups': []})
            return
        rows = self.conn.execute('''SELECT f.*, u.name agent_name FROM follow_ups f
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            WHERE f.customer_id=? ORDER BY f.created_at DESC LIMIT 10''', (customer_id,)).fetchall()
        fu_list = []
        last_comments = {}
        for r in rows:
            comment = self.conn.execute('''SELECT comment FROM follow_up_comments WHERE follow_up_id=? ORDER BY created_at DESC LIMIT 1''', (r['id'],)).fetchone()
            last_comments[r['id']] = comment['comment'] if comment else None
        # Get last comment for each
        for r in rows:
            fu_list.append({
                'id': r['id'], 'status': r['status'], 'reason': r['reason'] or '',
                'due_at': r['due_at'], 'due_at_display': to_jalali_display(r['due_at'])[:16] if r['due_at'] else '',
                'status_label': label(r['status']),
                'last_comment': last_comments.get(r['id'])
            })
        self.send_json({'followups': fu_list})

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def export_customers(self):
        rows = self.conn.execute('''SELECT c.id, c.full_name, c.national_code, c.primary_phone, c.secondary_phone, c.email, c.city, c.address, c.source, c.status, u.name agent, c.registration_date, c.last_contacted_at, c.next_follow_up_at, c.general_notes, c.created_at FROM customers c LEFT JOIN users u ON u.id=c.assigned_agent_id ORDER BY c.id''').fetchall()
        headers = ['شناسه', 'نام کامل', 'کد ملی', 'تلفن اصلی', 'تلفن دوم', 'ایمیل', 'شهر', 'آدرس', 'منبع', 'وضعیت', 'اپراتور', 'تاریخ ثبت نام', 'آخرین تماس', 'پیگیری بعدی', 'یادداشت‌ها', 'تاریخ ایجاد']
        return self.csv_export(rows, headers, 'customers')

    def export_daily_report(self):
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        # Date range from query params (Jalali dates)
        from_j = self.query.get('from_date', [''])[0].strip()
        to_j = self.query.get('to_date', [''])[0].strip()
        today_str = date.today().isoformat()
        date_from = parse_jalali(from_j, False) if from_j else today_str
        date_to = parse_jalali(to_j, False) if to_j else today_str
        if date_to < date_from:
            date_from, date_to = date_to, date_from
        date_filter = " AND date(cl.created_at) BETWEEN ? AND ?"
        date_params = (date_from, date_to)
        rows = self.conn.execute(f'''SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, 
            u.name agent, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
            FROM call_logs cl 
            JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN users u ON u.id=cl.agent_id
            WHERE 1=1{agent_filter}{date_filter}
            ORDER BY cl.created_at DESC''', agent_params + date_params).fetchall()
        headers = ['شناسه', 'نام مشتری', 'تلفن', 'نوع تماس', 'موضوع تماس', 'اپراتور', 'تاریخ تماس', 'مدت (دقیقه)', 'یادداشت‌ها', 'تاریخ ثبت']
        return self.csv_export(rows, headers, 'daily_report')
    
    def export_project_calls(self):
        """Export call logs grouped by project with per-project summary sections."""
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        sel_project_id = self.query.get('project_id', [''])[0].strip()
        project_filter = " AND cl.project_id=?" if sel_project_id else ""
        project_params = (sel_project_id,) if sel_project_id else ()
        rows = self.conn.execute('''SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type,
            u.name agent, p.name project_name, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
            FROM call_logs cl
            JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN users u ON u.id=cl.agent_id
            LEFT JOIN projects p ON p.id=cl.project_id
            WHERE 1=1''' + agent_filter + project_filter + '''
            ORDER BY p.name, cl.created_at DESC''', agent_params + project_params).fetchall()
        if not rows:
            return self.send_html('<p>داده‌ای یافت نشد.</p>')
        # Group rows by project
        from collections import OrderedDict
        grouped = OrderedDict()
        for r in rows:
            proj = r['project_name'] or '(\u0628\u062f\u0648\u0646 \u067e\u0631\u0648\u0698\u0647)'
            if proj not in grouped:
                grouped[proj] = []
            grouped[proj].append(r)
        buf = io.StringIO()
        w = csv.writer(buf)
        headers = ['\u0634\u0646\u0627\u0633\u0647', '\u0646\u0627\u0645 \u0645\u0634\u062a\u0631\u06cc', '\u062a\u0644\u0641\u0646', '\u0646\u0648\u0639 \u062a\u0645\u0627\u0633', '\u0645\u0648\u0636\u0648\u0639 \u062a\u0645\u0627\u0633', '\u0627\u067e\u0631\u0627\u062a\u0648\u0631', '\u062a\u0627\u0631\u06cc\u062e \u062a\u0645\u0627\u0633', '\u0645\u062f\u062a (\u062f\u0642\u06cc\u0642\u0647)', '\u06cc\u0627\u062f\u062f\u0627\u0634\u062a\u200c\u0647\u0627', '\u062a\u0627\u0631\u06cc\u062e \u062b\u0628\u062a']
        for proj_name, proj_rows in grouped.items():
            total_calls = len(proj_rows)
            total_dur = sum((r['call_duration_seconds'] or 0) for r in proj_rows)
            w.writerow([''])
            w.writerow(['=' * 8 + ' ' + proj_name + ' ' + '=' * 8, '', '', '', '', '', '', '', '', ''])
            w.writerow(['\u06a9\u0644 \u062a\u0645\u0627\u0633\u200c\u0647\u0627: ' + str(total_calls), '\u0645\u062f\u062a \u06a9\u0644: ' + str(round(total_dur / 60, 1)) + ' \u062f\u0642\u06cc\u0642\u0647', '', '', '', '', '', '', '', ''])
            w.writerow([''])
            w.writerow(headers)
            for r in proj_rows:
                row_vals = []
                for k in r.keys():
                    val = str(r[k] or '')
                    # Translate codes to Persian
                    if k in ('call_type', 'problem_type'):
                        val = label_text(val)
                    # Convert dates to Jalali (Shamsi)
                    if k in ('call_started_at', 'created_at', 'completed_at', 'due_at',
                             'registration_date', 'last_contacted_at', 'next_follow_up_at',
                             'updated_at', 'expected_completion_date', 'update_date') and r[k]:
                        val = to_jalali_display(r[k])[:16]
                    # Duration from seconds to minutes
                    if 'duration' in k:
                        try:
                            secs = int(r[k] or 0)
                            val = str(round(secs / 60, 1))
                        except (ValueError, TypeError):
                            pass
                    # Skip project_name column (it's the section header)
                    if k == 'project_name':
                        continue
                    row_vals.append(val)
                w.writerow(row_vals)
        data = ('\ufeff' + buf.getvalue()).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename=project_calls.csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def export_project_member_calls(self):
        """Export all call logs grouped by agent/member."""
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        sel_project_id = self.query.get('project_id', [''])[0].strip()
        project_filter = " AND cl.project_id=?" if sel_project_id else ""
        project_params = (sel_project_id,) if sel_project_id else ()
        rows = self.conn.execute('''SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type,
            u.name agent, p.name project, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
            FROM call_logs cl
            JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN users u ON u.id=cl.agent_id
            LEFT JOIN projects p ON p.id=cl.project_id
            WHERE 1=1''' + agent_filter + project_filter + '''
            ORDER BY u.name, cl.created_at DESC''', agent_params + project_params).fetchall()
        headers = ['\u0634\u0646\u0627\u0633\u0647', '\u0646\u0627\u0645 \u0645\u0634\u062a\u0631\u06cc', '\u062a\u0644\u0641\u0646', '\u0646\u0648\u0639 \u062a\u0645\u0627\u0633', '\u0645\u0648\u0636\u0648\u0639 \u062a\u0645\u0627\u0633', '\u0627\u067e\u0631\u0627\u062a\u0648\u0631', '\u067e\u0631\u0648\u0698\u0647', '\u062a\u0627\u0631\u06cc\u062e \u062a\u0645\u0627\u0633', '\u0645\u062f\u062a (\u062b\u0627\u0646\u06cc\u0647)', '\u06cc\u0627\u062f\u062f\u0627\u0634\u062a\u200c\u0647\u0627', '\u062a\u0627\u0631\u06cc\u062e \u062b\u0628\u062a']
        return self.csv_export(rows, headers, 'member_calls')

    def export_project_detail(self):
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        pid = self.query.get('project_id', [''])[0].strip()
        if not pid:
            return self.send_html('<p>لطفا project_id را مشخص کنید.</p>', status=422)
        proj = self.conn.execute("SELECT id, name, location, stage FROM projects WHERE id=?", (pid,)).fetchone()
        if not proj:
            return self.send_html('<p>پروژه یافت نشد.</p>', status=404)
        # Summary stats
        total_calls = self.conn.execute(f"SELECT COUNT(*) c FROM call_logs cl WHERE cl.project_id=?{agent_filter}", (pid,) + agent_params).fetchone()["c"]
        total_customers = self.conn.execute(f"SELECT COUNT(DISTINCT cl.customer_id) c FROM call_logs cl WHERE cl.project_id=?{agent_filter}", (pid,) + agent_params).fetchone()["c"]
        total_duration = self.conn.execute(f"SELECT COALESCE(SUM(cl.call_duration_seconds), 0) s FROM call_logs cl WHERE cl.project_id=?{agent_filter}", (pid,) + agent_params).fetchone()["s"]
        rows = self.conn.execute(f'''SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, 
            u.name agent, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
            FROM call_logs cl 
            JOIN customers c ON c.id=cl.customer_id
            LEFT JOIN users u ON u.id=cl.agent_id
            WHERE cl.project_id=?{agent_filter}
            ORDER BY cl.created_at DESC''', (pid,) + agent_params).fetchall()
        headers = ['شناسه', 'نام مشتری', 'تلفن', 'نوع تماس', 'موضوع تماس', 'اپراتور', 'تاریخ تماس', 'مدت (ثانیه)', 'یادداشت‌ها', 'تاریخ ثبت']
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['گزارش پروژه: ' + proj['name'], '', '', '', '', '', '', '', '', ''])
        w.writerow(['موقعیت: ' + (proj['location'] or '—'), 'مرحله: ' + label_text(proj['stage']), 'کل تماس‌ها: ' + str(total_calls), 'مشتریان: ' + str(total_customers), 'مدت کل: ' + str(round(total_duration / 60, 1)) + ' دقیقه', '', '', '', '', ''])
        w.writerow([])
        w.writerow(headers)
        for r in rows:
            row_vals = []
            for k in r.keys():
                val = str(r[k] or '')
                if 'duration' in k or 'total_sec' in k:
                    try:
                        secs = int(r[k] or 0)
                        val = str(round(secs / 60, 1))
                    except (ValueError, TypeError):
                        pass
                # Translate known code values to Persian titles
                if k in ('call_type', 'problem_type'):
                    val = label_text(val)
                # Convert dates to Jalali (Shamsi)
                if k in ('call_started_at', 'created_at', 'completed_at', 'due_at',
                         'registration_date', 'last_contacted_at', 'next_follow_up_at',
                         'updated_at', 'expected_completion_date', 'update_date') and r[k]:
                    val = to_jalali_display(r[k])[:16]
                row_vals.append(val)
            w.writerow(row_vals)
        data = ('﻿' + buf.getvalue()).encode('utf-8')
        filename = 'project_' + str(pid) + '_details'
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename={filename}.csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def export_follow_ups(self):
        rows = self.conn.execute(f'''SELECT f.id, c.full_name, c.primary_phone, f.reason, f.priority, f.status,
            u.name agent, cu.name creator, f.due_at, f.completed_at, f.notes, f.created_at
            FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            LEFT JOIN users cu ON cu.id=f.created_by
            ORDER BY f.created_at DESC''').fetchall()
        headers = ['شناسه', 'نام مشتری', 'تلفن', 'موضوع', 'اولویت', 'وضعیت', 'اپراتور', 'ایجادکننده', 'مهلت', 'تاریخ تکمیل', 'یادداشت‌ها', 'تاریخ ایجاد']
        return self.csv_export(rows, headers, 'follow_ups')

    def csv_export(self, rows, headers, filename):
        if not rows:
            return self.send_html('<p>داده‌ای یافت نشد.</p>')
        # Column keys whose values should be translated to Persian titles
        _LABEL_KEYS = {'call_type', 'problem_type', 'source', 'status', 'priority',
                        'stage', 'registration_status', 'note_type', 'role'}
        _DATE_KEYS = {'call_started_at', 'created_at', 'completed_at', 'due_at',
                       'registration_date', 'last_contacted_at', 'next_follow_up_at',
                       'updated_at', 'expected_completion_date', 'update_date'}
        keys = rows[0].keys()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        for r in rows:
            row_vals = []
            for k in keys:
                val = str(r[k] or '')
                # Translate known code values to Persian titles
                if k in _LABEL_KEYS:
                    val = label_text(val)
                # Convert dates to Jalali (Shamsi)
                if k in _DATE_KEYS and r[k]:
                    val = to_jalali_display(r[k])[:16]
                # Convert duration from seconds to minutes if key contains duration
                if 'duration' in k or 'total_sec' in k or 'avg_sec' in k:
                    try:
                        secs = int(r[k] or 0)
                        val = str(round(secs / 60, 1))
                    except (ValueError, TypeError):
                        pass
                row_vals.append(val)
            w.writerow(row_vals)
        data = ('﻿' + buf.getvalue()).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/csv; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename={filename}.csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def css(self):
        path = os.path.join(BASE_DIR, 'app.css')
        alt = os.path.join(os.path.dirname(BASE_DIR), 'app.css')
        if os.path.exists(path):
            pass
        elif os.path.exists(alt):
            path = alt
        else:
            return self.not_found()
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read().encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/css; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def _local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    init_db()
    host = os.environ.get('CRM_HOST', '0.0.0.0')
    port = int(os.environ.get('CRM_PORT', 8000))
    srv = ThreadingHTTPServer((host, port), App)
    banner = []
    banner.append('=' * 60)
    banner.append('[CRM] آدرس برای خودتان (همین سیستم):')
    banner.append(f'      http://127.0.0.1:{port}')
    ips = _local_ips()
    if ips:
        banner.append('[CRM] آدرس برای بقیه اپراتورها (از مرورگر خودشان):')
        for ip in ips:
            banner.append(f'      http://{ip}:{port}')
    else:
        banner.append('[CRM] آدرس شبکه پیدا نشد؛ بقیه باید از نام شبکه این سیستم استفاده کنند.')
    banner.append('')
    banner.append('[CRM] فقط یک نسخه اجرا شود؛ بقیه با مرورگر وصل شوند تا دیتابیس لاک نشود.')
    banner.append('=' * 60)
    for line in banner:
        print(line, flush=True)
    try:
        with open(os.path.join(BASE_DIR, 'crm-access-url.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(banner) + '\n')
    except Exception:
        pass
    print(f'Serving on http://127.0.0.1:{port}', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()