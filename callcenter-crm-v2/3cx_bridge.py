#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import sys
import threading
import traceback
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get("BRIDGE_CRM_DB") or os.path.join(BASE_DIR, "crm.sqlite3")
HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("BRIDGE_PORT", "8090"))
TOKEN = os.environ.get("BRIDGE_TOKEN", "").strip()
INCLUDE_JALALI = os.environ.get("BRIDGE_INCLUDE_JALALI", "0") == "1"
LOG_PATH = os.environ.get("BRIDGE_LOG") or os.path.join(BASE_DIR, "3cx_bridge.log")

try:
    TZ_OFFSET_HOURS = float(os.environ.get("BRIDGE_TZ_OFFSET_HOURS", "3.5"))
except Exception:
    TZ_OFFSET_HOURS = 3.5
LOCAL_TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))

AGENT_MAP = {}
for _pair in os.environ.get("BRIDGE_AGENT_MAP", "").split(","):
    if "=" in _pair:
        _k, _v = _pair.split("=", 1)
        AGENT_MAP[_k.strip()] = _v.strip()

CALLER_KEYS = ["callernumber", "caller_number", "callerid", "caller", "from", "fromnumber", "phonenumber", "phone", "callersnumber", "externalnumber", "remote", "number", "dnis", "number_caller"]
NAME_KEYS = ["calleridname", "callername", "caller_name", "cidname", "contactname", "displayname", "fullname", "name"]
STATUS_KEYS = ["callstatus", "status", "disposition", "answered", "callanswered", "callresult", "result", "terminationreason", "state", "reason"]
DURATION_KEYS = ["callduration", "duration", "talktime", "talkduration", "durationseconds", "totalduration", "billingduration", "calltime", "seconds", "minutes"]
TIME_KEYS = ["timestamp", "calltime", "starttime", "datetime", "callstarttime", "startedat", "calldatetime", "calldate", "date", "time"]
DIRECTION_KEYS = ["direction", "calldirection", "type", "calltype"]
AGENT_KEYS = ["agentextension", "agent", "extension", "ext", "agentname", "operator", "user", "destination", "to"]
ID_KEYS = ["callid", "callhistoryid", "eventid", "segmentid", "pbxcallid", "historyid", "id"]

LOCK = threading.Lock()


def log(message):
    line = "{} {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def now_iso():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def local_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) + timedelta(hours=TZ_OFFSET_HOURS)


def only_digits(value):
    return re.sub(r"\D+", "", str(value or ""))


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
        return "{:04d}/{:02d}/{:02d}".format(jy, jm, jd) + (text[10:16] if len(text) > 10 else "")
    except Exception:
        return text


def flatten(obj, out=None, depth=0):
    if out is None:
        out = {}
    if depth > 8:
        return out
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                flatten(value, out, depth + 1)
            else:
                out.setdefault(str(key), value)
    elif isinstance(obj, list):
        for item in obj:
            flatten(item, out, depth + 1)
    return out


def pick(flat, keys, default=None):
    lowered = {}
    for key, value in flat.items():
        lowered.setdefault(str(key).lower(), value)
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None and str(value).strip() != "":
            return value
    return default


def xml_to_dict(element):
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result = {}
    for child in children:
        value = xml_to_dict(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def parse_body(raw, content_type):
    if raw is None:
        return {}
    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    text = text.strip()
    if not text:
        return {}
    lowered = (content_type or "").lower()
    if "json" in lowered or text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except Exception:
            pass
    if "xml" in lowered or text.startswith("<"):
        try:
            return xml_to_dict(ET.fromstring(text))
        except Exception:
            pass
    try:
        return {k: v[-1] for k, v in urllib.parse.parse_qs(text, keep_blank_values=True).items()}
    except Exception:
        return {}


def epoch_to_local(value):
    try:
        number = float(value)
    except Exception:
        return None
    if number > 10000000000:
        number = number / 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).astimezone(LOCAL_TZ).replace(tzinfo=None)
    except Exception:
        return None


def parse_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return epoch_to_local(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"/Date\((\d+)([+-]\d+)?\)/", text)
    if match:
        return epoch_to_local(int(match.group(1)) / 1000.0)
    if re.fullmatch(r"\d{13}", text):
        return epoch_to_local(int(text) / 1000.0)
    if re.fullmatch(r"\d{10}", text):
        return epoch_to_local(int(text))
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            return dt.astimezone(LOCAL_TZ).replace(tzinfo=None)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def parse_duration(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(round(float(text)))
    match = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2})", text)
    if match:
        return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
    match = re.fullmatch(r"(\d+):(\d{1,2})", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    total = 0
    found = False
    for number, unit in re.findall(r"(\d+)\s*([hms])", text.lower()):
        found = True
        total += int(number) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total if found else None


def missed_from_status(status):
    if status is None:
        return None
    text = str(status).lower()
    if any(token in text for token in ("missed", "unanswered", "no answer", "noanswer", "abandon", "cancel", "fail")):
        return True
    if any(token in text for token in ("answer", "success", "complete", "connected", "accept", "ok")):
        return False
    return None


def call_type_from(direction, missed):
    if missed is True:
        return "missed"
    if "out" in str(direction or "").lower():
        return "outgoing"
    return "incoming"


END_STATUS_TOKENS = ("hangup", "ended", "completed", "finished", "missed", "unanswered", "no answer", "noanswer", "disconnected", "busy", "terminated", "failed", "cancel", "abandon")


def is_ended_event(status, duration):
    if duration is not None:
        return True
    if status is None:
        return False
    text = str(status).lower()
    return any(token in text for token in END_STATUS_TOKENS)


def extension_digits(value):
    if value is None:
        return None
    match = re.search(r"(\d{2,6})", str(value))
    return match.group(1) if match else None


def open_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def find_customer(conn, phone):
    if not phone:
        return None
    row = conn.execute("SELECT * FROM customers WHERE primary_phone=? OR secondary_phone=? ORDER BY id LIMIT 1", (phone, phone)).fetchone()
    if row:
        return row
    norm = only_digits(phone)
    if len(norm) < 7:
        return None
    for size in (10, 9, 8, 7):
        if len(norm) < size:
            continue
        tail = norm[-size:]
        row = conn.execute(
            "SELECT * FROM customers WHERE "
            "replace(replace(replace(replace(replace(primary_phone,'+',''),'-',''),' ',''),'(',''),')','') LIKE ? OR "
            "replace(replace(replace(replace(replace(secondary_phone,'+',''),'-',''),' ',''),'(',''),')','') LIKE ? "
            "ORDER BY id LIMIT 1",
            ("%" + tail, "%" + tail),
        ).fetchone()
        if row:
            return row
    return None


def manager_id(conn):
    row = conn.execute("SELECT id FROM users WHERE role='manager' AND is_active=1 ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    return row["id"] if row else None


def create_customer(conn, phone, name):
    full_name = (str(name).strip() if name else "") or phone
    created = now_iso()
    cur = conn.execute(
        "INSERT INTO customers(full_name,national_code,primary_phone,city,source,status,assigned_agent_id,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (full_name, None, phone, None, "phone_call", "new_lead", None, manager_id(conn), created, created),
    )
    return conn.execute("SELECT * FROM customers WHERE id=?", (cur.lastrowid,)).fetchone()


def resolve_agent(conn, extension, name):
    if extension and extension in AGENT_MAP:
        try:
            return int(AGENT_MAP[extension])
        except Exception:
            pass
    if extension:
        row = conn.execute("SELECT id FROM users WHERE replace(phone,' ','')=? OR replace(phone,' ','') LIKE ? LIMIT 1", (extension, "%" + extension)).fetchone()
        if row:
            return row["id"]
    if name:
        row = conn.execute("SELECT id FROM users WHERE name=? LIMIT 1", (str(name).strip(),)).fetchone()
        if row:
            return row["id"]
    return None


def ensure_live_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS live_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id INTEGER,
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
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_calls_agent ON live_calls(agent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_calls_extension ON live_calls(extension)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_calls_call_id ON live_calls(call_id)")


def purge_live_calls(conn):
    conn.execute("""DELETE FROM live_calls WHERE
        (ended_at IS NOT NULL AND ended_at < datetime('now','-3 hours'))
        OR (ended_at IS NULL AND started_at < datetime('now','-2 hours'))
        OR (ended_at IS NULL AND duration_seconds IS NOT NULL AND updated_at < datetime('now','-30 minutes'))""")


def upsert_live(conn, phone, name, status, extension, agent_id, event_id, duration, started, ended):
    ensure_live_table(conn)
    purge_live_calls(conn)
    row = None
    if event_id:
        row = conn.execute("SELECT * FROM live_calls WHERE call_id=? ORDER BY id DESC LIMIT 1", (str(event_id),)).fetchone()
    if not row and (agent_id or extension):
        recent_cutoff = (datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        if agent_id:
            row = conn.execute("SELECT * FROM live_calls WHERE agent_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1", (agent_id,)).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM live_calls WHERE agent_id=? AND started_at>=? ORDER BY id DESC LIMIT 1", (agent_id, recent_cutoff)).fetchone()
        if not row and extension:
            row = conn.execute("SELECT * FROM live_calls WHERE extension=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1", (extension,)).fetchone()
    now = now_iso()
    if row:
        conn.execute("""UPDATE live_calls SET phone=?, caller_name=?, call_id=?, status=?, started_at=?, ended_at=?, duration_seconds=?, updated_at=? WHERE id=?""",
            (phone, name, str(event_id) if event_id else None, status, started,
             now if ended else None, duration if ended else None, now, row["id"]))
        return row["id"]
    cur = conn.execute("""INSERT INTO live_calls(agent_id,extension,phone,caller_name,call_id,status,started_at,ended_at,duration_seconds,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (agent_id, extension, phone, name, str(event_id) if event_id else None, status, started,
         now if ended else None, duration if ended else None, now, now))
    return cur.lastrowid


def duplicate_exists(conn, customer_id, started, duration):
    if duration is None:
        row = conn.execute("SELECT id FROM call_logs WHERE customer_id=? AND call_started_at=? AND call_duration_seconds IS NULL LIMIT 1", (customer_id, started)).fetchone()
    else:
        row = conn.execute("SELECT id FROM call_logs WHERE customer_id=? AND call_started_at=? AND call_duration_seconds=? LIMIT 1", (customer_id, started, duration)).fetchone()
    return row["id"] if row else None


def process_event(payload):
    flat = flatten(payload)
    phone = pick(flat, CALLER_KEYS)
    if phone is None or str(phone).strip() == "":
        return 400, {"status": "error", "error": "caller number not found", "received_keys": sorted(flat.keys())[:40]}
    phone = str(phone).strip()
    name = pick(flat, NAME_KEYS)
    status = pick(flat, STATUS_KEYS)
    direction = pick(flat, DIRECTION_KEYS)
    duration = parse_duration(pick(flat, DURATION_KEYS))
    extension = extension_digits(pick(flat, AGENT_KEYS))
    event_id = pick(flat, ID_KEYS)
    timestamp = parse_timestamp(pick(flat, TIME_KEYS))
    started = (timestamp or local_now()).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    missed = missed_from_status(status)
    ctype = call_type_from(direction, missed)
    with LOCK:
        conn = open_db()
        try:
            customer = find_customer(conn, phone)
            created_new = False
            if customer is None:
                customer = create_customer(conn, phone, name)
                created_new = True
            customer_id = customer["id"]
            agent_id = resolve_agent(conn, extension, name)
            ended = is_ended_event(status, duration)
            live_id = upsert_live(conn, phone, (str(name).strip() if name else None), (str(status) if status else None), extension, agent_id, event_id, duration, started, ended)
            existing = duplicate_exists(conn, customer_id, started, duration)
            target = existing
            if not target and duration is not None:
                open_row = conn.execute("SELECT id FROM call_logs WHERE customer_id=? AND call_started_at=? AND call_duration_seconds IS NULL LIMIT 1", (customer_id, started)).fetchone()
                target = open_row["id"] if open_row else None
            if target:
                if duration is not None:
                    conn.execute("UPDATE call_logs SET call_duration_seconds=?, updated_at=? WHERE id=?", (duration, now_iso(), target))
                conn.commit()
                return 200, {"status": ("updated" if duration is not None else "duplicate"), "call_log_id": target, "customer_id": customer_id, "live_call_id": live_id, "call_ended": ended, "duration_seconds": duration}
            parts = ["3CX"]
            if status:
                parts.append("status=" + str(status))
            if direction:
                parts.append("direction=" + str(direction))
            if extension:
                parts.append("ext=" + extension)
            if duration is not None:
                parts.append("duration=" + str(duration) + "s")
            if event_id:
                parts.append("id=" + str(event_id))
            if INCLUDE_JALALI:
                parts.append("jalali=" + to_jalali_display(started)[:16])
            notes = " | ".join(parts)
            created = now_iso()
            cur = conn.execute(
                "INSERT INTO call_logs(customer_id,agent_id,call_type,problem_type,project_id,call_started_at,call_duration_seconds,notes,follow_up_required,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (customer_id, agent_id, ctype, None, None, started, duration, notes, 0, created, created),
            )
            conn.execute("UPDATE customers SET last_contacted_at=?, updated_at=? WHERE id=?", (created, created, customer_id))
            conn.commit()
            log("stored call phone={} type={} duration={} agent={} customer={} new_customer={} live={}".format(phone, ctype, duration, agent_id, customer_id, created_new, live_id))
            return 200, {
                "status": "ok",
                "call_log_id": cur.lastrowid,
                "customer_id": customer_id,
                "new_customer": created_new,
                "call_type": ctype,
                "call_started_at": started,
                "duration_seconds": duration,
                "agent_id": agent_id,
                "phone": phone,
                "live_call_id": live_id,
                "call_ended": ended,
            }
        except Exception as exc:
            conn.rollback()
            log("ERROR " + repr(exc))
            log(traceback.format_exc())
            return 500, {"status": "error", "error": str(exc)}
        finally:
            conn.close()


def check_token(provided):
    if not TOKEN:
        return True
    return provided == TOKEN


def dispatch(raw, content_type, query):
    payload = parse_body(raw, content_type)
    if isinstance(query, dict) and query:
        query_items = {k: (v[-1] if isinstance(v, list) else v) for k, v in query.items()}
        if isinstance(payload, dict):
            merged = dict(query_items)
            merged.update({k: v for k, v in payload.items() if v not in (None, "")})
            payload = merged
        elif not payload:
            payload = query_items
    return process_event(payload)


class Handler(BaseHTTPRequestHandler):
    server_version = "3cx-bridge"

    def log_message(self, *args):
        pass

    def respond(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path in ("/", "/health"):
            self.respond(200, {"status": "ok", "service": "3cx-bridge", "db": DB_PATH, "standalone": True})
        else:
            self.respond(404, {"status": "error", "error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/3cx/webhook", "/webhook", "/"):
            self.respond(404, {"status": "error", "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        query = parse_qs(parsed.query)
        token = (query.get("token", [""])[0] if query.get("token") else "") or self.headers.get("X-Webhook-Token", "") or self.headers.get("X-3CX-Token", "")
        if not check_token(token):
            self.respond(401, {"status": "error", "error": "unauthorized"})
            return
        code, body = dispatch(raw, self.headers.get("Content-Type", ""), query)
        self.respond(code, body)


def main():
    log("3cx-bridge start db={} host={} port={} auth={} tz={} frozen={}".format(DB_PATH, HOST, PORT, "on" if TOKEN else "off", TZ_OFFSET_HOURS, getattr(sys, "frozen", False)))
    if not os.path.exists(DB_PATH):
        log("WARNING database not found at " + DB_PATH)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log("3CX bridge listening on http://{}:{}/3cx/webhook".format(HOST, PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
