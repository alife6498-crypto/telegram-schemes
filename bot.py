import os
import threading
import requests
import asyncio

from flask import Flask, jsonify, send_from_directory

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID", "")


def hdr():
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def admin(update):
    return str(update.effective_user.id) == str(ADMIN_USER_ID)


def rows():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/schemes",
        headers=hdr(),
        params={
            "select": "*",
            "order": "id.desc",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/schemes")
def api():
    try:
        return jsonify(rows())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/")
def home():
    return send_from_directory(".", "index.html")


NAME, CAT, STATUS, COLOR, IMAGE, DESC, FACTS, EXAM = range(8)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Government Schemes Bot\n\n"
        "/add — add scheme (admin)\n"
        "/schemes — manage schemes\n"
        "/help — help"
    )


async def helpc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/add — Add a new scheme\n"
        "/schemes — View schemes\n"
        "/cancel — Cancel"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END

    context.user_data.clear()

    await update.message.reply_text("1/8 — Scheme name?")
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()

    await update.message.reply_text("2/8 — Category?")
    return CAT


async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category"] = update.message.text.strip()

    await update.message.reply_text(
        "3/8 — Status/badge? (e.g. 2026, UPDATED)"
    )
    return STATUS


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["status"] = update.message.text.strip()

    await update.message.reply_text(
        "4/8 — Card colour? hex like #168a45, or default"
    )
    return COLOR


async def color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()

    if value.lower() == "default":
        context.user_data["color"] = "#168a45"
    else:
        context.user_data["color"] = value

    await update.message.reply_text("5/8 — Image URL? or none")
    return IMAGE


async def image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()

    if value.lower() == "none":
        context.user_data["image"] = ""
    else:
        context.user_data["image"] = value

    await update.message.reply_text("6/8 — Short description?")
    return DESC


async def desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()

    await update.message.reply_text(
        "7/8 — Exam facts, one per line.\n"
        "Example:\n"
        "Announced in Budget 2026-27.\n"
        "Target: 100 districts."
    )

    return FACTS


async def facts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["facts"] = [
        [f"Fact {i + 1}", x.strip()]
        for i, x in enumerate(update.message.text.splitlines())
        if x.strip()
    ]

    await update.message.reply_text(
        "8/8 — Important exam points, one per line."
    )

    return EXAM


async def exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["exam_facts"] = [
        x.strip()
        for x in update.message.text.splitlines()
        if x.strip()
    ]

    d = context.user_data

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Publish",
                callback_data="publish",
            ),
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel",
            ),
        ]
    ]

    await update.message.reply_text(
        f"📝 PREVIEW\n\n"
        f"<b>{d['name']}</b>\n"
        f"Category: {d['category']}\n"
        f"Status: {d['status']}\n\n"
        f"{d['description']}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return ConversationHandler.END


async def addcb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not admin(update):
        await query.edit_message_text("⛔ Admin only.")
        return

    if query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("Cancelled.")
        return

    d = context.user_data

    payload = {
        "name": d["name"],
        "category": d["category"],
        "status": d["status"],
        "color": d["color"],
        "image": d["image"],
        "description": d["description"],
        "facts": d["facts"],
        "exam_facts": d["exam_facts"],
    }

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/schemes",
            headers=hdr(),
            json=payload,
            timeout=20,
        )

        r.raise_for_status()

        context.user_data.clear()

        await query.edit_message_text(
            "✅ Published.\n"
            "Stack Card will update automatically."
        )

    except Exception as e:
        await query.edit_message_text(
            f"❌ Publish failed: {e}"
        )


async def schemes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return

    try:
        data = rows()

        if not data:
            await update.message.reply_text(
                "📚 No schemes found."
            )
            return

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{x['id']} • {x['name'][:35]}",
                    callback_data=f"view:{x['id']}",
                )
            ]
            for x in data[:30]
        ]

        await update.message.reply_text(
            "📚 Schemes:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}"
        )


async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not admin(update):
        await query.edit_message_text("⛔ Admin only.")
        return

    scheme_id = query.data.split(":", 1)[1]

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/schemes",
        headers=hdr(),
        params={
            "id": f"eq.{scheme_id}",
            "select": "*",
        },
        timeout=20,
    )

    r.raise_for_status()

    data = r.json()

    if not data:
        await query.edit_message_text("Not found.")
        return

    x = data[0]

    keyboard = [
        [
            InlineKeyboardButton(
                "🗑 Delete",
                callback_data=f"del:{scheme_id}",
            )
        ]
    ]

    await query.edit_message_text(
        f"📚 <b>{x['name']}</b>\n"
        f"Category: {x.get('category', '')}\n"
        f"Status: {x.get('status', '')}\n\n"
        f"{x.get('description', '')}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not admin(update):
        await query.edit_message_text("⛔ Admin only.")
        return

    scheme_id = query.data.split(":", 1)[1]

    r = requests.delete(
        f"{SUPABASE_URL}/rest/v1/schemes",
        headers=hdr(),
        params={
            "id": f"eq.{scheme_id}"
        },
        timeout=20,
    )

    if r.ok:
        await query.edit_message_text(
            "🗑 Scheme deleted."
        )
    else:
        await query.edit_message_text(
            f"❌ Delete failed: {r.text}"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Cancelled."
    )

    return ConversationHandler.END


def runbot():
    asyncio.set_event_loop(
        asyncio.new_event_loop()
    )

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add", add)
        ],
        states={
            NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    name,
                )
            ],
            CAT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    cat,
                )
            ],
            STATUS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    status,
                )
            ],
            COLOR: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    color,
                )
            ],
            IMAGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    image,
                )
            ],
            DESC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    desc,
                )
            ],
            FACTS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    facts,
                )
            ],
            EXAM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    exam,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", helpc)
    )

    application.add_handler(
        CommandHandler("schemes", schemes)
    )

    application.add_handler(conversation)

    application.add_handler(
        CallbackQueryHandler(
            addcb,
            pattern="^(publish|cancel)$",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            view,
            pattern="^view:",
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            delete,
            pattern="^del:",
        )
    )

    application.run_polling(
        close_loop=False
    )


if __name__ == "__main__":

    if not all(
        [
            SUPABASE_URL,
            SUPABASE_SECRET_KEY,
            BOT_TOKEN,
            ADMIN_USER_ID,
        ]
    ):
        raise RuntimeError(
            "Missing required environment variables"
        )

    threading.Thread(
        target=runbot,
        daemon=True,
    ).start()

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                "10000"
            )
        ),
    )
