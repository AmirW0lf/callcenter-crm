# -*- coding: utf-8 -*-
"""
Unified VoIP Integration Bridge for CallCenter CRM v2.0
Supports:
- 3CX Phone System (HTTP webhook / Call Control)
- Asterisk / Issabel / FreePBX (AMI - Asterisk Manager Interface)
- Standalone Simulator / Test Mode (--simulate)
"""

import sys
import os
import json
import time
import socket
import threading
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

CRM_BASE_URL = os.environ.get("CRM_URL", "http://127.0.0.1:8000")
CRM_WEBHOOK_URL = f"{CRM_BASE_URL}/api/voip-webhook"
WEBHOOK_SECRET = os.environ.get("VOIP_SECRET", "crm_voip_secret_2026")

def notify_crm(phone, extension, event="ringing", call_id="", caller_name="", duration=None):
    payload = {
        "phone": phone,
        "extension": extension,
        "event": event,
        "call_id": call_id or f"voip_{int(time.time())}",
        "caller_name": caller_name,
        "duration": duration,
        "token": WEBHOOK_SECRET
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(CRM_WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            print(f"[{time.strftime('%H:%M:%S')}] CRM Webhook Response ({resp.status}): {body}")
            return json.loads(body)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Failed to post to CRM: {e}")
        return {"status": "error", "error": str(e)}

# ----------------- 3CX HTTP Server Handler -----------------
class ThreeCXHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            data = urllib.parse.parse_qs(body)
            data = {k: v[0] for k, v in data.items()}

        phone = data.get("Number") or data.get("phone") or data.get("caller_id") or ""
        ext = data.get("Extension") or data.get("ext") or data.get("agent_ext") or ""
        event = data.get("Event") or data.get("event") or "ringing"
        call_id = data.get("CallID") or data.get("call_id") or ""
        duration = data.get("Duration") or data.get("duration")

        print(f"[3CX] Received event: {event} | Phone: {phone} | Ext: {ext}")
        res = notify_crm(phone, ext, event=event, call_id=call_id, duration=duration)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(qs).items()}
        phone = params.get("phone") or params.get("Number") or ""
        ext = params.get("ext") or params.get("Extension") or ""
        event = params.get("event") or "ringing"
        call_id = params.get("call_id") or params.get("CallID") or ""
        duration = params.get("duration")

        print(f"[3CX-GET] Received event: {event} | Phone: {phone} | Ext: {ext}")
        res = notify_crm(phone, ext, event=event, call_id=call_id, duration=duration)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))

def start_3cx_server(port=5000):
    server = HTTPServer(("0.0.0.0", port), ThreeCXHandler)
    print(f"📞 3CX Relay Bridge listening on port {port}...")
    server.serve_forever()

# ----------------- Asterisk / Issabel AMI Client -----------------
def listen_asterisk_ami(host="127.0.0.1", port=5038, user="crm", secret="crm_secret_123"):
    print(f"📞 Connecting to Asterisk/Issabel AMI at {host}:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
    except Exception as e:
        print(f"❌ Asterisk AMI connection failed: {e}")
        return

    # Login
    login_cmd = f"Action: Login\r\nUsername: {user}\r\nSecret: {secret}\r\nEvents: on\r\n\r\n"
    s.sendall(login_cmd.encode("utf-8"))

    buf = ""
    while True:
        try:
            chunk = s.recv(4096).decode("utf-8", errors="ignore")
            if not chunk:
                break
            buf += chunk
            while "\r\n\r\n" in buf:
                msg, buf = buf.split("\r\n\r\n", 1)
                lines = msg.split("\r\n")
                event_dict = {}
                for line in lines:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        event_dict[k.strip().lower()] = v.strip()

                event_name = event_dict.get("event", "").lower()
                if event_name in ("dialbegin", "dial"):
                    caller = event_dict.get("calleridnum", "")
                    dest = event_dict.get("destcalleridnum") or event_dict.get("connectedlinenum") or ""
                    uid = event_dict.get("uniqueid", "")
                    if caller:
                        notify_crm(phone=caller, extension=dest, event="ringing", call_id=uid)

                elif event_name in ("bridgeenter", "agentconnect"):
                    caller = event_dict.get("calleridnum", "")
                    dest = event_dict.get("connectedlinenum", "")
                    uid = event_dict.get("uniqueid", "")
                    if caller:
                        notify_crm(phone=caller, extension=dest, event="connected", call_id=uid)

                elif event_name == "hangup":
                    caller = event_dict.get("calleridnum", "")
                    dest = event_dict.get("connectedlinenum", "")
                    uid = event_dict.get("uniqueid", "")
                    dur = event_dict.get("duration")
                    if caller:
                        notify_crm(phone=caller, extension=dest, event="hangup", call_id=uid, duration=dur)

        except Exception as e:
            print(f"AMI error: {e}")
            break
    s.close()

# ----------------- Simulation Mode -----------------
def simulate_call(phone="09121234567", ext="101", duration=120):
    print("=" * 60)
    print(f"🎬 SIMULATING INCOMING VOIP CALL")
    print(f"   Phone: {phone}")
    print(f"   Extension: {ext}")
    print(f"   Expected duration: {duration} seconds")
    print("=" * 60)

    cid = f"sim_{int(time.time())}"
    print(f"\n1. Sending 'ringing' event to CRM...")
    r1 = notify_crm(phone, ext, event="ringing", call_id=cid, caller_name="تست سامانه ویپ")
    print(f"   Response: {r1}")

    print("\n2. Call ringing for 4 seconds...")
    time.sleep(4)

    print("\n3. Sending 'connected' event (call answered)...")
    r2 = notify_crm(phone, ext, event="connected", call_id=cid)
    print(f"   Response: {r2}")

    print(f"\n4. Call active. Waiting 4 seconds before hangup...")
    time.sleep(4)

    print(f"\n5. Sending 'hangup' event with duration {duration} seconds...")
    r3 = notify_crm(phone, ext, event="hangup", call_id=cid, duration=duration)
    print(f"   Response: {r3}")

    print("\n✅ Simulation completed successfully! Check the operator's dashboard.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CallCenter CRM VoIP Integration Bridge")
    parser.add_argument("--simulate", action="store_true", help="Run a simulated incoming call test")
    parser.add_argument("--phone", default="09121234567", help="Phone number for simulation")
    parser.add_argument("--ext", default="101", help="Operator extension")
    parser.add_argument("--duration", type=int, default=120, help="Simulated call duration in seconds")
    parser.add_argument("--mode", default="3cx", choices=["3cx", "asterisk", "simulate"], help="Integration mode")
    parser.add_argument("--port", type=int, default=5000, help="Port for 3CX HTTP server")
    args = parser.parse_args()

    if args.simulate or args.mode == "simulate":
        simulate_call(phone=args.phone, ext=args.ext, duration=args.duration)
    elif args.mode == "asterisk":
        listen_asterisk_ami()
    else:
        start_3cx_server(port=args.port)
