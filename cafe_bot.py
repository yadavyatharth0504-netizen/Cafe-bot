import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= 1. DUMMY WEB SERVER (FOR 24/7 RENDER HOSTING) =================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"The Cafeteria Bot is 24/7 Active & Running!")

    def log_message(self, format, *args):
        return  # Keep terminal logs clean

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# ================= 2. BOT CONFIGURATION & DATA =================
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
    # Snacks
    "fries": {"category": "Snacks", "price": 40, "type": "kitchen", "ingredients": ["potato", "oil", "salt"]},
    "garlic_bread": {"category": "Snacks", "price": 50, "type": "kitchen", "ingredients": ["bread", "garlic_butter"]},
    "nuggets": {"category": "Snacks", "price": 75, "type": "kitchen", "ingredients": ["chicken", "batter", "oil"]},
    # Mains
    "sandwich": {"category": "Mains", "price": 90, "type": "kitchen", "ingredients": ["bread", "veggies", "cheese"]},
    "burger": {"category": "Mains", "price": 110, "type": "kitchen", "ingredients": ["bun", "patty", "lettuce"]},
    "pasta": {"category": "Mains", "price": 140, "type": "kitchen", "ingredients": ["pasta", "sauce", "cheese"]},
    "pizza": {"category": "Mains", "price": 180, "type": "kitchen", "ingredients": ["dough", "mozzarella", "sauce"]},
    "steak": {"category": "Mains", "price": 240, "type": "kitchen", "ingredients": ["meat_cut", "butter", "veggies"]},
    # Coffee & Beverages
    "espresso": {"category": "Coffee & Beverages", "price": 35, "type": "barista", "ingredients": ["coffee_beans", "water"]},
    "americano": {"category": "Coffee & Beverages", "price": 45, "type": "barista", "ingredients": ["coffee_beans", "water", "ice"]},
    "cappuccino": {"category": "Coffee & Beverages", "price": 65, "type": "barista", "ingredients": ["coffee_beans", "milk"]},
    "frappe": {"category": "Coffee & Beverages", "price": 90, "type": "barista", "ingredients": ["coffee_beans", "milk", "caramel"]},
    "matcha": {"category": "Coffee & Beverages", "price": 95, "type": "barista", "ingredients": ["matcha_powder", "milk"]},
    # Desserts
    "croissant": {"category": "Bakery & Desserts", "price": 45, "type": "kitchen", "ingredients": ["croissant_pastry"]},
    "brownie": {"category": "Bakery & Desserts", "price": 60, "type": "kitchen", "ingredients": ["chocolate", "flour"]},
    "cheesecake": {"category": "Bakery & Desserts", "price": 85, "type": "kitchen", "ingredients": ["cream_cheese", "biscuit_base"]},
    # Bar
    "beer": {"category": "Bar", "price": 110, "type": "bar", "ingredients": ["beer_tap"]},
    "mojito": {"category": "Bar", "price": 130, "type": "bar", "ingredients": ["white_rum", "mint", "lime"]},
    "wine": {"category": "Bar", "price": 160, "type": "bar", "ingredients": ["wine_bottle"]},
    "whiskey": {"category": "Bar", "price": 200, "type": "bar", "ingredients": ["whiskey_bottle"]},
}

groups_data = {}

def get_group(chat_id):
    if chat_id not in groups_data:
        groups_data[chat_id] = {
            "is_clean": True,
            "roles": {},          # {user_id: {"role": role_name, "name": user_name}}
            "balances": {},       # {user_id: amount}
            "daily_claimed": {},  # {user_id: datetime}
            "stock": {"ingredients": 50, "alcohol": 50},
            "orders": {},         # {order_id: dict}
            "order_counter": 1,
            "daily_revenue": 0,
            "orders_completed": 0,
            "ratings": [],
            "pending_offers": {},
            "impeach_votes": set(),
        }
    return groups_data[chat_id]

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

# ================= 3. COMMAND HANDLERS =================

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📜 **CAFE MANAGEMENT BOT - ALL COMMANDS** 📜\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👥 **Customer & General Commands:**\n"
        "• `/help` — View this complete command list\n"
        "• `/menu` — View available food, coffee & bar drinks\n"
        "• `/order <item> [qty]` — Order items (e.g., `/order burger 2`)\n"
        "• `/account` — Check your wallet balance, role & salary\n"
        "• `/daily` — Claim daily 10,000 coins (+ role salary)\n"
        "• `/tip <order_id> <amount>` — Tip the staff member\n"
        "• `/rate <1-5>` — Rate the cafe (1 to 5 stars)\n"
        "• `/impeach_owner` — Vote to remove the Owner (5 votes needed)\n\n"
        "💼 **Role & Staff Management:**\n"
        "• `/claim_role <role>` — Take an open job role\n"
        "• `/workers` — View list of all active cafe staff\n"
        "• `/appoint <role>` — Appoint a user to a post (Reply to user)\n"
        "• `/fire` — Dismiss a staff member (Reply to user)\n"
        "• `/summary` — View operational report & daily revenue (Manager/Owner)\n\n"
        "👨‍🍳 **Staff Operations (Owner, Manager & Butler can do all):**\n"
        "• `/arrange_ingredients` — Refill kitchen stock (Store Manager)\n"
        "• `/arrange_alcohol` — Refill bar stock (Bar Manager)\n"
        "• `/recipe <item>` — View dish ingredients (Chef)\n"
        "• `/cook <order_id>` — Cook food (Cook/Chef)\n"
        "• `/make <order_id>` — Prepare coffee (Barista)\n"
        "• `/supply <order_id>` — Prepare & supply drinks (Bar Manager)\n"
        "• `/serve <order_id>` — Deliver food/drink to customer (Waiter/Butler)\n"
        "• `/billing <order_id>` — Collect payment & settle bill (Cashier)\n"
        "• `/cleaning` — Clean and reopen the cafe (Cleaner)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# /claim_role
async def claim_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)
    
    if not context.args:
        roles_list = "\n".join([f"• `{r}` (Max: {limit})" for r, limit in ROLE_LIMITS.items()])
        await update.message.reply_text(
            f"**Available Roles & Limits:**\n{roles_list}\n\nUsage: `/claim_role <role_name>`\n(e.g., `/claim_role bouncer` or `/claim_role butler`)",
            parse_mode="Markdown"
        )
        return

    requested_role = normalize_role(" ".join(context.args))
    if requested_role not in ROLE_LIMITS:
        await update.message.reply_text("❌ Invalid role name! Type `/claim_role` to view options.")
        return

    current_count = sum(1 for data in group["roles"].values() if data["role"] == requested_role)
    if current_count >= ROLE_LIMITS[requested_role]:
        await update.message.reply_text(
            f"❌ All slots for **{requested_role.replace('_', ' ').title()}** ({ROLE_LIMITS[requested_role]}/{ROLE_LIMITS[requested_role]}) are occupied!"
        )
        return

    group["roles"][user.id] = {"role": requested_role, "name": user.first_name}
    await update.message.reply_text(
        f"🎉 Congratulations {user.first_name}! You are now assigned as **{requested_role.replace('_', ' ').title()}**.",
        parse_mode="Markdown"
    )

# /account
async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)
    
    balance = get_user_balance(group, user.id)
    user_info = group["roles"].get(user.id)
    role_name = user_info["role"].replace("_", " ").title() if user_info else "Customer"
    salary = SALARIES.get(user_info["role"], 0) if user_info else 0

    all_rounder_tag = " *(All-Rounder)*" if user_info and user_info["role"] in ALL_ROUNDERS else ""

    await update.message.reply_text(
        f"👤 **Account Details**\n"
        f"• Name: {user.first_name}\n"
        f"• Role: **{role_name}**{all_rounder_tag}\n"
        f"• Daily Salary: **{salary:,} Coins**\n"
        f"• Total Balance: **{balance:,} Coins**",
        parse_mode="Markdown"
    )

# /workers
async def workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    group = get_group(chat_id)
    
    if not group["roles"]:
        await update.message.reply_text("🏢 No staff members are currently hired in this cafe.")
        return

    text = "🏢 **CAFE STAFF DIRECTORY** 🏢\n\n"
    by_role = {}
    for uid, data in group["roles"].items():
        by_role.setdefault(data["role"], []).append(data["name"])

    for role, names in by_role.items():
        role_title = role.replace("_", " ").title()
        names_str = ", ".join(names)
        text += f"• **{role_title}** ({len(names)}/{ROLE_LIMITS.get(role, 0)}): {names_str}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# /appoint
async def appoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    group = get_group(chat_id)

    sender_role = group["roles"].get(sender.id, {}).get("role")
    if sender_role not in ["owner", "manager"]:
        await update.message.reply_text("❌ Only the **Owner** or **Manager** can appoint staff!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to a user's message: `/appoint <role>`")
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.is_bot:
        await update.message.reply_text("❌ You cannot appoint a bot.")
        return

    if not context.args:
        await update.message.reply_text("Usage: Reply to a user with `/appoint <role>`")
        return

    target_role = normalize_role(" ".join(context.args))
    if target_role not in ROLE_LIMITS:
        await update.message.reply_text("❌ Invalid role specified.")
        return

    if sender_role == "manager" and target_role in ["owner", "manager"]:
        await update.message.reply_text("❌ Managers cannot appoint another Manager or Owner.")
        return

    current_count = sum(1 for data in group["roles"].values() if data["role"] == target_role)
    if current_count >= ROLE_LIMITS[target_role]:
        await update.message.reply_text(f"❌ All slots for **{target_role.replace('_', ' ').title()}** are filled.")
        return

    group["pending_offers"][target_user.id] = {"role": target_role, "chat_id": chat_id}

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept Offer", callback_data=f"accept_job_{target_user.id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"decline_job_{target_user.id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📩 **Job Offer!**\n"
        f"Hey {target_user.first_name}, you have been offered the role of **{target_role.replace('_', ' ').title()}** by {sender.first_name}!\n"
        f"Daily Salary: **{SALARIES.get(target_role, 0):,} Coins**\n\n"
        f"Do you accept?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Callback for Job Acceptance/Rejection
async def job_response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_id = update.effective_chat.id
    group = get_group(chat_id)

    if data.startswith("accept_job_"):
        target_id = int(data.replace("accept_job_", ""))
        if user.id != target_id:
            await query.answer("❌ This offer is not for you!", show_alert=True)
            return

        offer = group["pending_offers"].pop(user.id, None)
        if not offer:
            await query.edit_message_text("❌ This offer has expired or is no longer valid.")
            return

        role = offer["role"]
        group["roles"][user.id] = {"role": role, "name": user.first_name}
        await query.edit_message_text(f"🎉 **Offer Accepted!** {user.first_name} is now hired as **{role.replace('_', ' ').title()}**.")

    elif data.startswith("decline_job_"):
        target_id = int(data.replace("decline_job_", ""))
        if user.id != target_id:
            await query.answer("❌ This offer is not for you!", show_alert=True)
            return

        group["pending_offers"].pop(user.id, None)
        await query.edit_message_text(f"❌ {user.first_name} declined the job offer.")

# /fire
async def fire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender = update.effective_user
    group = get_group(chat_id)

    sender_role = group["roles"].get(sender.id, {}).get("role")
    if sender_role not in ["owner", "manager"]:
        await update.message.reply_text("❌ Only the **Owner** or **Manager** can fire staff!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Please reply to the user you want to fire: `/fire`")
        return

    target_user = update.message.reply_to_message.from_user
    if target_user.id not in group["roles"]:
        await update.message.reply_text("❌ That user does not hold any staff position.")
        return

    target_role = group["roles"][target_user.id]["role"]
    if target_role == "owner":
        await update.message.reply_text("❌ The Owner cannot be fired directly! Use `/impeach_owner` to vote them out.")
        return

    if sender_role == "manager" and target_role == "manager":
        await update.message.reply_text("❌ Managers cannot fire other Managers!")
        return

    del group["roles"][target_user.id]
    await update.message.reply_text(
        f"⚠️ {target_user.first_name} has been dismissed from their position as **{target_role.replace('_', ' ').title()}**."
    )

# /impeach_owner
async def impeach_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    voter = update.effective_user
    group = get_group(chat_id)

    owner_entry = next(((uid, data) for uid, data in group["roles"].items() if data["role"] == "owner"), None)
    if not owner_entry:
        await update.message.reply_text("ℹ️ There is currently no active Owner in this cafe to impeach.")
        return

    owner_id, owner_data = owner_entry
    if voter.id == owner_id:
        await update.message.reply_text("❌ You cannot vote to impeach yourself!")
        return

    if voter.id in group["impeach_votes"]:
        await update.message.reply_text(f"⚠️ {voter.first_name}, you already voted! Current votes: **{len(group['impeach_votes'])}/5**", parse_mode="Markdown")
        return

    group["impeach_votes"].add(voter.id)
    vote_count = len(group["impeach_votes"])

    if vote_count >= 5:
        del group["roles"][owner_id]
        group["impeach_votes"].clear()
        await update.message.reply_text(
            f"🚨 **IMPEACHMENT SUCCESSFUL!** 🚨\n\n"
            f"**5 members** have voted against Owner **{owner_data['name']}**.\n"
            f"**{owner_data['name']}** has been removed from the Owner position!\n\n"
            f"👑 The Owner role is now open. Anyone can claim it using `/claim_role owner`.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"🗳️ **Impeachment Vote Registered!**\n"
            f"{voter.first_name} voted to remove Owner **{owner_data['name']}**.\n"
            f"Current votes: **{vote_count}/5**\n"
            f"*(Need {5 - vote_count} more votes to remove the Owner)*",
            parse_mode="Markdown"
        )

# /daily
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)
    
    last_claim = group["daily_claimed"].get(user.id)
    now = datetime.utcnow()
    
    if last_claim and (now - last_claim) < timedelta(hours=20):
        await update.message.reply_text("⏳ You already claimed your daily reward. Come back tomorrow!")
        return

    base_reward = 10000
    user_info = group["roles"].get(user.id)
    salary = SALARIES.get(user_info["role"], 0) if user_info else 0
    total_received = base_reward + salary

    group["balances"][user.id] = get_user_balance(group, user.id) + total_received
    group["daily_claimed"][user.id] = now
    
    salary_text = f"\n💼 Role Salary: +{salary:,} Coins ({user_info['role'].replace('_', ' ').title()})" if salary else ""
    await update.message.reply_text(
        f"💰 **Daily Allowance Collected!**\n"
        f"• Base Allowance: **+{base_reward:,} Coins**{salary_text}\n"
        f"• Total Added: **+{total_received:,} Coins**\n"
        f"• Total Balance: **{group['balances'][user.id]:,} Coins**",
        parse_mode="Markdown"
    )

# /menu
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories = {}
    for item_key, details in MENU.items():
        cat = details["category"]
        categories.setdefault(cat, []).append((item_key, details["price"], details["type"]))

    text = "☕ **CAFE MENU** 🍽️\n"
    for cat, items in categories.items():
        text += f"\n**--- {cat} ---**\n"
        for item_key, price, prep_type in items:
            text += f"• `{item_key}` — **{price:,} Coins** ({prep_type.capitalize()})\n"
    
    text += "\n📌 Order Format: `/order <item> [quantity]` (e.g. `/order burger 2`)"
    await update.message.reply_text(text, parse_mode="Markdown")

# /order
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not group["is_clean"]:
        await update.message.reply_text("🧹 The cafe is untidy! Cleaners (or Manager/Butler) must use `/cleaning` first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/order <food_name> [quantity]` (e.g., `/order burger 2`)")
        return

    item_name = context.args[0].lower()
    quantity = 1
    if len(context.args) > 1:
        try:
            quantity = int(context.args[1])
            if quantity <= 0 or quantity > 20:
                await update.message.reply_text("❌ Quantity must be between 1 and 20.")
                return
        except ValueError:
            await update.message.reply_text("❌ Quantity must be a valid number.")
            return

    if item_name not in MENU:
        await update.message.reply_text("❌ Item not found in the menu. Check `/menu`.")
        return

    item_data = MENU[item_name]
    total_cost = item_data["price"] * quantity
    user_balance = get_user_balance(group, user.id)

    if user_balance < total_cost:
        await update.message.reply_text(
            f"❌ Insufficient balance!\nTotal: {total_cost:,} Coins | Your Balance: {user_balance:,} Coins"
        )
        return

    order_id = group["order_counter"]
    group["order_counter"] += 1
    
    group["orders"][order_id] = {
        "customer_id": user.id,
        "customer_name": user.first_name,
        "item": item_name,
        "quantity": quantity,
        "total_cost": total_cost,
        "type": item_data["type"],
        "status": "pending_cook",
        "waiter_id": None,
        "created_at": datetime.utcnow().strftime("%H:%M:%S UTC")
    }

    if item_data["type"] == "kitchen":
        action_hint = "/cook"
    elif item_data["type"] == "barista":
        action_hint = "/make"
    else:
        action_hint = "/supply"

    await update.message.reply_text(
        f"📝 **Order Placed: #{order_id}**\n"
        f"👤 Customer: {user.first_name}\n"
        f"🍽️ Item: {item_name.capitalize()} x {quantity}\n"
        f"💰 Total Amount: **{total_cost:,} Coins**\n"
        f"📌 Status: Pending Preparation ({action_hint})",
        parse_mode="Markdown"
    )

# /recipe
async def recipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "chef"):
        await update.message.reply_text("❌ Access Denied: Only the **Chef** (or Owner/Manager/Butler) can inspect recipes.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/recipe <food_name>`")
        return

    food_name = context.args[0].lower()
    if food_name not in MENU:
        await update.message.reply_text("❌ Recipe not found.")
        return

    ingredients = ", ".join(MENU[food_name]["ingredients"])
    await update.message.reply_text(
        f"📜 **Recipe for {food_name.capitalize()}:**\nRequired Ingredients: `{ingredients}`",
        parse_mode="Markdown"
    )

# /arrange_ingredients & /arrange_alcohol
async def arrange_ingredients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "store_manager"):
        await update.message.reply_text("❌ Access Denied: Only a **Store Manager** can restock ingredients.")
        return

    group["stock"]["ingredients"] += 30
    await update.message.reply_text(f"📦 Kitchen supplies refilled! Current stock: {group['stock']['ingredients']} units.")

async def arrange_alcohol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "bar_manager"):
        await update.message.reply_text("❌ Access Denied: Only a **Bar Manager** can restock the bar.")
        return

    group["stock"]["alcohol"] += 30
    await update.message.reply_text(f"🍾 Bar inventory refilled! Current stock: {group['stock']['alcohol']} units.")

# /cook
async def cook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, ["cook", "chef"]):
        await update.message.reply_text("❌ Access Denied: Only **Cooks**, **Chef**, or All-Rounders can cook meals.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/cook <order_id>`")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["status"] != "pending_cook" or order_data["type"] != "kitchen":
        await update.message.reply_text("❌ Invalid order ID or item is not pending in the kitchen.")
        return

    req_stock = order_data["quantity"]
    if group["stock"]["ingredients"] < req_stock:
        await update.message.reply_text(f"❌ Not enough kitchen ingredients! Need {req_stock}, have {group['stock']['ingredients']}.")
        return

    group["stock"]["ingredients"] -= req_stock
    order_data["status"] = "ready_to_serve"
    await update.message.reply_text(
        f"🍳 Order #{order_id} ({order_data['item'].capitalize()} x {order_data['quantity']}) is cooked! Staff can deliver with `/serve {order_id}`."
    )

# /make
async def make_coffee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "barista"):
        await update.message.reply_text("❌ Access Denied: Only a **Barista** (or All-Rounders) can make coffee.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/make <order_id>`")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["status"] != "pending_cook" or order_data["type"] != "barista":
        await update.message.reply_text("❌ Invalid order ID or item is not pending with the barista.")
        return

    order_data["status"] = "ready_to_serve"
    await update.message.reply_text(
        f"☕ Order #{order_id} ({order_data['item'].capitalize()} x {order_data['quantity']}) is ready! Staff can deliver with `/serve {order_id}`."
    )

# /supply
async def supply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "bar_manager"):
        await update.message.reply_text("❌ Access Denied: Only a **Bar Manager** (or All-Rounders) can supply bar drinks!")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/supply <order_id>`")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["status"] != "pending_cook" or order_data["type"] != "bar":
        await update.message.reply_text("❌ Invalid order ID or item is not pending at the bar.")
        return

    req_stock = order_data["quantity"]
    if group["stock"]["alcohol"] < req_stock:
        await update.message.reply_text(f"❌ Not enough alcohol units in stock! Need {req_stock}, have {group['stock']['alcohol']}. Use `/arrange_alcohol` first.")
        return

    group["stock"]["alcohol"] -= req_stock
    order_data["status"] = "ready_to_serve"
    await update.message.reply_text(
        f"🍾 Order #{order_id} ({order_data['item'].capitalize()} x {order_data['quantity']}) is supplied and ready! Staff can deliver with `/serve {order_id}`."
    )

# /serve
async def serve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "waiter"):
        await update.message.reply_text("❌ Access Denied: Only **Waiters** or All-Rounders can serve orders.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/serve <order_id>`")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["status"] != "ready_to_serve":
        await update.message.reply_text("❌ Order is not ready to serve or already delivered.")
        return

    order_data["status"] = "served"
    order_data["waiter_id"] = user.id
    await update.message.reply_text(
        f"🍽️ Order #{order_id} served to {order_data['customer_name']} by {user.first_name}!\n"
        f"Cashier (or All-Rounders) can now process the invoice with `/billing {order_id}`."
    )

# /billing
async def billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "cashier"):
        await update.message.reply_text("❌ Access Denied: Only a **Cashier** (or All-Rounders) can settle invoices.")
        return

    if not context.args:
        await update.message.reply_text("Usage: `/billing <order_id>`")
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["status"] != "served":
        await update.message.reply_text("❌ Invoices can only be processed for served orders.")
        return

    total_cost = order_data["total_cost"]
    cust_id = order_data["customer_id"]
    
    group["balances"][cust_id] = get_user_balance(group, cust_id) - total_cost
    group["daily_revenue"] += total_cost
    group["orders_completed"] += 1
    order_data["status"] = "paid"

    await update.message.reply_text(
        f"🧾 **Invoice Settled**\n"
        f"• Order: #{order_id} ({order_data['item'].capitalize()} x {order_data['quantity']})\n"
        f"• Total Deducted: **{total_cost:,} Coins**\n"
        f"• Customer Balance: **{group['balances'][cust_id]:,} Coins**\n\n"
        f"Customer can tip the server: `/tip {order_id} <amount>`",
        parse_mode="Markdown"
    )

# /tip
async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/tip <order_id> <amount>`")
        return

    try:
        order_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid parameters.")
        return

    order_data = group["orders"].get(order_id)
    if not order_data or order_data["customer_id"] != user.id:
        await update.message.reply_text("❌ You can only tip on your own orders.")
        return

    waiter_id = order_data.get("waiter_id")
    if not waiter_id:
        await update.message.reply_text("❌ No staff member is linked to this order.")
        return

    user_bal = get_user_balance(group, user.id)
    if user_bal < amount or amount <= 0:
        await update.message.reply_text("❌ Insufficient balance or invalid amount.")
        return

    group["balances"][user.id] -= amount
    group["balances"][waiter_id] = get_user_balance(group, waiter_id) + amount
    await update.message.reply_text(f"💖 Tip of **{amount:,} Coins** successfully delivered to the staff member!")

# /rate
async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not context.args:
        await update.message.reply_text("Usage: `/rate <1 to 5>` (e.g., `/rate 5`)")
        return

    try:
        score = int(context.args[0])
        if score < 1 or score > 5:
            await update.message.reply_text("❌ Rating must be between 1 and 5.")
            return
    except ValueError:
        await update.message.reply_text("❌ Please provide a numerical rating from 1 to 5.")
        return

    group["ratings"].append(score)
    stars = "⭐" * score
    await update.message.reply_text(f"🌟 Thank you {user.first_name} for rating us {score}/5 {stars}!")

# /summary
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, ["manager", "owner"]):
        await update.message.reply_text("❌ Access Denied: Only the **Manager**, **Owner**, or Butler can view the summary.")
        return

    total_orders = len(group["orders"])
    pending = sum(1 for o in group["orders"].values() if o["status"] != "paid")
    
    avg_rating = "No ratings yet"
    if group["ratings"]:
        avg_rating = f"{sum(group['ratings']) / len(group['ratings']):.2f} / 5.0 ⭐ ({len(group['ratings'])} reviews)"

    staff_count = len(group["roles"])

    report = (
        f"📊 **CAFE OPERATIONAL REPORT** 📊\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Financials:**\n"
        f"• Total Daily Revenue: **{group['daily_revenue']:,} Coins**\n\n"
        f"📋 **Orders Breakdown:**\n"
        f"• Total Orders Placed: **{total_orders}**\n"
        f"• Successfully Paid: **{group['orders_completed']}**\n"
        f"• In-Progress / Pending: **{pending}**\n\n"
        f"⭐ **Customer Satisfaction:**\n"
        f"• Average Rating: **{avg_rating}**\n\n"
        f"📦 **Inventory Status:**\n"
        f"• Kitchen Ingredients: **{group['stock']['ingredients']} units**\n"
        f"• Bar Alcohol Units: **{group['stock']['alcohol']} units**\n\n"
        f"🏢 **Operations:**\n"
        f"• Active Staff: **{staff_count} members**\n"
        f"• Cleanliness: **{'✨ Clean & Open' if group['is_clean'] else '🧹 Dirty (Needs Cleaning)'}**\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(report, parse_mode="Markdown")

# /cleaning
async def cleaning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    group = get_group(chat_id)

    if not check_role(group, user.id, "cleaner"):
        await update.message.reply_text("❌ Access Denied: Only a designated **Cleaner** (or All-Rounders) can sanitize the cafe.")
        return

    group["is_clean"] = True
    await update.message.reply_text("✨ The cafe has been cleaned and sanitized! Ready for new orders.")

# ================= 4. MAIN BOT EXECUTION =================
def main():
    # 1. Start the dummy web server in background thread for Render
    threading.Thread(target=run_web_server, daemon=True).start()

    # 2. Initialize Telegram Application
    app = Application.builder().token(BOT_TOKEN).build()

    # 3. Register All Handlers
    handlers = [
        ("help", help_command),
        ("claim_role", claim_role),
        ("account", account),
        ("workers", workers),
        ("appoint", appoint),
        ("fire", fire),
        ("impeach_owner", impeach_owner),
        ("daily", daily),
        ("menu", menu),
        ("order", order),
        ("recipe", recipe),
        ("arrange_ingredients", arrange_ingredients),
        ("arrange_alcohol", arrange_alcohol),
        ("cook", cook),
        ("make", make_coffee),
        ("supply", supply),
        ("serve", serve),
        ("billing", billing),
        ("tip", tip),
        ("rate", rate),
        ("summary", summary),
        ("cleaning", cleaning),
    ]

    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(job_response_callback))

    print("Cafe Bot is active and running 24/7...")
    app.run_polling()

if __name__ == "__main__":
    main()
