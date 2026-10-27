#!/usr/bin/env python3
"""Enhance follow-ups page and base tables with edit functionality"""
import re

import os
BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, 'app.py')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ============================================================
# 1. Enhance followups() - add status tabs & show all statuses
# ============================================================
old_followups = """    def followups(self):
        is_manager = self.current_user[\"role\"] == \"manager\"
        uid = self.current_user[\"id\"]
        agent_where = \"\" if is_manager else \" AND (f.assigned_agent_id=? OR f.created_by=?)\"
        agent_params = () if is_manager else (uid, uid)
        query = f'''SELECT f.*, c.full_name, c.primary_phone, u.name agent FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            WHERE f.status='pending'{agent_where}
            ORDER BY f.due_at ASC'''
        rows = self.conn.execute(query, agent_params).fetchall()
        out = ['<div class=\"filters\"><h2>لیست پیگیری‌ها</h2>'
               '<div style=\"flex:1;max-width:350px\"><input type=\"text\" id=\"fu-search\" class=\"search-input\" placeholder=\"🔍 جستجو...\" oninput=\"filterFollowUps()\"></div>'
               '</div>'
               '<div class=\"filters\" style=\"margin-bottom:12px\">'
               '<label style=\"display:flex;align-items:center;gap:6px;font-size:.8rem\">از تاریخ: <input type=\"text\" id=\"fu-date-from\" class=\"jalali-date search-input\" placeholder=\"از تاریخ...\" style=\"width:140px\" onchange=\"filterFollowUps()\"></label>'
               '<label style=\"display:flex;align-items:center;gap:6px;font-size:.8rem\">تا تاریخ: <input type=\"text\" id=\"fu-date-to\" class=\"jalali-date search-input\" placeholder=\"تا تاریخ...\" style=\"width:140px\" onchange=\"filterFollowUps()\"></label>'
               '<button type=\"button\" class=\"small secondary\" onclick=\"clearDateFilters()\">✕ پاک کردن فیلتر</button>'
               '</div>'
               '<div class=\"follow-up-list\" id=\"follow-up-list\">']
        for r in rows:
            due = to_jalali_display(r[\"due_at\"])[:16]
            over = ''
            try:
                if datetime.fromisoformat(r[\"due_at\"]) < datetime.now():
                    over = ' (عقب افتاده)'
            except Exception:
                pass
            notes = esc(r[\"notes\"] or '')
            fu_agent_opts = user_options(self.conn, blank='انتخاب اپراتور')
            out.append(f'''<div class=\"follow-up-card fu-card\">
                <div class=\"fu-header\"><strong>{esc(r[\"full_name\"])}</strong><span class=\"pill prio-{esc(r[\"priority\"])}\">{label(r[\"priority\"])}</span></div>
                <div class=\"fu-body\"><small>موضوع: {esc(r[\"reason\"] or \"—\")}</small><small>مهلت: {due}{over}</small><small>اپراتور: {esc(r[\"agent\"] or \"—\")}</small><small>وضعیت: {label(r[\"status\"])}</small></div>
                <div class=\"fu-notes\"><p>{notes}</p></div>
                <div class=\"fu-actions\">
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/reassign\" style=\"display:inline-flex;gap:4px;align-items:center\">
                        <select name=\"agent_id\" onchange=\"this.form.submit()\">{fu_agent_opts}<option value=\"{r['assigned_agent_id']}\" selected>{esc(r['agent'] or 'بدون مسئول')}</option></select>
                        <input type=\"hidden\" name=\"reassign\" value=\"1\">
                    </form>
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/complete\" style=\"display:inline\">
                        <button type=\"submit\" class=\"small\">انجام شد</button>
                    </form>
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/cancel\" style=\"display:inline\">
                        <button type=\"submit\" class=\"small secondary\">لغو</button>
                    </form>
                    <a href=\"/follow-ups/{r['id']}\" class=\"button small secondary\">چت / جزئیات</a>
                </div>
            </div>''')
        out.append('</div>')
        return self.send_html("".join(out), \"پیگیری‌ها\")"""

new_followups = """    def followups(self):
        is_manager = self.current_user[\"role\"] == \"manager\"
        uid = self.current_user[\"id\"]
        agent_where = \"\" if is_manager else \" AND (f.assigned_agent_id=? OR f.created_by=?)\"
        agent_params = () if is_manager else (uid, uid)
        # status filter from query string
        status_filter = self.query.get('status', ['pending'])[0]
        if status_filter not in ('pending', 'done', 'cancelled', 'all'):
            status_filter = 'pending'
        status_where = \"\" if status_filter == 'all' else f\" AND f.status='{status_filter}'\"
        query = f'''SELECT f.*, c.full_name, c.primary_phone, u.name agent FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            WHERE 1=1{status_where}{agent_where}
            ORDER BY CASE f.status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END, f.due_at ASC'''
        rows = self.conn.execute(query, agent_params).fetchall()
        tabs = ''
        for st, label_fa in [('pending', 'در انتظار'), ('done', 'انجام شده'), ('cancelled', 'لغو شده'), ('all', 'همه')]:
            active = ' active' if st == status_filter else ''
            tabs += f'<a href=\"/follow-ups?status={st}\" class=\"tab{active}\">{label_fa}</a>'
        out = ['<div class=\"filters\"><h2>لیست پیگیری‌ها</h2>'
               '<div style=\"flex:1;max-width:350px\"><input type=\"text\" id=\"fu-search\" class=\"search-input\" placeholder=\"🔍 جستجو...\" oninput=\"filterFollowUps()\"></div>'
               '</div>'
               f'<div class=\"tab-bar\">{tabs}</div>'
               '<div class=\"filters\" style=\"margin-bottom:12px\">'
               '<label style=\"display:flex;align-items:center;gap:6px;font-size:.8rem\">از تاریخ: <input type=\"text\" id=\"fu-date-from\" class=\"jalali-date search-input\" placeholder=\"از تاریخ...\" style=\"width:140px\" onchange=\"filterFollowUps()\"></label>'
               '<label style=\"display:flex;align-items:center;gap:6px;font-size:.8rem\">تا تاریخ: <input type=\"text\" id=\"fu-date-to\" class=\"jalali-date search-input\" placeholder=\"تا تاریخ...\" style=\"width:140px\" onchange=\"filterFollowUps()\"></label>'
               '<button type=\"button\" class=\"small secondary\" onclick=\"clearDateFilters()\">✕ پاک کردن فیلتر</button>'
               '</div>'
               '<div class=\"follow-up-list\" id=\"follow-up-list\">']
        for r in rows:
            due = to_jalali_display(r[\"due_at\"])[:16]
            over = ''
            try:
                if r['status'] == 'pending' and datetime.fromisoformat(r[\"due_at\"]) < datetime.now():
                    over = ' (عقب افتاده)'
            except Exception:
                pass
            notes = esc(r[\"notes\"] or '')
            fu_agent_opts = user_options(self.conn, blank='انتخاب اپراتور')
            completed_display = ''
            if r['completed_at']:
                completed_display = f'<small>تکمیل: {to_jalali_display(r[\"completed_at\"])[:16]}</small>'
            out.append(f'''<div class=\"follow-up-card fu-card\">
                <div class=\"fu-header\"><strong>{esc(r[\"full_name\"])}</strong><span class=\"pill prio-{esc(r[\"priority\"])} status-{esc(r[\"status\"])}\">{label(r[\"priority\"])}</span></div>
                <div class=\"fu-body\"><small>موضوع: {esc(r[\"reason\"] or \"—\")}</small><small>مهلت: {due}{over}</small><small>اپراتور: {esc(r[\"agent\"] or \"—\")}</small><small>وضعیت: <span class=\"pill status-{esc(r[\"status\"])}\">{label(r[\"status\"])}</span></small>{completed_display}</div>
                <div class=\"fu-notes\"><p>{notes}</p></div>
                <div class=\"fu-actions\">
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/reassign\" style=\"display:inline-flex;gap:4px;align-items:center\">
                        <select name=\"agent_id\" onchange=\"this.form.submit()\">{fu_agent_opts}<option value=\"{r['assigned_agent_id']}\" selected>{esc(r['agent'] or 'بدون مسئول')}</option></select>
                        <input type=\"hidden\" name=\"reassign\" value=\"1\">
                    </form>''')
            if r['status'] == 'pending':
                out.append(f'''
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/complete\" style=\"display:inline\">
                        <button type=\"submit\" class=\"small\">انجام شد</button>
                    </form>
                    <form method=\"post\" action=\"/follow-ups/{r['id']}/cancel\" style=\"display:inline\">
                        <button type=\"submit\" class=\"small secondary\">لغو</button>
                    </form>''')
            out.append(f'''
                    <a href=\"/follow-ups/{r['id']}\" class=\"button small secondary\">چت / جزئیات</a>
                </div>
            </div>''')
        out.append('</div>')
        return self.send_html("".join(out), \"پیگیری‌ها\")"""

if old_followups in content:
    content = content.replace(old_followups, new_followups)
    changes += 1
    print("[OK] Updated followups() - status tabs + completed_at display")
else:
    print("[WARN] Could not find old followups() method")

# ============================================================
# 2. Enhance followup_action() - add edit action
# ============================================================
old_fu_action_get_end = """        # GET single follow-up detail with chat
        row = self.conn.execute('''SELECT f.*, c.full_name, c.primary_phone, u.name agent, cu.name creator_name
            FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            LEFT JOIN users cu ON cu.id=f.created_by
            WHERE f.id=?''', (fu_id,)).fetchone()
        if not row:
            return self.not_found()
        due = to_jalali_display(row[\"due_at\"])[:16]
        created_display = to_jalali_display(row[\"created_at\"])[:16] if row[\"created_at\"] else ''
        comments = self.conn.execute('''SELECT fc.*, u.name user_name FROM follow_up_comments fc
            LEFT JOIN users u ON u.id=fc.user_id
            WHERE fc.follow_up_id=? ORDER BY fc.created_at ASC''', (fu_id,)).fetchall()
        comments_html = ''
        for c in comments:
            c_time = to_jalali_display(c['created_at'])[:16] if c['created_at'] else ''
            c_name = esc(c['user_name'] or 'سیستم')
            c_text = esc(c['comment'])
            comments_html += f'<div class=\"chat-msg\"><strong>{c_name}</strong> <small class=\"muted\">{c_time}</small><p>{c_text}</p></div>'
        if not comments_html:
            comments_html = '<p class=\"muted\">هنوز پیامی ثبت نشده است.</p>'
        body = f'''<div class=\"fu-detail-layout\">
          <div class=\"panel\" style=\"padding:16px\">
            <div class=\"top\"><h2>پیگیری: {esc(row[\"full_name\"])}</h2><a href=\"/follow-ups\" class=\"button small secondary\">← بازگشت</a></div>
            <div class=\"fu-body\" style=\"margin-top:8px\">
                <small>مشتری: {esc(row[\"full_name\"])}</small>
                <small>تلفن: {esc(row[\"primary_phone\"])}</small>
                <small>موضوع: {esc(row[\"reason\"] or \"—\")}</small>
                <small>مهلت: {due}</small>
                <small>اولویت: <span class=\"pill prio-{esc(row[\"priority\"])}\">{label(row[\"priority\"])}</span></small>
                <small>اپراتور: {esc(row[\"agent\"] or \"—\")}</small>
                <small>ایجادکننده: {esc(row[\"creator_name\"] or \"—\")}</small>
                <small>تاریخ ایجاد: {created_display}</small>
                <small>وضعیت: <span class=\"pill status-{esc(row[\"status\"])}\">{label(row[\"status\"])}</span></small>
            </div>
          </div>
          <div class=\"panel\" style=\"padding:16px;margin-top:12px\">
            <h3>💬 گفتگوی پیگیری</h3>
            <div class=\"chat-box\" id=\"chat-box\">{comments_html}</div>
            <form method=\"post\" action=\"/follow-ups/{fu_id}/comment\" class=\"chat-form\" style=\"margin-top:8px;display:flex;gap:8px\">
                <textarea name=\"comment\" placeholder=\"پیام خود را بنویسید...\" style=\"flex:1;min-height:44px\" required></textarea>
                <button type=\"submit\" class=\"small\" style=\"align-self:flex-end\">ارسال</button>
            </form>
          </div>
          <div class=\"panel\" style=\"padding:16px;margin-top:12px\">
            <h3>یادداشت‌ها</h3>
            <p>{esc(row[\"notes\"] or \"—\")}</p>
          </div>
        </div>'''
        return self.send_html(body, f\"پیگیری: {row['full_name']}\")"""

new_fu_action_get_end = """        # GET single follow-up detail with chat and edit capability
        row = self.conn.execute('''SELECT f.*, c.full_name, c.primary_phone, u.name agent, cu.name creator_name
            FROM follow_ups f
            JOIN customers c ON c.id=f.customer_id
            LEFT JOIN users u ON u.id=f.assigned_agent_id
            LEFT JOIN users cu ON cu.id=f.created_by
            WHERE f.id=?''', (fu_id,)).fetchone()
        if not row:
            return self.not_found()
        due = to_jalali_display(row[\"due_at\"])[:16]
        created_display = to_jalali_display(row[\"created_at\"])[:16] if row[\"created_at\"] else ''
        comments = self.conn.execute('''SELECT fc.*, u.name user_name FROM follow_up_comments fc
            LEFT JOIN users u ON u.id=fc.user_id
            WHERE fc.follow_up_id=? ORDER BY fc.created_at ASC''', (fu_id,)).fetchall()
        comments_html = ''
        for c in comments:
            c_time = to_jalali_display(c['created_at'])[:16] if c['created_at'] else ''
            c_name = esc(c['user_name'] or 'سیستم')
            c_text = esc(c['comment'])
            comments_html += f'<div class=\"chat-msg\"><strong>{c_name}</strong> <small class=\"muted\">{c_time}</small><p>{c_text}</p></div>'
        if not comments_html:
            comments_html = '<p class=\"muted\">هنوز پیامی ثبت نشده است.</p>'
        prio_opts = options(PRIORITIES, row['priority'])
        user_opts_all = user_options(self.conn, row['assigned_agent_id'], blank='انتخاب اپراتور')
        edit_form = ''
        if row['status'] == 'pending':
            edit_form = f'''<details class=\"panel\" style=\"padding:16px;margin-top:12px\">
            <summary style=\"cursor:pointer;font-weight:600;font-size:.9rem\">✏️ ویرایش پیگیری</summary>
            <form method=\"post\" action=\"/follow-ups/{fu_id}/edit\" class=\"form-layout\" style=\"margin-top:8px;box-shadow:none;padding:0\">
                <div class=\"form-row\"><label>موضوع (دلیل)<input name=\"reason\" value=\"{esc(row['reason'] or '')}\"></label>
                <label>اولویت<select name=\"priority\">{prio_opts}</select></label></div>
                <div class=\"form-row\"><label>مهلت پیگیری<input class=\"jalali-datetime\" name=\"due_at\" value=\"{jalali_input_value(row['due_at'], with_time=True)[:16]}\"></label>
                <label>مسئول<select name=\"assigned_agent_id\">{user_opts_all}</select></label></div>
                <label>یادداشت‌ها<textarea name=\"notes\">{esc(row['notes'] or '')}</textarea></label>
                <button type=\"submit\" class=\"small\">ذخیره تغییرات</button>
            </form></details>'''
        body = f'''<div class=\"fu-detail-layout\">
          <div class=\"panel\" style=\"padding:16px\">
            <div class=\"top\"><h2>پیگیری: {esc(row[\"full_name\"])}</h2><a href=\"/follow-ups\" class=\"button small secondary\">← بازگشت</a></div>
            <div class=\"fu-body\" style=\"margin-top:8px\">
                <small>مشتری: {esc(row[\"full_name\"])}</small>
                <small>تلفن: {esc(row[\"primary_phone\"])}</small>
                <small>موضوع: {esc(row[\"reason\"] or \"—\")}</small>
                <small>مهلت: {due}</small>
                <small>اولویت: <span class=\"pill prio-{esc(row[\"priority\"])}\">{label(row[\"priority\"])}</span></small>
                <small>اپراتور: {esc(row[\"agent\"] or \"—\")}</small>
                <small>ایجادکننده: {esc(row[\"creator_name\"] or \"—\")}</small>
                <small>تاریخ ایجاد: {created_display}</small>
                <small>وضعیت: <span class=\"pill status-{esc(row[\"status\"])}\">{label(row[\"status\"])}</span></small>
            </div>
          </div>
          {edit_form}
          <div class=\"panel\" style=\"padding:16px;margin-top:12px\">
            <h3>💬 گفتگوی پیگیری</h3>
            <div class=\"chat-box\" id=\"chat-box\">{comments_html}</div>
            <form method=\"post\" action=\"/follow-ups/{fu_id}/comment\" class=\"chat-form\" style=\"margin-top:8px;display:flex;gap:8px\">
                <textarea name=\"comment\" placeholder=\"پیام خود را بنویسید...\" style=\"flex:1;min-height:44px\" required></textarea>
                <button type=\"submit\" class=\"small\" style=\"align-self:flex-end\">ارسال</button>
            </form>
          </div>
          <div class=\"panel\" style=\"padding:16px;margin-top:12px\">
            <h3>یادداشت‌ها</h3>
            <p>{esc(row[\"notes\"] or \"—\")}</p>
          </div>
        </div>'''
        return self.send_html(body, f\"پیگیری: {row['full_name']}\")"""

if old_fu_action_get_end in content:
    content = content.replace(old_fu_action_get_end, new_fu_action_get_end)
    changes += 1
    print("[OK] Updated followup_action() GET - added edit form")
else:
    print("[WARN] Could not find old followup_action GET section")

# ============================================================
# 3. Add 'edit' action to followup_action() POST handler
# ============================================================
old_fu_post = """        if method == 'POST':
            if action == 'reassign':
                d = self.form()
                agent_id = d.get('agent_id', '').strip()
                if agent_id:
                    self.conn.execute(\"UPDATE follow_ups SET assigned_agent_id=?, updated_at=? WHERE id=?\",\"
                        (agent_id, now_iso(), fu_id))
                else:
                    self.conn.execute(\"UPDATE follow_ups SET assigned_agent_id=NULL, updated_at=? WHERE id=?\",\"
                        (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'complete':
                self.conn.execute(\"UPDATE follow_ups SET status='done', completed_at=?, updated_at=? WHERE id=?\",\"
                    (now_iso(), now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'cancel':
                self.conn.execute(\"UPDATE follow_ups SET status='cancelled', updated_at=? WHERE id=?\",\"
                    (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups')
            if action == 'comment':
                d = self.form()
                comment = d.get('comment', '').strip()
                if comment:
                    self.conn.execute(\"INSERT INTO follow_up_comments(follow_up_id,user_id,comment,created_at) VALUES(?,?,?,?)\",\"
                        (fu_id, self.current_user['id'], comment, now_iso()))
                    self.conn.commit()
                return self.redirect(f'/follow-ups/{fu_id}')"""

new_fu_post = """        if method == 'POST':
            if action == 'reassign':
                d = self.form()
                agent_id = d.get('agent_id', '').strip()
                if agent_id:
                    self.conn.execute(\"UPDATE follow_ups SET assigned_agent_id=?, updated_at=? WHERE id=?\",\"
                        (agent_id, now_iso(), fu_id))
                else:
                    self.conn.execute(\"UPDATE follow_ups SET assigned_agent_id=NULL, updated_at=? WHERE id=?\",\"
                        (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups' + ('?status=' + self.query.get('status',['pending'])[0] if 'status' in self.query else ''))
            if action == 'complete':
                self.conn.execute(\"UPDATE follow_ups SET status='done', completed_at=?, updated_at=? WHERE id=?\",\"
                    (now_iso(), now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups' + ('?status=' + self.query.get('status',['pending'])[0] if 'status' in self.query else ''))
            if action == 'cancel':
                self.conn.execute(\"UPDATE follow_ups SET status='cancelled', updated_at=? WHERE id=?\",\"
                    (now_iso(), fu_id))
                self.conn.commit()
                return self.redirect('/follow-ups' + ('?status=' + self.query.get('status',['pending'])[0] if 'status' in self.query else ''))
            if action == 'edit':
                d = self.form()
                reason = d.get('reason', '').strip()
                priority = d.get('priority', 'normal')
                due_at_raw = d.get('due_at', '').strip()
                due_at = parse_jalali(due_at_raw, True) if due_at_raw else None
                agent_id = d.get('assigned_agent_id', '').strip() or None
                notes = d.get('notes', '').strip()
                if due_at:
                    self.conn.execute(\"UPDATE follow_ups SET reason=?, priority=?, due_at=?, assigned_agent_id=?, notes=?, updated_at=? WHERE id=?\",\"
                        (reason or None, priority, due_at, agent_id, notes or None, now_iso(), fu_id))
                else:
                    self.conn.execute(\"UPDATE follow_ups SET reason=?, priority=?, assigned_agent_id=?, notes=?, updated_at=? WHERE id=?\",\"
                        (reason or None, priority, agent_id, notes or None, now_iso(), fu_id))
                self.conn.commit()
                return self.redirect(f'/follow-ups/{fu_id}')
            if action == 'comment':
                d = self.form()
                comment = d.get('comment', '').strip()
                if comment:
                    self.conn.execute(\"INSERT INTO follow_up_comments(follow_up_id,user_id,comment,created_at) VALUES(?,?,?,?)\",\"
                        (fu_id, self.current_user['id'], comment, now_iso()))
                    self.conn.commit()
                return self.redirect(f'/follow-ups/{fu_id}')"""

if old_fu_post in content:
    content = content.replace(old_fu_post, new_fu_post)
    changes += 1
    print("[OK] Updated followup_action() POST - added edit action")
else:
    print("[WARN] Could not find old followup_action POST section")

# ============================================================
# 4. Enhance base_tables() - add edit functionality
# ============================================================
old_base_tables = """    def base_tables(self, method):
        if method == 'POST':
            d = self.form()
            action = d.get('action','')
            if action == 'add' and d.get('lookup_type') and d.get('value') and d.get('label'):
                self.conn.execute('''INSERT OR IGNORE INTO lookup_items(lookup_type,value,label,is_active,created_at,updated_at) VALUES(?,?,?,1,?,?)''',
                    (d['lookup_type'], d['value'], d['label'], now_iso(), now_iso()))
                self.conn.commit()
            elif action == 'delete' and d.get('id'):
                self.conn.execute(\"UPDATE lookup_items SET is_active=0,updated_at=? WHERE id=?\", (now_iso(), d['id']))
                self.conn.commit()
            return self.redirect('/base-tables')
        out = ['<h2>جداول پایه</h2>']
        for lookup_type, (title, _) in LOOKUP_DEFS.items():
            items = self.conn.execute(\"SELECT * FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id\", (lookup_type,)).fetchall()
            out.append(f'<div class=\"section\"><h3>{esc(title)}</h3><table><thead><tr><th>مقدار</th><th>برچسب</th><th>عملیات</th></tr></thead><tbody>')
            for it in items:
                out.append(f'<tr><td>{esc(it[\"value\"])}</td><td>{esc(it[\"label\"])}</td><td><form method=\"post\" style=\"display:inline\"><input type=\"hidden\" name=\"action\" value=\"delete\"><input type=\"hidden\" name=\"id\" value=\"{it[\"id\"]}\"><button type=\"submit\" class=\"small secondary\">حذف</button></form></td></tr>')
            out.append('</tbody></table>')
            out.append(f'''<form method=\"post\" class=\"form-row\">
                <input type=\"hidden\" name=\"lookup_type\" value=\"{esc(lookup_type)}\">
                <input type=\"hidden\" name=\"action\" value=\"add\">
                <label>مقدار<input name=\"value\" placeholder=\"مقدار انگلیسی\" required></label>
                <label>برچسب<input name=\"label\" placeholder=\"برچسب فارسی\" required></label>
                <button type=\"submit\" class=\"small\">افزودن</button>
            </form></div>''')
        return self.send_html(\"\".join(out), \"جداول پایه\")"""

new_base_tables = """    def base_tables(self, method):
        if method == 'POST':
            d = self.form()
            action = d.get('action','')
            if action == 'add' and d.get('lookup_type') and d.get('value') and d.get('label'):
                self.conn.execute('''INSERT OR IGNORE INTO lookup_items(lookup_type,value,label,is_active,created_at,updated_at) VALUES(?,?,?,1,?,?)''',
                    (d['lookup_type'], d['value'], d['label'], now_iso(), now_iso()))
                self.conn.commit()
            elif action == 'delete' and d.get('id'):
                self.conn.execute(\"UPDATE lookup_items SET is_active=0,updated_at=? WHERE id=?\", (now_iso(), d['id']))
                self.conn.commit()
            elif action == 'edit' and d.get('id') and d.get('label'):
                self.conn.execute(\"UPDATE lookup_items SET label=?,updated_at=? WHERE id=?\", (d['label'], now_iso(), d['id']))
                self.conn.commit()
            return self.redirect('/base-tables')
        out = ['<h2>جداول پایه</h2>']
        for lookup_type, (title, _) in LOOKUP_DEFS.items():
            items = self.conn.execute(\"SELECT * FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id\", (lookup_type,)).fetchall()
            out.append(f'<div class=\"section\"><h3>{esc(title)}</h3><table><thead><tr><th>مقدار</th><th>برچسب</th><th>عملیات</th></tr></thead><tbody>')
            for it in items:
                out.append(f'<tr><td>{esc(it[\"value\"])}</td><td>{esc(it[\"label\"])}</td>'
                    f'<td class=\"actions\" style=\"display:flex;gap:4px\">'
                    f'<form method=\"post\" style=\"display:inline-flex;gap:4px;align-items:center\">'
                    f'<input type=\"hidden\" name=\"id\" value=\"{it[\"id\"]}\">'
                    f'<input type=\"hidden\" name=\"action\" value=\"edit\">'
                    f'<input type=\"text\" name=\"label\" value=\"{esc(it[\"label\"])}\" style=\"width:100px;padding:3px 6px;font-size:.78rem\">'
                    f'<button type=\"submit\" class=\"small\">✓</button>'
                    f'</form>'
                    f'<form method=\"post\" style=\"display:inline\"><input type=\"hidden\" name=\"action\" value=\"delete\">'
                    f'<input type=\"hidden\" name=\"id\" value=\"{it[\"id\"]}\"><button type=\"submit\" class=\"small secondary\">✕</button></form></td></tr>')
            out.append('</tbody></table>')
            out.append(f'''<form method=\"post\" class=\"form-row\">
                <input type=\"hidden\" name=\"lookup_type\" value=\"{esc(lookup_type)}\">
                <input type=\"hidden\" name=\"action\" value=\"add\">
                <label>مقدار<input name=\"value\" placeholder=\"مقدار انگلیسی\" required></label>
                <label>برچسب<input name=\"label\" placeholder=\"برچسب فارسی\" required></label>
                <button type=\"submit\" class=\"small\">افزودن</button>
            </form></div>''')
        return self.send_html(\"\".join(out), \"جداول پایه\")"""

if old_base_tables in content:
    content = content.replace(old_base_tables, new_base_tables)
    changes += 1
    print("[OK] Updated base_tables() - added inline edit for labels")
else:
    print("[WARN] Could not find old base_tables() method")

# ============================================================
# 5. Add CSS for tab-bar
# ============================================================
css_path = os.path.join(BASE, 'app.css')
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

tab_bar_css = """
/* Tab bar */
.tab-bar{display:flex;gap:2px;margin-bottom:12px;background:var(--bg);border-radius:10px;padding:3px;overflow-x:auto}
.tab-bar a.tab{padding:6px 16px;border-radius:8px;font-size:.82rem;font-weight:500;color:var(--muted);text-decoration:none;transition:var(--transition);white-space:nowrap}
.tab-bar a.tab:hover{background:var(--card);color:var(--text)}
.tab-bar a.tab.active{background:var(--card);color:var(--text);box-shadow:var(--shadow)}"""

if tab_bar_css not in css:
    # Insert before chat box styles
    css = css.replace(
        "/* Follow-up detail */",
        tab_bar_css + "\n/* Follow-up detail */"
    )
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css)
    print("[OK] Added tab-bar CSS")
else:
    print("[OK] tab-bar CSS already exists")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nDone! {changes} changes applied to app.py")
