import telebot
from telebot import types
import sqlite3
import time
import random
import os
import re
import json
from datetime import datetime
from threading import Thread
import logging

# ========== إعدادات التسجيل (للمساعدة في تتبع الأخطاء) ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== إعدادات البوت ==========
TOKEN = "your token"
OWNER_ID = your id
bot = telebot.TeleBot(TOKEN)

# ========== قاعدة البيانات ==========
DB_PATH = "shop.db"

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات مع check_same_thread=False"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # للوصول إلى الأعمدة بالاسم
    return conn

# إنشاء الجداول (مرة واحدة عند بدء التشغيل)
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        points INTEGER DEFAULT 0,
        join_date TEXT,
        last_active TEXT,
        is_banned INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        price INTEGER,
        type TEXT,
        file_id TEXT,
        description TEXT,
        added_by INTEGER,
        added_date TEXT,
        views INTEGER DEFAULT 0,
        purchases INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        added_by INTEGER,
        added_date TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        price INTEGER,
        purchase_date TEXT,
        status TEXT DEFAULT 'completed'
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS point_codes (
        code TEXT PRIMARY KEY,
        points INTEGER,
        is_used INTEGER DEFAULT 0,
        created_by INTEGER,
        created_date TEXT,
        used_by INTEGER,
        used_date TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_date TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        rating INTEGER,
        comment TEXT,
        review_date TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pending_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        status TEXT DEFAULT 'pending',
        order_date TEXT
    )""")
    conn.commit()
    conn.close()

init_db()  # تشغيل عند بدء البوت

# ========== دوال مساعدة ==========
def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def add_user(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    existing = cur.fetchone()
    if not existing:
        cur.execute("""INSERT INTO users (user_id, username, first_name, last_name, points, join_date, last_active)
                       VALUES (?, ?, ?, ?, 0, ?, ?)""",
                   (user_id, username, first_name, last_name,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    else:
        cur.execute("UPDATE users SET last_active=? WHERE user_id=?", 
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()
    conn.close()

def get_points(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0

def add_points(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def remove_points(user_id, amount):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_products(category=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if category:
        cur.execute("SELECT id, name, category, price, type, description, views, purchases FROM products WHERE category=? ORDER BY id DESC", (category,))
    else:
        cur.execute("SELECT id, name, category, price, type, description, views, purchases FROM products ORDER BY id DESC")
    products = cur.fetchall()
    conn.close()
    return products

def get_product(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    conn.close()
    return product

def get_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()
    return categories

def is_owner(user_id):
    return user_id == OWNER_ID

def is_banned(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res and res[0] == 1

def add_notification(user_id, message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO notifications (user_id, message, created_date) VALUES (?, ?, ?)",
               (user_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_notifications(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, message, is_read, created_date FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_date DESC", (user_id,))
    notifs = cur.fetchall()
    conn.close()
    return notifs

def mark_notification_read(notif_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notif_id,))
    conn.commit()
    conn.close()

# ========== القائمة الرئيسية ==========
def main_menu_markup(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛍️ المتجر", callback_data="shop"),
        types.InlineKeyboardButton("📂 الفئات", callback_data="categories"),
        types.InlineKeyboardButton("💰 رصيدي", callback_data="my_points"),
        types.InlineKeyboardButton("🎁 كود نقاط", callback_data="redeem_code"),
        types.InlineKeyboardButton("📤 تحويل نقاط", callback_data="transfer_points"),
        types.InlineKeyboardButton("📜 مشترياتي", callback_data="my_purchases"),
        types.InlineKeyboardButton("🔔 الإشعارات", callback_data="notifications")
    )
    if is_owner(uid):
        kb.add(types.InlineKeyboardButton("⚙️ لوحة المالك", callback_data="admin_panel"))
    return kb

# ========== أمر /start ==========
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    if is_banned(uid):
        bot.send_message(uid, "⛔️ تم حظرك من استخدام البوت.")
        return
    
    username = msg.from_user.username or ""
    first_name = msg.from_user.first_name or ""
    last_name = msg.from_user.last_name or ""
    add_user(uid, username, first_name, last_name)
    
    kb = main_menu_markup(uid)
    welcome_text = (
        f"🎉 <b>مرحباً بك في متجر النقاط!</b>\n\n"
        f"👤 المستخدم: {first_name}\n"
        f"🆔 ايديك: <code>{uid}</code>\n"
        f"💰 نقاطك: {get_points(uid)}\n\n"
        f"📌 استخدم الأزرار أدناه للتنقل في المتجر.\n"
        f"⭐ يمكنك شراء السلع بالنقاط التي تجمعها."
    )
    bot.send_message(uid, welcome_text, reply_markup=kb, parse_mode="HTML")

# ========== زر الرجوع (تم إصلاحه) ==========
@bot.callback_query_handler(func=lambda c: c.data == "back_menu")
def back_menu(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    # التأكد من وجود المستخدم
    if not get_user(uid):
        username = call.from_user.username or ""
        first_name = call.from_user.first_name or ""
        last_name = call.from_user.last_name or ""
        add_user(uid, username, first_name, last_name)
    
    kb = main_menu_markup(uid)
    welcome_text = (
        f"🎉 <b>مرحباً بك في متجر النقاط!</b>\n\n"
        f"👤 المستخدم: {call.from_user.first_name or ''}\n"
        f"🆔 ايديك: <code>{uid}</code>\n"
        f"💰 نقاطك: {get_points(uid)}\n\n"
        f"📌 استخدم الأزرار أدناه للتنقل في المتجر.\n"
        f"⭐ يمكنك شراء السلع بالنقاط التي تجمعها."
    )
    try:
        bot.edit_message_text(
            welcome_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in back_menu edit: {e}")
        # إذا فشل التعديل، نرسل رسالة جديدة
        bot.send_message(uid, welcome_text, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ========== عرض الفئات ==========
@bot.callback_query_handler(func=lambda c: c.data == "categories")
def show_categories(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    categories = get_categories()
    if not categories:
        bot.answer_callback_query(call.id, "📭 لا توجد فئات حالياً.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cat_id, cat_name in categories:
        kb.add(types.InlineKeyboardButton(f"📁 {cat_name}", callback_data=f"cat_{cat_id}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_menu"))
    
    try:
        bot.edit_message_text(
            "📂 <b>فئات المتجر:</b>\n\nاختر فئة لعرض سلعها.",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in show_categories: {e}")
        bot.send_message(uid, "📂 <b>فئات المتجر:</b>\n\nاختر فئة لعرض سلعها.", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
def show_category_products(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    cat_id = int(call.data.split("_")[1])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_name = cur.fetchone()[0]
    conn.close()
    
    products = get_products(cat_name)
    if not products:
        bot.answer_callback_query(call.id, f"📭 لا توجد سلع في فئة {cat_name}")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for p in products:
        p_id, name, _, price, _, desc, _, _ = p
        kb.add(types.InlineKeyboardButton(
            f"{name} | {price} نقطة",
            callback_data=f"view_{p_id}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="categories"))
    
    try:
        bot.edit_message_text(
            f"📁 <b>فئة: {cat_name}</b>\n\nاختر سلعة لعرض تفاصيلها.",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in show_category_products: {e}")
        bot.send_message(uid, f"📁 <b>فئة: {cat_name}</b>\n\nاختر سلعة لعرض تفاصيلها.", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ========== عرض المتجر ==========
@bot.callback_query_handler(func=lambda c: c.data == "shop")
def show_shop(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    products = get_products()
    if not products:
        bot.answer_callback_query(call.id, "📭 المتجر فارغ حالياً.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for p in products:
        p_id, name, category, price, p_type, desc, views, purchases = p
        btn_text = f"{name} | {price} نقطة"
        if views > 0:
            btn_text += f" 👁️{views}"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"view_{p_id}"))
    kb.add(
        types.InlineKeyboardButton("📂 الفئات", callback_data="categories"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_menu")
    )
    
    try:
        bot.edit_message_text(
            "🛍️ <b>جميع السلع المتاحة:</b>\n\nاختر سلعة لعرض تفاصيلها.",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in show_shop: {e}")
        bot.send_message(uid, "🛍️ <b>جميع السلع المتاحة:</b>\n\nاختر سلعة لعرض تفاصيلها.", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ========== عرض تفاصيل السلعة ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("view_"))
def view_product(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    product_id = int(call.data.split("_")[1])
    product = get_product(product_id)
    if not product:
        bot.answer_callback_query(call.id, "السلعة غير موجودة.")
        return
    
    _, name, category, price, p_type, file_id, desc, added_by, added_date, views, purchases = product
    
    # زيادة المشاهدات
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE products SET views = views + 1 WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💳 شراء", callback_data=f"buy_{product_id}"),
        types.InlineKeyboardButton("⭐ تقييم", callback_data=f"review_{product_id}")
    )
    kb.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="shop"),
        types.InlineKeyboardButton("📂 الفئات", callback_data="categories")
    )
    
    text = (
        f"<b>{name}</b>\n"
        f"📁 الفئة: {category}\n"
        f"💰 السعر: {price} نقطة\n\n"
        f"📝 {desc}\n\n"
        f"👁️ المشاهدات: {views+1}\n"
        f"🛒 المشتريات: {purchases}"
    )
    
    try:
        if p_type == "text":
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                reply_markup=kb, parse_mode="HTML")
        elif p_type == "photo":
            bot.send_photo(uid, file_id, caption=text, reply_markup=kb, parse_mode="HTML")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        elif p_type == "video":
            bot.send_video(uid, file_id, caption=text, reply_markup=kb, parse_mode="HTML")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.send_document(uid, file_id, caption=text, reply_markup=kb, parse_mode="HTML")
            bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error in view_product: {e}")
        bot.send_message(uid, f"❌ حدث خطأ في عرض السلعة. قد يكون الملف غير صالح.\nالخطأ: {e}", parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ========== شراء السلعة ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_product(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    product_id = int(call.data.split("_")[1])
    product = get_product(product_id)
    if not product:
        bot.answer_callback_query(call.id, "السلعة غير موجودة.")
        return
    
    _, name, _, price, _, _, _, _, _, _, _ = product
    points = get_points(uid)
    
    if points < price:
        bot.answer_callback_query(call.id, f"❌ رصيدك غير كافٍ!\nرصيدك: {points} نقطة\nالسعر: {price} نقطة", show_alert=True)
        return
    
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ تأكيد", callback_data=f"confirm_buy_{product_id}"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data=f"view_{product_id}")
    )
    try:
        bot.edit_message_text(
            f"⚠️ <b>تأكيد الشراء</b>\n\n"
            f"السلعة: {name}\n"
            f"السعر: {price} نقطة\n"
            f"رصيدك الحالي: {points} نقطة\n\n"
            f"هل أنت متأكد من رغبتك في الشراء؟",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in buy_product edit: {e}")
        bot.send_message(uid, f"⚠️ <b>تأكيد الشراء</b>\n\nالسلعة: {name}\nالسعر: {price} نقطة\nرصيدك الحالي: {points}\n\nهل أنت متأكد؟", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_buy_"))
def confirm_buy(call):
    uid = call.from_user.id
    product_id = int(call.data.split("_")[2])
    product = get_product(product_id)
    if not product:
        bot.answer_callback_query(call.id, "السلعة غير موجودة.")
        return
    
    _, name, _, price, p_type, file_id, desc, _, _, _, _ = product
    points = get_points(uid)
    
    if points < price:
        bot.answer_callback_query(call.id, "❌ رصيدك غير كافٍ!", show_alert=True)
        return
    
    # خصم النقاط وتسجيل العملية
    remove_points(uid, price)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE products SET purchases = purchases + 1 WHERE id=?", (product_id,))
    cur.execute("INSERT INTO purchases (user_id, product_id, product_name, price, purchase_date) VALUES (?, ?, ?, ?, ?)",
               (uid, product_id, name, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    msg_text = f"🎉 <b>تم شراء {name} بنجاح!</b>\n💰 رصيدك المتبقي: {get_points(uid)} نقطة"
    
    # ✅ إرسال المحتوى مع معالجة الأخطاء بالكامل
    success = False
    try:
        if p_type == "text":
            bot.send_message(uid, f"{msg_text}\n\n📄 المحتوى:\n{file_id}", parse_mode="HTML")
        elif p_type == "photo":
            bot.send_photo(uid, file_id, caption=msg_text, parse_mode="HTML")
        elif p_type == "video":
            bot.send_video(uid, file_id, caption=msg_text, parse_mode="HTML")
        else:
            bot.send_document(uid, file_id, caption=msg_text, parse_mode="HTML")
        success = True
    except Exception as e:
        logger.error(f"Error sending product file: {e}")
        bot.send_message(uid, f"❌ تم خصم النقاط بنجاح، ولكن حدث خطأ أثناء إرسال الملف.\nقد يكون الملف قد تم حذفه أو انتهت صلاحيته بسبب تغيير التوكن.\nيرجى إبلاغ المالك لإعادة رفع المنتج.\n\nالخطأ: {e}", parse_mode="HTML")
        # إرسال إشعار للمالك
        bot.send_message(OWNER_ID, f"⚠️ خطأ في إرسال ملف للمستخدم {uid}\nالسلعة: {name}\nالخطأ: {e}")
    
    # حذف رسالة التأكيد
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
    
    # إشعار للمالك بعملية شراء ناجحة (إذا كانت ناجحة)
    if success and is_owner(uid):
        bot.send_message(OWNER_ID, f"🛒 <b>عملية شراء جديدة</b>\n\nالمستخدم: {uid}\nالسلعة: {name}\nالسعر: {price} نقطة", parse_mode="HTML")
    
    bot.answer_callback_query(call.id, "✅ تم الشراء بنجاح!" if success else "⚠️ تم الشراء ولكن حدث خطأ في الإرسال", show_alert=True)

# ========== باقي الأوامر (رصيدي، كود نقاط، تحويل، مشترياتي، إشعارات، تقييم، لوحة المالك، إلخ) ==========
# ... (سيتم إدراج جميع الدوال الأخرى بنفس النهج مع معالجة الأخطاء)
# ولكن اختصاراً، سأكتبها كلها مع ضمان معالجة الأخطاء.

# ========== عرض الرصيد ==========
@bot.callback_query_handler(func=lambda c: c.data == "my_points")
def my_points(call):
    uid = call.from_user.id
    points = get_points(uid)
    bot.answer_callback_query(call.id, f"💰 رصيدك: {points} نقطة", show_alert=True)

# ========== استبدال كود نقاط ==========
@bot.callback_query_handler(func=lambda c: c.data == "redeem_code")
def redeem_code(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    bot.send_message(uid, "🎟 <b>أرسل الكود الذي حصلت عليه:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_redeem)

def process_redeem(msg):
    uid = msg.from_user.id
    code = msg.text.strip().upper()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT points, is_used, created_by FROM point_codes WHERE code=?", (code,))
    res = cur.fetchone()
    conn.close()
    
    if not res:
        bot.send_message(uid, "❌ الكود غير صحيح.")
        return
    if res[1] == 1:
        bot.send_message(uid, "❌ هذا الكود مستخدم بالفعل.")
        return
    
    points = res[0]
    add_points(uid, points)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE point_codes SET is_used=1, used_by=?, used_date=? WHERE code=?",
               (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code))
    conn.commit()
    conn.close()
    
    bot.send_message(uid, f"✅ تم إضافة {points} نقطة إلى رصيدك!\n💰 رصيدك الحالي: {get_points(uid)} نقطة")

# ========== تحويل نقاط ==========
@bot.callback_query_handler(func=lambda c: c.data == "transfer_points")
def transfer_points(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    bot.send_message(uid, "📤 <b>أرسل: ايدي_المستخدم | عدد_النقاط</b>\nمثال: <code>123456789 | 50</code>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_transfer)

def process_transfer(msg):
    uid = msg.from_user.id
    try:
        parts = msg.text.split('|')
        if len(parts) != 2:
            raise ValueError
        target_id = int(parts[0].strip())
        amount = int(parts[1].strip())
        
        if amount <= 0:
            bot.send_message(uid, "❌ يجب أن تكون النقاط أكبر من 0.")
            return
        if get_points(uid) < amount:
            bot.send_message(uid, "❌ رصيدك غير كافٍ.")
            return
        if target_id == uid:
            bot.send_message(uid, "❌ لا يمكنك التحويل لنفسك.")
            return
        
        remove_points(uid, amount)
        add_points(target_id, amount)
        bot.send_message(uid, f"✅ تم تحويل {amount} نقطة إلى {target_id}")
        bot.send_message(target_id, f"🎁 استلمت {amount} نقطة من {uid}")
    except:
        bot.send_message(uid, "❌ صيغة غير صحيحة. استخدم: `ايدي_المستخدم | عدد_النقاط`")

# ========== مشترياتي ==========
@bot.callback_query_handler(func=lambda c: c.data == "my_purchases")
def my_purchases(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, product_name, price, purchase_date FROM purchases WHERE user_id=? ORDER BY purchase_date DESC LIMIT 20", (uid,))
    purchases = cur.fetchall()
    conn.close()
    
    if not purchases:
        bot.send_message(uid, "📭 لم تقم بأي عملية شراء بعد.")
        return
    
    text = "📜 <b>آخر مشترياتك:</b>\n\n"
    for p in purchases:
        p_id, name, price, date = p
        text += f"🛒 {name} | {price} نقطة | {date}\n"
    
    bot.send_message(uid, text, parse_mode="HTML")

# ========== الإشعارات ==========
@bot.callback_query_handler(func=lambda c: c.data == "notifications")
def show_notifications(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    notifs = get_notifications(uid)
    if not notifs:
        bot.answer_callback_query(call.id, "🔔 لا توجد إشعارات جديدة.", show_alert=True)
        return
    
    text = "🔔 <b>إشعاراتك الجديدة:</b>\n\n"
    for n in notifs:
        n_id, msg, _, date = n
        text += f"📌 {msg}\n{date}\n\n"
        mark_notification_read(n_id)
    
    bot.send_message(uid, text, parse_mode="HTML")

# ========== تقييم السلعة ==========
@bot.callback_query_handler(func=lambda c: c.data.startswith("review_"))
def review_product(call):
    uid = call.from_user.id
    if is_banned(uid):
        bot.answer_callback_query(call.id, "⛔️ أنت محظور.")
        return
    
    product_id = int(call.data.split("_")[1])
    product = get_product(product_id)
    if not product:
        bot.answer_callback_query(call.id, "السلعة غير موجودة.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=5)
    for i in range(1, 6):
        kb.add(types.InlineKeyboardButton(str(i), callback_data=f"rate_{product_id}_{i}"))
    
    try:
        bot.edit_message_text(
            f"⭐ <b>تقييم السلعة</b>\n\nاختر التقييم من 1 إلى 5:",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in review_product: {e}")
        bot.send_message(uid, f"⭐ <b>تقييم السلعة</b>\n\nاختر التقييم من 1 إلى 5:", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_"))
def save_review(call):
    uid = call.from_user.id
    parts = call.data.split("_")
    product_id = int(parts[1])
    rating = int(parts[2])
    
    bot.send_message(uid, "📝 <b>أضف تعليقك على السلعة (اختياري):</b>\nأرسل 'تخطي' لتجاوز.", parse_mode="HTML")
    bot.register_next_step_handler(call.message, lambda m: save_review_comment(m, product_id, rating))

def save_review_comment(msg, product_id, rating):
    uid = msg.from_user.id
    comment = msg.text.strip()
    if comment.lower() == "تخطي":
        comment = ""
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO reviews (user_id, product_id, rating, comment, review_date) VALUES (?, ?, ?, ?, ?)",
               (uid, product_id, rating, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    bot.send_message(uid, f"✅ تم تقييم السلعة بـ {rating} نجمة!")
    show_product_reviews(uid, product_id)

def show_product_reviews(uid, product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id, rating, comment, review_date FROM reviews WHERE product_id=? ORDER BY review_date DESC LIMIT 5", (product_id,))
    reviews = cur.fetchall()
    conn.close()
    
    if not reviews:
        bot.send_message(uid, "لا توجد تقييمات لهذه السلعة.")
        return
    
    text = "⭐ <b>تقييمات السلعة:</b>\n\n"
    for r in reviews:
        user_id, rating, comment, date = r
        text += f"👤 {user_id} | {'⭐'*rating}\n"
        if comment:
            text += f"💬 {comment}\n"
        text += f"📅 {date}\n\n"
    
    bot.send_message(uid, text, parse_mode="HTML")

# ========== لوحة المالك (جميع الوظائف) ==========
@bot.callback_query_handler(func=lambda c: c.data == "admin_panel")
def admin_panel(call):
    uid = call.from_user.id
    if not is_owner(uid):
        bot.answer_callback_query(call.id, "⛔️ هذا الأمر للمالك فقط.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ إضافة سلعة", callback_data="add_product"),
        types.InlineKeyboardButton("🗑️ حذف سلعة", callback_data="delete_product"),
        types.InlineKeyboardButton("📂 إدارة الفئات", callback_data="manage_categories"),
        types.InlineKeyboardButton("🎟️ كود نقاط", callback_data="create_code"),
        types.InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
        types.InlineKeyboardButton("📤 إضافة نقاط", callback_data="add_points_admin"),
        types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user"),
        types.InlineKeyboardButton("📢 إشعار عام", callback_data="broadcast"),
        types.InlineKeyboardButton("📋 طلبات الشراء", callback_data="pending_orders"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back_menu")
    )
    try:
        bot.edit_message_text(
            "⚙️ <b>لوحة تحكم المالك</b>\n\nاختر الإجراء المطلوب:",
            call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}")
        bot.send_message(uid, "⚙️ <b>لوحة تحكم المالك</b>\n\nاختر الإجراء المطلوب:", reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ========== إضافة سلعة ==========
@bot.callback_query_handler(func=lambda c: c.data == "add_product")
def add_product_start(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    bot.send_message(uid, "📝 <b>أرسل اسم السلعة:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, add_product_name)

def add_product_name(msg):
    uid = msg.from_user.id
    name = msg.text.strip()
    bot.send_message(uid, "📂 <b>أرسل اسم الفئة (أو أنشئ فئة جديدة):</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: add_product_category(m, name))

def add_product_category(msg, name):
    uid = msg.from_user.id
    category = msg.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM categories WHERE name=?", (category,))
    if not cur.fetchone():
        cur.execute("INSERT INTO categories (name, added_by, added_date) VALUES (?, ?, ?)",
                   (category, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(uid, f"✅ تم إضافة فئة جديدة: {category}")
    conn.close()
    
    bot.send_message(uid, "📝 <b>أرسل وصف السلعة:</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: add_product_desc(m, name, category))

def add_product_desc(msg, name, category):
    uid = msg.from_user.id
    desc = msg.text.strip()
    bot.send_message(uid, "💰 <b>أرسل سعر السلعة (بالنقاط):</b>", parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda m: add_product_price(m, name, category, desc))

def add_product_price(msg, name, category, desc):
    uid = msg.from_user.id
    try:
        price = int(msg.text.strip())
        if price <= 0:
            bot.send_message(uid, "❌ السعر يجب أن يكون أكبر من 0.")
            return
        bot.send_message(uid, 
            "📎 <b>أرسل محتوى السلعة:</b>\n"
            "• نص: اكتب النص\n"
            "• صورة: أرسل صورة\n"
            "• فيديو: أرسل فيديو\n"
            "• ملف: أرسل ملف", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: add_product_file(m, name, category, desc, price))
    except:
        bot.send_message(uid, "❌ أرسل رقماً صحيحاً.")

def add_product_file(msg, name, category, desc, price):
    uid = msg.from_user.id
    p_type = "text"
    file_id = ""
    
    if msg.text:
        p_type = "text"
        file_id = msg.text.strip()
    elif msg.photo:
        p_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        p_type = "video"
        file_id = msg.video.file_id
    elif msg.document:
        p_type = "document"
        file_id = msg.document.file_id
    else:
        bot.send_message(uid, "❌ نوع غير مدعوم. أرسل نص، صورة، فيديو، أو ملف.")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO products (name, category, price, type, file_id, description, added_by, added_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
               (name, category, price, p_type, file_id, desc, uid,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    bot.send_message(uid, f"✅ تم إضافة السلعة <b>{name}</b> بنجاح!", parse_mode="HTML")
    
    # إشعار لجميع المستخدمين
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    for user in users:
        add_notification(user[0], f"🆕 تم إضافة سلعة جديدة: {name} - {price} نقطة")

# ========== حذف سلعة ==========
@bot.callback_query_handler(func=lambda c: c.data == "delete_product")
def delete_product(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    products = get_products()
    if not products:
        bot.send_message(uid, "📭 لا توجد سلع لحذفها.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for p in products:
        p_id, name, _, _, _, _, _, _ = p
        kb.add(types.InlineKeyboardButton(f"🗑️ {name}", callback_data=f"del_{p_id}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    
    bot.send_message(uid, "اختر السلعة لحذفها:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def confirm_delete(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    product_id = int(call.data.split("_")[1])
    product = get_product(product_id)
    if product:
        name = product[1]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"✅ تم حذف السلعة: {name}")
    else:
        bot.answer_callback_query(call.id, "❌ السلعة غير موجودة.")
    
    # العودة إلى لوحة المالك
    admin_panel(call)

# ========== إدارة الفئات ==========
@bot.callback_query_handler(func=lambda c: c.data == "manage_categories")
def manage_categories(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ إضافة فئة", callback_data="add_category"),
        types.InlineKeyboardButton("🗑️ حذف فئة", callback_data="delete_category"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
    )
    bot.send_message(uid, "📂 <b>إدارة الفئات:</b>", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "add_category")
def add_category_start(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    bot.send_message(uid, "📝 <b>أرسل اسم الفئة الجديدة:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_add_category)

def process_add_category(msg):
    uid = msg.from_user.id
    name = msg.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categories (name, added_by, added_date) VALUES (?, ?, ?)",
                   (name, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        bot.send_message(uid, f"✅ تم إضافة الفئة: {name}")
    except:
        bot.send_message(uid, "❌ الفئة موجودة مسبقاً.")
    conn.close()

@bot.callback_query_handler(func=lambda c: c.data == "delete_category")
def delete_category_start(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    categories = get_categories()
    if not categories:
        bot.send_message(uid, "📭 لا توجد فئات لحذفها.")
        return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for cat_id, cat_name in categories:
        kb.add(types.InlineKeyboardButton(f"🗑️ {cat_name}", callback_data=f"delcat_{cat_id}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="manage_categories"))
    bot.send_message(uid, "اختر الفئة لحذفها:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delcat_"))
def confirm_delete_category(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    cat_id = int(call.data.split("_")[1])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "✅ تم حذف الفئة.")
    manage_categories(call)

# ========== إنشاء كود نقاط ==========
@bot.callback_query_handler(func=lambda c: c.data == "create_code")
def create_code(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    bot.send_message(uid, "🎟️ <b>أرسل عدد النقاط للكود:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_create_code)

def process_create_code(msg):
    uid = msg.from_user.id
    try:
        points = int(msg.text.strip())
        if points <= 0:
            bot.send_message(uid, "❌ يجب أن تكون النقاط أكبر من 0.")
            return
        code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO point_codes (code, points, created_by, created_date) VALUES (?, ?, ?, ?)",
                   (code, points, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        bot.send_message(uid, f"🎟️ <b>كود النقاط الجديد:</b>\n<code>{code}</code>\n💰 القيمة: {points} نقطة\n\nيمكنك مشاركة هذا الكود مع المستخدمين.", parse_mode="HTML")
    except:
        bot.send_message(uid, "❌ أرسل رقماً صحيحاً.")

# ========== إحصائيات ==========
@bot.callback_query_handler(func=lambda c: c.data == "stats")
def stats(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    products = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM purchases")
    purchases = cur.fetchone()[0]
    cur.execute("SELECT SUM(points) FROM users")
    total_points = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM categories")
    categories = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM reviews")
    reviews = cur.fetchone()[0]
    conn.close()
    
    text = f"""📊 <b>إحصائيات البوت:</b>
    
👥 المستخدمين: {users}
🛍️ السلع: {products}
📂 الفئات: {categories}
💳 المشتريات: {purchases}
⭐ التقييمات: {reviews}
💰 إجمالي النقاط: {total_points}"""
    
    bot.send_message(uid, text, parse_mode="HTML")

# ========== إضافة نقاط يدوياً ==========
@bot.callback_query_handler(func=lambda c: c.data == "add_points_admin")
def add_points_admin(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    bot.send_message(uid, "📤 <b>أرسل: ايدي_المستخدم | عدد_النقاط</b>\nمثال: <code>123456789 | 100</code>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_add_points_admin)

def process_add_points_admin(msg):
    uid = msg.from_user.id
    try:
        parts = msg.text.split('|')
        if len(parts) != 2:
            raise ValueError
        target_id = int(parts[0].strip())
        amount = int(parts[1].strip())
        add_points(target_id, amount)
        bot.send_message(uid, f"✅ تم إضافة {amount} نقطة للمستخدم {target_id}")
        bot.send_message(target_id, f"🎁 تم إضافة {amount} نقطة إلى رصيدك من قبل المالك.")
    except:
        bot.send_message(uid, "❌ صيغة غير صحيحة.")

# ========== حظر مستخدم ==========
@bot.callback_query_handler(func=lambda c: c.data == "ban_user")
def ban_user(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    bot.send_message(uid, "🚫 <b>أرسل ايدي المستخدم لحظره:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_ban_user)

def process_ban_user(msg):
    uid = msg.from_user.id
    try:
        target_id = int(msg.text.strip())
        if target_id == OWNER_ID:
            bot.send_message(uid, "❌ لا يمكنك حظر نفسك.")
            return
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (target_id,))
        conn.commit()
        conn.close()
        bot.send_message(uid, f"✅ تم حظر المستخدم {target_id}")
        bot.send_message(target_id, "⛔️ تم حظرك من استخدام البوت.")
    except:
        bot.send_message(uid, "❌ أرسل ايدي صحيح.")

# ========== إشعار عام ==========
@bot.callback_query_handler(func=lambda c: c.data == "broadcast")
def broadcast_start(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    bot.send_message(uid, "📢 <b>أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:</b>", parse_mode="HTML")
    bot.register_next_step_handler(call.message, process_broadcast)

def process_broadcast(msg):
    uid = msg.from_user.id
    broadcast_msg = msg.text.strip()
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    
    success = 0
    fail = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 <b>إشعار عام من المالك:</b>\n\n{broadcast_msg}", parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except:
            fail += 1
    
    bot.send_message(uid, f"✅ تم إرسال الإشعار إلى {success} مستخدم.\n❌ فشل الإرسال إلى {fail} مستخدم.")

# ========== طلبات الشراء المعلقة ==========
@bot.callback_query_handler(func=lambda c: c.data == "pending_orders")
def pending_orders(call):
    uid = call.from_user.id
    if not is_owner(uid): return
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, product_id, status, order_date FROM pending_orders WHERE status='pending'")
    orders = cur.fetchall()
    conn.close()
    
    if not orders:
        bot.send_message(uid, "📭 لا توجد طلبات شراء معلقة.")
        return
    
    text = "📋 <b>طلبات الشراء المعلقة:</b>\n\n"
    for order in orders:
        order_id, user_id, product_id, status, date = order
        product = get_product(product_id)
        product_name = product[1] if product else "غير معروف"
        text += f"🆔 {order_id} | مستخدم: {user_id} | سلعة: {product_name} | {date}\n"
    
    bot.send_message(uid, text, parse_mode="HTML")

# ========== معالج الرسائل العامة ==========
@bot.message_handler(func=lambda m: True)
def handle_all_messages(msg):
    uid = msg.from_user.id
    if is_banned(uid):
        bot.send_message(uid, "⛔️ أنت محظور.")
        return
    bot.send_message(uid, "📌 استخدم /start للبدء.")

# ========== تشغيل البوت ==========
if __name__ == "__main__":
    print("🛍️ بوت المتجر شغال يا سيدي!")
    print(f"👤 المالك: {OWNER_ID}")
    print("📌 جميع المستخدمين يمكنهم استخدام البوت.")
    print("⚙️ لوحة المالك محمية.")
    bot.infinity_polling()
