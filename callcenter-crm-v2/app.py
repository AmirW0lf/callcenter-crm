#!/usr/bin/env python3
"""
CallCenter CRM v2 - Multilingual & Enhanced Edition
Supports: Persian (fa), English (en), Arabic (ar), Russian (ru)
RTL & LTR Automatic Layout, High-Concurrency SQLite (WAL), Clean Architecture
"""
import csv
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import socket
import sqlite3
import sys
import traceback
import urllib.parse
from datetime import datetime, date, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sms_service
import backup_manager

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "crm.sqlite3")
SESSION_COOKIE = "crm_session"
LANG_COOKIE = "crm_lang"
DEFAULT_LANG = "fa"
SUPPORTED_LANGS = ["fa", "en", "ar", "ru"]
SESSIONS = {}

def _load_asset(filename):
    try:
        p = os.path.join(BASE_DIR, filename)
        if not os.path.exists(p):
            p = os.path.join(os.path.dirname(BASE_DIR), filename)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return ""

_FLATPICKR_CSS = _load_asset("flatpickr.min.css")
_FLATPICKR_JS = _load_asset("flatpickr.min.js")
_FLATPICKR_FA = _load_asset("flatpickr-fa.js")

# Lookup core keys
SOURCES = ["phone_call", "walk_in", "facebook", "instagram", "website", "referral", "old_customer", "other"]
PROJECT_STAGES = ["planning", "permits", "foundation", "structure", "brickwork", "electrical_plumbing", "finishing", "final_inspection", "ready", "delivered", "paused"]
REG_STATUSES = ["open", "closed", "coming_soon", "sold_out"]
CALL_TYPES = ["incoming", "outgoing", "missed", "follow_up"]
PRIORITIES = ["low", "normal", "high", "urgent"]
NOTE_TYPES = ["general", "manager_note", "project_note", "complaint_note", "document_note"]
PROBLEM_TYPES = [
    "registration_question", "project_progress", "payment_question", "documents_question",
    "site_visit", "delay_complaint", "quality_complaint", "wrong_number", "other"
]
FOLLOW_UP_REASONS = [
    "site_visit", "payment_follow_up", "document_follow_up", "call_back",
    "contract_follow_up", "progress_update", "general_follow_up", "other"
]
STATUSES = ["pending", "done", "cancelled"]
CUSTOMER_STATUSES = [
    "new_lead", "contacted", "interested", "needs_follow_up", "site_visit_scheduled",
    "documents_requested", "documents_received", "registered_signed", "payment_pending",
    "active_customer", "project_progress_inquiry", "complaint_issue", "not_interested", "closed"
]

# Multilingual Vocabulary Dictionary
I18N = {
    "fa": {
        "lang_name": "فارسی", "dir": "rtl",
        "app_title": "CRM مرکز تماس و ارتباط با مشتریان",
        "login_title": "ورود به سامانه CRM", "login_heading": "سامانه پاسخگویی و ثبت اطلاعات",
        "email": "ایمیل", "password": "رمز عبور", "login_btn": "ورود به حساب",
        "demo_accounts": "حساب‌های پیش‌فرض: مدیر (admin@crm.local / admin123) | اپراتور (agent@crm.local / password123)",
        "invalid_login": "ایمیل یا رمز عبور اشتباه است.",
        "dashboard": "داشبورد", "customers": "مشتریان", "projects": "پروژه‌ها", "follow_ups": "پیگیری‌ها",
        "reports": "گزارش‌ها", "my_report": "گزارش من", "users": "کاربران", "base_tables": "جداول پایه",
        "logout": "خروج", "active": "فعال", "inactive": "غیرفعال", "actions": "عملیات",
        "save": "ذخیره", "cancel": "انصراف", "edit": "ویرایش", "delete": "حذف", "view": "مشاهده",
        "search": "جستجو...", "filter": "فیلتر", "clear_filter": "پاک کردن فیلتر",
        "from_date": "از تاریخ", "to_date": "تا تاریخ", "date": "تاریخ", "time": "ساعت",
        "total_customers": "کل مشتریان", "calls_today": "تماس‌های امروز", "follow_today": "پیگیری‌های امروز",
        "overdue_followups": "پیگیری‌های عقب‌افتاده", "signed_customers": "ثبت‌نام شده", "total_projects": "پروژه‌ها",
        "avg_duration": "میانگین مدت (دقیقه)", "total_duration": "مجموع مدت (دقیقه)",
        "new_call_title": "📞 ثبت تماس جدید", "recent_calls": "تماس‌های اخیر", "customer_projects": "پروژه‌های مشتری",
        "recent_followups": "پیگیری‌های مشتری", "call_date": "تاریخ تماس", "call_time": "ساعت شروع",
        "search_customer_box": "جستجوی مشتری (کد ملی، تلفن یا نام)",
        "search_hint": "شماره ملی، شماره تماس یا نام مشتری را تایپ کنید تا پرونده بارگذاری شود",
        "new_customer_heading": "اطلاعات مشتری جدید", "customer_name": "نام کامل مشتری", "primary_phone": "تلفن تماس",
        "national_code": "کد ملی / شناسه", "city": "شهر", "address": "آدرس", "secondary_phone": "تلفن دوم",
        "source": "منبع جذب", "customer_status": "وضعیت مشتری", "assigned_agent": "اپراتور مسئول",
        "call_duration": "مدت تماس (دقیقه)", "call_type": "نوع تماس", "call_topic": "موضوع/دلیل تماس",
        "call_project": "پروژه مرتبط با این تماس", "needs_followup": "نیاز به پیگیری دارد",
        "followup_reason": "دلیل پیگیری", "followup_due": "مهلت پیگیری (تاریخ و ساعت)", "followup_agent": "اپراتور پیگیری",
        "followup_notes": "یادداشت برای اپراتور مسئول", "call_notes": "یادداشت‌ها و توضیحات تماس",
        "save_call_btn": "ذخیره تماس", "no_active_followups": "هیچ پیگیری فعالی وجود ندارد.",
        "today_overdue_followups": "پیگیری‌های امروز و عقب‌افتاده",
        "due_deadline": "مهلت", "priority": "اولویت", "operator": "اپراتور", "customer": "مشتری",
        "status": "وضعیت", "overdue_label": "عقب‌افتاده", "done_btn": "انجام شد", "cancel_btn": "لغو",
        "chat_details": "گفتگو / جزئیات", "followup_conversation": "💬 گفتگوی پیگیری",
        "write_comment": "پیام خود را بنویسید...", "send_btn": "ارسال", "no_comments_yet": "هنوز پیامی ثبت نشده است.",
        "delete_confirm": "آیا از حذف این مورد اطمینان دارید؟",
        "new_customer_btn": "+ مشتری جدید", "new_project_btn": "+ پروژه جدید", "new_user_btn": "+ کاربر جدید",
        "export_excel": "خروجی Excel", "daily_report": "گزارش روزانه", "by_project": "بر اساس پروژه",
        "by_agent": "بر اساس اپراتور", "customer_list": "لیست مشتریان", "followup_list": "لیست پیگیری‌ها",
        "date_range_export": "خروجی بازه زمانی", "call_types_chart": "نوع تماس‌ها",
        "topics_chart": "موضوعات تماس", "daily_calls_chart": "تماس‌های ۳۰ روز اخیر", "agent_performance": "عملکرد اپراتورها",
        "project_calls": "تماس‌ها بر اساس پروژه", "source_distribution": "منبع جذب مشتریان",
        "stage": "مرحله ساخت", "progress": "پیشرفت", "reg_status": "وضعیت ثبت‌نام",
        "expected_date": "تاریخ تکمیل پیش‌بینی شده", "description": "توضیحات", "public_update": "گزارش پیشرفت عمومی",
        "internal_notes": "یادداشت‌های داخلی", "add_item": "افزودن مورد جدید",
        "code_value": "کد انگلیسی", "label_title": "عنوان نمایشی", "role": "نقش کاربر",
        "manager": "مدیر سیستم", "agent": "اپراتور", "all": "همه", "unique_customers": "مشتریان یکتا",
        "count": "تعداد", "percentage": "درصد", "minute": "دقیقه", "second": "ثانیه",
        "unassigned": "بدون مسئول", "no_project": "بدون پروژه",
        "saved_success": "اطلاعات با موفقیت ذخیره شد.", "watermark": "سیستم جامع ثبت اطلاعات و مدیریت ارتباط با مشتریان مرکز تماس",
        "developer_credit": "تهیه شده توسط امیرحسین کرمی • شماره تماس: 09106827218",
        "backup_db": "پشتیبان‌گیری پایگاه داده",
        "no_records_found": "هیچ رکوردی در بازه زمانی انتخابی یافت نشد.",
        "preset_today": "امروز",
        "preset_7days": "۷ روز اخیر",
        "preset_30days": "۳۰ روز اخیر",
        "preset_all": "همه زمان‌ها",
        "satisfaction_score": "ارزیابی و رضایت مخاطب",
        "satisfaction_notes": "یادداشت رضایت‌سنجی",
        "qa_score": "امتیاز کنترل کیفیت (QA)",
        "qa_notes": "یادداشت ناظر کیفی",
        "rating_5": "بسیار عالی (۵ ستاره)",
        "rating_4": "خوب و راضی (۴ ستاره)",
        "rating_3": "متوسط (۳ ستاره)",
        "rating_2": "ضعیف و ناراضی (۲ ستاره)",
        "rating_1": "بسیار ضعیف (۱ ستاره)",
        "sms_settings": "تنظیمات پیامک",
        "sms_logs": "گزارش پیامک‌ها",
        "csat_title": "ارزیابی کیفیت و رضایت‌سنجی مخاطبان (CSAT)",
        "avg_csat": "میانگین رضایت مخاطبان",
        "avg_qa": "میانگین نمره کیفی (QA)",
        "incoming_call_alert": "تماس ورودی جدید"
    },
    "en": {
        "lang_name": "English", "dir": "ltr",
        "app_title": "CallCenter CRM System",
        "login_title": "Login - CallCenter CRM", "login_heading": "Call Center CRM & Inquiries",
        "email": "Email Address", "password": "Password", "login_btn": "Sign In",
        "demo_accounts": "Default Logins: Manager (admin@crm.local / admin123) | Agent (agent@crm.local / password123)",
        "invalid_login": "Invalid email or password.",
        "dashboard": "Dashboard", "customers": "Customers", "projects": "Projects", "follow_ups": "Follow-ups",
        "reports": "Reports", "my_report": "My Report", "users": "Users", "base_tables": "Base Tables",
        "logout": "Logout", "active": "Active", "inactive": "Inactive", "actions": "Actions",
        "save": "Save", "cancel": "Cancel", "edit": "Edit", "delete": "Delete", "view": "View",
        "search": "Search...", "filter": "Filter", "clear_filter": "Clear Filter",
        "from_date": "From Date", "to_date": "To Date", "date": "Date", "time": "Time",
        "total_customers": "Total Customers", "calls_today": "Today's Calls", "follow_today": "Today's Follow-ups",
        "overdue_followups": "Overdue Follow-ups", "signed_customers": "Registered / Signed", "total_projects": "Projects",
        "avg_duration": "Avg Duration (min)", "total_duration": "Total Duration (min)",
        "new_call_title": "📞 Register New Call", "recent_calls": "Recent Calls", "customer_projects": "Customer Projects",
        "recent_followups": "Customer Follow-ups", "call_date": "Call Date", "call_time": "Start Time",
        "search_customer_box": "Search Customer (National ID, Phone or Name)",
        "search_hint": "Type national ID, phone number or name to search or register quickly",
        "new_customer_heading": "New Customer Information", "customer_name": "Full Name", "primary_phone": "Primary Phone",
        "national_code": "National ID / Passport", "city": "City", "address": "Address", "secondary_phone": "Secondary Phone",
        "source": "Lead Source", "customer_status": "Customer Status", "assigned_agent": "Assigned Agent",
        "call_duration": "Call Duration (minutes)", "call_type": "Call Type", "call_topic": "Topic / Reason",
        "call_project": "Project for this call", "needs_followup": "Follow-up Required",
        "followup_reason": "Follow-up Reason", "followup_due": "Follow-up Due (Date & Time)", "followup_agent": "Assigned Agent",
        "followup_notes": "Note for Follow-up Agent", "call_notes": "Call Notes & Details",
        "save_call_btn": "Save Call", "no_active_followups": "No active follow-ups found.",
        "today_overdue_followups": "Today's & Overdue Follow-ups",
        "due_deadline": "Due Date", "priority": "Priority", "operator": "Agent", "customer": "Customer",
        "status": "Status", "overdue_label": "Overdue", "done_btn": "Completed", "cancel_btn": "Cancel",
        "chat_details": "Chat / Details", "followup_conversation": "💬 Follow-up Conversation Thread",
        "write_comment": "Type your comment...", "send_btn": "Send", "no_comments_yet": "No comments yet.",
        "delete_confirm": "Are you sure you want to delete this item?",
        "new_customer_btn": "+ New Customer", "new_project_btn": "+ New Project", "new_user_btn": "+ New User",
        "export_excel": "Export Excel/CSV", "daily_report": "Daily Report", "by_project": "Grouped by Project",
        "by_agent": "Grouped by Agent", "customer_list": "Customer List", "followup_list": "Follow-up List",
        "date_range_export": "Date Range Export", "call_types_chart": "Call Types",
        "topics_chart": "Call Topics / Reasons", "daily_calls_chart": "Daily Calls (Last 30 Days)", "agent_performance": "Agent Performance",
        "project_calls": "Calls by Project", "source_distribution": "Lead Sources",
        "stage": "Stage", "progress": "Progress", "reg_status": "Registration Status",
        "expected_date": "Expected Completion Date", "description": "Description", "public_update": "Public Progress Update",
        "internal_notes": "Internal Notes", "add_item": "Add Item",
        "code_value": "Key Code", "label_title": "Display Title", "role": "Role",
        "manager": "Manager", "agent": "Agent", "all": "All", "unique_customers": "Unique Customers",
        "count": "Count", "percentage": "Percentage", "minute": "min", "second": "sec",
        "unassigned": "Unassigned", "no_project": "No Project",
        "saved_success": "Information saved successfully.", "watermark": "Call Center Customer Inquiries & Information Management CRM",
        "developer_credit": "Developed by Amirhossein Karami • Contact: 09106827218",
        "backup_db": "Database Backup",
        "no_records_found": "No records found for the selected date range.",
        "preset_today": "Today",
        "preset_7days": "Last 7 Days",
        "preset_30days": "Last 30 Days",
        "preset_all": "All Time",
        "satisfaction_score": "Customer Satisfaction (CSAT)",
        "satisfaction_notes": "Satisfaction Notes",
        "qa_score": "QA Quality Score",
        "qa_notes": "Supervisor Review Notes",
        "rating_5": "Excellent (5 Stars)",
        "rating_4": "Good (4 Stars)",
        "rating_3": "Neutral (3 Stars)",
        "rating_2": "Poor (2 Stars)",
        "rating_1": "Very Poor (1 Star)",
        "sms_settings": "SMS Gateway Settings",
        "sms_logs": "SMS Delivery Logs",
        "csat_title": "Quality Assessment & Satisfaction (CSAT)",
        "avg_csat": "Avg Customer Satisfaction",
        "avg_qa": "Avg QA Score",
        "incoming_call_alert": "Incoming Live Call"
    },
    "ar": {
        "lang_name": "العربية", "dir": "rtl",
        "app_title": "نظام CRM لمركز الاتصال والاستجابة",
        "login_title": "تسجيل الدخول - نظام CRM", "login_heading": "نظام إدارة الاتصالات وتسجيل المعلومات",
        "email": "البريد الإلكتروني", "password": "كلمة المرور", "login_btn": "تسجيل الدخول",
        "demo_accounts": "الحسابات الافتراضية: المدير (admin@crm.local / admin123) | المشغل (agent@crm.local / password123)",
        "invalid_login": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "dashboard": "لوحة القيادة", "customers": "العملاء", "projects": "المشاريع", "follow_ups": "المتابعات",
        "reports": "التقارير", "my_report": "تقريري", "users": "المستخدمون", "base_tables": "الجداول الأساسية",
        "logout": "تسجيل الخروج", "active": "نشط", "inactive": "غير نشط", "actions": "الإجراءات",
        "save": "حفظ", "cancel": "إلغاء", "edit": "تعديل", "delete": "حذف", "view": "عرض",
        "search": "بحث...", "filter": "تصفية", "clear_filter": "مسح التصفية",
        "from_date": "من تاريخ", "to_date": "إلى تاريخ", "date": "التاريخ", "time": "الوقت",
        "total_customers": "إجمالي العملاء", "calls_today": "مكالمات اليوم", "follow_today": "متابعات اليوم",
        "overdue_followups": "المتابعات المتأخرة", "signed_customers": "المسجلون / المتعاقدون", "total_projects": "المشاريع",
        "avg_duration": "متوسط المدة (دقيقة)", "total_duration": "إجمالي المدة (دقيقة)",
        "new_call_title": "📞 تسجيل مكالمة جديدة", "recent_calls": "المكالمات الأخيرة", "customer_projects": "مشاريع العميل",
        "recent_followups": "متابعات العميل", "call_date": "تاريخ المكالمة", "call_time": "وقت البدء",
        "search_customer_box": "البحث عن عميل (الرقم القومي، الهاتف أو الاسم)",
        "search_hint": "اكتب الرقم القومي أو رقم الهاتف أو الاسم للبحث أو التسجيل السريع",
        "new_customer_heading": "بيانات العميل الجديد", "customer_name": "اسم العميل الكامل", "primary_phone": "رقم الهاتف",
        "national_code": "الرقم القومي / الهوية", "city": "المدينة", "address": "العنوان", "secondary_phone": "الهاتف البديل",
        "source": "مصدر العميل", "customer_status": "حالة العميل", "assigned_agent": "المشغل المسؤول",
        "call_duration": "مدة المكالمة (بالدقائق)", "call_type": "نوع المكالمة", "call_topic": "موضوع / سبب المكالمة",
        "call_project": "المشروع المرتبط بالمكالمة", "needs_followup": "تتطلب متابعة",
        "followup_reason": "سبب المتابعة", "followup_due": "موعد المتابعة (التاريخ والوقت)", "followup_agent": "المشغل المتابع",
        "followup_notes": "ملاحظة للمشغل المسؤول", "call_notes": "ملاحظات وتفاصيل المكالمة",
        "save_call_btn": "حفظ المكالمة", "no_active_followups": "لا توجد متابعات نشطة.",
        "today_overdue_followups": "متابعات اليوم والمتأخرة",
        "due_deadline": "الموعد", "priority": "الأولوية", "operator": "المشغل", "customer": "العميل",
        "status": "الحالة", "overdue_label": "متأخر", "done_btn": "تم الإنجاز", "cancel_btn": "إلغاء",
        "chat_details": "محادثة / تفاصيل", "followup_conversation": "💬 سجل محادثة المتابعة",
        "write_comment": "اكتب تعليقك هنا...", "send_btn": "إرسال", "no_comments_yet": "لا توجد رسائل حتى الآن.",
        "delete_confirm": "هل أنت متأكد من حذف هذا العنصر؟",
        "new_customer_btn": "+ عميل جديد", "new_project_btn": "+ مشروع جديد", "new_user_btn": "+ مستخدم جديد",
        "export_excel": "تصدير Excel/CSV", "daily_report": "التقرير اليومي", "by_project": "حسب المشروع",
        "by_agent": "حسب المشغل", "customer_list": "قائمة العملاء", "followup_list": "قائمة المتابعات",
        "date_range_export": "تصدير نطاق زمني", "call_types_chart": "أنواع المكالمات",
        "topics_chart": "مواضيع المكالمات", "daily_calls_chart": "مكالمات آخر ۳۰ يومًا", "agent_performance": "أداء المشغلين",
        "project_calls": "المكالمات حسب المشروع", "source_distribution": "مصادر العملاء",
        "stage": "مرحلة البناء", "progress": "نسبة الإنجاز", "reg_status": "حالة التسجيل",
        "expected_date": "تاريخ الانتهاء المتوقع", "description": "الوصف", "public_update": "تحديث الإنجاز العام",
        "internal_notes": "ملاحظات داخلية", "add_item": "إضافة عنصر جديد",
        "code_value": "رمز القيمة", "label_title": "العنوان المعروض", "role": "الدور",
        "manager": "مدير النظام", "agent": "مشغل", "all": "الكل", "unique_customers": "عملاء فريدون",
        "count": "العدد", "percentage": "النسبة", "minute": "دقيقة", "second": "ثانية",
        "unassigned": "غير محدد", "no_project": "بدون مشروع",
        "saved_success": "تم حفظ البيانات بنجاح.", "watermark": "نظام مركز الاتصال لإدارة علاقات العملاء واستقبال الاستفسارات",
        "developer_credit": "تم الإعداد والتطوير بواسطة أمير حسين كرمي • هاتف: 09106827218",
        "backup_db": "نسخ احتياطي لقاعدة البيانات",
        "no_records_found": "لم يتم العثور على أي سجلات في النطاق الزمني المحدد.",
        "preset_today": "اليوم",
        "preset_7days": "آخر ۷ أيام",
        "preset_30days": "آخر ۳۰ يوماً",
        "preset_all": "كل الأوقات",
        "satisfaction_score": "تقييم ورضا المتصل (CSAT)",
        "satisfaction_notes": "ملاحظات رضا المتصل",
        "qa_score": "درجة ضبط الجودة (QA)",
        "qa_notes": "ملاحظات المشرف",
        "rating_5": "ممتاز (٥ نجوم)",
        "rating_4": "جيد (٤ نجوم)",
        "rating_3": "متوسط (٣ نجوم)",
        "rating_2": "ضعيف (نجمتان)",
        "rating_1": "ضعيف جداً (نجمة واحدة)",
        "sms_settings": "إعدادات الرسائل (SMS)",
        "sms_logs": "سجل الرسائل",
        "csat_title": "تقييم الجودة ورضا المتصلين (CSAT)",
        "avg_csat": "متوسط رضا المتصلين",
        "avg_qa": "متوسط درجة الجودة",
        "incoming_call_alert": "مكالمة واردة جديدة"
    },
    "ru": {
        "lang_name": "Русский", "dir": "ltr",
        "app_title": "CRM-система колл-центра",
        "login_title": "Вход в систему - CallCenter CRM", "login_heading": "Система колл-центра и регистрации обращений",
        "email": "Электронная почта", "password": "Пароль", "login_btn": "Войти в систему",
        "demo_accounts": "Учетные записи: Руководитель (admin@crm.local / admin123) | Оператор (agent@crm.local / password123)",
        "invalid_login": "Неверный email или пароль.",
        "dashboard": "Панель управления", "customers": "Клиенты", "projects": "Проекты", "follow_ups": "Задачи и контроль",
        "reports": "Отчёты", "my_report": "Мой отчёт", "users": "Пользователи", "base_tables": "Справочники",
        "logout": "Выйти", "active": "Активен", "inactive": "Неактивен", "actions": "Действия",
        "save": "Сохранить", "cancel": "Отмена", "edit": "Редактировать", "delete": "Удалить", "view": "Просмотр",
        "search": "Поиск...", "filter": "Фильтр", "clear_filter": "Сбросить фильтр",
        "from_date": "С даты", "to_date": "По дату", "date": "Дата", "time": "Время",
        "total_customers": "Всего клиентов", "calls_today": "Звонков сегодня", "follow_today": "Задач на сегодня",
        "overdue_followups": "Просроченных задач", "signed_customers": "Оформлено / Договор", "total_projects": "Проекты",
        "avg_duration": "Средняя длит. (мин)", "total_duration": "Общая длит. (мин)",
        "new_call_title": "📞 Регистрация нового звонка", "recent_calls": "Последние звонки", "customer_projects": "Проекты клиента",
        "recent_followups": "Задачи по клиенту", "call_date": "Дата звонка", "call_time": "Время начала",
        "search_customer_box": "Поиск клиента (паспорт/ИНН, телефон или имя)",
        "search_hint": "Введите номер документа, телефон или имя для быстрого поиска или создания",
        "new_customer_heading": "Данные нового клиента", "customer_name": "ФИО клиента", "primary_phone": "Основной телефон",
        "national_code": "ИИН / Паспорт", "city": "Город", "address": "Адрес", "secondary_phone": "Доп. телефон",
        "source": "Источник лида", "customer_status": "Статус клиента", "assigned_agent": "Ответственный оператор",
        "call_duration": "Длительность звонка (мин)", "call_type": "Тип звонка", "call_topic": "Тема / Причина звонка",
        "call_project": "Проект звонка", "needs_followup": "Требуется повторный звонок/задача",
        "followup_reason": "Причина контроля", "followup_due": "Срок выполнения (дата и время)", "followup_agent": "Ответственный оператор",
        "followup_notes": "Примечание к задаче", "call_notes": "Заметки и детали разговора",
        "save_call_btn": "Сохранить звонок", "no_active_followups": "Нет активных задач.",
        "today_overdue_followups": "Задачи на сегодня и просроченные",
        "due_deadline": "Срок", "priority": "Приоритет", "operator": "Оператор", "customer": "Клиент",
        "status": "Статус", "overdue_label": "Просрочено", "done_btn": "Выполнено", "cancel_btn": "Отменить",
        "chat_details": "Чат / Детали", "followup_conversation": "💬 Лента обсуждения задачи",
        "write_comment": "Введите сообщение...", "send_btn": "Отправить", "no_comments_yet": "Сообщений пока нет.",
        "delete_confirm": "Вы уверены, что хотите удалить этот элемент?",
        "new_customer_btn": "+ Новый клиент", "new_project_btn": "+ Новый проект", "new_user_btn": "+ Новый пользователь",
        "export_excel": "Экспорт в Excel/CSV", "daily_report": "Ежедневный отчёт", "by_project": "По проектам",
        "by_agent": "По операторам", "customer_list": "Список клиентов", "followup_list": "Список задач",
        "date_range_export": "Экспорт за период", "call_types_chart": "Типы звонков",
        "topics_chart": "Темы обращений", "daily_calls_chart": "Звонки за 30 дней", "agent_performance": "Эффективность операторов",
        "project_calls": "Звонки по проектам", "source_distribution": "Источники клиентов",
        "stage": "Стадия строительства", "progress": "Прогресс", "reg_status": "Статус регистрации",
        "expected_date": "Планируемый срок завершения", "description": "Описание", "public_update": "Отчёт о ходе работ",
        "internal_notes": "Внутренние заметки", "add_item": "Добавить пункт",
        "code_value": "Код ключа", "label_title": "Отображаемое название", "role": "Роль",
        "manager": "Руководитель", "agent": "Оператор", "all": "Все", "unique_customers": "Уникальных клиентов",
        "count": "Количество", "percentage": "Процент", "minute": "мин", "second": "сек",
        "unassigned": "Не назначен", "no_project": "Без проекта",
        "saved_success": "Данные успешно сохранены.", "watermark": "CRM-система колл-центра и управления взаимодействием с клиентами",
        "developer_credit": "Разработано: Амирхосейн Карами • Тел: 09106827218",
        "backup_db": "Резервная копия БД",
        "no_records_found": "Записей за указанный период не найдено.",
        "preset_today": "Сегодня",
        "preset_7days": "Последние 7 дней",
        "preset_30days": "Последние 30 дней",
        "preset_all": "За все время",
        "satisfaction_score": "Оценка удовлетворенности (CSAT)",
        "satisfaction_notes": "Заметки об оценке",
        "qa_score": "Оценка контроля качества (QA)",
        "qa_notes": "Заметки супервизора",
        "rating_5": "Отлично (5 звёзд)",
        "rating_4": "Хорошо (4 звезды)",
        "rating_3": "Удовлетворительно (3 звезды)",
        "rating_2": "Плохо (2 звезды)",
        "rating_1": "Очень плохо (1 звезда)",
        "sms_settings": "Настройки SMS",
        "sms_logs": "Журнал SMS",
        "csat_title": "Контроль качества и удовлетворенность (CSAT)",
        "avg_csat": "Средняя удовлетворенность",
        "avg_qa": "Средний балл QA",
        "incoming_call_alert": "Входящий звонок"
    }
}

LOOKUP_LABELS = {
    "phone_call": {"fa": "تماس تلفنی", "en": "Phone Call", "ar": "اتصال هاتفي", "ru": "Телефонный звонок"},
    "walk_in": {"fa": "حضوری", "en": "Walk-in", "ar": "زيارة شخصية", "ru": "Личный визит"},
    "facebook": {"fa": "فیسبوک", "en": "Facebook", "ar": "فيسبوك", "ru": "Facebook"},
    "instagram": {"fa": "اینستاگرام", "en": "Instagram", "ar": "إنستغرام", "ru": "Instagram"},
    "website": {"fa": "وب‌سایت", "en": "Website", "ar": "الموقع الإلكتروني", "ru": "Веб-сайт"},
    "referral": {"fa": "معرفی / توصیه", "en": "Referral", "ar": "توصية / إحالة", "ru": "Рекомендация"},
    "old_customer": {"fa": "مشتری سابق", "en": "Existing Customer", "ar": "عميل سابق", "ru": "Постоянный клиент"},
    "other": {"fa": "سایر موارد", "en": "Other", "ar": "أخرى", "ru": "Другое"},
    
    "planning": {"fa": "برنامه‌ریزی", "en": "Planning", "ar": "التخطيط", "ru": "Планирование"},
    "permits": {"fa": "اخذ مجوزها", "en": "Permits & Licenses", "ar": "التراخيص والتصاريح", "ru": "Разрешительная документация"},
    "foundation": {"fa": "فونداسیون", "en": "Foundation", "ar": "الأساسات", "ru": "Фундамент"},
    "structure": {"fa": "اسکلت و سازه", "en": "Structure / Framing", "ar": "الهيكل الإنشائي", "ru": "Несущие конструкции"},
    "brickwork": {"fa": "سفت‌کاری و دیوارچینی", "en": "Masonry / Brickwork", "ar": "البناء والجدران", "ru": "Кладка стен"},
    "electrical_plumbing": {"fa": "تاسیسات برق و لوله‌کشی", "en": "Electrical & Plumbing", "ar": "الكهرباء والسباكة", "ru": "Инженерные сети"},
    "finishing": {"fa": "نازک‌کاری و نما", "en": "Interior & Finishing", "ar": "التشطيبات النهائية", "ru": "Отделочные работы"},
    "final_inspection": {"fa": "بازرسی و کنترل نهایی", "en": "Final Inspection", "ar": "المعاينة النهائية", "ru": "Приёмка объекта"},
    "ready": {"fa": "آماده تحویل", "en": "Ready for Handover", "ar": "جاهز للتسليم", "ru": "Готов к сдаче"},
    "delivered": {"fa": "تحویل داده شده", "en": "Delivered", "ar": "تم التسليم", "ru": "Сдан в эксплуатацию"},
    "paused": {"fa": "متوقف شده", "en": "Paused / On Hold", "ar": "متوقف مؤقتاً", "ru": "Приостановлен"},
    
    "open": {"fa": "ثبت‌نام باز", "en": "Open for Booking", "ar": "التسجيل مفتوح", "ru": "Открыта регистрация"},
    "closed": {"fa": "بسته شده", "en": "Closed", "ar": "مغلق", "ru": "Закрыто"},
    "coming_soon": {"fa": "به‌زودی", "en": "Coming Soon", "ar": "قريباً", "ru": "Скоро открытие"},
    "sold_out": {"fa": "تکمیل ظرفیت / واگذار شده", "en": "Sold Out", "ar": "مكتمل العدد", "ru": "Все продано"},
    
    "incoming": {"fa": "تماس ورودی", "en": "Incoming", "ar": "واردة", "ru": "Входящий"},
    "outgoing": {"fa": "تماس خروجی", "en": "Outgoing", "ar": "صادرة", "ru": "Исходящий"},
    "missed": {"fa": "از دست رفته", "en": "Missed Call", "ar": "فائتة", "ru": "Пропущенный"},
    "follow_up": {"fa": "پیگیری", "en": "Follow-up", "ar": "متابعة", "ru": "Повторный"},
    
    "low": {"fa": "کم", "en": "Low", "ar": "منخفضة", "ru": "Низкий"},
    "normal": {"fa": "عادی", "en": "Normal", "ar": "عادية", "ru": "Обычный"},
    "high": {"fa": "بالا", "en": "High", "ar": "عالية", "ru": "Высокий"},
    "urgent": {"fa": "فوری / بحرانی", "en": "Urgent", "ar": "عاجلة جداً", "ru": "Срочный"},
    
    "pending": {"fa": "در انتظار", "en": "Pending", "ar": "قيد الانتظار", "ru": "В ожидании"},
    "done": {"fa": "انجام شده", "en": "Done", "ar": "منجز", "ru": "Выполнено"},
    "cancelled": {"fa": "لغو شده", "en": "Cancelled", "ar": "ملغي", "ru": "Отменено"},
    
    "registration_question": {"fa": "سوال درباره شرایط ثبت‌نام", "en": "Registration Inquiry", "ar": "استفسار عن التسجيل", "ru": "Вопрос о регистрации"},
    "project_progress": {"fa": "پیگیری روند پیشرفت پروژه", "en": "Project Progress Inquiry", "ar": "استفسار عن سير المشروع", "ru": "Ход строительства"},
    "payment_question": {"fa": "مسائل مالی و نحوه پرداخت", "en": "Payment & Installments", "ar": "الدفعات والأقساط", "ru": "Оплата и рассрочка"},
    "documents_question": {"fa": "استعلام مدارک و قراردادها", "en": "Contract & Documents", "ar": "المستندات والعقود", "ru": "Документы и договор"},
    "site_visit": {"fa": "درخواست هماهنگی بازدید حضوری", "en": "Site Visit Request", "ar": "طلب موعد زيارة ميدانية", "ru": "Запись на осмотр объекта"},
    "delay_complaint": {"fa": "شکایت از تاخیر در تحویل", "en": "Delay Complaint", "ar": "شكوى من التأخير", "ru": "Жалоба на задержку"},
    "quality_complaint": {"fa": "انتقاد یا شکایت کیفی", "en": "Quality Complaint", "ar": "شكوى بخصوص الجودة", "ru": "Претензия по качеству"},
    "wrong_number": {"fa": "شماره اشتباه", "en": "Wrong Number", "ar": "رقم خاطئ", "ru": "Неверный номер"},
    
    "payment_follow_up": {"fa": "پیگیری وصول قسط / واریز", "en": "Payment Follow-up", "ar": "متابعة الدفعات", "ru": "Контроль платежа"},
    "document_follow_up": {"fa": "پیگیری تحویل مدارک", "en": "Document Follow-up", "ar": "متابعة المستندات", "ru": "Контроль документов"},
    "call_back": {"fa": "تماس مجدد طبق هماهنگی", "en": "Scheduled Call Back", "ar": "إعادة الاتصال المجدول", "ru": "Обратный звонок"},
    "contract_follow_up": {"fa": "پیگیری امضای قرارداد", "en": "Contract Follow-up", "ar": "متابعة توقيع العقد", "ru": "Подписание договора"},
    "progress_update": {"fa": "ارائه گزارش پیشرفت جدید", "en": "Progress Update Follow-up", "ar": "إبلاغ بتحديث المشروع", "ru": "Информирование о статусе"},
    "general_follow_up": {"fa": "پیگیری عمومی", "en": "General Follow-up", "ar": "متابعة عامة", "ru": "Общий контроль"},
    
    "new_lead": {"fa": "سرنخ جدید", "en": "New Lead", "ar": "عميل محتمل جديد", "ru": "Новый лид"},
    "contacted": {"fa": "ارتباط اولیه برقرار شد", "en": "Contacted", "ar": "تم التواصل", "ru": "Контакт установлен"},
    "interested": {"fa": "علاقه‌مند به خرید/مشارکت", "en": "Interested", "ar": "مهتم", "ru": "Заинтересован"},
    "needs_follow_up": {"fa": "نیازمند تماس بعدی", "en": "Needs Follow-up", "ar": "بحاجة لمتابعة", "ru": "Требует доработки"},
    "site_visit_scheduled": {"fa": "بازدید هماهنگ شده", "en": "Site Visit Scheduled", "ar": "موعد زيارة مجدول", "ru": "Визит назначен"},
    "documents_requested": {"fa": "مدارک ارسال شد/درخواست شد", "en": "Documents Requested", "ar": "طلب المستندات", "ru": "Запрошены документы"},
    "documents_received": {"fa": "مدارک دریافت و بررسی شد", "en": "Documents Received", "ar": "استلام المستندات", "ru": "Документы получены"},
    "registered_signed": {"fa": "عقد قرارداد / ثبت‌نام قطعی", "en": "Registered / Signed", "ar": "تم التعاقد / التسجيل", "ru": "Договор подписан"},
    "payment_pending": {"fa": "در انتظار واریز پیش‌پرداخت", "en": "Payment Pending", "ar": "بانتظار السداد", "ru": "Ожидает оплаты"},
    "active_customer": {"fa": "مشتری فعال و خریدار", "en": "Active Customer", "ar": "عميل نشط", "ru": "Действующий клиент"},
    "project_progress_inquiry": {"fa": "پیگیر روند پروژه", "en": "Progress Inquiry", "ar": "مستفسر عن المشروع", "ru": "Интересуется ходом работ"},
    "complaint_issue": {"fa": "دارای شکایت یا مشکل", "en": "Has Issue / Complaint", "ar": "لديه شكوى", "ru": "Есть претензия"},
    "not_interested": {"fa": "عدم تمایل / انصراف", "en": "Not Interested", "ar": "غير مهتم / انسحب", "ru": "Отказ"},
    "closed": {"fa": "پرونده مختومه", "en": "Closed", "ar": "مغلق", "ru": "Закрыт"},
    
    "manager": {"fa": "مدیر سیستم", "en": "Manager", "ar": "مدير النظام", "ru": "Руководитель"},
    "agent": {"fa": "اپراتور", "en": "Agent", "ar": "مشغل", "ru": "Оператор"}
}

LOOKUP_DEFS = {
    "sources": ("sources", SOURCES),
    "problem_types": ("call_topic", PROBLEM_TYPES),
    "project_stages": ("stage", PROJECT_STAGES),
    "registration_statuses": ("reg_status", REG_STATUSES),
    "follow_up_reasons": ("followup_reason", FOLLOW_UP_REASONS),
}

def t(key, lang="fa", fallback=None):
    dic = I18N.get(lang, I18N["fa"])
    if key in dic:
        return dic[key]
    if key in I18N["en"]:
        return I18N["en"][key]
    return fallback if fallback is not None else key

def label_text(value, lang="fa"):
    value_str = "" if value is None else str(value)
    if value_str in LOOKUP_LABELS:
        return LOOKUP_LABELS[value_str].get(lang, LOOKUP_LABELS[value_str].get("en", value_str))
    return t(value_str, lang, value_str.replace("_", " ").title())

def esc(value):
    return html.escape("" if value is None else str(value), quote=True)

def label(value, lang="fa"):
    return esc(label_text(value, lang))

def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

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

def to_jalali_display(value):
    text = str(value or "")
    try:
        part = text[:10]
        gy, gm, gd = [int(x) for x in part.split("-")]
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        time_part = text[10:16] if len(text) > 10 else ""
        return f"{jy:04d}/{jm:02d}/{jd:02d}" + time_part
    except Exception:
        return text

def normalize_digits(s):
    if not s:
        return ""
    s = str(s)
    for fa_d, en_d in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789"):
        s = s.replace(fa_d, en_d)
    for ar_d, en_d in zip("٠١٢٣٤٥٦٧٨٩", "0123456789"):
        s = s.replace(ar_d, en_d)
    return s.strip()

def parse_date_input(value, with_time=False):
    if not value:
        return None
    raw = normalize_digits(value).replace(".", "/").replace("-", "/")
    if not raw:
        return None
    try:
        date_part, _, time_part = raw.partition(" ")
        if "T" in date_part:
            date_part, time_part = date_part.split("T", 1)
        parts = [int(x) for x in date_part.split("/") if x]
        if len(parts) != 3:
            return raw.replace("T", " ")
        if parts[0] > 1700:
            out = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
        else:
            gy, gm, gd = jalali_to_gregorian(parts[0], parts[1], parts[2])
            out = f"{gy:04d}-{gm:02d}-{gd:02d}"
        if with_time:
            time_clean = (time_part[:5] if time_part else "00:00")
            out += " " + time_clean
        return out
    except Exception:
        return raw.replace("T", " ")

def format_date_display(value, lang="fa", with_time=False):
    if not value:
        return "—"
    text = str(value)
    if lang == "fa":
        val = to_jalali_display(text)
        return val[:16] if with_time else val[:10]
    else:
        clean = text.replace("T", " ")
        return clean[:16] if with_time else clean[:10]

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
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

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
    national_code TEXT,
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
CREATE INDEX IF NOT EXISTS idx_customers_national ON customers(national_code);
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
    call_type TEXT NOT NULL DEFAULT 'incoming',
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

CREATE TABLE IF NOT EXISTS follow_up_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    follow_up_id INTEGER NOT NULL REFERENCES follow_ups(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    comment TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_follow_up_comments_follow ON follow_up_comments(follow_up_id);

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

CREATE TABLE IF NOT EXISTS lookup_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lookup_type TEXT NOT NULL,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(lookup_type, value)
);
"""

def init_db():
    conn = db()
    conn.executescript(SCHEMA)
    users_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if users_count == 0:
        seed_clean_database(conn)
    conn.close()

def seed_clean_database(conn):
    admin_pw = hash_password("admin123")
    agent_pw = hash_password("password123")
    
    conn.execute(
        "INSERT INTO users(name,email,password,phone,role,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
        ("System Administrator", "admin@crm.local", admin_pw, "+989100000001", "manager", now_iso(), now_iso())
    )
    conn.execute(
        "INSERT INTO users(name,email,password,phone,role,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
        ("Operator 1", "agent@crm.local", agent_pw, "+989100000002", "agent", now_iso(), now_iso())
    )
    
    for lk_type, (_, values) in LOOKUP_DEFS.items():
        for val in values:
            lbl = label_text(val, "fa")
            conn.execute(
                "INSERT OR IGNORE INTO lookup_items(lookup_type, value, label, is_active, created_at, updated_at) VALUES(?,?,?,1,?,?)",
                (lk_type, val, lbl, now_iso(), now_iso())
            )
    conn.commit()

def options(values, selected=None, blank=None, lang="fa"):
    out = []
    if blank is not None:
        out.append(f'<option value="">{esc(blank)}</option>')
    for v in values:
        sel = " selected" if str(v) == str(selected or "") else ""
        out.append(f'<option value="{esc(v)}"{sel}>{label(v, lang)}</option>')
    return "".join(out)

def lookup_options(conn, lookup_type, selected=None, blank=None, lang="fa"):
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    try:
        rows = conn.execute("SELECT value, label FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id", (lookup_type,)).fetchall()
    except Exception:
        rows = []
    if not rows and lookup_type in LOOKUP_DEFS:
        return options(LOOKUP_DEFS[lookup_type][1], selected, blank, lang)
    for r in rows:
        sel = " selected" if str(r["value"]) == str(selected or "") else ""
        lbl = label_text(r["value"], lang)
        out.append(f'<option value="{esc(r["value"])}"{sel}>{esc(lbl)}</option>')
    return "".join(out)

def user_options(conn, selected=None, blank="—", lang="fa"):
    rows = conn.execute("SELECT id, name, role FROM users WHERE is_active=1 ORDER BY role DESC, name").fetchall()
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for r in rows:
        sel = " selected" if str(r["id"]) == str(selected or "") else ""
        role_title = label(r["role"], lang)
        out.append(f'<option value="{r["id"]}"{sel}>{esc(r["name"])} ({role_title})</option>')
    return "".join(out)

def project_options(conn, selected=None, blank="—"):
    rows = conn.execute("SELECT id, name FROM projects WHERE is_active=1 ORDER BY name").fetchall()
    out = [f'<option value="">{esc(blank)}</option>'] if blank is not None else []
    for r in rows:
        sel = " selected" if str(r["id"]) == str(selected or "") else ""
        out.append(f'<option value="{r["id"]}"{sel}>{esc(r["name"])}</option>')
    return "".join(out)

class App(BaseHTTPRequestHandler):
    server_version = "CallCenterCRM/2.0"

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
        self.lang = self.detect_language()
        self.current_user = self.get_current_user()

        if "lang" in self.query and self.query["lang"][0] in SUPPORTED_LANGS:
            new_lang = self.query["lang"][0]
            query_clean = {k: v for k, v in self.query.items() if k != "lang"}
            redirect_to = path + ("?" + urllib.parse.urlencode(query_clean, doseq=True) if query_clean else "")
            self.send_response(303)
            self.send_header("Location", redirect_to)
            self.send_header("Set-Cookie", f"{LANG_COOKIE}={new_lang}; Path=/; Max-Age=31536000; SameSite=Lax")
            self.end_headers()
            self.conn.close()
            return

        try:
            if path == "/static/app.css":
                return self.css()
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

            # API routes
            if path == "/api/customers/search":
                return self.api_customer_search()
            if path == "/api/customers/by-national-code":
                return self.api_customer_by_national_code()
            if path == "/api/customers/by-phone":
                return self.api_customer_by_phone()
            if path == "/api/customers/follow-up-history":
                return self.api_customer_followup_history()
            if path == "/api/live-call":
                return self.api_live_call()
            if path == "/api/voip-webhook":
                return self.api_voip_webhook(method)
            if path == "/settings/sms":
                return self.settings_sms(method)

            # Backup
            if path == "/backup":
                return self.backup_db()

            # Exports
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
                err_text = html.escape(traceback.format_exc())
                self.send_html(f"<h1>Server Error</h1><pre style='background:#fee2e2;padding:16px;border-radius:8px'>{err_text}</pre>", status=500)
            except Exception:
                pass
        finally:
            self.conn.close()

    def detect_language(self):
        if "lang" in self.query and self.query["lang"][0] in SUPPORTED_LANGS:
            return self.query["lang"][0]
        cookies = self.headers.get("Cookie", "")
        for chunk in cookies.split(";"):
            if "=" in chunk:
                k, v = chunk.strip().split("=", 1)
                if k == LANG_COOKIE and v in SUPPORTED_LANGS:
                    return v
        return DEFAULT_LANG

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
        data = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        return urllib.parse.parse_qs(data, keep_blank_values=True)

    def form(self):
        if not hasattr(self, "_form_data"):
            self._form_data = self.form_all()
        return {k: v[-1] for k, v in self._form_data.items()}

    def form_list(self):
        if not hasattr(self, "_form_data"):
            self._form_data = self.form_all()
        return self._form_data

    def count_unviewed_followups(self):
        if not self.current_user:
            return 0
        row = self.conn.execute(
            "SELECT COUNT(*) c FROM follow_ups WHERE assigned_agent_id=? AND status='pending' AND viewed_at IS NULL",
            (self.current_user["id"],)
        ).fetchone()
        return row["c"] if row else 0

    def render_language_switcher(self):
        cur = self.lang
        flags = [
            ("fa", "🇮🇷", "فا"),
            ("en", "🇬🇧", "EN"),
            ("ar", "🇸🇦", "ع"),
            ("ru", "🇷🇺", "RU")
        ]
        items = []
        for code, flag, label_short in flags:
            active_cls = " active" if code == cur else ""
            items.append(f'<a href="?lang={code}" class="lang-btn{active_cls}" title="{I18N[code]["lang_name"]}">{flag} {label_short}</a>')
        return f'<div class="lang-switcher">{"".join(items)}</div>'

    def send_html(self, body, title="CRM", status=200):
        lang = self.lang
        lang_dir = t("dir", lang, "rtl")
        user = self.current_user
        lang_switcher = self.render_language_switcher()
        
        nav = ""
        if user:
            unviewed_count = self.count_unviewed_followups()
            badge_html = f'<span class="nav-badge">{unviewed_count}</span>' if unviewed_count > 0 else ""
            is_manager = user["role"] == "manager"
            
            if is_manager:
                manager_links = f'''
                <div class="nav-drop">
                    <a href="/base-tables" class="nav-link">{t("base_tables", lang)} ▾</a>
                    <div class="nav-menu">
                        <a href="/base-tables">{t("base_tables", lang)}</a>
                        <a href="/users">{t("users", lang)}</a>
                        <a href="/settings/sms">📱 {t("sms_settings", lang)}</a>
                    </div>
                </div>
                <a href="/reports" class="nav-link">{t("reports", lang)}</a>
                <a href="/users" class="nav-link">{t("users", lang)}</a>
                '''
                hamb_manager_links = f'<a href="/reports">{t("reports", lang)}</a><a href="/users">{t("users", lang)}</a><a href="/base-tables">{t("base_tables", lang)}</a>'
            else:
                manager_links = f'<a href="/reports" class="nav-link">{t("my_report", lang)}</a>'
                hamb_manager_links = f'<a href="/reports">{t("my_report", lang)}</a>'

            nav = f'''
            <nav>
                <a href="/dashboard" class="brand">
                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                    <span>CRM</span>
                </a>
                
                <div class="hamb">☰
                    <div class="hamb-menu">
                        <a href="/dashboard">{t("dashboard", lang)}</a>
                        <a href="/customers">{t("customers", lang)}</a>
                        <a href="/projects">{t("projects", lang)}</a>
                        <a href="/follow-ups">{t("follow_ups", lang)} {badge_html}</a>
                        {hamb_manager_links}
                        <hr style="margin:6px 0;border:none;border-top:1px solid var(--line)">
                        <div style="padding:6px">{lang_switcher}</div>
                        <a href="/logout" style="color:var(--danger)">{t("logout", lang)}</a>
                    </div>
                </div>

                <a href="/dashboard" class="nav-link">{t("dashboard", lang)}</a>
                <a href="/customers" class="nav-link">{t("customers", lang)}</a>
                <a href="/projects" class="nav-link">{t("projects", lang)}</a>
                <a href="/follow-ups" class="nav-link">{t("follow_ups", lang)} {badge_html}</a>
                {manager_links}

                <div class="nav-spacer"></div>

                {lang_switcher}

                <div class="nav-user">
                    <span class="user-pill">{esc(user["name"])} <span class="pill" style="font-size:0.7rem">{label(user["role"], lang)}</span></span>
                    <a href="/logout" class="button small secondary" title="{t('logout', lang)}">{t("logout", lang)}</a>
                </div>
            </nav>
            '''

        if lang == "fa":
            picker_script = '''
            document.addEventListener('DOMContentLoaded', function(){
              try {
                document.querySelectorAll('.jalali-date').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {locale:'fa', dateFormat:'Y/m/d'}); });
                document.querySelectorAll('.jalali-datetime').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {locale:'fa', enableTime:true, dateFormat:'Y/m/d H:i', time_24hr:true}); });
                document.querySelectorAll('input[type="time"]').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {noCalendar:true, enableTime:true, dateFormat:'H:i', time_24hr:true}); });
              } catch(e){ console.error('Picker error:', e); }
            });
            '''
            flatpickr_fa_tag = f'<script>{_FLATPICKR_FA}</script>'
        else:
            picker_script = '''
            document.addEventListener('DOMContentLoaded', function(){
              try {
                document.querySelectorAll('.jalali-date').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {dateFormat:'Y-m-d'}); });
                document.querySelectorAll('.jalali-datetime').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {enableTime:true, dateFormat:'Y-m-d H:i', time_24hr:true}); });
                document.querySelectorAll('input[type="time"]').forEach(function(el){ if(el._flatpickr)return; el.readOnly=true; flatpickr(el, {noCalendar:true, enableTime:true, dateFormat:'H:i', time_24hr:true}); });
              } catch(e){ console.error('Picker error:', e); }
            });
            '''
            flatpickr_fa_tag = ""

        helper_scripts = '''
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
          var query = q ? q.value.trim().toLowerCase() : '';
          var dateFrom = document.getElementById('fu-date-from');
          var dateTo = document.getElementById('fu-date-to');
          var fromVal = dateFrom ? dateFrom.value.trim() : '';
          var toVal = dateTo ? dateTo.value.trim() : '';
          var cards = document.querySelectorAll('.fu-card');
          for (var i = 0; i < cards.length; i++) {
            var text = cards[i].textContent.toLowerCase();
            var show = query === '' || text.indexOf(query) > -1;
            if (show && (fromVal || toVal)) {
              var dateMatch = text.match(/(\\d{4}[\\/\\-]\\d{2}[\\/\\-]\\d{2})/);
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

        full_title = f"{title} - {t('app_title', lang)}"
        watermark_text = t("watermark", lang)
        
        html_doc = f"""<!doctype html>
<html lang="{lang}" dir="{lang_dir}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <link rel="stylesheet" href="/static/app.css">
  <style>{_FLATPICKR_CSS}</style>
</head>
<body>
  {nav}
  <main>{body}</main>
  <footer>
    <div style="max-width:1200px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;padding:6px 0">
      <div style="display:flex;align-items:center;gap:8px;font-size:0.86rem;color:var(--text)">
        <span style="font-size:1.15rem">👨‍💻</span>
        <span style="font-weight:500">{esc(t('developer_credit', lang))}</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px;font-size:0.82rem;color:var(--muted)">
        <a href="tel:09106827218" style="color:var(--primary);text-decoration:none;font-weight:600;display:inline-flex;align-items:center;gap:4px">📞 09106827218</a>
        <span style="opacity:0.3">•</span>
        <a href="/backup" class="button small secondary" style="padding:2px 8px;font-size:0.75rem" title="{t('backup_db', lang)}">💾 {t('backup_db', lang)}</a>
        <span class="pill" style="opacity:0.85">CallCenterCRM v2.0 • Pro</span>
      </div>
    </div>
  </footer>
  <script>{_FLATPICKR_JS}</script>
  {flatpickr_fa_tag}
  <script>{picker_script}</script>
  <script>{helper_scripts}</script>
</body>
</html>"""
        data = html_doc.encode("utf-8")
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
        self.send_html(f"<h1>404 - Not Found</h1><p>{t('invalid_login', self.lang, 'The requested page was not found.')}</p>", status=404)

    def css(self):
        p = os.path.join(BASE_DIR, "app.css")
        if not os.path.exists(p):
            p = os.path.join(os.path.dirname(BASE_DIR), "app.css")
        if not os.path.exists(p):
            return self.not_found()
        with open(p, "r", encoding="utf-8") as f:
            data = f.read().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def require_manager(self):
        if self.current_user["role"] != "manager":
            self.send_html(f"<h1>403 - Forbidden</h1><p>{t('manager', self.lang)} access required.</p>", status=403)
            return False
        return True


    def login(self, method):
        lang = self.lang
        error = ""
        if method == "POST":
            data = self.form()
            email = data.get("email", "").strip()
            password = data.get("password", "")
            user = self.conn.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
            if user and check_password(password, user["password"]):
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = user["id"]
                self.conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now_iso(), user["id"]))
                self.conn.commit()
                self.send_response(303)
                self.send_header("Location", "/dashboard")
                self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax")
                self.end_headers()
                return
            error = f'<div class="alert">{t("invalid_login", lang)}</div>'
        
        lang_switcher = self.render_language_switcher()
        body = f"""
        <div style="display:flex;justify-content:center;margin-bottom:12px">{lang_switcher}</div>
        <section class="login">
            <h1>{t("login_heading", lang)}</h1>
            {error}
            <form method="post">
                <label>{t("email", lang)}<input name="email" value="admin@crm.local" required></label>
                <label>{t("password", lang)}<input type="password" name="password" value="admin123" required></label>
                <button type="submit">{t("login_btn", lang)}</button>
            </form>
            <p class="muted" style="margin-top:16px;font-size:0.8rem">{t("demo_accounts", lang)}</p>
        </section>
        """
        self.send_html(body, t("login_title", lang))

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
        lang = self.lang
        uid = self.current_user["id"]
        is_manager = self.current_user["role"] == "manager"
        
        if self.command == "POST":
            d = self.form()
            data_all = self.form_list()
            customer_id = d.get("customer_id", "").strip()
            call_project_id = d.get("project_id", "").strip() or None

            if not customer_id:
                new_name = d.get("new_customer_name", "").strip()
                new_phone = d.get("new_customer_phone", "").strip()
                if new_name and new_phone:
                    national_code = d.get("search_customer", "").strip() or d.get("nc_lookup", "").strip()
                    new_city = d.get("new_customer_city", "").strip()
                    new_project_ids = [pid.strip() for pid in data_all.get("new_customer_project_ids", []) if pid.strip()]
                    self.conn.execute(
                        """INSERT INTO customers(full_name, national_code, primary_phone, city, source, status, assigned_agent_id, created_by, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (new_name, national_code or None, new_phone, new_city or None, "phone_call", "new_lead", uid, uid, now_iso(), now_iso())
                    )
                    customer_id = str(self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"])
                    for new_pid in new_project_ids:
                        self.conn.execute("INSERT OR IGNORE INTO customer_projects(customer_id, project_id, created_at) VALUES(?,?,?)", (customer_id, new_pid, now_iso()))
                    if new_project_ids and not call_project_id:
                        call_project_id = new_project_ids[0]
                else:
                    return self.send_html(f"<div class='alert'>{t('search_hint', lang)}</div>", status=422)

            existing_proj_ids = [pid.strip() for pid in data_all.get("existing_customer_project_ids", []) if pid.strip()]
            for ep_id in existing_proj_ids:
                self.conn.execute("INSERT OR IGNORE INTO customer_projects(customer_id, project_id, created_at) VALUES(?,?,?)", (customer_id, ep_id, now_iso()))

            call_date = parse_date_input(d.get("call_date")) or date.today().isoformat()
            call_time = (d.get("call_time") or datetime.now().strftime("%H:%M")).strip()
            call_started_at = f"{call_date[:10]} {call_time[:5]}"
            dur = d.get("call_duration", "").strip()
            dur_seconds = int(float(dur) * 60) if dur else None
            follow_up = 1 if d.get("follow_up_required") else 0
            sat_score = int(d.get("satisfaction_score")) if d.get("satisfaction_score") else None
            sat_notes = d.get("satisfaction_notes", "").strip() or None
            
            self.conn.execute(
                """INSERT INTO call_logs(customer_id, agent_id, call_type, problem_type, project_id, call_started_at, call_duration_seconds, notes, follow_up_required, satisfaction_score, satisfaction_notes, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (customer_id, uid, d.get("call_type", "incoming"), d.get("problem_type") or None, call_project_id, call_started_at, dur_seconds, d.get("notes", "").strip() or None, follow_up, sat_score, sat_notes, now_iso(), now_iso())
            )
            new_call_id = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
            
            # Send thank you SMS automatically
            cust_row = self.conn.execute("SELECT full_name, primary_phone FROM customers WHERE id=?", (customer_id,)).fetchone()
            if cust_row and cust_row["primary_phone"]:
                sms_service.send_call_thank_you_sms(self.conn, customer_id, cust_row["full_name"], cust_row["primary_phone"], new_call_id)

            if follow_up and d.get("follow_up_datetime"):
                fu_due = parse_date_input(d.get("follow_up_datetime"), True) or now_iso()
                fu_agent = d.get("follow_up_agent") or uid
                fu_reason = d.get("follow_up_reason", "").strip() or "general_follow_up"
                fu_notes = d.get("follow_up_notes", "").strip() or ""
                self.conn.execute(
                    """INSERT INTO follow_ups(customer_id, assigned_agent_id, created_by, due_at, status, priority, reason, notes, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (customer_id, fu_agent, uid, fu_due, "pending", d.get("priority") or "normal", fu_reason, fu_notes, now_iso(), now_iso())
                )
                if cust_row and cust_row["primary_phone"]:
                    sms_service.send_followup_reminder_sms(self.conn, customer_id, cust_row["full_name"], cust_row["primary_phone"], fu_reason, format_date_display(fu_due, lang, with_time=True))
                if fu_notes:
                    new_fu_id = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
                    self.conn.execute(
                        "INSERT INTO follow_up_comments(follow_up_id, user_id, comment, created_at) VALUES(?,?,?,?)",
                        (new_fu_id, uid, fu_notes, now_iso())
                    )

            self.conn.execute("UPDATE customers SET last_contacted_at=?, updated_at=? WHERE id=?", (now_iso(), now_iso(), customer_id))
            self.conn.commit()
            return self.redirect("/dashboard?saved=1")

        agent_params = () if is_manager else (uid,)
        total_customers = self.conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        calls_today = self.conn.execute("SELECT COUNT(*) c FROM call_logs WHERE date(created_at)=date('now')" + ("" if is_manager else " AND agent_id=?"), agent_params).fetchone()["c"]
        follow_today = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending' AND date(due_at)=date('now')" + ("" if is_manager else " AND assigned_agent_id=?"), agent_params).fetchone()["c"]
        overdue = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending' AND datetime(due_at)<datetime('now')" + ("" if is_manager else " AND assigned_agent_id=?"), agent_params).fetchone()["c"]
        signed = self.conn.execute("SELECT COUNT(*) c FROM customers WHERE status='registered_signed'").fetchone()["c"]
        csat_dash_row = self.conn.execute("SELECT ROUND(AVG(satisfaction_score), 1) avg_s FROM call_logs").fetchone()
        avg_csat_dash = ("⭐ " + str(csat_dash_row["avg_s"])) if (csat_dash_row and csat_dash_row["avg_s"]) else "—"

        fu_agent_where = "" if is_manager else " AND f.assigned_agent_id=?"
        rows = self.conn.execute(
            f"""SELECT f.*, c.full_name, c.primary_phone, u.name agent
               FROM follow_ups f
               JOIN customers c ON c.id=f.customer_id
               LEFT JOIN users u ON u.id=f.assigned_agent_id
               WHERE f.status='pending' AND (date(f.due_at)=date('now') OR datetime(f.due_at)<datetime('now')) {fu_agent_where}
               ORDER BY f.due_at LIMIT 10""",
            agent_params
        ).fetchall()

        table_rows = []
        if not rows:
            table_html = f'<p class="muted">{t("no_active_followups", lang)}</p>'
        else:
            table_rows.append(f'<table><thead><tr><th>{t("customer", lang)}</th><th>{t("followup_reason", lang)}</th><th>{t("operator", lang)}</th><th>{t("due_deadline", lang)}</th><th>{t("priority", lang)}</th><th>{t("actions", lang)}</th></tr></thead><tbody>')
            for r in rows:
                due = format_date_display(r["due_at"], lang, with_time=True)
                pri = label(r["priority"], lang)
                table_rows.append(f'<tr><td><strong>{esc(r["full_name"])}</strong></td><td>{esc(r["reason"] or "—")}</td><td>{esc(r["agent"] or "—")}</td><td>{due}</td><td><span class="pill prio-{esc(r["priority"])}">{pri}</span></td><td class="actions"><a href="/follow-ups/{r["id"]}" class="button small secondary">{t("view", lang)}</a></td></tr>')
            table_rows.append('</tbody></table>')
            table_html = "".join(table_rows)

        today_formatted = format_date_display(date.today().isoformat(), lang)
        tomorrow_formatted = format_date_display((date.today() + timedelta(days=1)).isoformat(), lang)
        current_time = datetime.now().strftime("%H:%M")

        problem_opts = lookup_options(self.conn, "problem_types", lang=lang)
        fu_opts = lookup_options(self.conn, "follow_up_reasons", lang=lang)
        call_opts = options(CALL_TYPES, "incoming", lang=lang)
        user_opts = user_options(self.conn, blank=t("unassigned", lang), lang=lang)
        project_opts = project_options(self.conn, blank=t("no_project", lang))

        saved_alert = f'<div class="alert alert-success">{t("saved_success", lang)}</div>' if "saved" in self.query else ""

        dash_js = """
        <script>
        var searchInput = document.getElementById('cust-search-input');
        var customerInfo = document.getElementById('customer-info');
        var foundCustomer = document.getElementById('found-customer');
        var foundProjectRow = document.getElementById('found-project-row');
        var newCustomer = document.getElementById('new-customer');
        var saveBtn = document.getElementById('save-call-btn');
        var searchTimer;

        if (searchInput) {
          searchInput.addEventListener('input', function(){
            clearTimeout(searchTimer);
            var query = this.value.trim();
            if (!query) {
              customerInfo.hidden = true;
              foundCustomer.hidden = true;
              foundProjectRow.hidden = true;
              newCustomer.hidden = true;
              document.getElementById('call-logs-sidebar').hidden = true;
              saveBtn.disabled = true;
              return;
            }
            searchTimer = setTimeout(async function(){
              try {
                var res = await fetch('/api/customers/search?q=' + encodeURIComponent(query));
                var data = await res.json();
                if (data.id) {
                  document.getElementById('customer-id').value = data.id;
                  document.querySelector('[name="customer_name_display"]').value = data.full_name;
                  document.querySelector('[name="customer_phone_display"]').value = data.primary_phone;
                  
                  var sel = document.getElementById('project-select');
                  var html = '<option value="">__NO_PROJECT__</option>';
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
                      logsHtml += '<a href="/call-logs/' + c.id + '" class="call-log-item"><span class="call-log-time">' + (c.call_started_at_display || '—') + '</span><span class="call-log-topic">' + (c.problem_type_label || '—') + '</span></a>';
                    }
                    logsDiv.innerHTML = logsHtml;
                    document.getElementById('call-logs-sidebar').hidden = false;
                  }
                  fetchFollowUpHistory(data.id);
                  populateCustomerProjects(data);

                  foundCustomer.hidden = false;
                  foundProjectRow.hidden = false;
                  newCustomer.hidden = true;
                  customerInfo.hidden = false;
                  saveBtn.disabled = false;
                } else {
                  document.getElementById('customer-id').value = '';
                  var isDigits = /^\\+?\\d+$/.test(query);
                  document.querySelector('[name="new_customer_name"]').value = isDigits ? '' : query;
                  document.querySelector('[name="new_customer_phone"]').value = isDigits ? query : '';
                  document.getElementById('call-logs-sidebar').hidden = true;
                  foundCustomer.hidden = true;
                  foundProjectRow.hidden = true;
                  newCustomer.hidden = false;
                  customerInfo.hidden = false;
                  saveBtn.disabled = false;
                }
              } catch(e) {
                console.error(e);
              }
            }, 350);
          });
        }

        function populateCustomerProjects(data) {
          var projDiv = document.getElementById('customer-projects-sidebar-list');
          projDiv.innerHTML = '';
          if (data.projects && data.projects.length > 0) {
            var projHtml = '';
            for (var i = 0; i < data.projects.length; i++) {
              var p = data.projects[i];
              projHtml += '<a href="/projects/' + p.id + '" class="call-log-item">';
              projHtml += '<span class="call-log-topic" style="font-weight:600">' + p.name + '</span>';
              projHtml += '<small class="muted" style="width:100%">' + p.progress_percentage + '% | ' + p.registration_status + '</small>';
              projHtml += '</a>';
            }
            projDiv.innerHTML = projHtml;
          } else {
            projDiv.innerHTML = '<small class="muted" style="padding:6px 8px;display:block">—</small>';
          }
        }

        function addNewCustomerProject() {
          var wrap = document.createElement('div');
          wrap.className = 'project-pick';
          wrap.innerHTML = '<select name="new_customer_project_ids">__PROJECT_OPTS__</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button>';
          document.getElementById('new-customer-projects').appendChild(wrap);
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
            wrap.innerHTML = '<select name="existing_customer_project_ids">__PROJECT_OPTS__</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button>';
          }
          document.getElementById('found-customer-projects').appendChild(wrap);
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
                fuHtml += '<a href="/follow-ups/' + fu.id + '" class="call-log-item">';
                fuHtml += '<span class="call-log-time">' + (fu.due_at_display || '—') + '</span>';
                fuHtml += '<span class="pill ' + statusClass + '">' + (fu.status_label || '—') + '</span>';
                fuHtml += '<span class="call-log-topic">' + (fu.reason || '—') + '</span>';
                fuHtml += '</a>';
              }
              fuDiv.innerHTML = fuHtml;
              sidebar.hidden = false;
            }
          } catch(e) {
            console.error('Follow-up error:', e);
          }
        }

        function toggleFollowUpFields() {
          var fields = document.getElementById('follow-up-fields');
          var notesField = document.getElementById('follow-up-notes-field');
          var cb = document.querySelector('[name="follow_up_required"]');
          fields.style.display = cb.checked ? 'flex' : 'none';
          notesField.style.display = cb.checked ? 'block' : 'none';
        }

        var lastLiveId = null;
        function pollLiveCall() {
          fetch('/api/live-call')
            .then(function(r){ return r.json(); })
            .then(function(lc){
              if (!lc.found) return;
              if (lc.id !== lastLiveId) {
                lastLiveId = lc.id;
                if (searchInput) {
                  searchInput.value = lc.phone;
                  searchInput.dispatchEvent(new Event('input'));
                }
              }
              if (lc.ended && lc.duration_seconds != null) {
                var d = document.querySelector('[name="call_duration"]');
                if (d) d.value = Math.max(1, Math.round(lc.duration_seconds / 60));
              }
            })
            .catch(function(){});
        }
        setInterval(pollLiveCall, 2500);
        </script>
        """.replace("__NO_PROJECT__", t("no_project", lang)).replace("__PROJECT_OPTS__", project_opts)

        body = f"""
        <div class="dashboard">
            {saved_alert}
            <div class="stats">
                <div class="stat"><span>{total_customers}</span><small>{t("total_customers", lang)}</small></div>
                <div class="stat stat-success"><span>{calls_today}</span><small>{t("calls_today", lang)}</small></div>
                <div class="stat stat-warning"><span>{follow_today}</span><small>{t("follow_today", lang)}</small></div>
                <div class="stat stat-danger"><span>{overdue}</span><small>{t("overdue_followups", lang)}</small></div>
                <div class="stat"><span>{signed}</span><small>{t("signed_customers", lang)}</small></div>
                <div class="stat stat-success"><span>{avg_csat_dash}</span><small>{t("avg_csat", lang)}</small></div>
            </div>

    
        

        <div class="panel" style="padding:16px 20px;margin-bottom:20px">
                <h2 style="margin-bottom:12px">{t("today_overdue_followups", lang)}</h2>
                <div class="table-wrap" style="margin-bottom:0;border:none;box-shadow:none">{table_html}</div>
            </div>

            <div class="call-form-layout">
                <div id="call-logs-sidebar" class="panel call-logs-sidebar" hidden>
                    <div class="top"><h2>{t("recent_calls", lang)}</h2></div>
                    <div id="call-logs-sidebar-list" class="call-logs-list"></div>
                    <hr style="margin:8px 0;border:none;border-top:1px solid var(--line)">
                    <div class="top"><h2>{t("customer_projects", lang)}</h2></div>
                    <div id="customer-projects-sidebar-list" class="call-logs-list"></div>
                    <hr style="margin:8px 0;border:none;border-top:1px solid var(--line)">
                    <div class="top"><h2>{t("recent_followups", lang)}</h2></div>
                    <div id="follow-up-sidebar-list" class="call-logs-list"></div>
                </div>

                <section class="panel call-save">
                    <div class="top"><h2>{t("new_call_title", lang)}</h2></div>
                    <form method="post" class="call-form" id="call-save-form">
                        <div class="call-form-row">
                            <label>{t("call_date", lang)}<input class="jalali-date" name="call_date" value="{today_formatted}"></label>
                            <label>{t("call_time", lang)}<input type="time" name="call_time" value="{current_time}"></label>
                            <label class="nc-field" style="flex:2">{t("search_customer_box", lang)}
                                <input type="text" id="cust-search-input" name="search_customer" placeholder="{t('search_hint', lang)}" autocomplete="off">
                                <small class="muted" style="margin-top:3px">{t("search_hint", lang)}</small>
                            </label>
                        </div>

                        <div id="customer-info" hidden class="call-form-body">
                            <div id="found-customer" class="call-form-row" hidden>
                                <label>{t("customer_name", lang)}<input name="customer_name_display" readonly placeholder="—"></label>
                                <label>{t("primary_phone", lang)}<input name="customer_phone_display" readonly placeholder="—"></label>
                            </div>

                            <div id="found-project-row" hidden>
                                <div class="call-form-row">
                                    <label>{t("customer_projects", lang)} <button type="button" class="small secondary" onclick="addFoundCustomerProject()" style="margin-inline-start:8px">+ {t("projects", lang)}</button></label>
                                    <div id="found-customer-projects"></div>
                                </div>
                                <div class="call-form-row" style="margin-top:8px">
                                    <label>{t("call_project", lang)}<select name="project_id" id="project-select"><option value="">{t("no_project", lang)}</option></select></label>
                                </div>
                            </div>

                            <div id="new-customer" hidden>
                                <div class="call-form-row">
                                    <label>{t("customer_name", lang)} *<input name="new_customer_name" placeholder="{t('customer_name', lang)}"></label>
                                    <label>{t("primary_phone", lang)} *<input name="new_customer_phone" placeholder="{t('primary_phone', lang)}"></label>
                                    <label>{t("city", lang)}<input name="new_customer_city" placeholder="{t('city', lang)}"></label>
                                </div>
                                <div style="margin-top:10px">
                                    <label>{t("projects", lang)} <button type="button" class="small secondary" onclick="addNewCustomerProject()" style="margin-inline-start:8px">+ {t("projects", lang)}</button></label>
                                    <div id="new-customer-projects">
                                        <div class="project-pick"><select name="new_customer_project_ids">{project_opts}</select><button type="button" class="small secondary" onclick="this.parentElement.remove()">-</button></div>
                                    </div>
                                </div>
                            </div>

                            <div class="call-form-row" style="margin-top:12px">
                                <label>{t("call_duration", lang)}<input type="number" name="call_duration" min="0" step="1" placeholder="5"></label>
                                <label>{t("call_type", lang)}<select name="call_type">{call_opts}</select></label>
                                <label>{t("call_topic", lang)}<select name="problem_type">{problem_opts}</select></label>
                                <label class="check" style="align-self:flex-end;margin-bottom:2px">
                                    <input type="checkbox" name="follow_up_required" value="1" onclick="toggleFollowUpFields()"> {t("needs_followup", lang)}
                                </label>
                            </div>

                            <div id="follow-up-fields" class="call-form-row" style="display:none;margin-top:10px">
                                <label>{t("followup_reason", lang)}<select name="follow_up_reason">{fu_opts}</select></label>
                                <label>{t("followup_due", lang)}<input class="jalali-datetime" name="follow_up_datetime" value="{tomorrow_formatted} {current_time}"></label>
                                <label>{t("followup_agent", lang)}<select name="follow_up_agent">{user_opts}</select></label>
                            </div>

                            <div id="follow-up-notes-field" style="display:none;margin-top:10px">
                                <label>{t("followup_notes", lang)}<textarea name="follow_up_notes" placeholder="{t('followup_notes', lang)}..."></textarea></label>
                            </div>

                            <div class="call-form-row" style="margin-top:10px">
                                <label style="flex:1">⭐ {t("satisfaction_score", lang)}
                                    <select name="satisfaction_score">
                                        <option value="">— {t("unassigned", lang)} —</option>
                                        <option value="5">⭐⭐⭐⭐⭐ {t("rating_5", lang)}</option>
                                        <option value="4">⭐⭐⭐⭐ {t("rating_4", lang)}</option>
                                        <option value="3">⭐⭐⭐ {t("rating_3", lang)}</option>
                                        <option value="2">⭐⭐ {t("rating_2", lang)}</option>
                                        <option value="1">⭐ {t("rating_1", lang)}</option>
                                    </select>
                                </label>
                                <label style="flex:1">{t("satisfaction_notes", lang)}
                                    <input type="text" name="satisfaction_notes" placeholder="{t('satisfaction_notes', lang)}...">
                                </label>
                            </div>

                            <label style="margin-top:10px">{t("call_notes", lang)}<textarea name="notes" placeholder="{t('call_notes', lang)}..."></textarea></label>
                            <input type="hidden" name="customer_id" id="customer-id">
                            <button id="save-call-btn" style="margin-top:12px;width:100%" disabled>{t("save_call_btn", lang)}</button>
                        </div>
                    </form>
                </section>
            </div>
            {dash_js}
        </div>
        """
        self.send_html(body, t("dashboard", lang))

    def followups(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_where = "" if is_manager else " AND (f.assigned_agent_id=? OR f.created_by=?)"
        agent_params = () if is_manager else (uid, uid)

        # Mark all pending follow-ups assigned to current user as viewed
        self.conn.execute(
            "UPDATE follow_ups SET viewed_at=? WHERE assigned_agent_id=? AND status='pending' AND viewed_at IS NULL",
            (now_iso(), uid)
        )
        self.conn.commit()

        status_filter = self.query.get("status", ["pending"])[0]
        if status_filter not in ("pending", "done", "cancelled", "all"):
            status_filter = "pending"
        status_where = "" if status_filter == "all" else f" AND f.status='{status_filter}'"

        query = f"""SELECT f.*, c.full_name, c.primary_phone, c.national_code, u.name agent
                    FROM follow_ups f
                    JOIN customers c ON c.id=f.customer_id
                    LEFT JOIN users u ON u.id=f.assigned_agent_id
                    WHERE 1=1{status_where}{agent_where}
                    ORDER BY CASE f.status WHEN 'pending' THEN 0 WHEN 'done' THEN 1 ELSE 2 END, f.due_at ASC"""
        rows = self.conn.execute(query, agent_params).fetchall()

        tabs = []
        for st in ["pending", "done", "cancelled", "all"]:
            active = " active" if st == status_filter else ""
            st_label = t(st, lang, label_text(st, lang))
            tabs.append(f'<a href="/follow-ups?status={st}" class="tab{active}">{esc(st_label)}</a>')
        tabs_html = "".join(tabs)

        cards = []
        for r in rows:
            due = format_date_display(r["due_at"], lang, with_time=True)
            over = ""
            try:
                if r["status"] == "pending" and datetime.fromisoformat(r["due_at"].replace(" ", "T")) < datetime.now():
                    over = f' <span class="pill prio-urgent" style="font-size:0.65rem">{t("overdue_label", lang)}</span>'
            except Exception:
                pass

            notes = esc(r["notes"] or "")
            national_code = esc(r["national_code"] or "")
            completed_display = ""
            if r["completed_at"]:
                comp_date = format_date_display(r["completed_at"], lang, with_time=True)
                completed_display = f'<small>{t("done_btn", lang)}: {comp_date}</small>'

            agent_select = user_options(self.conn, r["assigned_agent_id"], blank=t("unassigned", lang), lang=lang)
            priority_select = options(PRIORITIES, r["priority"], lang=lang)

            actions_html = f'''
            <form method="post" action="/follow-ups/{r['id']}/reassign" style="display:inline-flex;gap:4px;align-items:center">
                <select name="agent_id" onchange="this.form.submit()" style="width:auto;padding:3px 8px;font-size:0.8rem">{agent_select}</select>
                <input type="hidden" name="reassign" value="1">
            </form>
            '''

            if r["status"] == "pending":
                actions_html += f'''
                <form method="post" action="/follow-ups/{r['id']}/complete" style="display:inline">
                    <button type="submit" class="button small success">{t("done_btn", lang)}</button>
                </form>
                <form method="post" action="/follow-ups/{r['id']}/cancel" style="display:inline">
                    <button type="submit" class="button small secondary">{t("cancel_btn", lang)}</button>
                </form>
                <button type="button" class="button small secondary" onclick="toggleEditCard('{r['id']}')">✏️</button>
                '''

            actions_html += f'<a href="/follow-ups/{r["id"]}" class="button small secondary">{t("chat_details", lang)}</a>'

            due_input_val = format_date_display(r["due_at"], lang, with_time=True)
            edit_card = f'''
            <div class="fu-edit-form" id="fu-edit-{r['id']}" style="display:none;background:var(--bg);padding:14px;border-radius:0 0 var(--radius) var(--radius);border-top:1px solid var(--line)">
                <form method="post" action="/follow-ups/{r['id']}/edit" style="display:flex;flex-direction:column;gap:8px">
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        <input name="reason" value="{esc(r['reason'] or '')}" placeholder="{t('followup_reason', lang)}" style="flex:1;min-width:140px;padding:5px 8px;font-size:0.82rem">
                        <select name="priority" style="width:auto;padding:5px 8px;font-size:0.82rem">{priority_select}</select>
                        <input class="jalali-datetime" name="due_at" value="{due_input_val}" style="width:180px;padding:5px 8px;font-size:0.82rem">
                    </div>
                    <textarea name="notes" placeholder="{t('followup_notes', lang)}" style="padding:5px 8px;font-size:0.82rem;min-height:50px">{esc(r['notes'] or '')}</textarea>
                    <div style="display:flex;gap:6px">
                        <button type="submit" class="small">{t("save", lang)}</button>
                        <button type="button" class="small secondary" onclick="toggleEditCard('{r['id']}')">{t("cancel", lang)}</button>
                    </div>
                </form>
            </div>
            '''

            cards.append(f'''
            <div class="follow-up-card fu-card">
                <div class="fu-header">
                    <strong>{esc(r["full_name"])}</strong>
                    <div>
                        <span class="pill prio-{esc(r["priority"])}">{label(r["priority"], lang)}</span>
                        <span class="pill status-{esc(r["status"])}">{label(r["status"], lang)}</span>
                    </div>
                </div>
                <span aria-hidden="true" style="display:none">{national_code}</span>
                <div class="fu-body">
                    <small><strong>{t("followup_reason", lang)}:</strong> {esc(r["reason"] or "—")}</small>
                    <small><strong>{t("due_deadline", lang)}:</strong> {due}{over}</small>
                    <small><strong>{t("operator", lang)}:</strong> {esc(r["agent"] or "—")}</small>
                    {completed_display}
                </div>
                <div class="fu-notes"><p>{notes}</p></div>
                <div class="fu-actions">{actions_html}</div>
                {edit_card}
            </div>
            ''')

        cards_html = "".join(cards) if cards else f'<p class="muted">{t("no_active_followups", lang)}</p>'

        body = f"""
        <div class="filters">
            <h2>{t("follow_ups", lang)}</h2>
            <div style="flex:1;max-width:350px">
                <input type="text" id="fu-search" class="search-input" placeholder="🔍 {t('search', lang)}" oninput="filterFollowUps()">
            </div>
        </div>
        <div class="tab-bar">{tabs_html}</div>
        <div class="filters" style="margin-bottom:16px">
            <label style="display:flex;align-items:center;gap:6px;font-size:0.85rem">
                {t("from_date", lang)}: <input type="text" id="fu-date-from" class="jalali-date search-input" placeholder="{t('from_date', lang)}..." style="width:140px" onchange="filterFollowUps()">
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:0.85rem">
                {t("to_date", lang)}: <input type="text" id="fu-date-to" class="jalali-date search-input" placeholder="{t('to_date', lang)}..." style="width:140px" onchange="filterFollowUps()">
            </label>
            <button type="button" class="button small secondary" onclick="clearDateFilters()">✕ {t("clear_filter", lang)}</button>
        </div>
        <div class="follow-up-list" id="follow-up-list">{cards_html}</div>
        """
        self.send_html(body, t("follow_ups", lang))

    def followup_action(self, path, method):
        lang = self.lang
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.not_found()
        fu_id = parts[1]
        action = parts[2] if len(parts) > 2 else ""

        if method == "POST":
            if action == "reassign":
                d = self.form()
                agent_id = d.get("agent_id", "").strip()
                self.conn.execute(
                    "UPDATE follow_ups SET assigned_agent_id=?, viewed_at=NULL, updated_at=? WHERE id=?",
                    (agent_id or None, now_iso(), fu_id)
                )
                self.conn.commit()
                return self.redirect("/follow-ups")
            if action == "complete":
                self.conn.execute(
                    "UPDATE follow_ups SET status='done', completed_at=?, updated_at=? WHERE id=?",
                    (now_iso(), now_iso(), fu_id)
                )
                self.conn.commit()
                return self.redirect("/follow-ups")
            if action == "cancel":
                self.conn.execute(
                    "UPDATE follow_ups SET status='cancelled', updated_at=? WHERE id=?",
                    (now_iso(), fu_id)
                )
                self.conn.commit()
                return self.redirect("/follow-ups")
            if action == "comment":
                d = self.form()
                comment = d.get("comment", "").strip()
                if comment:
                    self.conn.execute(
                        "INSERT INTO follow_up_comments(follow_up_id, user_id, comment, created_at) VALUES(?,?,?,?)",
                        (fu_id, self.current_user["id"], comment, now_iso())
                    )
                    self.conn.commit()
                return self.redirect(f"/follow-ups/{fu_id}")
            if action == "qa":
                if not self.require_manager():
                    return
                d = self.form()
                qa_sc = int(d.get("qa_score")) if d.get("qa_score") else None
                qa_nt = d.get("qa_notes", "").strip() or None
                self.conn.execute(
                    "UPDATE call_logs SET qa_score=?, qa_notes=?, qa_agent_id=?, updated_at=? WHERE id=?",
                    (qa_sc, qa_nt, self.current_user["id"], now_iso(), call_id)
                )
                self.conn.commit()
                return self.redirect(f"/call-logs/{call_id}")
            if action == "edit":
                d = self.form()
                reason = d.get("reason", "").strip()
                priority = d.get("priority", "normal")
                due_at = parse_date_input(d.get("due_at", ""), True) or now_iso()
                agent_id = d.get("assigned_agent_id", "").strip()
                notes = d.get("notes", "").strip() or None
                self.conn.execute(
                    "UPDATE follow_ups SET reason=?, priority=?, assigned_agent_id=?, due_at=?, notes=?, updated_at=? WHERE id=?",
                    (reason, priority, agent_id or None, due_at, notes, now_iso(), fu_id)
                )
                self.conn.commit()
                return self.redirect(f"/follow-ups/{fu_id}")

        # GET detail view
        row = self.conn.execute(
            """SELECT f.*, c.full_name, c.primary_phone, u.name agent, cu.name creator_name
               FROM follow_ups f
               JOIN customers c ON c.id=f.customer_id
               LEFT JOIN users u ON u.id=f.assigned_agent_id
               LEFT JOIN users cu ON cu.id=f.created_by
               WHERE f.id=?""",
            (fu_id,)
        ).fetchone()
        if not row:
            return self.not_found()

        if row["assigned_agent_id"] == self.current_user["id"]:
            self.conn.execute("UPDATE follow_ups SET viewed_at=? WHERE id=? AND viewed_at IS NULL", (now_iso(), fu_id))
            self.conn.commit()

        due = format_date_display(row["due_at"], lang, with_time=True)
        created_display = format_date_display(row["created_at"], lang, with_time=True)

        comments = self.conn.execute(
            """SELECT fc.*, u.name user_name FROM follow_up_comments fc
               LEFT JOIN users u ON u.id=fc.user_id
               WHERE fc.follow_up_id=? ORDER BY fc.created_at ASC""",
            (fu_id,)
        ).fetchall()

        comments_list = []
        for c in comments:
            c_time = format_date_display(c["created_at"], lang, with_time=True)
            c_name = esc(c["user_name"] or "CRM")
            c_text = esc(c["comment"])
            comments_list.append(f'<div class="chat-msg"><strong>{c_name}</strong> <small class="muted">{c_time}</small><p>{c_text}</p></div>')
        comments_html = "".join(comments_list) if comments_list else f'<p class="muted">{t("no_comments_yet", lang)}</p>'

        prio_opts = options(PRIORITIES, row["priority"], lang=lang)
        user_opts_all = user_options(self.conn, row["assigned_agent_id"], blank=t("unassigned", lang), lang=lang)
        due_input_val = format_date_display(row["due_at"], lang, with_time=True)

        edit_form = ""
        if row["status"] == "pending":
            edit_form = f'''
            <details class="panel" style="padding:16px 20px;margin-top:16px">
                <summary style="cursor:pointer;font-weight:600;font-size:0.95rem">✏️ {t("edit", lang)}</summary>
                <form method="post" action="/follow-ups/{fu_id}/edit" class="form-layout" style="margin-top:12px;box-shadow:none;padding:0;border:none">
                    <div class="form-row">
                        <label>{t("followup_reason", lang)}<input name="reason" value="{esc(row['reason'] or '')}"></label>
                        <label>{t("priority", lang)}<select name="priority">{prio_opts}</select></label>
                    </div>
                    <div class="form-row">
                        <label>{t("due_deadline", lang)}<input class="jalali-datetime" name="due_at" value="{due_input_val}"></label>
                        <label>{t("operator", lang)}<select name="assigned_agent_id">{user_opts_all}</select></label>
                    </div>
                    <label>{t("followup_notes", lang)}<textarea name="notes">{esc(row['notes'] or '')}</textarea></label>
                    <button type="submit" class="button small">{t("save", lang)}</button>
                </form>
            </details>
            '''

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="panel" style="padding:20px">
                <div class="top">
                    <h2>{t("follow_ups", lang)}: {esc(row["full_name"])}</h2>
                    <a href="/follow-ups" class="button small secondary">← {t("cancel", lang)}</a>
                </div>
                <div class="fu-body" style="margin-top:12px">
                    <small><strong>{t("customer", lang)}:</strong> {esc(row["full_name"])}</small>
                    <small><strong>{t("primary_phone", lang)}:</strong> {esc(row["primary_phone"])}</small>
                    <small><strong>{t("followup_reason", lang)}:</strong> {esc(row["reason"] or "—")}</small>
                    <small><strong>{t("due_deadline", lang)}:</strong> {due}</small>
                    <small><strong>{t("priority", lang)}:</strong> <span class="pill prio-{esc(row['priority'])}">{label(row['priority'], lang)}</span></small>
                    <small><strong>{t("operator", lang)}:</strong> {esc(row["agent"] or "—")}</small>
                    <small><strong>{t("date", lang)}:</strong> {created_display}</small>
                    <small><strong>{t("status", lang)}:</strong> <span class="pill status-{esc(row['status'])}">{label(row['status'], lang)}</span></small>
                </div>
            </div>
            {edit_form}
            <div class="panel" style="padding:20px;margin-top:16px">
                <h3>{t("followup_conversation", lang)}</h3>
                <div class="chat-box">{comments_html}</div>
                <form method="post" action="/follow-ups/{fu_id}/comment" style="margin-top:12px;display:flex;gap:10px">
                    <textarea name="comment" placeholder="{t('write_comment', lang)}" style="flex:1;min-height:50px" required></textarea>
                    <button type="submit" class="button small" style="align-self:flex-end">{t("send_btn", lang)}</button>
                </form>
            </div>
            <div class="panel" style="padding:20px;margin-top:16px">
                <h3>{t("call_notes", lang)}</h3>
                <p>{esc(row["notes"] or "—")}</p>
            </div>
        </div>
        """
        self.send_html(body, f"{t('follow_ups', lang)}: {row['full_name']}")

    def call_log_detail(self, path, method):
        lang = self.lang
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.not_found()
        call_id = parts[1]

        if method == "POST":
            action = parts[2] if len(parts) > 2 else ""
            if action == "edit":
                d = self.form()
                call_date = parse_date_input(d.get("call_started_date", ""), False) or ""
                call_time = (d.get("call_started_time") or "").strip()
                call_started_at = f"{call_date[:10]} {call_time[:5]}" if call_date and call_time else ""
                dur = d.get("call_duration", "").strip()
                dur_seconds = int(float(dur) * 60) if dur else None
                self.conn.execute(
                    """UPDATE call_logs SET call_type=?, problem_type=?, project_id=?, call_started_at=?, call_duration_seconds=?, notes=?, updated_at=? WHERE id=?""",
                    (d.get("call_type", "incoming"), d.get("problem_type") or None, d.get("project_id") or None, call_started_at or None, dur_seconds, d.get("notes", "").strip() or None, now_iso(), call_id)
                )
                self.conn.commit()
                return self.redirect(f"/call-logs/{call_id}")
            if action == "delete":
                self.conn.execute("DELETE FROM call_logs WHERE id=?", (call_id,))
                self.conn.commit()
                return self.redirect("/reports")
            return self.not_found()

        row = self.conn.execute(
            """SELECT cl.*, c.full_name, c.primary_phone, u.name agent, p.name project
               FROM call_logs cl
               JOIN customers c ON c.id=cl.customer_id
               LEFT JOIN users u ON u.id=cl.agent_id
               LEFT JOIN projects p ON p.id=cl.project_id
               WHERE cl.id=?""",
            (call_id,)
        ).fetchone()
        if not row:
            return self.not_found()

        dur_display = ""
        if row["call_duration_seconds"]:
            secs = int(row["call_duration_seconds"])
            dur_display = f"{secs // 60}:{secs % 60:02d} {t('minute', lang)}"

        date_val = str(row["call_started_at"] or "")[:10]
        time_val = str(row["call_started_at"] or "")[11:16]
        can_edit = self.current_user["role"] == "manager" or row["agent_id"] == self.current_user["id"]

        call_type_opts = options(CALL_TYPES, row["call_type"], lang=lang)
        problem_opts = lookup_options(self.conn, "problem_types", row["problem_type"], blank="—", lang=lang)
        project_opts = project_options(self.conn, row["project_id"], blank=t("no_project", lang))

        edit_section = ""
        if can_edit:
            edit_section = f'''
            <details class="panel" style="padding:20px;margin-top:16px">
                <summary style="cursor:pointer;font-weight:600;font-size:0.95rem">✏️ {t("edit", lang)}</summary>
                <form method="post" action="/call-logs/{call_id}/edit" class="form-layout" style="margin-top:12px;box-shadow:none;padding:0;border:none">
                    <div class="form-row">
                        <label>{t("call_date", lang)}<input class="jalali-date" name="call_started_date" value="{format_date_display(date_val, lang)}"></label>
                        <label>{t("call_time", lang)}<input type="time" name="call_started_time" value="{esc(time_val)}"></label>
                    </div>
                    <div class="form-row">
                        <label>{t("call_type", lang)}<select name="call_type">{call_type_opts}</select></label>
                        <label>{t("call_topic", lang)}<select name="problem_type">{problem_opts}</select></label>
                        <label>{t("call_duration", lang)}<input type="number" name="call_duration" min="0" step="1" value="{int(row['call_duration_seconds'] / 60) if row['call_duration_seconds'] else ''}"></label>
                    </div>
                    <div class="form-row">
                        <label>{t("call_project", lang)}<select name="project_id">{project_opts}</select></label>
                    </div>
                    <label>{t("call_notes", lang)}<textarea name="notes">{esc(row['notes'] or '')}</textarea></label>
                    <div style="display:flex;gap:8px;margin-top:10px">
                        <button type="submit" class="button small">{t("save", lang)}</button>
                    </div>
                </form>
                <form method="post" action="/call-logs/{call_id}/delete" style="margin-top:12px" onsubmit="return confirm('{t('delete_confirm', lang)}')">
                    <button type="submit" class="button small danger">🗑️ {t("delete", lang)}</button>
                </form>
            </details>
            '''


        sat_stars = ("⭐ " * row["satisfaction_score"]) if row["satisfaction_score"] else "—"
        qa_supervisor_box = ""
        if self.current_user["role"] == "manager":
            qa_supervisor_box = f'''
            <div class="panel" style="margin-top:16px;background:rgba(59,130,246,0.04);border:1px solid rgba(59,130,246,0.25);padding:14px">
                <h4 style="margin:0 0 10px 0;font-size:0.9rem">📋 ارزیابی کنترل کیفیت مکالمه (ویژه مدیر / ناظر کیفی)</h4>
                <form method="post" action="/call-logs/{call_id}/qa" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                    <label style="font-size:0.85rem;margin:0">نمره کیفی (۰ تا ۱۰۰):
                        <input type="number" name="qa_score" min="0" max="100" value="{row['qa_score'] or ''}" style="width:80px;padding:3px 6px">
                    </label>
                    <label style="font-size:0.85rem;margin:0;flex:1">یادداشت ناظر کیفی:
                        <input type="text" name="qa_notes" value="{esc(row['qa_notes'] or '')}" placeholder="توضیحات ارزیابی مکالمه..." style="width:100%;padding:3px 6px">
                    </label>
                    <button type="submit" class="button small primary">ثبت ارزیابی کیفیت</button>
                </form>
            </div>
            '''

        started_display = format_date_display(row["call_started_at"], lang, with_time=True)
        created_display = format_date_display(row["created_at"], lang, with_time=True)

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="panel" style="padding:20px">
                <div class="top">
                    <h2>{t('recent_calls', lang)} #{call_id}</h2>
                    <a href="/reports" class="button small secondary">← {t('reports', lang)}</a>
                </div>
                <div class="fu-body" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px">
                    <small><strong>{t('customer', lang)}:</strong> <a href="/customers/{row['customer_id']}"><strong>{esc(row['full_name'])}</strong></a></small>
                    <small><strong>{t('primary_phone', lang)}:</strong> {esc(row['primary_phone'])}</small>
                    <small><strong>{t('call_type', lang)}:</strong> <span class="pill">{label(row['call_type'], lang)}</span></small>
                    <small><strong>{t('call_topic', lang)}:</strong> {label(row['problem_type'], lang) or '—'}</small>
                    <small><strong>{t('projects', lang)}:</strong> {esc(row['project'] or '—')}</small>
                    <small><strong>{t('operator', lang)}:</strong> {esc(row['agent'] or '—')}</small>
                    <small><strong>{t('time', lang)}:</strong> {started_display}</small>
                    <small><strong>{t('call_duration', lang)}:</strong> {dur_display or '—'}</small>
                    <small style="grid-column:1/-1"><strong>{t('date', lang)}:</strong> {created_display}</small>
                </div>
            </div>
            {edit_section}
            <div class="panel" style="padding:20px;margin-top:16px">
                <h3>{t('call_notes', lang)}</h3>
                <p>{esc(row['notes'] or '—')}</p>
            </div>
        </div>
        """
        self.send_html(body, f"#{call_id}")

    def customers(self, method):
        lang = self.lang
        rows = self.conn.execute(
            """SELECT c.*, u.name agent_name FROM customers c
               LEFT JOIN users u ON u.id=c.assigned_agent_id
               ORDER BY c.updated_at DESC"""
        ).fetchall()

        table_rows = []
        for r in rows:
            created_date = format_date_display(r["created_at"], lang)
            table_rows.append(f'''
            <tr>
                <td><a href="/customers/{r["id"]}"><strong>{esc(r["full_name"])}</strong></a></td>
                <td>{esc(r["national_code"] or "—")}</td>
                <td>{esc(r["primary_phone"])}</td>
                <td><span class="pill">{label(r["status"], lang)}</span></td>
                <td>{esc(r["agent_name"] or "—")}</td>
                <td>{created_date}</td>
                <td class="actions">
                    <a href="/customers/{r["id"]}" class="button small secondary">✏️</a>
                    <form method="post" action="/customers/{r['id']}/delete" style="display:inline" onsubmit="return confirm('{t('delete_confirm', lang)}')">
                        <button type="submit" class="button small secondary">🗑️</button>
                    </form>
                </td>
            </tr>
            ''')

        body = f"""
        <div class="top">
            <h2>{t("customers", lang)}</h2>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <div style="flex:1;min-width:260px">
                    <input type="text" id="cust-search" class="search-input" placeholder="🔍 {t('search', lang)}" oninput="filterTable('cust-table', this.value)">
                </div>
                <a href="/customers/new" class="button">+ {t("new_customer_btn", lang)}</a>
            </div>
        </div>
        <div class="table-wrap">
            <table id="cust-table">
                <thead>
                    <tr>
                        <th>{t("customer_name", lang)}</th>
                        <th>{t("national_code", lang)}</th>
                        <th>{t("primary_phone", lang)}</th>
                        <th>{t("status", lang)}</th>
                        <th>{t("operator", lang)}</th>
                        <th>{t("date", lang)}</th>
                        <th>{t("actions", lang)}</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>
        """
        self.send_html(body, t("customers", lang))

    def customer_form(self, method):
        lang = self.lang
        if method == "POST":
            d = self.form()
            self.conn.execute(
                """INSERT INTO customers(full_name, national_code, primary_phone, secondary_phone, email, city, address, source, status, assigned_agent_id, general_notes, created_by, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d.get("full_name", "").strip(), d.get("national_code", "").strip() or None, d.get("primary_phone", "").strip(),
                 d.get("secondary_phone", "").strip() or None, d.get("email", "").strip() or None, d.get("city", "").strip() or None,
                 d.get("address", "").strip() or None, d.get("source", "phone_call"), d.get("status", "new_lead"),
                 d.get("assigned_agent_id") or None, d.get("general_notes", "").strip() or None,
                 self.current_user["id"], now_iso(), now_iso())
            )
            cid = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
            self.conn.commit()
            return self.redirect(f"/customers/{cid}")

        src_opts = lookup_options(self.conn, "sources", blank=t("source", lang), lang=lang)
        status_opts = options(CUSTOMER_STATUSES, "new_lead", lang=lang)
        agent_opts = user_options(self.conn, blank=t("unassigned", lang), lang=lang)

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="top">
                <h2>{t("new_customer_btn", lang)}</h2>
                <a href="/customers" class="button small secondary">← {t("cancel", lang)}</a>
            </div>
            <form method="post" class="form-layout">
                <div class="form-row">
                    <label>{t("customer_name", lang)} *<input name="full_name" required></label>
                    <label>{t("national_code", lang)}<input name="national_code"></label>
                </div>
                <div class="form-row">
                    <label>{t("primary_phone", lang)} *<input name="primary_phone" required></label>
                    <label>{t("secondary_phone", lang)}<input name="secondary_phone"></label>
                </div>
                <div class="form-row">
                    <label>{t("email", lang)}<input name="email" type="email"></label>
                    <label>{t("city", lang)}<input name="city"></label>
                </div>
                <div class="form-row">
                    <label>{t("address", lang)}<input name="address"></label>
                </div>
                <div class="form-row">
                    <label>{t("source", lang)}<select name="source">{src_opts}</select></label>
                    <label>{t("customer_status", lang)}<select name="status">{status_opts}</select></label>
                    <label>{t("operator", lang)}<select name="assigned_agent_id">{agent_opts}</select></label>
                </div>
                <label>{t("call_notes", lang)}<textarea name="general_notes"></textarea></label>
                <button type="submit" style="margin-top:12px">{t("save", lang)}</button>
            </form>
        </div>
        """
        self.send_html(body, t("new_customer_btn", lang))

    def customer_routes(self, path, method):
        lang = self.lang
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.not_found()
        cid = parts[1]

        if method == "POST" and len(parts) >= 3 and parts[2] == "delete":
            self.conn.execute("DELETE FROM customers WHERE id=?", (cid,))
            self.conn.commit()
            return self.redirect("/customers")

        if method == "POST" and len(parts) >= 3 and parts[2] == "edit":
            d = self.form()
            self.conn.execute(
                """UPDATE customers SET full_name=?, national_code=?, primary_phone=?, secondary_phone=?, email=?, city=?, address=?, source=?, status=?, assigned_agent_id=?, general_notes=?, updated_at=? WHERE id=?""",
                (d.get("full_name", "").strip(), d.get("national_code", "").strip() or None, d.get("primary_phone", "").strip(),
                 d.get("secondary_phone", "").strip() or None, d.get("email", "").strip() or None, d.get("city", "").strip() or None,
                 d.get("address", "").strip() or None, d.get("source", "phone_call"), d.get("status", "new_lead"),
                 d.get("assigned_agent_id") or None, d.get("general_notes", "").strip() or None, now_iso(), cid)
            )
            self.conn.commit()
            return self.redirect(f"/customers/{cid}")

        row = self.conn.execute(
            """SELECT c.*, u.name agent_name FROM customers c
               LEFT JOIN users u ON u.id=c.assigned_agent_id WHERE c.id=?""",
            (cid,)
        ).fetchone()
        if not row:
            return self.not_found()

        src_opts = lookup_options(self.conn, "sources", row["source"], lang=lang)
        status_opts = options(CUSTOMER_STATUSES, row["status"], lang=lang)
        agent_opts = user_options(self.conn, row["assigned_agent_id"], blank=t("unassigned", lang), lang=lang)

        # Get linked projects
        projects = self.conn.execute(
            """SELECT p.* FROM projects p
               JOIN customer_projects cp ON cp.project_id=p.id
               WHERE cp.customer_id=? ORDER BY p.name""",
            (cid,)
        ).fetchall()
        proj_list = "".join([f'<span class="pill" style="margin:2px">{esc(p["name"])} ({p["progress_percentage"]}%)</span>' for p in projects]) or "—"

        # Get recent calls
        calls = self.conn.execute(
            """SELECT cl.*, u.name agent FROM call_logs cl
               LEFT JOIN users u ON u.id=cl.agent_id
               WHERE cl.customer_id=? ORDER BY cl.created_at DESC LIMIT 10""",
            (cid,)
        ).fetchall()
        call_rows = []
        for c in calls:
            c_date = format_date_display(c["call_started_at"] or c["created_at"], lang, with_time=True)
            call_rows.append(f'<tr><td><a href="/call-logs/{c["id"]}">#{c["id"]}</a></td><td>{c_date}</td><td>{label(c["call_type"], lang)}</td><td>{label(c["problem_type"], lang) or "—"}</td><td>{esc(c["agent"] or "—")}</td></tr>')
        calls_table = f'<div class="table-wrap"><table><thead><tr><th>ID</th><th>{t("date", lang)}</th><th>{t("call_type", lang)}</th><th>{t("call_topic", lang)}</th><th>{t("operator", lang)}</th></tr></thead><tbody>{"".join(call_rows)}</tbody></table></div>' if call_rows else f'<p class="muted">{t("recent_calls", lang)}: —</p>'

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="top">
                <h2>{esc(row["full_name"])}</h2>
                <a href="/customers" class="button small secondary">← {t("customers", lang)}</a>
            </div>

            <div class="panel" style="padding:16px 20px;margin-bottom:16px">
                <h3>{t("customer_projects", lang)}</h3>
                <div style="margin-top:8px">{proj_list}</div>
            </div>

            <form method="post" action="/customers/{cid}/edit" class="form-layout">
                <div class="form-row">
                    <label>{t("customer_name", lang)} *<input name="full_name" value="{esc(row['full_name'])}" required></label>
                    <label>{t("national_code", lang)}<input name="national_code" value="{esc(row['national_code'] or '')}"></label>
                </div>
                <div class="form-row">
                    <label>{t("primary_phone", lang)} *<input name="primary_phone" value="{esc(row['primary_phone'])}" required></label>
                    <label>{t("secondary_phone", lang)}<input name="secondary_phone" value="{esc(row['secondary_phone'] or '')}"></label>
                </div>
                <div class="form-row">
                    <label>{t("email", lang)}<input name="email" type="email" value="{esc(row['email'] or '')}"></label>
                    <label>{t("city", lang)}<input name="city" value="{esc(row['city'] or '')}"></label>
                </div>
                <div class="form-row">
                    <label>{t("address", lang)}<input name="address" value="{esc(row['address'] or '')}"></label>
                </div>
                <div class="form-row">
                    <label>{t("source", lang)}<select name="source">{src_opts}</select></label>
                    <label>{t("customer_status", lang)}<select name="status">{status_opts}</select></label>
                    <label>{t("operator", lang)}<select name="assigned_agent_id">{agent_opts}</select></label>
                </div>
                <label>{t("call_notes", lang)}<textarea name="general_notes">{esc(row['general_notes'] or '')}</textarea></label>
                <button type="submit" style="margin-top:12px">{t("save", lang)}</button>
            </form>

            <div class="panel" style="padding:20px;margin-top:20px">
                <h3 style="margin-bottom:12px">{t("recent_calls", lang)}</h3>
                {calls_table}
            </div>
        </div>
        """
        self.send_html(body, f"{row['full_name']}")

    def projects(self, method):
        lang = self.lang
        rows = self.conn.execute("SELECT * FROM projects WHERE is_active=1 ORDER BY name").fetchall()
        table_rows = []
        for r in rows:
            pct = r["progress_percentage"]
            progress_bar = f'<div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div></div>'
            table_rows.append(f'''
            <tr>
                <td><a href="/projects/{r["id"]}"><strong>{esc(r["name"])}</strong></a></td>
                <td>{esc(r["location"] or "—")}</td>
                <td><span class="pill">{label(r["stage"], lang)}</span></td>
                <td style="min-width:120px">{pct}% {progress_bar}</td>
                <td><span class="pill">{label(r["registration_status"], lang)}</span></td>
            </tr>
            ''')

        body = f"""
        <div class="top">
            <h2>{t("projects", lang)}</h2>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <div style="flex:1;min-width:260px">
                    <input type="text" id="proj-search" class="search-input" placeholder="🔍 {t('search', lang)}" oninput="filterTable('proj-table', this.value)">
                </div>
                <a href="/projects/new" class="button">+ {t("new_project_btn", lang)}</a>
            </div>
        </div>
        <div class="table-wrap">
            <table id="proj-table">
                <thead>
                    <tr>
                        <th>{t("projects", lang)}</th>
                        <th>{t("city", lang)}</th>
                        <th>{t("stage", lang)}</th>
                        <th>{t("progress", lang)}</th>
                        <th>{t("reg_status", lang)}</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>
        """
        self.send_html(body, t("projects", lang))

    def project_form(self, method):
        lang = self.lang
        if method == "POST":
            d = self.form()
            self.conn.execute(
                """INSERT INTO projects(name, location, description, stage, progress_percentage, expected_completion_date, registration_status, public_update, internal_notes, is_active, created_by, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?)""",
                (d.get("name", "").strip(), d.get("location", "").strip() or None, d.get("description", "").strip() or None,
                 d.get("stage", "planning"), int(d.get("progress_percentage", 0)), parse_date_input(d.get("expected_completion_date", ""), False) or None,
                 d.get("registration_status", "open"), d.get("public_update", "").strip() or None, d.get("internal_notes", "").strip() or None,
                 self.current_user["id"], now_iso(), now_iso())
            )
            self.conn.commit()
            return self.redirect("/projects")

        stage_opts = options(PROJECT_STAGES, "planning", lang=lang)
        reg_opts = options(REG_STATUSES, "open", lang=lang)

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="top">
                <h2>{t("new_project_btn", lang)}</h2>
                <a href="/projects" class="button small secondary">← {t("cancel", lang)}</a>
            </div>
            <form method="post" class="form-layout">
                <div class="form-row">
                    <label>{t("projects", lang)} *<input name="name" required></label>
                    <label>{t("city", lang)}<input name="location"></label>
                </div>
                <div class="form-row">
                    <label>{t("stage", lang)}<select name="stage">{stage_opts}</select></label>
                    <label>{t("progress", lang)} (%)<input name="progress_percentage" type="number" min="0" max="100" value="0"></label>
                </div>
                <div class="form-row">
                    <label>{t("reg_status", lang)}<select name="registration_status">{reg_opts}</select></label>
                    <label>{t("expected_date", lang)}<input name="expected_completion_date" class="jalali-date"></label>
                </div>
                <label>{t("description", lang)}<textarea name="description"></textarea></label>
                <label>{t("public_update", lang)}<textarea name="public_update"></textarea></label>
                <label>{t("internal_notes", lang)}<textarea name="internal_notes"></textarea></label>
                <button type="submit" style="margin-top:12px">{t("save", lang)}</button>
            </form>
        </div>
        """
        self.send_html(body, t("new_project_btn", lang))

    def project_routes(self, path, method):
        lang = self.lang
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.not_found()
        pid = parts[1]

        if method == "POST" and len(parts) >= 3 and parts[2] == "edit":
            d = self.form()
            self.conn.execute(
                """UPDATE projects SET name=?, location=?, description=?, stage=?, progress_percentage=?, expected_completion_date=?, registration_status=?, public_update=?, internal_notes=?, updated_at=? WHERE id=?""",
                (d.get("name", "").strip(), d.get("location", "").strip() or None, d.get("description", "").strip() or None,
                 d.get("stage", "planning"), int(d.get("progress_percentage", 0)), parse_date_input(d.get("expected_completion_date", ""), False) or None,
                 d.get("registration_status", "open"), d.get("public_update", "").strip() or None, d.get("internal_notes", "").strip() or None,
                 now_iso(), pid)
            )
            self.conn.commit()
            return self.redirect(f"/projects/{pid}")

        row = self.conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            return self.not_found()

        stage_opts = options(PROJECT_STAGES, row["stage"], lang=lang)
        reg_opts = options(REG_STATUSES, row["registration_status"], lang=lang)
        exp_date_val = format_date_display(row["expected_completion_date"], lang)

        body = f"""
        <div style="max-width:850px;margin:0 auto">
            <div class="top">
                <h2>{esc(row["name"])}</h2>
                <a href="/projects" class="button small secondary">← {t("projects", lang)}</a>
            </div>
            <form method="post" action="/projects/{pid}/edit" class="form-layout">
                <div class="form-row">
                    <label>{t("projects", lang)} *<input name="name" value="{esc(row['name'])}" required></label>
                    <label>{t("city", lang)}<input name="location" value="{esc(row['location'] or '')}"></label>
                </div>
                <div class="form-row">
                    <label>{t("stage", lang)}<select name="stage">{stage_opts}</select></label>
                    <label>{t("progress", lang)} (%)<input name="progress_percentage" type="number" min="0" max="100" value="{row['progress_percentage']}"></label>
                </div>
                <div class="form-row">
                    <label>{t("reg_status", lang)}<select name="registration_status">{reg_opts}</select></label>
                    <label>{t("expected_date", lang)}<input name="expected_completion_date" class="jalali-date" value="{exp_date_val}"></label>
                </div>
                <label>{t("description", lang)}<textarea name="description">{esc(row['description'] or '')}</textarea></label>
                <label>{t("public_update", lang)}<textarea name="public_update">{esc(row['public_update'] or '')}</textarea></label>
                <label>{t("internal_notes", lang)}<textarea name="internal_notes">{esc(row['internal_notes'] or '')}</textarea></label>
                <button type="submit" style="margin-top:12px">{t("save", lang)}</button>
            </form>
        </div>
        """
        self.send_html(body, f"{row['name']}")

    def reports(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        agent_where = "" if is_manager else " WHERE cl.agent_id=?"

        sel_project_id = self.query.get("project_id", [""])[0].strip()
        project_filter_sql = " AND cl.project_id=?" if sel_project_id else ""
        project_params = (sel_project_id,) if sel_project_id else ()

        total_calls = self.conn.execute(f"SELECT COUNT(*) c FROM call_logs cl WHERE 1=1{agent_filter}", agent_params).fetchone()["c"]
        total_customers = self.conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        total_projects = self.conn.execute("SELECT COUNT(*) c FROM projects WHERE is_active=1").fetchone()["c"]
        today_calls = self.conn.execute(f"SELECT COUNT(*) c FROM call_logs cl WHERE date(cl.created_at)=date('now'){agent_filter}", agent_params).fetchone()["c"]
        today_customers = self.conn.execute(f"SELECT COUNT(DISTINCT cl.customer_id) c FROM call_logs cl WHERE date(cl.created_at)=date('now'){agent_filter}", agent_params).fetchone()["c"]
        follow_pending = self.conn.execute("SELECT COUNT(*) c FROM follow_ups WHERE status='pending'").fetchone()["c"]
        signed = self.conn.execute("SELECT COUNT(*) c FROM customers WHERE status='registered_signed'").fetchone()["c"]

        avg_duration_row = self.conn.execute(f"SELECT COALESCE(AVG(cl.call_duration_seconds), 0) avg_sec FROM call_logs cl WHERE cl.call_duration_seconds IS NOT NULL{agent_filter}", agent_params).fetchone()
        avg_duration = round(avg_duration_row["avg_sec"] / 60, 1) if avg_duration_row["avg_sec"] else 0
        total_duration_row = self.conn.execute(f"SELECT COALESCE(SUM(cl.call_duration_seconds), 0) total_sec FROM call_logs cl{agent_where}", agent_params).fetchone()
        total_duration = round(total_duration_row["total_sec"] / 60, 0) if total_duration_row["total_sec"] else 0


        # CSAT & Quality Assessment Metrics
        csat_stats = self.conn.execute(
            f"""SELECT 
                  COUNT(cl.satisfaction_score) total_rated,
                  ROUND(AVG(cl.satisfaction_score), 1) avg_csat,
                  SUM(CASE WHEN cl.satisfaction_score >= 4 THEN 1 ELSE 0 END) satisfied_count,
                  ROUND(AVG(cl.qa_score), 0) avg_qa,
                  SUM(CASE WHEN cl.satisfaction_score = 5 THEN 1 ELSE 0 END) s5,
                  SUM(CASE WHEN cl.satisfaction_score = 4 THEN 1 ELSE 0 END) s4,
                  SUM(CASE WHEN cl.satisfaction_score = 3 THEN 1 ELSE 0 END) s3,
                  SUM(CASE WHEN cl.satisfaction_score = 2 THEN 1 ELSE 0 END) s2,
                  SUM(CASE WHEN cl.satisfaction_score = 1 THEN 1 ELSE 0 END) s1
               FROM call_logs cl WHERE 1=1{agent_filter}{project_filter_sql}""",
            agent_params + project_params
        ).fetchone()

        csat_rated = csat_stats["total_rated"] or 0
        avg_csat = csat_stats["avg_csat"] or 0
        avg_qa = int(csat_stats["avg_qa"] or 0)
        csat_pct = round((csat_stats["satisfied_count"] or 0) / csat_rated * 100, 1) if csat_rated > 0 else 0
        s5_cnt = csat_stats["s5"] or 0
        s4_cnt = csat_stats["s4"] or 0
        s3_cnt = csat_stats["s3"] or 0
        s2_cnt = csat_stats["s2"] or 0
        s1_cnt = csat_stats["s1"] or 0
        p5 = round(s5_cnt / (csat_rated or 1) * 100) if csat_rated > 0 else 0
        p4 = round(s4_cnt / (csat_rated or 1) * 100) if csat_rated > 0 else 0
        p3 = round(s3_cnt / (csat_rated or 1) * 100) if csat_rated > 0 else 0
        p2 = round(s2_cnt / (csat_rated or 1) * 100) if csat_rated > 0 else 0
        p1 = round(s1_cnt / (csat_rated or 1) * 100) if csat_rated > 0 else 0

        qa_operator_rows = self.conn.execute(
            f"""SELECT u.name agent, 
                       COUNT(cl.id) total_calls,
                       COUNT(cl.satisfaction_score) rated_calls,
                       ROUND(AVG(cl.satisfaction_score), 1) agent_csat,
                       ROUND(AVG(cl.qa_score), 0) agent_qa
                FROM call_logs cl
                JOIN users u ON u.id=cl.agent_id
                WHERE 1=1{agent_filter}{project_filter_sql}
                GROUP BY cl.agent_id ORDER BY agent_csat DESC, total_calls DESC""",
            agent_params + project_params
        ).fetchall()
        qa_operator_table_rows = "".join([f'<tr><td><strong>{esc(r["agent"])}</strong></td><td>{r["total_calls"]}</td><td>{r["rated_calls"]}</td><td>{"⭐ " + str(r["agent_csat"]) if r["agent_csat"] else "—"}</td><td>{str(int(r["agent_qa"])) + "%" if r["agent_qa"] else "—"}</td></tr>' for r in qa_operator_rows])

        today_val = format_date_display(date.today().isoformat(), lang)
        from_date_val = format_date_display((date.today() - timedelta(days=30)).isoformat(), lang)

        # 1. Project filter
        project_opts_rep = project_options(self.conn, sel_project_id, blank=t("all", lang))

        # 2. Call types
        type_rows = self.conn.execute(
            f"""SELECT cl.call_type, COUNT(*) cnt FROM call_logs cl
                WHERE cl.call_type IS NOT NULL AND cl.call_type != ''{agent_filter}{project_filter_sql}
                GROUP BY cl.call_type ORDER BY cnt DESC""",
            agent_params + project_params
        ).fetchall()
        type_total = sum(r["cnt"] for r in type_rows) or 1
        type_table_rows = "".join([f'<tr><td><span class="pill">{label(r["call_type"], lang)}</span></td><td>{r["cnt"]}</td><td>{round(r["cnt"]/type_total*100, 1)}%</td></tr>' for r in type_rows])

        # 3. Problem types
        prob_rows = self.conn.execute(
            f"""SELECT cl.problem_type, COUNT(*) cnt FROM call_logs cl
                WHERE cl.problem_type IS NOT NULL AND cl.problem_type != ''{agent_filter}{project_filter_sql}
                GROUP BY cl.problem_type ORDER BY cnt DESC""",
            agent_params + project_params
        ).fetchall()
        prob_total = sum(r["cnt"] for r in prob_rows) or 1
        prob_table_rows = "".join([f'<tr><td>{label(r["problem_type"], lang)}</td><td>{r["cnt"]}</td><td>{round(r["cnt"]/prob_total*100, 1)}%</td></tr>' for r in prob_rows])

        # 4. Daily calls
        daily_rows = self.conn.execute(
            f"""SELECT date(cl.created_at) as d, COUNT(*) as cnt, COUNT(DISTINCT cl.customer_id) as cust_cnt
                FROM call_logs cl WHERE 1=1{agent_filter}{project_filter_sql}
                GROUP BY d ORDER BY d DESC LIMIT 30""",
            agent_params + project_params
        ).fetchall()
        daily_table_rows = "".join([f'<tr><td>{format_date_display(r["d"], lang)}</td><td>{r["cnt"]}</td><td>{r["cust_cnt"]}</td></tr>' for r in daily_rows])

        # 5. Agent performance
        agent_rows = self.conn.execute(
            f"""SELECT u.name agent, COUNT(*) cnt, COUNT(DISTINCT cl.customer_id) cust_cnt, COALESCE(SUM(cl.call_duration_seconds), 0) total_sec
                FROM call_logs cl JOIN users u ON u.id=cl.agent_id
                WHERE 1=1{agent_filter}{project_filter_sql}
                GROUP BY cl.agent_id ORDER BY cnt DESC""",
            agent_params + project_params
        ).fetchall()
        agent_table_rows = "".join([f'<tr><td><strong>{esc(r["agent"])}</strong></td><td>{r["cnt"]}</td><td>{r["cust_cnt"]}</td><td>{int(round(r["total_sec"]/60, 0))}</td></tr>' for r in agent_rows])

        # 6. Recent calls
        recent_rows = self.conn.execute(
            f"""SELECT cl.*, c.full_name, c.primary_phone, u.name agent, p.name project
                FROM call_logs cl
                JOIN customers c ON c.id=cl.customer_id
                LEFT JOIN users u ON u.id=cl.agent_id
                LEFT JOIN projects p ON p.id=cl.project_id
                WHERE 1=1{agent_filter}{project_filter_sql}
                ORDER BY cl.created_at DESC LIMIT 20""",
            agent_params + project_params
        ).fetchall()
        recent_table_rows = []
        for r in recent_rows:
            dur = f"{int(r['call_duration_seconds']) // 60}:{int(r['call_duration_seconds']) % 60:02d}" if r["call_duration_seconds"] else "—"
            c_date = format_date_display(r["call_started_at"] or r["created_at"], lang, with_time=True)
            recent_table_rows.append(f'''
            <tr>
                <td>{c_date}</td>
                <td><a href="/call-logs/{r["id"]}"><strong>{esc(r["full_name"])}</strong></a></td>
                <td>{esc(r["primary_phone"])}</td>
                <td><span class="pill">{label(r["call_type"], lang)}</span></td>
                <td>{label(r["problem_type"], lang) or "—"}</td>
                <td>{dur}</td>
                <td>{esc(r["project"] or "—")}</td>
                <td>{esc(r["agent"] or "—")}</td>
            </tr>
            ''')

        body = f"""
        <div class="top">
            <h2>{t("reports", lang)}</h2>
        </div>

        <div class="stats">
            <div class="stat"><span>{total_calls}</span><small>{t("calls_today", lang)}</small></div>
            <div class="stat stat-success"><span>{today_calls}</span><small>{t("calls_today", lang)}</small></div>
            <div class="stat"><span>{today_customers}</span><small>{t("unique_customers", lang)}</small></div>
            <div class="stat"><span>{total_customers}</span><small>{t("total_customers", lang)}</small></div>
            <div class="stat stat-warning"><span>{follow_pending}</span><small>{t("follow_today", lang)}</small></div>
            <div class="stat"><span>{avg_duration}</span><small>{t("avg_duration", lang)}</small></div>
            <div class="stat"><span>{int(total_duration)}</span><small>{t("total_duration", lang)}</small></div>
        </div>

        <div class="panel" style="padding:16px 20px;margin-bottom:20px">
            <div class="top" style="margin-bottom:12px">
                <h3>📊 {t("export_excel", lang)}</h3>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
                    <a href="/backup" class="button small secondary" title="{t('backup_db', lang)}">💾 {t('backup_db', lang)}</a>
                    <a href="/exports/project-calls" class="button small secondary">📁 {t("by_project", lang)}</a>
                    <a href="/exports/project-member-calls" class="button small secondary">👤 {t("by_agent", lang)}</a>
                    <a href="/exports/customers" class="button small secondary">👥 {t("customer_list", lang)}</a>
                    <a href="/exports/follow-ups" class="button small secondary">⏰ {t("followup_list", lang)}</a>
                </div>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:var(--bg);padding:10px 14px;border-radius:var(--radius);border:1px solid var(--line)">
                <span style="font-weight:600;font-size:0.85rem">📅 {t("date_range_export", lang)}:</span>
                <button type="button" class="button small secondary" onclick="setExportPreset('today')">{t('preset_today', lang)}</button>
                <button type="button" class="button small secondary" onclick="setExportPreset('7days')">{t('preset_7days', lang)}</button>
                <button type="button" class="button small secondary" onclick="setExportPreset('30days')">{t('preset_30days', lang)}</button>
                <button type="button" class="button small secondary" onclick="setExportPreset('all')">{t('preset_all', lang)}</button>
                <span style="opacity:0.3;margin:0 4px">|</span>
                <span style="display:inline-flex;gap:4px;align-items:center">
                    <label style="font-size:0.8rem;margin:0">{t('from_date', lang)}:</label>
                    <input type="text" id="export-from" class="jalali-date" value="{from_date_val}" style="width:115px;padding:4px 8px;font-size:0.82rem">
                    <label style="font-size:0.8rem;margin:0">{t('to_date', lang)}:</label>
                    <input type="text" id="export-to" class="jalali-date" value="{today_val}" style="width:115px;padding:4px 8px;font-size:0.82rem">
                    <button type="button" class="button small primary" onclick="exportRange()">📥 {t("export_excel", lang)}</button>
                </span>
            </div>
        </div>

<div class="panel" style="padding:16px 20px;margin-bottom:20px;background:linear-gradient(135deg, rgba(59,130,246,0.05), rgba(16,185,129,0.05));border:1px solid rgba(59,130,246,0.2)">
            <h3 style="margin-top:0">🌟 {t("csat_title", lang)}</h3>
            <div class="stats" style="margin-bottom:16px">
                <div class="stat stat-success">
                    <span>{"⭐ " + str(avg_csat) if avg_csat else "—"}</span>
                    <small>{t("avg_csat", lang)} (از ۵)</small>
                </div>
                <div class="stat">
                    <span>{csat_pct}%</span>
                    <small>درصد رضایت مخاطبان</small>
                </div>
                <div class="stat stat-warning">
                    <span>{avg_qa}%</span>
                    <small>{t("avg_qa", lang)}</small>
                </div>
                <div class="stat">
                    <span>{csat_rated}</span>
                    <small>تعداد تماس‌های ارزیابی‌شده</small>
                </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
                <div class="section" style="box-shadow:none;background:var(--card)">
                    <h4 style="margin-top:0">توزیع امتیازهای رضایت مخاطبان:</h4>
                    <div style="display:flex;flex-direction:column;gap:8px;font-size:0.85rem">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="width:120px">⭐⭐⭐⭐⭐ عالی</span>
                            <div style="flex:1;background:var(--bg);height:12px;border-radius:6px;overflow:hidden"><div style="background:#10b981;height:100%;width:{p5}%"></div></div>
                            <span style="width:35px;text-align:end">{s5_cnt}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="width:120px">⭐⭐⭐⭐ خوب</span>
                            <div style="flex:1;background:var(--bg);height:12px;border-radius:6px;overflow:hidden"><div style="background:#3b82f6;height:100%;width:{p4}%"></div></div>
                            <span style="width:35px;text-align:end">{s4_cnt}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="width:120px">⭐⭐⭐ متوسط</span>
                            <div style="flex:1;background:var(--bg);height:12px;border-radius:6px;overflow:hidden"><div style="background:#f59e0b;height:100%;width:{p3}%"></div></div>
                            <span style="width:35px;text-align:end">{s3_cnt}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="width:120px">⭐⭐ ضعیف</span>
                            <div style="flex:1;background:var(--bg);height:12px;border-radius:6px;overflow:hidden"><div style="background:#ef4444;height:100%;width:{p2}%"></div></div>
                            <span style="width:35px;text-align:end">{s2_cnt}</span>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="width:120px">⭐ بسیار ضعیف</span>
                            <div style="flex:1;background:var(--bg);height:12px;border-radius:6px;overflow:hidden"><div style="background:#991b1b;height:100%;width:{p1}%"></div></div>
                            <span style="width:35px;text-align:end">{s1_cnt}</span>
                        </div>
                    </div>
                </div>

                <div class="section" style="box-shadow:none;background:var(--card)">
                    <h4 style="margin-top:0">رتبه‌بندی عملکرد و رضایت اپراتورها:</h4>
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>{t("operator", lang)}</th>
                                    <th>کل تماس‌ها</th>
                                    <th>ارزیابی‌شده</th>
                                    <th>میانگین رضایت</th>
                                    <th>امتیاز کیفی</th>
                                </tr>
                            </thead>
                            <tbody>
                                {qa_operator_table_rows or '<tr><td colspan="5">—</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="section" style="margin-bottom:20px">
            <h3>{t("filter", lang)} ({t("projects", lang)})</h3>
            <form method="get" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <select name="project_id" onchange="this.form.submit()" style="max-width:280px">{project_opts_rep}</select>
                <noscript><button type="submit" class="button small secondary">{t("filter", lang)}</button></noscript>
                <a href="/reports" class="button small secondary">{t("clear_filter", lang)}</a>
            </form>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
            <div class="section">
                <h3>{t("call_types_chart", lang)}</h3>
                <div class="table-wrap">
                    <table><thead><tr><th>{t("call_type", lang)}</th><th>{t("count", lang)}</th><th>{t("percentage", lang)}</th></tr></thead><tbody>{type_table_rows or '<tr><td colspan="3">—</td></tr>'}</tbody></table>
                </div>
            </div>
            <div class="section">
                <h3>{t("topics_chart", lang)}</h3>
                <div class="table-wrap">
                    <table><thead><tr><th>{t("call_topic", lang)}</th><th>{t("count", lang)}</th><th>{t("percentage", lang)}</th></tr></thead><tbody>{prob_table_rows or '<tr><td colspan="3">—</td></tr>'}</tbody></table>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>{t("agent_performance", lang)}</h3>
            <div class="table-wrap">
                <table><thead><tr><th>{t("operator", lang)}</th><th>{t("calls_today", lang)}</th><th>{t("unique_customers", lang)}</th><th>{t("total_duration", lang)}</th></tr></thead><tbody>{agent_table_rows or '<tr><td colspan="4">—</td></tr>'}</tbody></table>
            </div>
        </div>

        <div class="section">
            <h3>{t("daily_calls_chart", lang)}</h3>
            <div class="table-wrap">
                <table><thead><tr><th>{t("date", lang)}</th><th>{t("calls_today", lang)}</th><th>{t("unique_customers", lang)}</th></tr></thead><tbody>{daily_table_rows or '<tr><td colspan="3">—</td></tr>'}</tbody></table>
            </div>
        </div>

        <div class="section">
            <h3>{t("recent_calls", lang)}</h3>
            <div class="table-wrap">
                <table><thead><tr><th>{t("date", lang)}</th><th>{t("customer", lang)}</th><th>{t("primary_phone", lang)}</th><th>{t("call_type", lang)}</th><th>{t("call_topic", lang)}</th><th>{t("call_duration", lang)}</th><th>{t("projects", lang)}</th><th>{t("operator", lang)}</th></tr></thead><tbody>{''.join(recent_table_rows) or '<tr><td colspan="8">—</td></tr>'}</tbody></table>
            </div>
        </div>

        <script>
        function setExportPreset(preset) {{
          window.location.href = '/exports/daily-report?preset=' + encodeURIComponent(preset);
        }}
        function exportRange() {{
          var f = document.getElementById('export-from').value.trim();
          var t = document.getElementById('export-to').value.trim();
          window.location.href = '/exports/daily-report?from_date=' + encodeURIComponent(f) + '&to_date=' + encodeURIComponent(t);
        }}
        </script>
        """
        self.send_html(body, t("reports", lang))

    def users(self, method):
        if not self.require_manager():
            return
        lang = self.lang
        if method == "POST":
            d = self.form()
            pw = hash_password(d.get("password", "password123"))
            self.conn.execute(
                """INSERT INTO users(name, email, password, phone, role, is_active, created_at, updated_at)
                   VALUES(?,?,?,?,?,1,?,?)""",
                (d.get("name", "").strip(), d.get("email", "").strip(), pw, d.get("phone", "").strip() or None, d.get("role", "agent"), now_iso(), now_iso())
            )
            self.conn.commit()
            return self.redirect("/users")

        rows = self.conn.execute("SELECT * FROM users ORDER BY role DESC, name").fetchall()
        table_rows = []
        for r in rows:
            active_label = t("active", lang) if r["is_active"] else t("inactive", lang)
            active_pill = f'<span class="pill status-done">{active_label}</span>' if r["is_active"] else f'<span class="pill status-cancelled">{active_label}</span>'
            toggle_label = t("inactive", lang) if r["is_active"] else t("active", lang)
            table_rows.append(f'''
            <tr>
                <td><strong>{esc(r["name"])}</strong></td>
                <td>{esc(r["email"])}</td>
                <td><span class="pill">{label(r["role"], lang)}</span></td>
                <td>{active_pill}</td>
                <td class="actions">
                    <a href="/users/{r['id']}/toggle" class="button small secondary">{toggle_label}</a>
                    <a href="/users/{r['id']}/edit" class="button small secondary">✏️</a>
                    <form method="post" action="/users/{r['id']}/delete" style="display:inline" onsubmit="return confirm('{t('delete_confirm', lang)}')">
                        <button type="submit" class="button small secondary">🗑️</button>
                    </form>
                </td>
            </tr>
            ''')

        role_options = options(["manager", "agent"], "agent", lang=lang)

        body = f"""
        <div class="top">
            <h2>{t("users", lang)}</h2>
        </div>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>{t("customer_name", lang)}</th>
                        <th>{t("email", lang)}</th>
                        <th>{t("role", lang)}</th>
                        <th>{t("status", lang)}</th>
                        <th>{t("actions", lang)}</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="panel" style="padding:20px;margin-top:24px">
            <h3 style="margin-bottom:12px">{t("new_user_btn", lang)}</h3>
            <form method="post" class="form-layout" style="box-shadow:none;border:none;padding:0">
                <div class="form-row">
                    <label>{t("customer_name", lang)} *<input name="name" required></label>
                    <label>{t("email", lang)} *<input name="email" type="email" required></label>
                </div>
                <div class="form-row">
                    <label>{t("password", lang)} *<input name="password" type="password" value="password123"></label>
                    <label>{t("primary_phone", lang)}<input name="phone"></label>
                </div>
                <div class="form-row">
                    <label>{t("role", lang)}<select name="role">{role_options}</select></label>
                </div>
                <button type="submit" style="margin-top:10px">{t("save", lang)}</button>
            </form>
        </div>
        """
        self.send_html(body, t("users", lang))

    def user_action(self, path, method):
        if not self.require_manager():
            return
        lang = self.lang
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.not_found()
        uid = parts[1]
        action = parts[2] if len(parts) > 2 else ""

        if action == "toggle":
            row = self.conn.execute("SELECT is_active FROM users WHERE id=?", (uid,)).fetchone()
            if row:
                self.conn.execute("UPDATE users SET is_active=? WHERE id=?", (0 if row["is_active"] else 1, uid))
                self.conn.commit()
            return self.redirect("/users")

        if action == "edit":
            if method == "POST":
                d = self.form()
                name = d.get("name", "").strip()
                email = d.get("email", "").strip()
                phone = d.get("phone", "").strip() or None
                role = d.get("role", "agent")
                password = d.get("password", "").strip()
                if name and email:
                    if password:
                        pw = hash_password(password)
                        self.conn.execute(
                            "UPDATE users SET name=?, email=?, password=?, phone=?, role=?, updated_at=? WHERE id=?",
                            (name, email, pw, phone, role, now_iso(), uid)
                        )
                    else:
                        self.conn.execute(
                            "UPDATE users SET name=?, email=?, phone=?, role=?, updated_at=? WHERE id=?",
                            (name, email, phone, role, now_iso(), uid)
                        )
                    self.conn.commit()
                return self.redirect("/users")

            row = self.conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return self.not_found()
            role_opts = options(["manager", "agent"], row["role"], lang=lang)
            body = f"""
            <div style="max-width:700px;margin:0 auto">
                <div class="top">
                    <h2>{t("edit", lang)}: {esc(row["name"])}</h2>
                    <a href="/users" class="button small secondary">← {t("cancel", lang)}</a>
                </div>
                <form method="post" action="/users/{uid}/edit" class="form-layout">
                    <div class="form-row">
                        <label>{t("customer_name", lang)} *<input name="name" value="{esc(row['name'])}" required></label>
                        <label>{t("email", lang)} *<input name="email" type="email" value="{esc(row['email'])}" required></label>
                    </div>
                    <div class="form-row">
                        <label>{t("password", lang)}<input name="password" type="password" placeholder="..."></label>
                        <label>{t("primary_phone", lang)}<input name="phone" value="{esc(row['phone'] or '')}"></label>
                    </div>
                    <div class="form-row">
                        <label>{t("role", lang)}<select name="role">{role_opts}</select></label>
                    </div>
                    <button type="submit" style="margin-top:10px">{t("save", lang)}</button>
                </form>
            </div>
            """
            return self.send_html(body, f"{row['name']}")

        if action == "delete" and method == "POST":
            if str(uid) != str(self.current_user["id"]):
                self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
                self.conn.commit()
            return self.redirect("/users")

        return self.not_found()

    def base_tables(self, method):
        if not self.require_manager():
            return
        lang = self.lang
        if method == "POST":
            d = self.form()
            action = d.get("action", "")
            if action == "add" and d.get("lookup_type") and d.get("value") and d.get("label"):
                self.conn.execute(
                    "INSERT OR IGNORE INTO lookup_items(lookup_type, value, label, is_active, created_at, updated_at) VALUES(?,?,?,1,?,?)",
                    (d["lookup_type"], d["value"].strip(), d["label"].strip(), now_iso(), now_iso())
                )
                self.conn.commit()
            elif action == "delete" and d.get("id"):
                self.conn.execute("UPDATE lookup_items SET is_active=0, updated_at=? WHERE id=?", (now_iso(), d["id"]))
                self.conn.commit()
            elif action == "edit" and d.get("id") and d.get("label"):
                val = d.get("value", "").strip()
                if val:
                    self.conn.execute(
                        "UPDATE lookup_items SET value=?, label=?, updated_at=? WHERE id=?",
                        (val, d["label"].strip(), now_iso(), d["id"])
                    )
                else:
                    self.conn.execute(
                        "UPDATE lookup_items SET label=?, updated_at=? WHERE id=?",
                        (d["label"].strip(), now_iso(), d["id"])
                    )
                self.conn.commit()
            return self.redirect("/base-tables")

        sections = []
        for lookup_type, (title_key, _) in LOOKUP_DEFS.items():
            items = self.conn.execute(
                "SELECT * FROM lookup_items WHERE lookup_type=? AND is_active=1 ORDER BY id",
                (lookup_type,)
            ).fetchall()
            item_rows = []
            for it in items:
                item_rows.append(f'''
                <tr>
                    <td><code>{esc(it["value"])}</code></td>
                    <td>{esc(it["label"])}</td>
                    <td class="actions">
                        <form method="post" style="display:inline-flex;gap:4px;align-items:center">
                            <input type="hidden" name="id" value="{it['id']}">
                            <input type="hidden" name="action" value="edit">
                            <input type="text" name="value" value="{esc(it['value'])}" style="width:110px;padding:3px 6px;font-size:0.8rem">
                            <input type="text" name="label" value="{esc(it['label'])}" style="width:130px;padding:3px 6px;font-size:0.8rem">
                            <button type="submit" class="button small">✓</button>
                        </form>
                        <form method="post" style="display:inline">
                            <input type="hidden" name="action" value="delete">
                            <input type="hidden" name="id" value="{it['id']}">
                            <button type="submit" class="button small secondary">✕</button>
                        </form>
                    </td>
                </tr>
                ''')

            sections.append(f'''
            <div class="section bt-section" style="margin-bottom:20px">
                <h3>{t(title_key, lang, lookup_type)}</h3>
                <div class="table-wrap" style="margin-top:10px">
                    <table>
                        <thead><tr><th>{t("code_value", lang)}</th><th>{t("label_title", lang)}</th><th>{t("actions", lang)}</th></tr></thead>
                        <tbody>{''.join(item_rows)}</tbody>
                    </table>
                </div>
                <form method="post" class="form-row" style="margin-top:12px;display:flex;gap:10px;align-items:flex-end">
                    <input type="hidden" name="lookup_type" value="{esc(lookup_type)}">
                    <input type="hidden" name="action" value="add">
                    <label style="flex:1">{t("code_value", lang)}<input name="value" required placeholder="example_key"></label>
                    <label style="flex:1">{t("label_title", lang)}<input name="label" required placeholder="Title"></label>
                    <button type="submit" class="button small" style="margin-bottom:2px">{t("add_item", lang)}</button>
                </form>
            </div>
            ''')

        body = f"""
        <div class="top">
            <h2>{t("base_tables", lang)}</h2>
            <div style="flex:1;max-width:350px">
                <input type="text" id="bt-search" class="search-input" placeholder="🔍 {t('search', lang)}" oninput="filterBaseTables(this.value)">
            </div>
        </div>
        {''.join(sections)}
        """
        self.send_html(body, t("base_tables", lang))

    def _customer_payload(self, row):
        lang = self.lang
        projects = self.conn.execute(
            """SELECT p.id, p.name, p.stage, p.progress_percentage, p.registration_status
               FROM projects p
               JOIN customer_projects cp ON cp.project_id=p.id
               WHERE cp.customer_id=?""",
            (row["id"],)
        ).fetchall()
        recent_calls = self.conn.execute(
            """SELECT cl.id, cl.call_started_at, cl.problem_type
               FROM call_logs cl
               WHERE cl.customer_id=? ORDER BY cl.created_at DESC LIMIT 5""",
            (row["id"],)
        ).fetchall()
        return {
            "id": row["id"],
            "full_name": row["full_name"],
            "national_code": row["national_code"] or "",
            "primary_phone": row["primary_phone"],
            "projects": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "stage": label_text(p["stage"], lang),
                    "progress_percentage": p["progress_percentage"],
                    "registration_status": label_text(p["registration_status"], lang)
                } for p in projects
            ],
            "recent_calls": [
                {
                    "id": c["id"],
                    "call_started_at_display": format_date_display(c["call_started_at"], lang, with_time=True),
                    "problem_type_label": label_text(c["problem_type"], lang) if c["problem_type"] else "—"
                } for c in recent_calls
            ]
        }

    def api_customer_search(self):
        q = self.query.get("q", [""])[0].strip()
        if not q:
            return self.send_json({})

        # 1. Exact or suffix match on phone
        clean_phone = re.sub(r"\D+", "", q)
        if len(clean_phone) >= 4:
            row = self.conn.execute(
                """SELECT * FROM customers WHERE primary_phone LIKE ? OR secondary_phone LIKE ? ORDER BY id LIMIT 1""",
                (f"%{clean_phone}%", f"%{clean_phone}%")
            ).fetchone()
            if row:
                return self.send_json(self._customer_payload(row))

        # 2. Match national code / ID
        row = self.conn.execute("SELECT * FROM customers WHERE national_code=? ORDER BY id LIMIT 1", (q,)).fetchone()
        if row:
            return self.send_json(self._customer_payload(row))

        # 3. Match name
        row = self.conn.execute("SELECT * FROM customers WHERE full_name LIKE ? ORDER BY id LIMIT 1", (f"%{q}%",)).fetchone()
        if row:
            return self.send_json(self._customer_payload(row))

        return self.send_json({})

    def api_customer_by_national_code(self):
        code = self.query.get("code", [""])[0].strip()
        if not code:
            return self.send_json({})
        row = self.conn.execute("SELECT * FROM customers WHERE national_code=?", (code,)).fetchone()
        if not row:
            return self.send_json({})
        return self.send_json(self._customer_payload(row))

    def api_customer_by_phone(self):
        phone = self.query.get("phone", [""])[0].strip()
        if not phone:
            return self.send_json({})
        norm = re.sub(r"\D+", "", phone)
        row = self.conn.execute("SELECT * FROM customers WHERE primary_phone=? OR secondary_phone=? ORDER BY id LIMIT 1", (phone, phone)).fetchone()
        if not row and len(norm) >= 6:
            tail = norm[-7:]
            row = self.conn.execute("SELECT * FROM customers WHERE primary_phone LIKE ? OR secondary_phone LIKE ? ORDER BY id LIMIT 1", (f"%{tail}", f"%{tail}")).fetchone()
        if not row:
            return self.send_json({})
        return self.send_json(self._customer_payload(row))

    def api_customer_followup_history(self):
        lang = self.lang
        customer_id = self.query.get("customer_id", [""])[0].strip()
        if not customer_id:
            return self.send_json({"followups": []})
        rows = self.conn.execute(
            """SELECT f.*, u.name agent_name FROM follow_ups f
               LEFT JOIN users u ON u.id=f.assigned_agent_id
               WHERE f.customer_id=? ORDER BY f.created_at DESC LIMIT 10""",
            (customer_id,)
        ).fetchall()
        fu_list = []
        for r in rows:
            fu_list.append({
                "id": r["id"],
                "status": r["status"],
                "reason": r["reason"] or "",
                "due_at_display": format_date_display(r["due_at"], lang, with_time=True),
                "status_label": label_text(r["status"], lang)
            })
        return self.send_json({"followups": fu_list})

    def api_live_call(self):
        uid = self.current_user["id"]
        row = self.conn.execute(
            """SELECT * FROM live_calls WHERE
               agent_id=? OR
               agent_id IS NULL OR
               (extension IS NOT NULL AND EXISTS (
                   SELECT 1 FROM users u WHERE u.id=? AND (replace(u.phone,' ','')=live_calls.extension OR cast(u.id as text)=live_calls.extension)
               ))
               ORDER BY id DESC LIMIT 1""",
            (uid, uid)
        ).fetchone()
        if not row:
            return self.send_json({"found": False})
        return self.send_json({
            "found": True,
            "id": row["id"],
            "phone": row["phone"],
            "caller_name": row["caller_name"] or "",
            "status": row["status"] or "",
            "ended": row["ended_at"] is not None or row["duration_seconds"] is not None,
            "duration_seconds": row["duration_seconds"],
            "call_id": row["call_id"] or ""
        })

    def send_json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def export_customers(self):
        lang = self.lang
        rows = self.conn.execute(
            """SELECT c.id, c.full_name, c.national_code, c.primary_phone, c.secondary_phone, c.email, c.city, c.address, c.source, c.status, u.name agent, c.registration_date, c.last_contacted_at, c.next_follow_up_at, c.general_notes, c.created_at
               FROM customers c LEFT JOIN users u ON u.id=c.assigned_agent_id ORDER BY c.id"""
        ).fetchall()
        headers = [
            "ID", t("customer_name", lang), t("national_code", lang), t("primary_phone", lang),
            t("secondary_phone", lang), t("email", lang), t("city", lang), t("address", lang),
            t("source", lang), t("customer_status", lang), t("operator", lang),
            t("reg_status", lang), "Last Contact", "Next Follow-up", t("call_notes", lang), t("date", lang)
        ]
        return self.csv_export(rows, headers, "customers")

    def api_voip_webhook(self, method):
        if method == "POST":
            d = self.form() or self.json_body()
        else:
            d = {k: v[0] for k, v in self.query.items()}

        raw_phone = d.get("phone") or d.get("Number") or d.get("caller_id") or ""
        phone = sms_service.sanitize_phone(raw_phone)
        ext = str(d.get("extension") or d.get("Extension") or d.get("ext") or "").strip()
        event = str(d.get("event") or d.get("Event") or "ringing").lower()
        call_id = str(d.get("call_id") or d.get("CallID") or "")
        caller_name = str(d.get("caller_name") or "").strip()
        duration = d.get("duration")
        dur_seconds = int(float(duration)) if duration else None

        agent_id = None
        if ext:
            u_row = self.conn.execute("SELECT id FROM users WHERE replace(phone, ' ', '')=? OR id=?", (ext, ext)).fetchone()
            if u_row:
                agent_id = u_row["id"]

        now_str = now_iso()
        if event in ("ringing", "dial", "dialbegin"):
            self.conn.execute(
                """INSERT INTO live_calls(agent_id, extension, phone, caller_name, call_id, status, started_at, created_at, updated_at)
                   VALUES(?,?,?,?,?,'ringing',?,?,?)""",
                (agent_id, ext or None, phone or raw_phone, caller_name or None, call_id or None, now_str, now_str, now_str)
            )
            live_id = self.conn.execute("SELECT last_insert_rowid() id").fetchone()["id"]
            self.conn.commit()
            return self.send_json({"status": "ok", "event": "ringing", "live_id": live_id})

        elif event in ("connected", "bridgeenter", "agentconnect"):
            row = self.conn.execute("SELECT id FROM live_calls WHERE (call_id=? AND call_id IS NOT NULL) OR (phone=? AND ended_at IS NULL) ORDER BY id DESC LIMIT 1", (call_id, phone or raw_phone)).fetchone()
            if row:
                self.conn.execute("UPDATE live_calls SET status='connected', updated_at=? WHERE id=?", (now_str, row["id"]))
            else:
                self.conn.execute(
                    """INSERT INTO live_calls(agent_id, extension, phone, caller_name, call_id, status, started_at, created_at, updated_at)
                       VALUES(?,?,?,?,?,'connected',?,?,?)""",
                    (agent_id, ext or None, phone or raw_phone, caller_name or None, call_id or None, now_str, now_str, now_str)
                )
            self.conn.commit()
            return self.send_json({"status": "ok", "event": "connected"})

        elif event in ("hangup", "ended"):
            row = self.conn.execute("SELECT id, started_at FROM live_calls WHERE (call_id=? AND call_id IS NOT NULL) OR (phone=? AND ended_at IS NULL) ORDER BY id DESC LIMIT 1", (call_id, phone or raw_phone)).fetchone()
            if row:
                if not dur_seconds and row["started_at"]:
                    try:
                        st = datetime.fromisoformat(row["started_at"].replace(" ", "T"))
                        dur_seconds = max(1, int((datetime.now() - st).total_seconds()))
                    except Exception:
                        pass
                self.conn.execute(
                    "UPDATE live_calls SET status='ended', ended_at=?, duration_seconds=?, updated_at=? WHERE id=?",
                    (now_str, dur_seconds, now_str, row["id"])
                )
                self.conn.commit()
                return self.send_json({"status": "ok", "event": "hangup", "live_id": row["id"], "duration_seconds": dur_seconds})
            return self.send_json({"status": "ignored", "reason": "No active call found to hangup"})

        return self.send_json({"status": "ok", "event": event})

    def settings_sms(self, method):
        if not self.require_manager():
            return
        lang = self.lang
        msg_alert = ""

        if method == "POST":
            d = self.form()
            action = d.get("action", "")
            if action == "save_settings":
                new_settings = {
                    "enabled": "1" if d.get("sms_enabled") else "0",
                    "provider": d.get("sms_provider", "simulated"),
                    "api_key": d.get("sms_api_key", "").strip(),
                    "sender": d.get("sms_sender", "").strip(),
                    "thank_you_enabled": "1" if d.get("sms_thank_you_enabled") else "0",
                    "thank_you_template": d.get("sms_thank_you_template", "").strip(),
                    "followup_reminder_enabled": "1" if d.get("sms_followup_reminder_enabled") else "0",
                    "followup_reminder_template": d.get("sms_followup_reminder_template", "").strip(),
                }
                sms_service.save_sms_settings(self.conn, new_settings)
                msg_alert = f'<div class="alert alert-success">{t("saved_success", lang)}</div>'
            elif action == "test_send":
                test_phone = d.get("test_phone", "").strip()
                test_msg = d.get("test_message", "").strip() or "پیامک تستی سامانه CRM مرکز تماس"
                res = sms_service.send_sms(self.conn, test_phone, test_msg, sms_type="test_manual", async_mode=False)
                if res.get("success"):
                    msg_alert = f'<div class="alert alert-success">✅ پیامک تست ارسال شد ({res.get("info")})</div>'
                else:
                    msg_alert = f'<div class="alert alert-danger">❌ خطا در ارسال پیامک: {res.get("info") or res.get("reason")}</div>'

        cur = sms_service.get_sms_settings(self.conn)
        provider_opts = "".join([
            f'<option value="{p}" {"selected" if cur["provider"]==p else ""}>{lbl}</option>'
            for p, lbl in [
                ("simulated", "شبیه‌ساز داخلی (رایگان / بدون هزینه تستی)"),
                ("kavenegar", "کاوانگار (Kavenegar REST API)"),
                ("farazsms", "فراز اس‌ام‌اس / IPPanel"),
                ("melipayak", "ملی پیامک (MeliPayak)"),
                ("custom_webhook", "وب‌هوک اختصاصی (Custom HTTP Webhook)")
            ]
        ])

        logs = self.conn.execute("SELECT * FROM sms_logs ORDER BY id DESC LIMIT 50").fetchall()
        log_rows = []
        for r in logs:
            st_pill = '<span class="pill status-done">ارسال شد</span>' if r["status"] == "sent" else ('<span class="pill status-open">شبیه‌سازی</span>' if r["status"] == "simulated" else '<span class="pill status-cancelled">ناموفق</span>')
            created_disp = format_date_display(r["created_at"], lang, with_time=True)
            log_rows.append(f"""
            <tr>
                <td>#{r["id"]}</td>
                <td><strong>{esc(r["phone"])}</strong></td>
                <td>{esc(r["message"])}</td>
                <td><span class="pill">{r["sms_type"]}</span></td>
                <td>{st_pill}</td>
                <td><small>{created_disp}</small></td>
            </tr>
            """)

        body = f"""
        <div class="top">
            <h2>📱 {t("sms_settings", lang)}</h2>
        </div>
        {msg_alert}

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px">
            <div class="panel">
                <h3>⚙️ پیکربندی درگاه پیامک</h3>
                <form method="post" action="/settings/sms">
                    <input type="hidden" name="action" value="save_settings">
                    <div style="margin-bottom:12px">
                        <label style="display:inline-flex;align-items:center;gap:8px;font-weight:600">
                            <input type="checkbox" name="sms_enabled" {"checked" if cur["enabled"] else ""}> فعال‌سازی ارسال خودکار پیامک
                        </label>
                    </div>
                    <label>ارائه‌دهنده سرویس (Provider):
                        <select name="sms_provider">{provider_opts}</select>
                    </label>
                    <label style="margin-top:8px">کلید وب‌سرویس / توکن (API Key):
                        <input type="text" name="sms_api_key" value="{esc(cur['api_key'])}" placeholder="API Key / Token...">
                    </label>
                    <label style="margin-top:8px">شماره خط اختصاصی (Sender Line):
                        <input type="text" name="sms_sender" value="{esc(cur['sender'])}" placeholder="مثال: 10008888 یا 5000...">
                    </label>
                    
                    <hr style="margin:16px 0;border:none;border-top:1px solid var(--line)">
                    
                    <div style="margin-bottom:8px">
                        <label style="display:inline-flex;align-items:center;gap:8px">
                            <input type="checkbox" name="sms_thank_you_enabled" {"checked" if cur["thank_you_enabled"] else ""}> ارسال پیامک تشکر بعد از ثبت تماس
                        </label>
                    </div>
                    <label>متن الگوی پیامک تشکر:
                        <textarea name="sms_thank_you_template" rows="2">{esc(cur['thank_you_template'])}</textarea>
                        <small class="muted">متغیرها: <code>{{name}}</code> نام مخاطب | <code>{{call_id}}</code> شماره پیگیری تماس</small>
                    </label>

                    <div style="margin:12px 0 8px">
                        <label style="display:inline-flex;align-items:center;gap:8px">
                            <input type="checkbox" name="sms_followup_reminder_enabled" {"checked" if cur["followup_reminder_enabled"] else ""}> ارسال پیامک یادآوری پیگیری
                        </label>
                    </div>
                    <label>متن الگوی پیامک پیگیری:
                        <textarea name="sms_followup_reminder_template" rows="2">{esc(cur['followup_reminder_template'])}</textarea>
                        <small class="muted">متغیرها: <code>{{name}}</code> نام مخاطب | <code>{{reason}}</code> موضوع | <code>{{due_date}}</code> تاریخ پیگیری</small>
                    </label>

                    <button type="submit" class="button primary" style="margin-top:16px">💾 {t("save", lang)}</button>
                </form>
            </div>

            <div class="panel">
                <h3>🧪 تست ارسال پیامک فوری</h3>
                <form method="post" action="/settings/sms">
                    <input type="hidden" name="action" value="test_send">
                    <label>شماره تلفن همراه مقصد:
                        <input type="text" name="test_phone" placeholder="مثال: 09106827218" required>
                    </label>
                    <label style="margin-top:10px">متن پیامک آزمایشی:
                        <textarea name="test_message" rows="3">این یک پیامک آزمایشی از سامانه پاسخگویی و ثبت اطلاعات مرکز تماس می‌باشد.</textarea>
                    </label>
                    <button type="submit" class="button secondary" style="margin-top:14px">📤 ارسال پیامک تست</button>
                </form>

                <div class="panel" style="margin-top:20px;background:var(--bg)">
                    <h4 style="margin-top:0">💡 راهنمای اتصال:</h4>
                    <p style="font-size:0.85rem;margin-bottom:6px">• در حالت <strong>شبیه‌ساز (Simulated)</strong> بدون نیاز به پنل یا هزینه، پیامک‌ها در جدول زیر لاگ می‌شوند.</p>
                    <p style="font-size:0.85rem;margin-bottom:6px">• برای پنل‌های کاوانگار، فراز اس‌ام‌اس یا ملی‌پیامک، کلید و خط ارائه‌دهنده را وارد کنید.</p>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>📑 آخرین پیامک‌های ارسالی ({len(logs)})</h3>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>شماره تماس</th>
                            <th>متن پیامک</th>
                            <th>نوع پیامک</th>
                            <th>وضعیت</th>
                            <th>زمان ارسال</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(log_rows) if log_rows else '<tr><td colspan="6" style="text-align:center;opacity:0.6">هنوز پیامکی ارسال نشده است.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>
        """
        self.send_html(body, t("sms_settings", lang))

    def backup_db(self):
        if not self.require_manager():
            return
        try:
            self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crm_backup_{ts}.sqlite3"
            with open(DB_PATH, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/x-sqlite3")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_html(f"<h1>Backup failed</h1><p>{esc(str(e))}</p>", status=500)

    def export_daily_report(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)

        from_str = self.query.get("from_date", [""])[0].strip()
        to_str = self.query.get("to_date", [""])[0].strip()
        preset = self.query.get("preset", [""])[0].strip()

        if preset == "today":
            date_from = date.today().isoformat()
            date_to = date.today().isoformat()
        elif preset == "7days":
            date_from = (date.today() - timedelta(days=7)).isoformat()
            date_to = date.today().isoformat()
        elif preset == "30days":
            date_from = (date.today() - timedelta(days=30)).isoformat()
            date_to = date.today().isoformat()
        elif preset == "all":
            date_from = "2000-01-01"
            date_to = "2099-12-31"
        else:
            date_from = parse_date_input(from_str, False) if from_str else "2000-01-01"
            date_to = parse_date_input(to_str, False) if to_str else "2099-12-31"

        if date_to < date_from:
            date_from, date_to = date_to, date_from

        rows = self.conn.execute(
            f"""SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, 
                       u.name agent, p.name project_name, cl.call_started_at, cl.call_duration_seconds, 
                       cl.satisfaction_score, cl.satisfaction_notes, cl.qa_score, cl.notes, cl.created_at
               FROM call_logs cl
               JOIN customers c ON c.id=cl.customer_id
               LEFT JOIN users u ON u.id=cl.agent_id
               LEFT JOIN projects p ON p.id=cl.project_id
               WHERE 1=1{agent_filter} 
                 AND (
                   substr(COALESCE(cl.call_started_at, cl.created_at), 1, 10) BETWEEN ? AND ?
                   OR substr(cl.created_at, 1, 10) BETWEEN ? AND ?
                 )
               ORDER BY cl.created_at DESC""",
            agent_params + (date_from, date_to, date_from, date_to)
        ).fetchall()
        headers = ["ID", t("customer_name", lang), t("primary_phone", lang), t("call_type", lang), t("call_topic", lang), t("operator", lang), t("projects", lang), t("time", lang), t("call_duration", lang), t("satisfaction_score", lang), t("satisfaction_notes", lang), t("qa_score", lang), t("call_notes", lang), t("date", lang)]
        return self.csv_export(rows, headers, f"calls_report_{date_from}_to_{date_to}")

    def export_project_calls(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)

        from_str = self.query.get("from_date", [""])[0].strip()
        to_str = self.query.get("to_date", [""])[0].strip()
        date_from = parse_date_input(from_str, False) if from_str else "2000-01-01"
        date_to = parse_date_input(to_str, False) if to_str else "2099-12-31"
        if date_to < date_from:
            date_from, date_to = date_to, date_from

        pid = self.query.get("project_id", [""])[0].strip()
        proj_filter = " AND cl.project_id=?" if pid else ""
        proj_params = (pid,) if pid else ()

        rows = self.conn.execute(
            f"""SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, u.name agent, p.name project_name, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
               FROM call_logs cl
               JOIN customers c ON c.id=cl.customer_id
               LEFT JOIN users u ON u.id=cl.agent_id
               LEFT JOIN projects p ON p.id=cl.project_id
               WHERE 1=1{agent_filter}{proj_filter}
                 AND (
                   substr(COALESCE(cl.call_started_at, cl.created_at), 1, 10) BETWEEN ? AND ?
                   OR substr(cl.created_at, 1, 10) BETWEEN ? AND ?
                 )
               ORDER BY p.name, cl.created_at DESC""",
            agent_params + proj_params + (date_from, date_to, date_from, date_to)
        ).fetchall()
        headers = ["ID", t("customer_name", lang), t("primary_phone", lang), t("call_type", lang), t("call_topic", lang), t("operator", lang), t("projects", lang), t("time", lang), t("call_duration", lang), t("call_notes", lang), t("date", lang)]
        return self.csv_export(rows, headers, "project_calls")

    def export_project_member_calls(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)

        from_str = self.query.get("from_date", [""])[0].strip()
        to_str = self.query.get("to_date", [""])[0].strip()
        date_from = parse_date_input(from_str, False) if from_str else "2000-01-01"
        date_to = parse_date_input(to_str, False) if to_str else "2099-12-31"
        if date_to < date_from:
            date_from, date_to = date_to, date_from

        rows = self.conn.execute(
            f"""SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, u.name agent, p.name project, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
               FROM call_logs cl
               JOIN customers c ON c.id=cl.customer_id
               LEFT JOIN users u ON u.id=cl.agent_id
               LEFT JOIN projects p ON p.id=cl.project_id
               WHERE 1=1{agent_filter}
                 AND (
                   substr(COALESCE(cl.call_started_at, cl.created_at), 1, 10) BETWEEN ? AND ?
                   OR substr(cl.created_at, 1, 10) BETWEEN ? AND ?
                 )
               ORDER BY u.name, cl.created_at DESC""",
            agent_params + (date_from, date_to, date_from, date_to)
        ).fetchall()
        headers = ["ID", t("customer_name", lang), t("primary_phone", lang), t("call_type", lang), t("call_topic", lang), t("operator", lang), t("projects", lang), t("time", lang), t("call_duration", lang), t("call_notes", lang), t("date", lang)]
        return self.csv_export(rows, headers, "member_calls")

    def export_project_detail(self):
        lang = self.lang
        is_manager = self.current_user["role"] == "manager"
        uid = self.current_user["id"]
        agent_filter = "" if is_manager else " AND cl.agent_id=?"
        agent_params = () if is_manager else (uid,)
        pid = self.query.get("project_id", [""])[0].strip()
        if not pid:
            return self.send_html("<p>Missing project_id.</p>", status=422)
        rows = self.conn.execute(
            f"""SELECT cl.id, c.full_name, c.primary_phone, cl.call_type, cl.problem_type, u.name agent, cl.call_started_at, cl.call_duration_seconds, cl.notes, cl.created_at
               FROM call_logs cl
               JOIN customers c ON c.id=cl.customer_id
               LEFT JOIN users u ON u.id=cl.agent_id
               WHERE cl.project_id=?{agent_filter}
               ORDER BY cl.created_at DESC""",
            (pid,) + agent_params
        ).fetchall()
        headers = ["ID", t("customer_name", lang), t("primary_phone", lang), t("call_type", lang), t("call_topic", lang), t("operator", lang), t("time", lang), t("call_duration", lang), t("call_notes", lang), t("date", lang)]
        return self.csv_export(rows, headers, f"project_{pid}_details")

    def export_follow_ups(self):
        lang = self.lang
        from_str = self.query.get("from_date", [""])[0].strip()
        to_str = self.query.get("to_date", [""])[0].strip()
        date_from = parse_date_input(from_str, False) if from_str else "2000-01-01"
        date_to = parse_date_input(to_str, False) if to_str else "2099-12-31"
        if date_to < date_from:
            date_from, date_to = date_to, date_from

        rows = self.conn.execute(
            f"""SELECT f.id, c.full_name, c.primary_phone, f.reason, f.priority, f.status, u.name agent, cu.name creator, f.due_at, f.completed_at, f.notes, f.created_at
               FROM follow_ups f
               JOIN customers c ON c.id=f.customer_id
               LEFT JOIN users u ON u.id=f.assigned_agent_id
               LEFT JOIN users cu ON cu.id=f.created_by
               WHERE (
                   substr(COALESCE(f.due_at, f.created_at), 1, 10) BETWEEN ? AND ?
                   OR substr(f.created_at, 1, 10) BETWEEN ? AND ?
               )
               ORDER BY f.created_at DESC""",
            (date_from, date_to, date_from, date_to)
        ).fetchall()
        headers = ["ID", t("customer_name", lang), t("primary_phone", lang), t("followup_reason", lang), t("priority", lang), t("status", lang), t("operator", lang), "Creator", t("due_deadline", lang), "Completed At", t("call_notes", lang), t("date", lang)]
        return self.csv_export(rows, headers, "follow_ups")

    def csv_export(self, rows, headers, filename):
        lang = self.lang
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(headers)
        if not rows:
            w.writerow([t("no_records_found", lang, "No records found for the selected criteria.")] + [""] * (len(headers) - 1))
        else:
            _LABEL_KEYS = {"call_type", "problem_type", "source", "status", "priority", "stage", "registration_status", "note_type", "role"}
            _DATE_KEYS = {"call_started_at", "created_at", "completed_at", "due_at", "registration_date", "last_contacted_at", "next_follow_up_at", "updated_at", "expected_completion_date", "update_date"}
            keys = rows[0].keys()
            for r in rows:
                row_vals = []
                for k in keys:
                    val = str(r[k] or "")
                    if k in _LABEL_KEYS:
                        val = label_text(val, lang)
                    if k in _DATE_KEYS and r[k]:
                        val = format_date_display(r[k], lang, with_time=True)
                    if "duration" in k or "total_sec" in k or "avg_sec" in k:
                        try:
                            secs = int(r[k] or 0)
                            val = str(round(secs / 60, 1))
                        except Exception:
                            pass
                    row_vals.append(val)
                w.writerow(row_vals)
        # Prepend UTF-8 BOM so Excel opens Persian, Arabic, Russian & English perfectly
        data = ("\ufeff" + buf.getvalue()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename={filename}.csv")
        self.send_header("Content-Length", str(len(data)))
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

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    init_db()
    host = os.environ.get("CRM_HOST", "0.0.0.0")
    port = int(os.environ.get("CRM_PORT", 8000))
    srv = ThreadingHTTPServer((host, port), App)

    banner = [
        "=" * 60,
        "   CallCenter CRM v2.0 - Multilingual & Enhanced Edition",
        "   Languages: Persian (fa), English (en), Arabic (ar), Russian (ru)",
        "=" * 60,
        f" [Local URL]  http://127.0.0.1:{port}",
    ]
    ips = _local_ips()
    if ips:
        for ip in ips:
            banner.append(f" [Network URL] http://{ip}:{port}")
    banner.append("=" * 60)
    for line in banner:
        print(line, flush=True)

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
