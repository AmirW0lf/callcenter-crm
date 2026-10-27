# -*- coding: utf-8 -*-
"""
Nightly Automated Backup Manager for CallCenter CRM v2.0
- Safely performs SQLite WAL checkpoint
- Creates timestamped full database backup
- Automatically purges backups older than retention window (default: 30 days)
- Maintains audit log in backups/backup.log
"""

import os
import sys
import sqlite3
import datetime
import shutil

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "crm.sqlite3")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
LOG_PATH = os.path.join(BACKUPS_DIR, "backup.log")

def run_backup(retention_days=30, target_dir=None):
    destination_dir = target_dir or BACKUPS_DIR
    os.makedirs(destination_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"crm_backup_{timestamp}.sqlite3"
    backup_path = os.path.join(destination_dir, backup_filename)

    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "status": "pending",
        "backup_file": backup_filename,
        "size_bytes": 0,
        "purged_count": 0,
        "message": ""
    }

    try:
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"Source database not found at {DB_PATH}")

        # Checkpoint WAL safely
        conn = sqlite3.connect(DB_PATH, timeout=60.0)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Use SQLite online backup API for 100% ACID consistency
        bck_conn = sqlite3.connect(backup_path)
        conn.backup(bck_conn)
        bck_conn.close()
        conn.close()

        file_size = os.path.getsize(backup_path)
        log_entry["size_bytes"] = file_size
        log_entry["status"] = "success"
        log_entry["message"] = f"Backup created successfully ({round(file_size/1024, 1)} KB)"

        # Purge older backups
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        purged = 0
        for fname in os.listdir(destination_dir):
            if fname.startswith("crm_backup_") and fname.endswith(".sqlite3") and fname != backup_filename:
                fpath = os.path.join(destination_dir, fname)
                try:
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff_date:
                        os.remove(fpath)
                        purged += 1
                except Exception:
                    pass
        log_entry["purged_count"] = purged

    except Exception as e:
        log_entry["status"] = "failed"
        log_entry["message"] = str(e)
        print(f"❌ Backup failed: {e}", file=sys.stderr)

    # Write log
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            status_symbol = "✅" if log_entry["status"] == "success" else "❌"
            f.write(f"[{log_entry['timestamp']}] {status_symbol} File: {log_entry['backup_file']} | Size: {log_entry['size_bytes']} bytes | Purged: {log_entry['purged_count']} | {log_entry['message']}\n")
    except Exception:
        pass

    return log_entry

if __name__ == "__main__":
    retention = 30
    if len(sys.argv) > 1:
        try:
            retention = int(sys.argv[1])
        except ValueError:
            pass

    print(f"🚀 Starting CallCenter CRM Backup (Retention: {retention} days)...")
    res = run_backup(retention_days=retention)
    if res["status"] == "success":
        print(f"✅ Backup completed: {res['backup_file']} ({round(res['size_bytes']/1024, 1)} KB)")
        if res["purged_count"] > 0:
            print(f"🗑️ Cleaned up {res['purged_count']} old backup(s).")
        sys.exit(0)
    else:
        print(f"❌ Backup failed: {res['message']}")
        sys.exit(1)
