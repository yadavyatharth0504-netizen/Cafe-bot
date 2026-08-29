import os
import json
import sqlite3
import logging
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= 1. ROBUST WEB SERVER FOR RENDER =================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Cafe Bot is Running 24/7")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return  # Suppress HTTP access logs

def start_server_thread():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Start dummy server immediately
server_thread = threading.Thread(target=start_server_thread, daemon=True)
server_thread.start()

# ================= 2. DATABASE SETUP =================
DB_FILE = "cafe_database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cafe_groups (
            chat_id INTEGER PRIMARY KEY,
            data_json TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def load_group_data(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT data_json FROM cafe_groups WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        data = json.loads(row[0])
        data["roles"] = {int(k): v for k, v in data.get("roles", {}).items()}
        data["balances"] = {int(k): v for k, v in data.get("balances", {}).items()}
        data["orders"] = {int(k): v for k, v in data.get("orders", {}).items()}
        data["daily_claimed"] = {int(k): v for k, v in data.get("daily_claimed", {}).items()}
        data["pending_offers"] = {int(k): v for k, v in data.get("pending_offers", {}).items()}
        data["impeach_votes"] = set(data.get("impeach_votes", []))
        return data
    else:
        new_data = {
            "is_clean": True,
            "roles": {},
            "balances": {},
            "daily_claimed": {},
            "stock": {"ingredients": 50, "alcohol": 50},
            "orders": {},
            "order_counter": 1,
            "daily_revenue": 0,
            "orders_completed": 0,
            "ratings": [],
            "pending_offers": {},
            "impeach_votes": set(),
        }
        save_group_data(chat_id, new_data)
        return new_data

def save_group_data(chat_id, data):
    serializable = data.copy()
    serializable["impeach_votes"] = list(data.get("impeach_votes", set()))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cafe_groups (chat_id, data_json)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET data_json = excluded.data_json
    """, (chat_id, json.dumps(serializable)))
    conn.commit()
    conn.close()

# ================= 3. BOT CONFIGURATION =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

BOT_TOKEN = "8904773233:AAFsfvuVo5BxPxkEwmq7xGoEy4BvPJhT2FQ"

ROLE_LIMITS = {
    "owner": 1,
    "manager": 1,
    "store_manager": 3,
    "bar_manager": 3,
    "chef": 1,
    "barista": 5,
    "cook": 5,
    "waiter": 5,
    "butler": 3,
    "bouncer": 5,
    "cashier": 5,
    "cleaner": 2,
    "gatekeeper": 1,
}

SALARIES = {
    "owner": 5000,
    "manager": 3500,
    "store_manager": 2500,
    "bar_manager": 2500,
    "chef": 3000,
    "barista": 2000,
    "cook": 2000,
    "butler": 2200,
    "bouncer": 1500,
    "waiter": 1500,
    "cashier": 1800,
    "cleaner": 1200,
    "gatekeeper": 1000,
}

ALL_ROUNDERS = ["owner", "manager", "butler"]

MENU = {
    "fries": {"category": "Snacks", "price": 40, "type": "kitchen", "ingredients": ["potato", "oil", "salt"]},
    "garlic_bread": {"category": "Snacks", "price": 50, "type": "kitchen", "ingredients": ["bread", "garlic_butter"]},
    "nuggets": {"category": "Snacks", "price": 75, "type": "kitchen", "ingredients": ["chicken", "batter", "oil"]},
    "sandwich": {"category": "Mains", "price": 90, "type": "kitchen", "ingredients": ["bread", "veggies", "cheese"]},
    "burger": {"category": "Mains", "price": 110, "type": "kitchen", "ingredients": ["bun", "patty", "lettuce"]},
    "pasta": {"category": "Mains", "price": 140, "type": "kitchen", "ingredients": ["pasta", "sauce", "cheese"]},
    "pizza": {"category": "Mains", "price": 180, "type": "kitchen", "ingredients": ["dough", "mozzarella", "sauce"]},
    "steak": {"category": "Mains", "price": 240, "type": "kitchen", "ingredients": ["meat_cut", "butter", "veggies"]},
    "espresso": {"category": "Coffee & Beverages", "price": 35, "type": "barista", "ingredients": ["coffee_beans", "water"]},
    "americano": {"category": "Coffee & Beverages", "price": 45, "type": "barista", "ingredients": ["coffee_beans", "water", "ice"]},
    "cappuccino": {"category": "Coffee & Beverages", "price": 65, "type": "barista", "ingredients": ["coffee_beans", "milk"]},
    "frappe": {"category": "Coffee & Beverages", "price": 90, "type": "barista", "ingredients": ["coffee_beans", "milk", "caramel"]},
    "matcha": {"category": "Coffee & Beverages", "price": 95, "type": "barista", "ingredients": ["matcha_powder", "milk"]},
    "croissant": {"category": "Bakery & Desserts", "price": 45, "type": "kitchen", "ingredients": ["croissant_pastry"]},
    "brownie": {"category": "Bakery & Desserts", "price": 60, "type": "kitchen", "ingredients": ["chocolate", "flour"]},
    "cheesecake": {"category": "Bakery & Desserts", "price": 85, "type": "kitchen", "ingredients": ["cream_cheese", "biscuit_base"]},
    "beer": {"category": "Bar", "price": 110, "type": "bar", "ingredients": ["beer_tap"]},
    "mojito": {"category": "Bar", "price": 130, "type": "bar", "ingredients": ["white_rum", "mint", "lime"]},
    "wine": {"category": "Bar", "price": 160, "type": "bar", "ingredients": ["wine_bottle"]},
    "whiskey": {"category": "Bar", "price": 200, "type": "bar", "ingredients": ["whiskey_bottle"]},
}

def get_user_balance(group, user_id):
    return group["balances"].get(user_id, 10000)

def check_role(group, user_id, required_role):
    user_info = group["roles"].get(user_id)
    if not user_info:
        return False
    user_role = user_info["role"]
    if user_role in ALL_ROUNDERS:
        return True
    if isinstance(required_role, list):
        return user_role in required_role
    return user_role == required_role

def normalize_role(role_str):
    return role_str.strip().lower().replace(" ", "_")

# ================= 4. COMMANDS =================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **CAFE MANAGEMENT BOT - ALL COMMANDS** 📜\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👥 **Customer & General:**\n"
        "• `/help` — View command guide\n"
        "• `/menu` — View food, coffee & bar menu\n"
        "• `/order <item> [qty]` — Order items\n"
        "• `/account` — Check balance & salary\n"
        "• `/daily` — Claim 10,000 coins + salary\n"
        "• `/tip <order_id> <amount>` — Tip the staff\n"
        "• `/rate <1-5>` — Rate the cafe (1 to 5 stars)\n"
        "• `/impeach_owner` — Vote to remove the Owner (5 votes)\n\n"
        "💼 **Management:**\n"
        "• `/claim_role <role>` — Take an open role\n"
        "• `/workers` — View staff directory\n"
        "• `/appoint <role>` — Appoint staff (Reply to user)\n"
        "• `/fire` — Dismiss staff (Reply to user)\n"
        "• `/summary` — View operational report\n\n"
        "👨‍🍳 **Staff Operations (Owner, Manager & Butler do all):**\n"
        "• `/arrange_ingredients` — Refill kitchen stock (Store Mgr)\n"
        "• `/arrange_alcohol` — Refill bar stock (Bar Mgr)\n"
        "• `/recipe <item>` — View dish ingredients (Chef)\n"
        "• `/cook <order_id>` — Cook food (Cook/Chef)\n"
        "• `/make <order_id>` — Prepare coffee (Barista)\n"
        "• `/supply <order_id>` — Supply drinks (Bar Mgr)\n"
        "• `/serve <order_id>` — Deliver food (Waiter/Butler)\n"
        "• `/billing <order_id>` — Collect payment (Cashier)\n"
        "• `/cleaning` — Clean cafe (Cleaner)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def claim_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = load_group_data(chat_id)
    
    if not context.args:
        roles_list = "\n".join([f"• `{r}` (Max: {limit})" for r, limit in ROLE_LIMITS.items()])
        await update.message.reply_text(f"**Available Roles:**\n{roles_list}\n\nUsage: `/claim_role <role_name>`", parse_mode="Markdown")
        return

    requested_role = normalize_role(" ".join(context.args))
    if requested_role not in ROLE_LIMITS:
        await update.message.reply_text("❌ Invalid role name! Type `/claim_role` to view options.")
        return

    current_count = sum(1 for data in group["roles"].values() if data["role"] == requested_role)
    if current_count >= ROLE_LIMITS[requested_role]:
        await update.message.reply_text(f"❌ All slots for **{requested_role.replace('_', ' ').title()}** are filled!")
        return

    group["roles"][user.id] = {"role": requested_role, "name": user.first_name}
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🎉 Congratulations {user.first_name}! You are now **{requested_role.replace('_', ' ').title()}**.", parse_mode="Markdown")

async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = load_group_data(chat_id)
    
    balance = get_user_balance(group, user.id)
    user_info = group["roles"].get(user.id)
    role_name = user_info["role"].replace("_", " ").title() if user_info else "Customer"
    salary = SALARIES.get(user_info["role"], 0) if user_info else 0
    all_rounder_tag = " *(All-Rounder)*" if user_info and user_info["role"] in ALL_ROUNDERS else ""

    await update.message.reply_text(f"👤 **Account:**\n• Role: **{role_name}**{all_rounder_tag}\n• Daily Salary: **{salary:,} Coins**\n• Balance: **{balance:,} Coins**", parse_mode="Markdown")

async def workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    
    if not group["roles"]:
        await update.message.reply_text("🏢 No staff members hired yet in this cafe.")
        return

    text = "🏢 **CAFE STAFF DIRECTORY** 🏢\n\n"
    by_role = {}
    for uid, data in group["roles"].items():
        by_role.setdefault(data["role"], []).append(data["name"])
    for role, names in by_role.items():
        text += f"• **{role.replace('_', ' ').title()}** ({len(names)}/{ROLE_LIMITS.get(role, 0)}): {', '.join(names)}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def appoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    group = load_group_data(chat_id)

    sender_role = group["roles"].get(sender.id, {}).get("role")
    if sender_role not in ["owner", "manager"]:
        await update.message.reply_text("❌ Only Owner or Manager can appoint staff!")
        return

    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Usage: Reply to user with `/appoint <role>`")
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.is_bot:
        await update.message.reply_text("❌ Cannot appoint bots.")
        return

    target_role = normalize_role(" ".join(context.args))
    if target_role not in ROLE_LIMITS:
        await update.message.reply_text("❌ Invalid role.")
        return

    if sender_role == "manager" and target_role in ["owner", "manager"]:
        await update.message.reply_text("❌ Managers cannot appoint another Manager or Owner.")
        return

    current_count = sum(1 for data in group["roles"].values() if data["role"] == target_role)
    if current_count >= ROLE_LIMITS[target_role]:
        await update.message.reply_text(f"❌ Slots full for **{target_role.replace('_', ' ').title()}**.")
        return

    group["pending_offers"][target_user.id] = {"role": target_role, "chat_id": chat_id}
    save_group_data(chat_id, group)

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_job_{target_user.id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"decline_job_{target_user.id}")
        ]
    ]
    await update.message.reply_text(
        f"📩 **Job Offer!**\nHey {target_user.first_name}, you have been offered **{target_role.replace('_', ' ').title()}** by {sender.first_name}!\nDaily Salary: **{SALARIES.get(target_role, 0):,} Coins**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def job_response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)

    if data.startswith("accept_job_"):
        target_id = int(data.replace("accept_job_", ""))
        if user.id != target_id:
            await query.answer("❌ This offer is not for you!", show_alert=True)
            return

        offer = group["pending_offers"].pop(user.id, None)
        if not offer:
            await query.edit_message_text("❌ Offer expired.")
            return

        group["roles"][user.id] = {"role": offer["role"], "name": user.first_name}
        save_group_data(chat_id, group)
        await query.edit_message_text(f"🎉 **Offer Accepted!** {user.first_name} is now hired as **{offer['role'].replace('_', ' ').title()}**.")

    elif data.startswith("decline_job_"):
        target_id = int(data.replace("decline_job_", ""))
        if user.id != target_id:
            await query.answer("❌ This offer is not for you!", show_alert=True)
            return

        group["pending_offers"].pop(user.id, None)
        save_group_data(chat_id, group)
        await query.edit_message_text(f"❌ {user.first_name} declined the offer.")

async def fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    group = load_group_data(chat_id)

    sender_role = group["roles"].get(sender.id, {}).get("role")
    if sender_role not in ["owner", "manager"]:
        await update.message.reply_text("❌ Only Owner or Manager can fire staff!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the user with `/fire`.")
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.id not in group["roles"]:
        await update.message.reply_text("User is not holding any staff position.")
        return

    target_role = group["roles"][target_user.id]["role"]
    if target_role == "owner":
        await update.message.reply_text("Cannot fire Owner directly! Use `/impeach_owner`.")
        return

    if sender_role == "manager" and target_role == "manager":
        await update.message.reply_text("Managers cannot fire other Managers!")
        return

    del group["roles"][target_user.id]
    save_group_data(chat_id, group)
    await update.message.reply_text(f"⚠️ {target_user.first_name} has been dismissed from **{target_role.replace('_', ' ').title()}**.")

async def impeach_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    voter = update.effective_user
    group = load_group_data(chat_id)

    owner_entry = next(((uid, data) for uid, data in group["roles"].items() if data["role"] == "owner"), None)
    if not owner_entry:
        await update.message.reply_text("No active Owner to impeach.")
        return

    owner_id, owner_data = owner_entry
    if voter.id == owner_id:
        await update.message.reply_text("You cannot vote against yourself.")
        return

    if voter.id in group["impeach_votes"]:
        await update.message.reply_text(f"⚠️ Already voted! Votes: **{len(group['impeach_votes'])}/5**", parse_mode="Markdown")
        return

    group["impeach_votes"].add(voter.id)
    if len(group["impeach_votes"]) >= 5:
        del group["roles"][owner_id]
        group["impeach_votes"].clear()
        save_group_data(chat_id, group)
        await update.message.reply_text(f"🚨 **IMPEACHMENT SUCCESSFUL!** Owner **{owner_data['name']}** has been removed!\nOwner role is open: `/claim_role owner`.")
    else:
        save_group_data(chat_id, group)
        await update.message.reply_text(f"🗳️ Vote recorded! **{len(group['impeach_votes'])}/5 votes**.")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = load_group_data(chat_id)
    
    last_claim_str = group["daily_claimed"].get(user.id)
    now = datetime.utcnow()

    if last_claim_str:
        last_claim = datetime.fromisoformat(last_claim_str)
        if (now - last_claim) < timedelta(hours=20):
            await update.message.reply_text("⏳ You already claimed your daily reward today. Come back tomorrow!")
            return

    base_reward = 10000
    user_info = group["roles"].get(user.id)
    salary = SALARIES.get(user_info["role"], 0) if user_info else 0
    total = base_reward + salary

    group["balances"][user.id] = get_user_balance(group, user.id) + total
    group["daily_claimed"][user.id] = now.isoformat()
    save_group_data(chat_id, group)

    salary_text = f"\n💼 Role Salary: +{salary:,} Coins ({user_info['role'].replace('_', ' ').title()})" if salary else ""
    await update.message.reply_text(
        f"💰 **Daily Allowance Collected!**\n• Base Allowance: **+{base_reward:,} Coins**{salary_text}\n• Total Added: **+{total:,} Coins**\n• Balance: **{group['balances'][user.id]:,} Coins**",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = {}
    for item, details in MENU.items():
        categories.setdefault(details["category"], []).append((item, details["price"], details["type"]))
    text = "☕ **CAFE MENU** 🍽️\n"
    for cat, items in categories.items():
        text += f"\n**--- {cat} ---**\n"
        for i, p, t in items:
            text += f"• `{i}` — **{p:,} Coins** ({t.capitalize()})\n"
    text += "\n📌 `/order <item> [qty]` (e.g. `/order pizza 2`)"
    await update.message.reply_text(text, parse_mode="Markdown")

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = load_group_data(chat_id)

    if not group["is_clean"]:
        await update.message.reply_text("🧹 Cafe is dirty! Use `/cleaning` first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/order <food_name> [qty]`")
        return

    item = context.args[0].lower()
    qty = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 1
    if item not in MENU:
        await update.message.reply_text("❌ Item not in menu.")
        return

    cost = MENU[item]["price"] * qty
    if get_user_balance(group, user.id) < cost:
        await update.message.reply_text(f"❌ Need {cost:,} Coins! Your Balance: {get_user_balance(group, user.id):,}")
        return

    order_id = group["order_counter"]
    group["order_counter"] += 1
    group["orders"][order_id] = {
        "customer_id": user.id,
        "customer_name": user.first_name,
        "item": item,
        "quantity": qty,
        "total_cost": cost,
        "type": MENU[item]["type"],
        "status": "pending_cook",
        "waiter_id": None
    }
    save_group_data(chat_id, group)
    await update.message.reply_text(f"📝 **Order #{order_id}:** {item.capitalize()} x {qty} (**{cost:,} Coins**)")

async def recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = load_group_data(chat_id)
    if not check_role(group, user.id, "chef"): return
    if not context.args or context.args[0].lower() not in MENU: return
    await update.message.reply_text(f"📜 Ingredients: `{', '.join(MENU[context.args[0].lower()]['ingredients'])}`", parse_mode="Markdown")

async def arrange_ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "store_manager"): return
    group["stock"]["ingredients"] += 30
    save_group_data(chat_id, group)
    await update.message.reply_text(f"📦 Kitchen stock: {group['stock']['ingredients']} units.")

async def arrange_alcohol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "bar_manager"): return
    group["stock"]["alcohol"] += 30
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🍾 Bar stock: {group['stock']['alcohol']} units.")

async def cook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, ["cook", "chef"]) or not context.args: return
    order_id = int(context.args[0]) if context.args[0].isdigit() else 0
    o = group["orders"].get(order_id)
    if not o or o["status"] != "pending_cook" or o["type"] != "kitchen": return
    if group["stock"]["ingredients"] < o["quantity"]:
        await update.message.reply_text("❌ Out of kitchen ingredients!")
        return
    group["stock"]["ingredients"] -= o["quantity"]
    o["status"] = "ready_to_serve"
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🍳 Order #{order_id} cooked! Deliver with `/serve {order_id}`.")

async def make_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "barista") or not context.args: return
    order_id = int(context.args[0]) if context.args[0].isdigit() else 0
    o = group["orders"].get(order_id)
    if not o or o["status"] != "pending_cook" or o["type"] != "barista": return
    o["status"] = "ready_to_serve"
    save_group_data(chat_id, group)
    await update.message.reply_text(f"☕ Order #{order_id} ready! Deliver with `/serve {order_id}`.")

async def supply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "bar_manager") or not context.args: return
    order_id = int(context.args[0]) if context.args[0].isdigit() else 0
    o = group["orders"].get(order_id)
    if not o or o["status"] != "pending_cook" or o["type"] != "bar": return
    if group["stock"]["alcohol"] < o["quantity"]:
        await update.message.reply_text("❌ Out of alcohol units!")
        return
    group["stock"]["alcohol"] -= o["quantity"]
    o["status"] = "ready_to_serve"
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🍾 Order #{order_id} supplied! Deliver with `/serve {order_id}`.")

async def serve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "waiter") or not context.args: return
    order_id = int(context.args[0]) if context.args[0].isdigit() else 0
    o = group["orders"].get(order_id)
    if not o or o["status"] != "ready_to_serve": return
    o["status"] = "served"
    o["waiter_id"] = update.effective_user.id
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🍽️ Order #{order_id} served! Cashier settle with `/billing {order_id}`.")

async def billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "cashier") or not context.args: return
    order_id = int(context.args[0]) if context.args[0].isdigit() else 0
    o = group["orders"].get(order_id)
    if not o or o["status"] != "served": return
    cid = o["customer_id"]
    group["balances"][cid] = get_user_balance(group, cid) - o["total_cost"]
    group["daily_revenue"] += o["total_cost"]
    group["orders_completed"] += 1
    o["status"] = "paid"
    save_group_data(chat_id, group)
    await update.message.reply_text(f"🧾 Settled #{order_id}! Paid: **{o['total_cost']:,} Coins**.", parse_mode="Markdown")

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if len(context.args) < 2: return
    order_id, amt = int(context.args[0]), int(context.args[1])
    o = group["orders"].get(order_id)
    if not o or o["customer_id"] != update.effective_user.id or not o.get("waiter_id"): return
    if get_user_balance(group, update.effective_user.id) < amt: return
    group["balances"][update.effective_user.id] -= amt
    group["balances"][o["waiter_id"]] = get_user_balance(group, o["waiter_id"]) + amt
    save_group_data(chat_id, group)
    await update.message.reply_text(f"💖 Tip of **{amt:,} Coins** sent!", parse_mode="Markdown")

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not context.args or not context.args[0].isdigit(): return
    score = int(context.args[0])
    if 1 <= score <= 5:
        group["ratings"].append(score)
        save_group_data(chat_id, group)
        await update.message.reply_text(f"🌟 Rated {score}/5 {'⭐'*score}!")

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, ["manager", "owner"]): return
    avg = f"{sum(group['ratings'])/len(group['ratings']):.2f}/5 ⭐" if group["ratings"] else "No ratings"
    await update.message.reply_text(
        f"📊 **OPERATIONAL REPORT**\n• Revenue: **{group['daily_revenue']:,} Coins**\n• Completed Orders: **{group['orders_completed']}**\n• Rating: **{avg}**\n• Kitchen Stock: **{group['stock']['ingredients']}**\n• Bar Stock: **{group['stock']['alcohol']}**",
        parse_mode="Markdown"
    )

async def cleaning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = load_group_data(chat_id)
    if not check_role(group, update.effective_user.id, "cleaner"): return
    group["is_clean"] = True
    save_group_data(chat_id, group)
    await update.message.reply_text("✨ Cafe cleaned and sanitized!")

# ================= 5. APPLICATION RUNNER =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    commands = [
        ("help", help_command), ("claim_role", claim_role), ("account", account),
        ("workers", workers), ("appoint", appoint), ("fire", fire),
        ("impeach_owner", impeach_owner), ("daily", daily), ("menu", menu),
        ("order", order), ("recipe", recipe), ("arrange_ingredients", arrange_ingredients),
        ("arrange_alcohol", arrange_alcohol), ("cook", cook), ("make", make_coffee),
        ("supply", supply), ("serve", serve), ("billing", billing),
        ("tip", tip), ("rate", rate), ("summary", summary), ("cleaning", cleaning)
    ]
    for cmd, fn in commands:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(job_response_callback))
    
    print("Cafe Bot is active and running permanently...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
