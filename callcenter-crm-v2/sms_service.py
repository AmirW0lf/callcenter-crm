# -*- coding: utf-8 -*-
"""
SMS Gateway Service for CallCenter CRM v2.0
Supports:
- Simulated Mode (local testing, 0 cost, full logging)
- Kavenegar REST API
- FarazSMS / IPPanel REST API
- MeliPayak REST API
- Custom Webhook (HTTP POST)
"""

import os
import urllib.request
import urllib.parse
import json
import threading
import datetime
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "crm.sqlite3")

def sanitize_phone(phone):
    if not phone:
        return ""
    p = str(phone).strip().replace(" ", "").replace("-", "")
    for fa_d, en_d in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789"):
        p = p.replace(fa_d, en_d)
    for ar_d, en_d in zip("٠١٢٣٤٥٦٧٨٩", "0123456789"):
        p = p.replace(ar_d, en_d)
    if p.startswith("+98"):
        p = "0" + p[3:]
    elif p.startswith("98"):
        p = "0" + p[2:]
    return p

def get_sms_settings(conn):
    rows = conn.execute("SELECT key, value FROM system_settings WHERE key LIKE 'sms_%'").fetchall()
    settings = {r[0]: r[1] for r in rows}
    return {
        "enabled": settings.get("sms_enabled", "1") == "1",
        "provider": settings.get("sms_provider", "simulated"),
        "api_key": settings.get("sms_api_key", ""),
        "sender": settings.get("sms_sender", "10008888"),
        "thank_you_enabled": settings.get("sms_thank_you_enabled", "1") == "1",
        "thank_you_template": settings.get("sms_thank_you_template", "مشتری گرامی {name}، از تماس شما سپاسگزاریم. کد پیگیری: #{call_id}"),
        "followup_reminder_enabled": settings.get("sms_followup_reminder_enabled", "1") == "1",
        "followup_reminder_template": settings.get("sms_followup_reminder_template", "مشتری گرامی {name}، یادآوری پیگیری: {reason} در تاریخ {due_date}"),
    }

def save_sms_settings(conn, settings_dict):
    now_iso = datetime.datetime.now().isoformat()
    for k, v in settings_dict.items():
        db_key = f"sms_{k}" if not k.startswith("sms_") else k
        conn.execute("INSERT INTO system_settings(key, value, updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at", (db_key, str(v), now_iso))
    conn.commit()

def log_sms(conn, customer_id, phone, message, sms_type, status, response_info):
    now_iso = datetime.datetime.now().isoformat()
    conn.execute(
        """INSERT INTO sms_logs(customer_id, phone, message, sms_type, status, response_info, created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (customer_id, phone, message, sms_type, status, str(response_info), now_iso)
    )
    conn.commit()

def _dispatch_http(provider, api_key, sender, receptor, message):
    if provider == "simulated":
        return True, "Simulated SMS dispatched successfully (0 cost)"

    if provider == "kavenegar":
        url = f"https://api.kavenegar.com/v1/{api_key}/sms/send.json"
        data = urllib.parse.urlencode({
            "receptor": receptor,
            "sender": sender,
            "message": message
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"User-Agent": "CallCenterCRM/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            res_json = json.loads(body)
            if res_json.get("return", {}).get("status") == 200:
                return True, body
            return False, body

    if provider in ("farazsms", "ippanel"):
        url = "https://rest.ippanel.com/v1/messages/patterns/send"
        # Standard send endpoint
        url_simple = "https://rest.ippanel.com/v1/messages"
        payload = json.dumps({
            "originator": sender,
            "recipients": [receptor],
            "message": message
        }).encode("utf-8")
        req = urllib.request.Request(url_simple, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"AccessKey {api_key}"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return True, body

    if provider == "melipayak":
        url = f"https://restfulsms.com/api/MessageSend"
        payload = json.dumps({
            "Messages": [message],
            "MobileNumbers": [receptor],
            "LineNumber": sender
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "x-sms-ir-secure-token": api_key
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return True, body

    if provider == "custom_webhook":
        # Custom webhook expects api_key to be the full webhook URL
        req = urllib.request.Request(api_key, data=json.dumps({"phone": receptor, "message": message}).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, resp.read().decode("utf-8")

    return True, f"Simulated delivery for provider: {provider}"

def send_sms(conn, phone, message, sms_type="manual", customer_id=None, async_mode=True):
    clean_phone = sanitize_phone(phone)
    if not clean_phone:
        return {"success": False, "reason": "Invalid phone number"}

    settings = get_sms_settings(conn)
    if not settings["enabled"]:
        log_sms(conn, customer_id, clean_phone, message, sms_type, "disabled", "SMS sending is disabled in settings")
        return {"success": False, "reason": "SMS gateway is disabled"}

    provider = settings["provider"]
    api_key = settings["api_key"]
    sender = settings["sender"]

    def _worker():
        import sqlite3
        thread_conn = sqlite3.connect(DEFAULT_DB_PATH, timeout=30.0)
        try:
            ok, info = _dispatch_http(provider, api_key, sender, clean_phone, message)
            log_sms(thread_conn, customer_id, clean_phone, message, sms_type, "sent" if ok else "failed", info)
        except Exception as e:
            try:
                log_sms(thread_conn, customer_id, clean_phone, message, sms_type, "failed", str(e))
            except Exception:
                pass
        finally:
            thread_conn.close()

    if async_mode:
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return {"success": True, "status": "queued"}
    else:
        try:
            ok, info = _dispatch_http(provider, api_key, sender, clean_phone, message)
            log_sms(conn, customer_id, clean_phone, message, sms_type, "sent" if ok else "failed", info)
            return {"success": ok, "info": info}
        except Exception as e:
            log_sms(conn, customer_id, clean_phone, message, sms_type, "failed", str(e))
            return {"success": False, "info": str(e)}

def send_call_thank_you_sms(conn, customer_id, customer_name, phone, call_id):
    settings = get_sms_settings(conn)
    if not settings["enabled"] or not settings["thank_you_enabled"]:
        return
    template = settings["thank_you_template"]
    msg = template.replace("{name}", customer_name or "همراه گرامی").replace("{call_id}", str(call_id))
    send_sms(conn, phone, msg, sms_type="call_thank_you", customer_id=customer_id, async_mode=True)

def send_followup_reminder_sms(conn, customer_id, customer_name, phone, reason, due_date):
    settings = get_sms_settings(conn)
    if not settings["enabled"] or not settings["followup_reminder_enabled"]:
        return
    template = settings["followup_reminder_template"]
    msg = template.replace("{name}", customer_name or "همراه گرامی").replace("{reason}", reason or "پیگیری").replace("{due_date}", str(due_date))
    send_sms(conn, phone, msg, sms_type="followup_reminder", customer_id=customer_id, async_mode=True)
