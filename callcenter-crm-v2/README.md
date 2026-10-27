# CallCenter CRM v2.0 - Enterprise Edition
### سامانه جامع و هوشمند CRM مرکز تماس و پاسخگویی سازمانی

<div align="center">

[**فارسی (Persian)**](#-راهنمای-فارسی) • [**English**](#-english-manual) • [**العربية (Arabic)**](#-دليل-الاستخدام-بالعربية) • [**Русский (Russian)**](#-руководство-на-русском)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform: Windows / Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)]()
[![Multi-Language](https://img.shields.io/badge/Languages-FA%20%7C%20EN%20%7C%20AR%20%7C%20RU-orange.svg)]()

> 👨‍💻 **Developer / سازنده:** Amirhossein Karami (امیرحسین کرمی)  
> 📞 **Phone / شماره تماس:** `+98 910 682 7218` / `09106827218`

</div>

---

## 🌐 Language Selection / انتخاب زبان

- 🇮🇷 [مشاهده راهنمای کامل به زبان فارسی](#-راهنمای-فارسی)
- 🇬🇧 [Read the Full Documentation in English](#-english-manual)
- 🇸🇦 [اقرأ الدليل الكامل باللغة العربية](#-دليل-الاستخدام-بالعربية)
- 🇷🇺 [Читать руководство на русском языке](#-руководство-на-русском)

---

<a name="-english-manual"></a>
## 🇬🇧 English Manual

CallCenter CRM v2.0 is an enterprise-grade, lightweight, and modern contact center management system designed for high concurrency, zero client-side dependencies, and seamless operator workflows.

### 🌟 Key Features

1. **SMS Gateway Integration:**
   - Automated thank-you SMS containing reference tracking numbers dispatched upon call completion.
   - Automated follow-up task reminder alerts sent to customer phone numbers.
   - Built-in providers: **Kavenegar**, **FarazSMS (IPPanel)**, **MeliPayak**, **Custom Webhooks**, and a **Free Offline Simulator**.
   - Accessible via `/settings/sms` with direct test dispatch and delivery logs.

2. **VoIP Screen-Pop & PBX Bridge (3CX, Asterisk, Issabel):**
   - Instant operator alert banner with caller ID when phone rings.
   - Audio chime alert rendered via Web Audio API.
   - Auto-fills customer phone and retrieves history without manual search.
   - Auto-calculates call duration upon hangup.
   - Standalone PBX bridge script `voip_bridge.py` supporting 3CX webhooks and Asterisk AMI (Port 5038).

3. **Automated Nightly Backups:**
   - Non-blocking online SQLite backups using `wal_checkpoint(TRUNCATE)` and SQLite Online Backup API.
   - 30-day automatic retention cleanup policy.
   - Windows Task Scheduler integration for automated runs at 02:00 AM (`setup-scheduled-backup.bat`).

4. **CSAT (Customer Satisfaction) & QA Quality Auditing:**
   - 1-to-5 star CSAT rating input on call records.
   - Supervisor QA audit score (0-100%) and feedback in detail view (`/call-logs/<id>`).
   - Analytics dashboard on `/reports` with satisfaction distribution and agent leaderboard.
   - CSAT and QA metrics included in Excel/CSV exports.

5. **True Multilingual UI (4 Languages):**
   - 🇮🇷 **Persian (fa)** - RTL with Jalali (Shamsi) calendar.
   - 🇬🇧 **English (en)** - LTR with Gregorian calendar.
   - 🇸🇦 **Arabic (ar)** - RTL with Arabic localization.
   - 🇷🇺 **Russian (ru)** - LTR with Russian localization.

6. **Robust Date Range Filtering & Excel Export:**
   - Accurate dual calendar parsing (Jalali & Gregorian) supporting Persian digits (`۰-۹`).
   - One-click range presets (Today, 7 Days, 30 Days, All Time).
   - UTF-8 BOM encoding for clean display in Microsoft Excel without character distortion.

### 🚀 Quick Start (Windows)

1. **Run the CRM Server:**
   Double-click `start-crm.bat` or run in terminal:
   ```cmd
   python app.py
   ```
   Open browser at: `http://127.0.0.1:8000`

2. **Default Accounts:**
   - **Administrator:** `admin@crm.local` / `admin123`
   - **Agent / Operator:** `agent@crm.local` / `password123`

3. **Run VoIP Simulator (Optional):**
   ```cmd
   start-voip-bridge.bat
   ```

4. **Run Instant Backup:**
   ```cmd
   backup-now.bat
   ```

---

<a name="-راهنمای-فارسی"></a>
## 🇮🇷 راهنمای فارسی

نسخه ارتقا یافته، سازمانی و بازطراحی‌شده سامانه CRM مرکز تماس و پاسخگویی با معماری سبُک، دیتابیس بهینه WAL Mode، بدون نیاز به نصب نرم‌افزارهای جانبی روی کلاینت‌ها و مناسب برای استفاده شبکه‌ای.

### 🌟 قابلیت‌های برجسته نسخه Enterprise

1. **📱 سامانه و درگاه پیامک خودکار (SMS Gateway):**
   - **تنظیمات کامل در منوی مدیریت (`/settings/sms`):** فعال/غیرفعال‌سازی ارسال پیامک با یک کلیک.
   - **پشتیبانی از پنل‌ها:** کاوه‌نگار (Kavenegar)، فراز اس‌ام‌اس (FarazSMS / IPPanel)، ملی‌پیامک (MeliPayak)، وب‌هوک اختصاصی و شبیه‌ساز رایگان داخلی.
   - **ارسال خودکار پیامک تشکر و کد پیگیری:** بلافاصله پس از ثبت مکالمه با مخاطب.
   - **ارسال پیامک یادآوری پیگیری:** در زمان ثبت موعد پیگیری به همراه تاریخ و موضوع.
   - **تست ارسال مستقیم:** امکان ارسال آزمایشی به شماره دلخواه و مشاهده ۵۰ پیامک اخیر.

2. **📞 پاپ‌آپ تماس و اتصال به سانترال تلفنی (VoIP Screen-Pop):**
   - **پشتیبانی از 3CX، Asterisk و Issabel:** به همراه اسکریپت واسط `voip_bridge.py`.
   - **پاپ‌آپ خودکار پرونده مشتری:** پخش ملایم صدای زنگ، نمایش بنر تماس ورودی با نام و شماره، جستجوی خودکار سوابق مشتری بدون نیاز به تایپ، و ثبت خودکار مدت مکالمه پس از قطع تلفن.
   - **شبیه‌ساز داخلی:** اجرای آزمایشی با `start-voip-bridge.bat` بدون نیاز به اتصال فیزیکی سانترال.

3. **💾 پشتیبان‌گیری خودکار شبانه (Automated Nightly Backup):**
   - ماژول اختصاصی `backup_manager.py` با بهره‌گیری از SQLite Online Backup API بدون قفل شدن دیتابیس.
   - سیاست نگهداری ۳۰ روزه و پاکسازی خودکار نسخه‌های قدیمی‌تر.
   - ثبت تسک خودکار در Task Scheduler ویندوز با اجرای فایل `setup-scheduled-backup.bat` (هر شب ساعت ۰۲:۰۰).

4. **🌟 ارزیابی رضایت مشتریان و کیفیت اپراتور (CSAT & QA):**
   - ثبت امتیاز رضایت ۱ تا ۵ ستاره به همراه بازخورد مخاطب.
   - ممیزی کیفی مکالمه توسط سرپرست (۰ تا ۱۰۰٪) در صفحه جزئیات تماس (`/call-logs/<id>`).
   - داشبورد تحلیلی با نمودار میله‌ای و جدول مقایسه عملکرد کیفی اپراتورها در صفحه گزارش‌ها (`/reports`).
   - درج خودکار امتیازها در خروجی‌های اکسل.

5. **🌐 پشتیبانی کامل از ۴ زبان:**
   - 🇮🇷 **فارسی (fa):** راست‌چین (RTL) با تقویم شمسی جلالی.
   - 🇬🇧 **انگلیسی (en):** چپ‌چین (LTR) با تقویم استاندارد میلادی.
   - 🇸🇦 **عربی (ar):** راست‌چین (RTL) با تقویم و واژگان رسمی عربی.
   - 🇷🇺 **روسی (ru):** چپ‌چین (LTR) با زبان استاندارد روسی.

6. **📊 اصلاح قطعی باگ فیلتر و خروجی اکسل:**
   - پشتیبانی بی‌نقص از تاریخ‌های شمسی و میلادی و اعداد فارسی (`۰-۹`).
   - دکمه‌های بازه سریع (امروز، ۷ روز اخیر، ۳۰ روز اخیر، همه).
   - انکودینگ UTF-8 BOM جهت نمایش خوانا و بدون به‌هم‌ریختگی در نرم‌افزار اکسل.

### 🚀 نحوه اجرا در ویندوز

1. **اجرای سرور اصلی:**
   دوبار کلیک روی `start-crm.bat` یا اجرای دستور زیر:
   ```cmd
   python app.py
   ```
   ورود از مرورگر: `http://127.0.0.1:8000`

2. **حساب‌های کاربری پیش‌فرض:**
   - **مدیر:** `admin@crm.local` | رمز: `admin123`
   - **اپراتور:** `agent@crm.local` | رمز: `password123`

---

<a name="-دليل-الاستخدام-بالعربية"></a>
## 🇸🇦 دليل الاستخدام بالعربية

نظام متقدم وشامل لإدارة علاقات العملاء ومراكز الاتصال (CRM CallCenter Enterprise v2.0)، يدعم عدة لغات ويتميز بالاستقرار وسهولة الاستخدام داخل الشبكات المحلية دون الحاجة لتثبيت برامج إضافية على أجهزة الموظفين.

### 🌟 الميزات الرئيسية:
- **بوابة الرسائل القصيرة (SMS Gateway):** إرسال رسائل شكر ورقم التتبع تلقائيًا بعد إنهاء المكالمة وتذكير بالمواعيد.
- **التكامل مع السنترال الهاتفي (VoIP Screen-Pop):** نافذة منبثقة لملف العميل ورقم المتصل فور رنين الهاتف مع دعم 3CX وAsterisk.
- **النسخ الاحتياطي التلقائي (Automated Backup):** نسخ احتياطي ليلي مجدول دون توقف قاعدة البيانات وحذف النسخ القديمة تلقائيًا.
- **تقييم رضا العملاء ومراقبة الجودة (CSAT & QA):** تقييم من 1 إلى 5 نجوم للعملاء ومراجعة الجودة بنسبة 0-100% من قبل المشرفين مع لوحة تحليلات ورسوم بيانية.
- **دعم كامل لـ 4 لغات:** العربية (RTL)، الإنجليزية (LTR)، الفارسية (RTL)، والروسية (LTR).

---

<a name="-руководство-на-русском"></a>
## 🇷🇺 Руководство на русском

CallCenter CRM v2.0 — это корпоративная, легкая и современная система управления контакт-центром, разработанная для высокой производительности и удобства операторов.

### 🌟 Основные возможности:
- **SMS-шлюз:** Автоматическая отправка SMS с кодом обращения после звонка и напоминания о запланированных контактах.
- **Интеграция с телефонией (VoIP Screen-Pop):** Всплывающее окно карточки клиента при входящем звонке с поддержкой 3CX и Asterisk.
- **Автоматическое резервное копирование:** Ночной бэкап базы данных без остановки сервиса и удаление архивов старше 30 дней.
- **Оценка удовлетворенности и контроль качества (CSAT & QA):** Рейтинг 1–5 звезд от клиентов, оценка операторов супервайзером (0–100%) и аналитические графики.
- **Поддержка 4 языков:** Русский (LTR), Английский (LTR), Персиدский (RTL) и Арабский (RTL).

---

## 📁 ساختار پوشه‌ها و فایل‌ها / Directory Structure

```text
callcenter-crm-v2/
├── app.py                      # هسته اصلی سیستم و کنترلرها / Main application core
├── app.css                     # استایل شیشه‌ای مدرن / Glassmorphism UI styling
├── crm.sqlite3                 # پایگاه داده تمیز / Clean WAL SQLite database
├── sms_service.py              # ماژول پیامک هوشمند / SMS Gateway service
├── voip_bridge.py              # واسط اتصال به سانترال / VoIP 3CX & Asterisk bridge
├── backup_manager.py           # موتور پشتیبان‌گیری / Automated backup engine
├── start-crm.bat               # اجرای مستقیم در ویندوز / Windows launcher
├── backup-now.bat              # بکاپ فوری / Instant backup script
├── setup-scheduled-backup.bat  # فعال‌سازی بکاپ خودکار شبانه / Automated backup scheduler
├── backups/                    # پوشه ذخیره بکاپ‌ها / Backups directory
└── README.md                   # مستندات ۴ زبانه / Multilingual documentation
```

---

<div align="center">
  <b>CallCenter CRM v2.0 • Created with ❤️ by Amirhossein Karami</b><br>
  📞 09106827218 / +989106827218
</div>
