# khan_bot.py
# Khan Global Studies - Telegram Bot (Strict & Clean)
# ✅ No Auto-Reply Loop | ✅ Strict Input | ✅ Clean Menu | ✅ Thumbnail Links

import requests
import json
import gzip
import zlib
import re
import os
import asyncio
import tempfile
import traceback
from datetime import datetime
from collections import defaultdict

from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== CONFIG ==================
API_ID = int(os.getenv("API_ID", "29136894"))
API_HASH = os.getenv("API_HASH", "88f3d07b70de48ac1fc13866b0c9e562")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8634130308:AAGRbg2475S8YvmfZfY5QH2cw6wklfkpMdo")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003887045145"))
OWNER_ID = int(os.getenv("OWNER_ID", "7566796700"))
# ============================================

app = Client(
    "khan_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=50,
    sleep_threshold=60
)

API_BASE = "https://api.khanglobalstudies.com"
APP_BASE = "https://app.khanglobalstudies.com"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Origin": APP_BASE,
    "Referer": APP_BASE + "/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

user_sessions = {}

# ================== HELPERS ==================
def fix_thumb(url):
    if not url: return None
    if url.startswith('/'): return f"{APP_BASE}{url}"
    return url if url.startswith('http') else None

def smart_decompress(content):
    if not content: return ""
    if isinstance(content, str): return content
    if content[:2] == b'\x1f\x8b':
        try: return gzip.decompress(content).decode('utf-8', errors='ignore')
        except: pass
    if content[:2] in [b'\x78\x9c', b'\x78\x01', b'\x78\xda']:
        try: return zlib.decompress(content).decode('utf-8', errors='ignore')
        except: pass
    try: return content.decode('utf-8', errors='ignore')
    except: return content.decode('latin-1', errors='ignore')

def get_short_subject(name):
    if not name: return "Course"
    for s in [" By Khan Sir", " By Khan", " By Team", "& Team"]:
        if s in name: name = name.split(s)[0].strip()
    if "(" in name: name = name.split("(")[0].strip()
    if " & " in name: name = name.split(" & ")[0].strip()
    skip = {'the','and','by','for','with','in','on','at','to','of'}
    words = [w for w in name.split() if w.lower() not in skip]
    return (words[0] if words else name[:20]).rstrip(' -:')

def clean_title(title, batch):
    if not title: return "Untitled"
    result = title.strip()
    subj = get_short_subject(batch).lower()
    for p in [rf'{re.escape(subj)}\s+by\s+khan\s+sir\s*[-–:]\s*', rf'{re.escape(subj)}\s*[-–:]\s*', rf'khan\s+sir\s*[-–:]\s*', rf'{re.escape(batch)}\s*[-–:]\s*']:
        result = re.sub(p, "", result, flags=re.I).strip()
    return re.sub(r'\s+', ' ', re.sub(r'\s+[-–:]\s*', ' ', result).strip()) or title.strip()

def extract_lec_num(text):
    if not text: return 9999
    m = re.search(r'(?:lecture|lec|class)\s*[-–]?\s*(\d+)', text, re.I)
    if m: return int(m.group(1))
    m = re.search(r'(?:part|भाग)\s*[-–]?\s*(\d+)', text, re.I)
    return int(m.group(1)) if m else 9999

def is_pdf_test(t):
    return any(k in (t or "").lower() for k in ['pdf','test','answer','ans','sheet','printable'])

def extract_subject(full):
    if not full: return "Other"
    if is_pdf_test(full): return "📄 PDFs & Tests"
    m = re.match(r'^(.+?)\s*[-–]\s*(?:Lecture|lec|Class|Part|भाग)', full, re.I)
    if m: return m.group(1).strip()
    if '||' in full: return full.split('||')[0].strip()
    if ':' in full: return full.split(':')[0].strip()
    return "Other"

def _sort_groups(groups):
    result, pdfs = [], groups.get("📄 PDFs & Tests", [])
    for name in sorted(k for k in groups if k != "📄 PDFs & Tests"):
        entries = groups[name]
        vids = sorted([e for e in entries if not e[2]], key=lambda x: x[1])
        pdfs_only = sorted([e for e in entries if e[2]], key=lambda x: x[0].lower())
        result.extend([e[0] for e in vids + pdfs_only])
    if pdfs:
        result.extend([e[0] for e in sorted(pdfs, key=lambda x: x[0].lower())])
    return result

# ================== API FUNCTIONS ==================
def login_api(phone, pwd, sess):
    payload = {"phone": str(phone).strip(), "password": str(pwd).strip(), "remember": True}
    try:
        r = sess.post(f"{API_BASE}/cms/login?medium=0", headers=HEADERS, json=payload, timeout=20)
        txt = smart_decompress(r.content)
        if r.status_code == 422:
            try: return None, json.loads(txt).get('message', 'Validation failed')
            except: return None, "Validation error"
        if r.status_code != 200: return None, f"Status {r.status_code}"
        data = json.loads(txt)
        token = data.get("token") or data.get("access_token") or (data.get("data") or {}).get("token")
        return (token, None) if token else (None, "Token not found")
    except Exception as e: return None, str(e)

def get_courses_api(sess, token):
    headers = {**HEADERS, "authorization": f"Bearer {token}"}
    try:
        r = sess.get(f"{API_BASE}/v1/courses/paid", headers=headers, timeout=15)
        if r.status_code == 200:
            data = json.loads(smart_decompress(r.content))
            if isinstance(data, list): return data
    except Exception as e:
        print(f"[API] get_courses: {e}")
    return []

def get_lessons_api(sess, slug, token):
    headers = {**HEADERS, "authorization": f"Bearer {token}"}
    url = f"{API_BASE}/cms/user/courses/{slug}/lessons?medium=0"
    try:
        r = sess.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = json.loads(smart_decompress(r.content))
            if isinstance(data, dict):
                if 'lessons' in data: return data
                if 'data' in data and isinstance(data['data'], dict): return data['data']
    except Exception as e:
        print(f"[API] lessons ({slug}): {e}")
        
    try:
        r2 = sess.get(f"{API_BASE}/courses/{slug}/pdfs?groupBy=topic", headers=headers, timeout=15)
        if r2.status_code == 200:
            data = json.loads(smart_decompress(r2.content))
            if isinstance(data, dict) and data.get('state') == 200:
                return {"topics": data.get('data', {}).get('topics', [])}
    except Exception as e:
        print(f"[API] pdfs ({slug}): {e}")
    return {}

def extract_urls(data, batch, thumb):
    groups = defaultdict(list)
    if not data: return [], thumb
    prefix = get_short_subject(batch)
    topics = data.get('topics') or data.get('pdfs') or []
    if topics and not data.get('lessons'):
        for topic in topics:
            if not isinstance(topic, dict): continue
            tname = topic.get('topic', {}).get('topicName') or topic.get('section', {}).get('sectionName') or 'Sheet'
            for pdf in topic.get('pdfs', []):
                if not isinstance(pdf, dict): continue
                url = pdf.get('uploadPdf') or pdf.get('url')
                if url:
                    title = clean_title(pdf.get('title', 'PDF'), batch)
                    full = f"{tname} - {title}"
                    groups["📄 PDFs & Tests"].append((f"[{prefix}] {full} : {url}", extract_lec_num(full), True))
        return _sort_groups(groups), thumb
        
    lessons = data.get('lessons') or (data.get('data') or {}).get('lessons') or []
    if not isinstance(lessons, list): return [], thumb
    for lesson in lessons:
        if not isinstance(lesson, dict): continue
        lname = clean_title(lesson.get('name') or lesson.get('title') or 'Lesson', batch)
        for vid in (lesson.get('videos') or lesson.get('class_videos') or []):
            if not isinstance(vid, dict): continue
            vname = clean_title(vid.get('name') or vid.get('title') or 'Video', batch)
            url = vid.get('video_url') or vid.get('url') or vid.get('class_link')
            if url:
                full = f"{lname} - {vname}" if lname != vname else vname
                groups[extract_subject(full)].append((f"[{prefix}] {full} : {url}", extract_lec_num(full), False))
        for pdf in (lesson.get('classPdf') or lesson.get('pdfs') or []):
            if isinstance(pdf, dict) and pdf.get('url'):
                title = clean_title(pdf.get('title', 'PDF'), batch)
                full = f"{lname} - {title}"
                groups[extract_subject(full)].append((f"[{prefix}] {full} : {pdf['url']}", extract_lec_num(full), True))
    for note in (data.get('notes') or (data.get('data') or {}).get('notes') or []):
        if isinstance(note, dict) and note.get('video_url'):
            name = clean_title(note.get('name', 'Note'), batch)
            groups[extract_subject(name)].append((f"[{prefix}] {name} : {note['video_url']}", extract_lec_num(name), is_pdf_test(name)))
    return _sort_groups(groups), thumb

def save_txt(urls, batch, thumb):
    name = re.sub(r'[\\/:*?"<>|\n\r]', '_', batch).strip()[:40]
    path = os.path.join(tempfile.gettempdir(), f"{name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"[{batch}] Thumbnail : {thumb}\n\n")
        for u in urls: f.write(u + '\n')
    return path

# ================== KEYBOARD & MENU ==================
def build_kb(courses, selected):
    kb = []
    for c in courses:
        is_sel = c['id'] in selected
        kb.append([InlineKeyboardButton(f"{'✅' if is_sel else '▫️'} {c['title'][:40]}", callback_data=f"tgl_{c['id']}")])
    
    all_sel = len(selected) == len(courses)
    kb.append([InlineKeyboardButton("❌ Deselect All" if all_sel else "✅ Select All", callback_data="unsel_all" if all_sel else "sel_all")])
    kb.append([
        InlineKeyboardButton("📥 Export All", callback_data="exp_all"),
        InlineKeyboardButton("✅ Done", callback_data="done")
    ])
    return InlineKeyboardMarkup(kb)

async def show_menu(client, uid):
    if uid not in user_sessions: return
    sess = user_sessions[uid]
    courses, selected = sess['courses'], sess.get('selected', [])
    creds = sess.get('creds_raw', '')
    
    text = f"🔐 **Credentials:**\n```\n{creds}\n```\n\n📚 **Your Courses:**\n\n"
    
    for c in courses:
        thumb_url = fix_thumb(c.get('image', {}).get('large') or c.get('image', {}).get('medium'))
        thumb_link = f"[🔗 Thumbnail]({thumb_url})" if thumb_url else ""
        text += f"`{c['id']}` - {c['title']}\n{thumb_link}\n\n"
    
    text = text.strip()
    kb = build_kb(courses, selected)
    msg_id = sess.get('menu_msg_id')
    
    try:
        if msg_id:
            await client.edit_message_text(uid, msg_id, text, reply_markup=kb, parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            msg = await client.send_message(uid, text, reply_markup=kb, parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=True)
            sess['menu_msg_id'] = msg.id
    except Exception as e:
        if msg_id:
            try: await client.delete_messages(uid, msg_id)
            except: pass
        msg = await client.send_message(uid, text, reply_markup=kb, parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=True)
        sess['menu_msg_id'] = msg.id

# ================== BOT HANDLERS ==================
@app.on_message(filters.command("start"))
async def cmd_start(_, m):
    await m.reply(
        "🎓 **Khan Global Studies Bot**\n\n"
        "🔑 Login karein:\n"
        "```\n9876543210*yourpassword\n```\n"
        "Ya phir seedha **Token** paste karein.\n\n"
        "✅ Features:\n"
        "• Ek hi message me selection\n"
        "• Credentials copyable + Thumbnail link\n"
        "• Done dabane pe Photo → Details → TXT\n"
        "• Progress msg turant delete ho jata hai",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_text(client, m):
    uid = m.from_user.id
    txt = m.text.strip()
    if not txt: return

    # 🔒 STRICT: Sirf login format pe hi kaam karega. Baaki sab ignore.
    if "*" in txt or len(txt) > 35:
        if uid in user_sessions:
            del user_sessions[uid]
        await process_login(client, m, uid, txt)
    # ❌ Random text pe KUCH NAHI hoga (No reply, No loop)

async def process_login(client, m, uid, txt):
    prog = await m.reply("🔐 Processing login...")
    token, creds_raw = None, ""
    req_sess = requests.Session()

    if "*" in txt:
        phone, pwd = txt.split("*", 1)
        phone, pwd = phone.strip(), pwd.strip()
        token, err = login_api(phone, pwd, req_sess)
        if err:
            await prog.edit(f"❌ Login failed: {err}")
            return
        creds_raw = f"{phone}*{pwd}"
    else:
        token = txt.strip()
        req_sess.cookies.set('AUTH_USER', json.dumps({"token": f"0|{token}", "user": {}}), domain='.khanglobalstudies.com')
        creds_raw = token

    await prog.edit("✅ Login successful! Fetching courses...")
    courses = get_courses_api(req_sess, token)
    if not courses:
        await prog.edit("⚠️ No courses found. Check credentials or close Khan App.")
        return

    user_sessions[uid] = {
        'token': token,
        'sess': req_sess,
        'courses': courses,
        'selected': [],
        'creds_raw': creds_raw,
        'menu_msg_id': None
    }
    await prog.delete()
    await show_menu(client, uid)

@app.on_callback_query(filters.regex(r"^tgl_"))
async def cb_toggle(_, cq):
    uid = cq.from_user.id
    if uid not in user_sessions: return await cq.answer("⚠️ Session expired. Login again.", show_alert=True)
    course_id = int(cq.data.split("_")[1])
    sess = user_sessions[uid]
    sel = sess.get('selected', [])
    if course_id in sel:
        sel.remove(course_id)
        await cq.answer("▫️ Deselected")
    else:
        sel.append(course_id)
        await cq.answer("✅ Selected")
    sess['selected'] = sel
    await show_menu(_, uid)

@app.on_callback_query(filters.regex(r"^(sel_all|unsel_all)$"))
async def cb_all(_, cq):
    uid = cq.from_user.id
    if uid not in user_sessions: return await cq.answer("⚠️ Session expired.", show_alert=True)
    sess = user_sessions[uid]
    if cq.data == "sel_all":
        sess['selected'] = [c['id'] for c in sess['courses']]
        await cq.answer("✅ All selected")
    else:
        sess['selected'] = []
        await cq.answer("❌ All deselected")
    await show_menu(_, uid)

@app.on_callback_query(filters.regex(r"^exp_all$"))
async def cb_exp_all(_, cq):
    uid = cq.from_user.id
    if uid not in user_sessions: return await cq.answer("⚠️ Session expired.", show_alert=True)
    await cq.answer("🚀 Exporting all courses...")
    sess = user_sessions[uid]
    for c in sess['courses']:
        await export_course(_, uid, c, sess['sess'], sess['token'])
        await asyncio.sleep(3)

@app.on_callback_query(filters.regex(r"^done$"))
async def cb_done(_, cq):
    uid = cq.from_user.id
    if uid not in user_sessions: return await cq.answer("⚠️ Session expired.", show_alert=True)
    sess = user_sessions[uid]
    selected = sess.get('selected', [])
    if not selected: return await cq.answer("⚠️ Pehle koi batch select karein!", show_alert=True)
    await cq.answer(f"🚀 Exporting {len(selected)} batch(es)...")
    for c in sess['courses']:
        if c['id'] in selected:
            await export_course(_, uid, c, sess['sess'], sess['token'])
            await asyncio.sleep(3)

async def export_course(client, uid, course, req_sess, token):
    title = course.get('title', 'Course')
    slug = course.get('slug')
    thumb = fix_thumb(course.get('image', {}).get('large') or course.get('image', {}).get('medium'))
    
    if not slug:
        await client.send_message(uid, f"⚠️ Skipping {title} (no slug)")
        return
    
    prog = await client.send_message(uid, f"⏳ Fetching: {title}...")
    try:
        data = get_lessons_api(req_sess, slug, token)
        if not data:
            await prog.delete()
            await client.send_message(uid, f"⚠️ No data for {title}.")
            return
            
        urls, bthumb = extract_urls(data, title, thumb)
        if not urls:
            await prog.delete()
            await client.send_message(uid, f"⚠️ No URLs found in {title}")
            return
            
        path = save_txt(urls, title, bthumb or thumb)
        caption = f"📚 **{title}**\n🔗 Links: `{len(urls)}`\n📄 Format: Grouped + Sorted"
        
        if thumb:
            try:
                await client.send_photo(uid, thumb, caption=caption, parse_mode=enums.ParseMode.MARKDOWN)
            except:
                await client.send_message(uid, caption, parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await client.send_message(uid, caption, parse_mode=enums.ParseMode.MARKDOWN)
            
        await client.send_document(uid, path, caption=f"📄 {title[:30]}.txt")
        
        # 🗑️ TURANT DELETE
        await prog.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        print(f"[Export Error] {title}:\n{traceback.format_exc()}")
        await prog.edit(f"❌ Error: {e}")

# ================== RUN ==================
if __name__ == "__main__":
    print("🟢 Khan Bot Starting...")
    print(f"   API_ID: {API_ID}")
    print(f"   Bot: @{app.me.username if app.me else 'Unknown'}")
    app.run()
