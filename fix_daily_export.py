# -*- coding: utf-8 -*-
"""Replace export_daily_report with enhanced version."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with open('app.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Find the start of the method
start = src.find('def export_daily_report(self):')
# Find the end (next def or class end)
end = src.find('\n    def ', start + 10)
if end < 0:
    end = start + 2000

old_method = src[start:end]
print(f"Old method length: {len(old_method)}")
print(f"Starts with: {repr(old_method[:100])}")

new_method = '''    def export_daily_report(self):
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
        headers = ['شناسه', 'نام مشتری', 'تلفن', 'نوع تماس', 'موضوع تماس', 'اپراتور', 'تاریخ تماس', 'مدت (ثانیه)', 'یادداشت‌ها', 'تاریخ ثبت']
        return self.csv_export(rows, headers, 'daily_report')
'''

src = src[:start] + new_method + src[end:]

# Verify
import ast
try:
    ast.parse(src)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Done")
