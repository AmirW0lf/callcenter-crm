# راهنمای اتصال مرکز تماس 3CX به CRM

این سرویس تماس‌های ارسالی از 3CX را دریافت کرده و به‌صورت خودکار در فایل `crm.sqlite3` ثبت می‌کند.

**هیچ نصبی لازم نیست.** سرویس به‌صورت یک فایل اجرایی مستقل (`3cx_bridge.exe`) ارائه می‌شود و نه به پایتون نیاز دارد و نه به هیچ پکیج اضافه‌ای. کد پایتون (`3cx_bridge.py`) هم فقط برای حالت اختیاری در دسترس است و کاملاً به کتابخانه استاندارد پایتون تکیه دارد (بدون Flask و بدون pip).

هیچ بخشی از کد قبلی پروژه تغییر نکرده است.

## فایل‌ها

| فایل | نقش |
|------|------|
| `3cx_bridge.exe` | نسخهٔ مستقل و بدون نیاز به نصب (این را اجرا کنید) |
| `start-3cx-bridge.bat` | اجرای سرویس (اگر exe بود همان را، وگرنه پایتون) |
| `3cx_bridge.py` | سرویس (فقط کتابخانه استاندارد، بدون وابستگی) |
| `build-3cx-bridge.ps1` | ساخت مجدد exe روی کامپیوتر سازنده (اختیاری) |
| `3CX_SETUP_GUIDE.md` | همین راهنما |

## اجرا

فقط روی همان کامپیوتری که `crm.sqlite3` در آن است، فایل زیر را اجرا کنید:

```
start-3cx-bridge.bat
```

سرویس به‌صورت پیش‌فرض روی پورت `8090` گوش می‌دهد. نیازی به نصب پایتون نیست.

## متغیرهای محیطی (اختیاری)

قبل از اجرا می‌توانید این متغیرها را تنظیم کنید (داخل `start-3cx-bridge.bat` هم نمونه‌شان هست):

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `BRIDGE_HOST` | `0.0.0.0` | آدرس گوش‌دادن |
| `BRIDGE_PORT` | `8090` | پورت سرویس |
| `BRIDGE_CRM_DB` | کنار فایل اجرایی `crm.sqlite3` | مسیر دیتابیس CRM |
| `BRIDGE_TOKEN` | خالی (بدون احراز هویت) | توکن امنیتی اختیاری |
| `BRIDGE_TZ_OFFSET_HOURS` | `3.5` | اختلاف ساعت محلی (ایران) |
| `BRIDGE_AGENT_MAP` | خالی | نگاشت داخلی به کاربر، مثل `101=2,102=3` |
| `BRIDGE_INCLUDE_JALALI` | `0` | اگر `1` شود تاریخ شمسی هم به یادداشت اضافه می‌شود |
| `BRIDGE_LOG` | `3cx_bridge.log` | مسیر فایل لاگ |

## آدرس Webhook

- **URL:** `http://<IP-سرور>:8090/3cx/webhook`
- **Method:** `POST`
- **Content-Type:** `application/json` یا `application/x-www-form-urlencoded` یا `application/xml` (هر سه پشتیبانی می‌شوند)
- **احراز هویت (اختیاری):** اگر `BRIDGE_TOKEN` تنظیم شده باشد، توکن را به‌صورت `?token=...` یا هدر `X-Webhook-Token` یا هدر `X-3CX-Token` بفرستید.
- **سلامت سرویس:** `GET http://<IP-سرور>:8090/health`

## نگاشت پارامترها

| مقدار در 3CX (پیشنهادی) | کلیدهای پذیرفته‌شده در سرویس | وضعیت |
|--------------------------|-------------------------------|-------|
| `CallerNumber` | `CallerNumber`, `PhoneNumber`, `From`, `CallerID` | **اجباری** |
| `CallerName` | `CallerName`, `CallerIDName`, `Name` | اختیاری |
| `CallDuration` | `CallDuration`, `Duration`, `TalkTime` | ثانیه یا `hh:mm:ss` |
| `CallStatus` | `CallStatus`, `Status`, `Disposition`, `Answered` | `Answered` / `Missed` / … |
| `Direction` | `Direction`, `CallDirection`, `Type` | `inbound` / `outbound` |
| `AgentExtension` | `AgentExtension`, `Extension`, `Agent`, `To` | داخلی اپراتور |
| `DateTime` | `DateTime`, `Timestamp`, `CallTime`, `StartTime` | زمان تماس |
| `CallID` | `CallID`, `EventID`, `HistoryID` | برای جلوگیری از تکرار |

نام کلیدها به بزرگی/کوچکی حروف حساس نیست و ساختار تودرتوی JSON/XML هم پشتیبانی می‌شود.

## نمونه بدنه JSON

```json
{
  "CallerNumber": "[CallerNumber]",
  "CallerName": "[CallerName]",
  "CallDuration": "[CallDuration]",
  "CallStatus": "[CallStatus]",
  "Direction": "[Direction]",
  "AgentExtension": "[Agent]",
  "DateTime": "[DateTime]",
  "CallID": "[CallID]"
}
```

## نمایش خودکار تماس در فرم اپراتور (Screen-Pop)

وقتی 3CX رویدادها را به بریج بفرستد، فرم «ثبت تماس جدید» در پنل اپراتور خودکار پر می‌شود:

- **به محض برقرار شدن تماس** (رویداد با `CallStatus=Established` یا `Answered`): شماره و نام تماس‌گیرنده داخل فرم نمایش داده می‌شود (اگر شماره برای مشتری قبلی باشد، با اطلاعات همان مشتری پر می‌شود).
- **پس از پایان تماس** (رویداد با `CallDuration` یا `CallStatus=Hangup`): مدت تماس خودکار در کادر «مدت تماس» نوشته می‌شود.
- رویداد شروع و پایانِ یک تماس، فقط یک ردیف در `call_logs` می‌سازد (ردیف شروع با مدت به‌روزرسانی می‌شود؛ ردیف تکراری ساخته نمی‌شود).

پیش‌نیازها:

1. داخلی 3CX باید به کاربر CRM وصل شود؛ یکی از دو راه:
   - متغیر `BRIDGE_AGENT_MAP` مثل `101=2,102=3` (داخلی = شناسه کاربر در CRM)، یا
   - در بخش «کاربران»، فیلد **تلفن** را همان داخلی بگذارید (مثل `101`).
2. بریج و CRM روی همان سیستم اجرا شوند (هر دو به یک `crm.sqlite3` دسترسی دارند).
3. پنل اپراتور هر ۲ ثانیه وضعیت تماس را چک می‌کند؛ صفحه «ثبت تماس جدید» باید باز باشد.

اگر 3CX فقط **یک** رویداد در پایان تماس (با مدت) می‌فرستد، شماره و مدت یک‌جا پر می‌شوند. برای پر شدن شماره به محض برقراری تماس، 3CX باید رویداد شروع (`Established`/`Answered`) را هم ارسال کند (در تنظیمات CRM/Webhook در 3CX رویدادها را علامت بزنید).

## آزمون سریع (PowerShell)

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8090/3cx/webhook" `
  -ContentType "application/json" `
  -Body '{"CallerNumber":"09120000000","CallerName":"مشتری نمونه","CallDuration":60,"CallStatus":"Answered","Direction":"inbound","AgentExtension":"101","DateTime":"2026-10-11 09:32:00","CallID":"test-1"}'
```

پاسخ موفق:

```json
{"status":"ok","call_log_id":123,"customer_id":45,"new_customer":true,"call_type":"incoming"}
```

## تنظیم در کنسول 3CX

1. وارد **3CX Management Console** شوید.
2. به بخش **Integrations → CRM** (و زیربخش **Call Journaling**) یا بخش **Webhooks** بروید.
3. یک Webhook/CRM Template سفارشی جدید بسازید.
4. **POST URL** را روی `http://<IP-سرور>:8090/3cx/webhook` تنظیم کنید.
5. Method را `POST` و Content-Type را `application/json` بگذارید.
6. بدنه JSON را مطابق نمونه بالا با placeholderهای 3CX بسازید.
7. ذخیره کنید و با دکمه تست یا یک تماس واقعی آزمایش کنید.
8. برای ثبت تماس‌های بی‌پاسخ، حتماً فیلد `CallStatus` را ارسال کنید (مقدار `Missed` باعث ثبت با نوع `missed` می‌شود).

> در نسخه‌های مختلف 3CX نام placeholderها ممکن است متفاوت باشد (مثل `[CallerNumber]` یا `[$Number]`). هر نامی که بفرستید کافی است یکی از کلیدهای پذیرفته‌شده در جدول بالا باشد.

## نحوه ذخیره‌سازی

- تماس در جدول `call_logs` ثبت می‌شود و در صورت نبود شماره در `customers`، مشتری جدید با `source=phone_call` و `status=new_lead` ساخته می‌شود.
- تاریخ‌ها به‌صورت میلادی `YYYY-MM-DD HH:MM:SS` ذخیره می‌شوند؛ CRM هنگام نمایش خودش آن‌ها را شمسی نشان می‌دهد. (نیازی به تبدیل در دیتابیس نیست.)
- دیتابیس با `timeout=30.0` و `PRAGMA journal_mode=WAL` و `busy_timeout=30000` باز می‌شود تا با برنامه اصلی تداخل نکند.
- اگر رویدادی تکراری ارسال شود (همان مشتری/زمان/مدت)، دوباره ثبت نمی‌شود و پاسخ `duplicate` برمی‌گردد.

## ساخت مجدد exe (فقط روی کامپیوتر سازنده)

```
powershell -ExecutionPolicy Bypass -File build-3cx-bridge.ps1
```

خروجی در `dist\3cx_bridge.exe` ساخته می‌شود. این مرحله روی کامپیوتر مشتری لازم نیست.

## عیب‌یابی

- لاگ عملیات: فایل `3cx_bridge.log` کنار فایل اجرایی.
- بررسی سلامت: `GET http://<IP-سرور>:8090/health`
- اگر پاسخ `400 caller number not found` گرفتید، نام پارامتر شماره تماس‌گیرنده را در تنظیمات 3CX اصلاح کنید.
- پورت `8090` را در فایروال ویندوز باز کنید:
  ```
  netsh advfirewall firewall add rule name="3CX Bridge" dir=in action=allow protocol=TCP localport=8090
  ```
