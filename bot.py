#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🎬 KDLIVE EXTRACTOR BOT — FINAL FIXED VERSION
✅ ID*Password or userid|token
✅ Course buttons
✅ HTML-safe truncation — no "unclosed tag" errors
✅ Fixed URLs — no trailing spaces
✅ Better error handling — API errors, message edit errors
✅ Extract videos + PDFs
✅ Send TXT file on Telegram
"""

import os, re, time, hashlib, traceback, requests, urllib3
from html import escape
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─────────────────────────────────────────────────────
# 🎨 Terminal Colors
# ─────────────────────────────────────────────────────
G, R, C, Y, W, B = "\033[92m", "\033[91m", "\033[96m", "\033[93m", "\033[0m", "\033[1m"

# ─────────────────────────────────────────────────────
# ⚙️ CONFIG — FIXED: NO TRAILING SPACES IN URLs ✅
# ─────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ✅ BASE_URL: NO trailing spaces
BASE_URL = "https://web.kdcampus.live"

# ✅ Endpoint URLs: NO trailing spaces (fixed!)
LOGIN_URL = f"{BASE_URL}/android/Usersn/login_user"
COURSES_URL = f"{BASE_URL}/android/Dashboard/get_mycourse_data_renew_new"
SUBJECTS_URL = f"{BASE_URL}/android/Dashboard/course_subject"
VIDEOS_URL = f"{BASE_URL}/android/Dashboard/course_details_video"
PDFS_URL = f"{BASE_URL}/android/Dashboard/course_details_pdf"

IMAGE_BASE = "http://kdcampus.live/uploaded/landing_images/"
API_KEY = "kdc123"

HEADERS = {
    "User-Agent": "okhttp/4.10.0",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json",
}

USERS = {}

# ─────────────────────────────────────────────────────
# 🧩 HTML HELPERS
# ─────────────────────────────────────────────────────
def h(text):
    return escape(str(text if text is not None else ""))

def pre_box(text):
    return f"<pre>{h(text)}</pre>"

def quote_box(text):
    return f"<blockquote>{text}</blockquote>"

def safe_thumb_url(image_name):
    if not image_name:
        return ""
    return IMAGE_BASE + str(image_name)

# ─────────────────────────────────────────────────────
# ✂️ HTML-SAFE TRUNCATION — FIXED ✅
# ─────────────────────────────────────────────────────
def safe_truncate_html(html_text, max_len=3800, suffix="\n\n<i>...truncated</i>"):
    if len(html_text) <= max_len:
        return html_text
    
    cut_point = html_text.rfind("</blockquote>", 0, max_len)
    if cut_point == -1:
        cut_point = html_text.rfind("\n\n", 0, max_len)
    if cut_point == -1:
        cut_point = max_len
    
    truncated = html_text[:cut_point]
    
    open_tags = []
    for tag in ['<b>', '<i>', '<u>', '<s>', '<blockquote>', '<a href']:
        open_count = truncated.count(tag)
        close_tag = tag.replace('<', '</').replace(' href', '').replace('>', '') + '>'
        close_count = truncated.count(close_tag)
        if open_count > close_count:
            open_tags.append(close_tag)
    
    for close_tag in reversed(open_tags):
        truncated += close_tag
    
    truncated += suffix
    return truncated

# ─────────────────────────────────────────────────────
# 🔐 PARSE LOGIN RESPONSE
# ─────────────────────────────────────────────────────
def parse_login_response(resp_json):
    message = resp_json.get("message", "")
    response = resp_json.get("response", "")
    code = resp_json.get("code")
    data = resp_json.get("data")

    is_success = False
    if message and "login successful" in str(message).lower():
        is_success = True
    elif str(response) == "1":
        is_success = True
    elif (code is True or str(code).lower() == "true") and data:
        is_success = True

    if is_success and data:
        userid = data.get("id")
        token = data.get("connection_key")
        name = data.get("name", "User")
        if userid and token:
            return True, str(userid), str(token), str(name), str(message)
    return False, None, None, None, str(message)

# ─────────────────────────────────────────────────────
# 🔐 TWO-STEP LOGIN — WITH BETTER ERROR HANDLING ✅
# ─────────────────────────────────────────────────────
def login(mob, pwd):
    try:
        password_hash = hashlib.sha512(pwd.encode()).hexdigest()
        payload1 = {
            "code": "", "valid_id": "", "api_key": API_KEY,
            "mobilenumber": mob, "password": password_hash
        }
        session = requests.Session()
        resp1 = session.post(LOGIN_URL, headers=HEADERS, json=payload1, timeout=15, verify=False)
        
        # ✅ Check if response is HTML error page
        if not resp1.text.strip() or resp1.text.strip().startswith("<!DOCTYPE") or resp1.text.strip().startswith("<html"):
            print(f"{R}❌ API returned HTML error page (server issue){W}")
            return None, None, None, None, "Server error - try again later"
        
        try:
            resp1_json = resp1.json()
        except Exception as e:
            print(f"{R}❌ Invalid JSON response: {e}{W}")
            print(f"Response text: {resp1.text[:200]}")
            return None, None, None, None, "Invalid server response"

        success1, uid1, tok1, name1, msg1 = parse_login_response(resp1_json)
        if success1:
            return uid1, tok1, name1, session, None

        valid_id = resp1_json.get("valid_id")
        if valid_id and resp1_json.get("response") == "0":
            payload2 = payload1.copy()
            payload2["valid_id"] = valid_id
            resp2 = session.post(LOGIN_URL, headers=HEADERS, json=payload2, timeout=15, verify=False)
            
            if not resp2.text.strip() or resp2.text.strip().startswith("<!DOCTYPE"):
                return None, None, None, None, "Server error - try again later"
            
            try:
                resp2_json = resp2.json()
            except:
                return None, None, None, None, "Invalid server response"
            
            success2, userid, token, name, message = parse_login_response(resp2_json)
            if success2:
                return userid, token, name, session, None
            else:
                return None, None, None, None, message or "Login failed"
        
        return None, None, None, None, msg1 or "Login failed"
    except Exception as e:
        traceback.print_exc()
        return None, None, None, None, str(e)

# ─────────────────────────────────────────────────────
# 💰 GET PRICE
# ─────────────────────────────────────────────────────
def get_price(item):
    price_fields = ["price", "batch_price", "selling_price", "discounted_price", "final_price"]
    mrp_fields = ["mrp", "original_price", "marked_price", "list_price"]
    price = mrp = 0
    for field in price_fields:
        val = item.get(field)
        if val not in [None, '', '0']:
            try:
                price = int(float(str(val).replace(",", "").replace("₹", "").strip()))
                break
            except: pass
    for field in mrp_fields:
        val = item.get(field)
        if val not in [None, '', '0']:
            try:
                mrp = int(float(str(val).replace(",", "").replace("₹", "").strip()))
                break
            except: pass
    return price, mrp

# ─────────────────────────────────────────────────────
# 📅 FORMAT DATE
# ─────────────────────────────────────────────────────
def format_purchase_date(purchase_date):
    if not purchase_date:
        return "N/A"
    try:
        if isinstance(purchase_date, (int, float)) and purchase_date > 1e12:
            return datetime.fromtimestamp(purchase_date/1000).strftime("%Y-%m-%d")
        elif isinstance(purchase_date, (int, float)):
            return datetime.fromtimestamp(purchase_date).strftime("%Y-%m-%d")
        elif isinstance(purchase_date, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(purchase_date, fmt).strftime("%Y-%m-%d")
                except: continue
    except: pass
    return str(purchase_date)[:20]

# ─────────────────────────────────────────────────────
# 📦 FETCH COURSES
# ─────────────────────────────────────────────────────
def get_courses(session, userid, token):
    try:
        url = f"{COURSES_URL}/{token}/{userid}/4"
        resp = session.get(url, headers=HEADERS, timeout=15, verify=False)
        
        # Check for HTML error
        if not resp.text.strip() or resp.text.strip().startswith("<!DOCTYPE"):
            return []
        
        resp_json = resp.json()
        if isinstance(resp_json, list) and len(resp_json) > 0:
            courses = []
            for item in resp_json:
                purchase_date = item.get("purchase_date") or item.get("created_date") or item.get("date") or item.get("created_at")
                days_remaining = item.get("days_remaining") or item.get("remaining_days") or item.get("validity_days") or item.get("days_left") or 0
                try: days_remaining = int(days_remaining)
                except: days_remaining = 0
                is_expired = item.get("is_expired") or item.get("expired") or item.get("is_over") or (days_remaining <= 0)
                course = {
                    "course_id": str(item.get("course_id", "")),
                    "batch_id": str(item.get("batch_id", "")),
                    "batch_name": item.get("batch_name", "Unknown"),
                    "image": item.get("banner_image_name") or item.get("course_image") or "",
                    "purchase_date": purchase_date,
                    "days_remaining": days_remaining,
                    "is_expired": bool(is_expired),
                }
                courses.append(course)
            return courses
        return []
    except Exception:
        traceback.print_exc()
        return []

# ─────────────────────────────────────────────────────
# 🌐 SAFE REQUEST
# ─────────────────────────────────────────────────────
def safe_get(session, url, headers, timeout=15, max_retries=3):
    for attempt in range(max_retries):
        try:
            return session.get(url, headers=headers, timeout=timeout, verify=False)
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
        except:
            return None
    return None

# ─────────────────────────────────────────────────────
# 🎬 EXTRACT CONTENT
# ─────────────────────────────────────────────────────
def extract_content(session, userid, token, batch_id, course_id, course_name, course_image):
    content = []
    try:
        subjects_url = f"{SUBJECTS_URL}/{token}/{userid}/{course_id}/{batch_id}"
        subjects_resp = safe_get(session, subjects_url, HEADERS)
        if not subjects_resp:
            return []
        try: subjects_data = subjects_resp.json()
        except: return []
        if isinstance(subjects_data, dict):
            subjects = subjects_data.get("subjects", subjects_data.get("data", []))
        elif isinstance(subjects_data, list):
            subjects = subjects_data
        else:
            subjects = []
        if not subjects:
            return []
        for sub in subjects:
            sid = sub.get("id")
            sub_name = sub.get("subject_name", "Unknown")
            # Videos
            try:
                vid_url = f"{VIDEOS_URL}/{token}/{userid}/{course_id}/{batch_id}/0/{sid}/0"
                videos_resp = safe_get(session, vid_url, HEADERS)
                if videos_resp and videos_resp.status_code == 200:
                    videos_data = videos_resp.json()
                    videos = videos_data.get("videos", videos_data.get("data", [])) if isinstance(videos_data, dict) else (videos_data if isinstance(videos_data, list) else [])
                    for v in videos:
                        title = v.get("content_title", "Untitled")
                        jw_id = v.get("jwplayer_id", "")
                        if jw_id:
                            content.append(f"[VIDEO] ({sub_name}) {title} : https://{jw_id}")
            except: pass
            # PDFs
            try:
                pdf_url = f"{PDFS_URL}/{token}/{userid}/{course_id}/{batch_id}/0/{sid}/0"
                pdfs_resp = safe_get(session, pdf_url, HEADERS)
                if pdfs_resp and pdfs_resp.status_code == 200:
                    pdfs_data = pdfs_resp.json()
                    pdfs = pdfs_data.get("pdfs", pdfs_data.get("data", [])) if isinstance(pdfs_data, dict) else (pdfs_data if isinstance(pdfs_data, list) else [])
                    for p in pdfs:
                        title = p.get("content_title", "Untitled")
                        file_name = p.get("file_name", "")
                        if file_name:
                            content.append(f"[PDF] ({sub_name}) {title} : https://kdcampus.live/uploaded/content_data/{file_name}")
            except: pass
            time.sleep(0.15)
        return content
    except Exception:
        traceback.print_exc()
        return []

# ─────────────────────────────────────────────────────
# 💾 SAVE TO FILE
# ─────────────────────────────────────────────────────
def save_to_file(course_name, course_image, userid_token, content, batch_id="", expiry_date="N/A"):
    if not content:
        return None
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", course_name).strip()
    short_name = safe_name[:28].strip()
    filename = f"KDLive_{short_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    image_url = safe_thumb_url(course_image)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            if image_url:
                f.write(f"🖼 Batch Thumbnail : {image_url}\n\n")
            f.write("======== ALL LINKS ========\n\n")
            for item in content:
                f.write(item + "\n")
        return filename
    except Exception:
        traceback.print_exc()
        return None

# ─────────────────────────────────────────────────────
# 🧾 BUILD COURSE HTML — LIMITED DISPLAY ✅
# ─────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────
# 🧾 BUILD COURSE HTML — COMPACT VERSION
# ─────────────────────────────────────────────────────
def build_course_list_html(courses, max_display=15):
    """Build compact course list with blockquotes"""
    parts = []
    parts.append("📚 <b>List of Batches You Have :</b>\n")
    
    total = len(courses)
    display_courses = courses[:max_display]
    
    for c in display_courses:
        batch_id = h(c.get("batch_id", ""))
        batch_name = h(c.get("batch_name", "Unknown"))
        thumb = safe_thumb_url(c.get("image", ""))
        days_remaining = c.get("days_remaining", 0)
        is_expired = c.get("is_expired", False)
        
        # Compact format - single line per batch
        if is_expired or days_remaining <= 0:
            batch_info = f"📦 {batch_id} | {batch_name} | ⌛ EXPIRED"
        else:
            batch_info = f"📦 {batch_id} | {batch_name} | ⌛ {days_remaining} days"
        
        if thumb:
            batch_info += f' | 🖼 <a href="{h(thumb)}">Thumb</a>'
        
        parts.append(quote_box(batch_info))
    
    if total > max_display:
        remaining = total - max_display
        parts.append(f"\n<i>... and {remaining} more. Use buttons below 👇</i>")
    
    parts.append("\n👇 Niche buttons se batch select karo")
    return "\n".join(parts)  # Single \n instead of \n\n for less spacing
# ─────────────────────────────────────────────────────
# 🔘 BUTTONS
# ─────────────────────────────────────────────────────
def build_course_buttons(courses):
    rows = []
    for idx, c in enumerate(courses, 1):
        name = c.get("batch_name", "Unknown")
        short_name = name[:45] + "..." if len(name) > 45 else name
        rows.append([InlineKeyboardButton(short_name, callback_data=f"extract::{idx-1}")])
    return InlineKeyboardMarkup(rows)

# ─────────────────────────────────────────────────────
# 🤖 HANDLERS
# ─────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 <b>KDLIVE EXTRACTOR BOT</b>\n\n"
        "Send credentials in any one format:\n"
        "1. <code>ID*Password</code>\n"
        "2. <code>userid|token</code>\n\n"
        "Example:\n"
        "<pre>9163xxxxxx*anil@xxx</pre>"
        "<pre>4401xx|3a9xxc0axx67d1ccccbxxxbe4c3ee6b6</pre>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def handle_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user_id = update.effective_user.id
    cred_input = update.message.text.strip()
    userid = token = None
    name = "User"
    session = requests.Session()
    wait_msg = await update.message.reply_text("🔄 Processing...")
    
    if "|" in cred_input and "*" not in cred_input:
        parts = cred_input.split("|", 1)
        if len(parts) == 2:
            userid, token = parts[0].strip(), parts[1].strip()
        else:
            await wait_msg.edit_text("❌ Invalid token format")
            return
    elif "*" in cred_input:
        mob, pwd = cred_input.split("*", 1)
        mob, pwd = mob.strip(), pwd.strip()
        if not mob or not pwd:
            await wait_msg.edit_text("❌ Empty credentials")
            return
        userid, token, name, session, error = login(mob, pwd)
        if not userid or not token:
            # ✅ Use reply_text instead of edit_text to avoid "message not found" error
            await wait_msg.delete()
            await update.message.reply_text(f"❌ Login failed: {error or 'Invalid credentials'}\n\n<i>Server may be busy. Try again in 1-2 minutes.</i>", parse_mode=ParseMode.HTML)
            return
    else:
        await wait_msg.edit_text("❌ Invalid format\nUse:\nID*Password\nor\nuserid|token")
        return
    
    userid_token = f"{userid}|{token}"
    courses = get_courses(session, userid, token)
    if not courses:
        await wait_msg.delete()
        await update.message.reply_text("⚠️ No courses found\n\n<i>Server may be busy or account has no active batches.</i>", parse_mode=ParseMode.HTML)
        return
    
    USERS[user_id] = {
        "userid": userid, "token": token, "name": name,
        "session": session, "userid_token": userid_token, "courses": courses,
    }
    
    # Build final HTML message
    final_html = (
        "📱 <b>App Name: KD-Live</b>\n\n"
        "✅ <b>Logged in Successfully</b> 👨‍💻 with 🔑 Credential :\n\n"
        f"{pre_box(cred_input)}"
        "👤 <b>UserId | Token</b>\n"
        f"{pre_box(userid_token)}\n\n"
        f"{build_course_list_html(courses)}"
    )
    
    # Safe truncate HTML
    final_html = safe_truncate_html(final_html, max_len=3800)
    
    thumb = safe_thumb_url(courses[0].get("image", "")) if courses else ""
    reply_markup = build_course_buttons(courses)
    
    # ✅ Delete wait_msg first, then send new message (avoids edit errors)
    try:
        await wait_msg.delete()
    except:
        pass
    
    # Try send with photo
    media_sent = False
    if thumb:
        try:
            await update.message.reply_photo(
                photo=thumb, caption=final_html,
                parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
            media_sent = True
        except Exception as e:
            print(f"⚠️ Photo send failed: {e}")
            media_sent = False
    
    # Fallback: send as text
    if not media_sent:
        try:
            await update.message.reply_text(
                final_html, parse_mode=ParseMode.HTML, reply_markup=reply_markup
            )
        except Exception as e:
            print(f"⚠️ Text send failed: {e}")
            # Last resort: send batches as document
            await update.message.reply_text("⚠️ Too many batches! Sending list as file...")
            batch_list = "\n".join([
                f"{c.get('batch_name')}: {c.get('days_remaining', 0)} days"
                for c in courses[:50]
            ])
            batch_file = f"batches_{userid}_{int(time.time())}.txt"
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write(f"User: {userid_token}\nTotal Batches: {len(courses)}\n\n{batch_list}")
            await update.message.reply_document(
                document=batch_file,
                caption=f"📋 All {len(courses)} batches (file attached)\n👇 Use buttons to extract"
            )
            try: os.remove(batch_file)
            except: pass

async def handle_course_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.from_user:
        return
    user_id = query.from_user.id
    user_data = USERS.get(user_id)
    if not user_data:
        try:
            await query.edit_message_caption(caption="❌ Session expired. Send credentials again.")
        except:
            await query.message.reply_text("❌ Session expired. Send credentials again.")
        return
    try:
        idx = int(query.data.split("::", 1)[1])
    except:
        try:
            await query.edit_message_caption(caption="❌ Invalid selection")
        except:
            await query.message.reply_text("❌ Invalid selection")
        return
    courses = user_data.get("courses", [])
    if idx < 0 or idx >= len(courses):
        try:
            await query.edit_message_caption(caption="❌ Invalid course index")
        except:
            await query.message.reply_text("❌ Invalid course index")
        return
    selected = courses[idx]
    course_id = selected.get("course_id", "")
    batch_id = selected.get("batch_id", "")
    course_name = selected.get("batch_name", "Unknown_Course")
    course_image = selected.get("image", "")
    purchase_date = format_purchase_date(selected.get("purchase_date"))
    
    # ✅ Use reply_text instead of edit to avoid errors
    try:
        await query.edit_message_caption(caption=f"⏳ Extracting...\n\n📘 {course_name}", reply_markup=None)
    except:
        try:
            await query.message.reply_text(f"⏳ Extracting...\n\n📘 {course_name}")
        except:
            pass
    
    content = extract_content(user_data["session"], user_data["userid"], user_data["token"],
                              batch_id, course_id, course_name, course_image)
    if not content:
        await query.message.reply_text("⚠️ No content extracted.\n\n<i>Course may be empty or server error.</i>", parse_mode=ParseMode.HTML)
        return
    
    filename = save_to_file(course_name, course_image, user_data["userid_token"], content,
                            batch_id=batch_id, expiry_date=purchase_date)
    if not filename or not os.path.exists(filename):
        await query.message.reply_text("❌ Failed to save TXT file")
        return
    
    total_videos = sum(1 for x in content if x.startswith("[VIDEO]"))
    total_pdfs = sum(1 for x in content if x.startswith("[PDF]"))
    thumb = safe_thumb_url(course_image)
    
    batch_details = [
        f"🏷 Batch Id : {h(batch_id)}",
        f"📚 Batch Name : {h(course_name)}",
        f"🗓 Expiry Date : {h(purchase_date)}",
        f'🖼 Batch Thumbnail : <a href="{h(thumb)}">Thumbnail</a>' if thumb else "🖼 Batch Thumbnail : N/A"
    ]
    summary_details = [
        f"🔢 Total Number of Links : {len(content)}",
        f"🎥 Total Videos : {total_videos}",
        f"📄 Total PDFs : {total_pdfs}"
    ]
    caption_lines = [
        "📱 <b>App Name: KD-Live</b>", "",
        "======= BATCH DETAILS =======", "",
        "\n".join(batch_details), "",
        "======== <b>LINK SUMMARY</b> ========", "",
        "\n".join(summary_details), "",
        f"🕒 <b>Generated On</b> : {h(datetime.now().strftime('%d-%m-%Y %I:%M:%S %p'))}"
    ]
    caption = "\n".join(caption_lines)
    if len(caption) > 1000:
        caption = caption[:1000]
    
    with open(filename, "rb") as f:
        await query.message.reply_document(
            document=f, filename=os.path.basename(filename),
            caption=caption, parse_mode=ParseMode.HTML
        )
    try: os.remove(filename)
    except: pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("⚠️ Bot Error:")
    traceback.print_exception(None, context.error, context.error.__traceback__)

# ─────────────────────────────────────────────────────
# 🚀 MAIN
# ─────────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN env variable not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_course_select, pattern=r"^extract::"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_credentials))
    print("🚀 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Stopped by user\n")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
