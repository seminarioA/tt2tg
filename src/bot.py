from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import database as db
from worker import archive_account

logger = logging.getLogger(__name__)

HELP_TEXT = """
📋 *Comandos disponibles*

/add @usuario — registrar cuenta y archivar todos sus videos
/remove @usuario — dejar de monitorear una cuenta
/list — ver cuentas monitoreadas
/status — estado del bot
/help — mostrar esta ayuda
""".strip()


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /add @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    chat_id = update.effective_chat.id

    existing = await db.get_account_by_username(username)
    if existing and existing["is_active"]:
        await update.message.reply_text(f"@{username} ya está siendo monitoreado.")
        return

    account = await db.add_account(username, chat_id)
    # Run initial archive as background task so the command returns immediately
    context.application.create_task(archive_account(context.bot, account))


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /remove @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    removed = await db.remove_account(username)

    if removed:
        await update.message.reply_text(f"✅ @{username} eliminado del monitoreo.")
    else:
        await update.message.reply_text(f"No se encontró @{username} en el monitoreo.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await db.get_active_accounts()
    if not accounts:
        await update.message.reply_text("No hay cuentas monitoreadas.")
        return

    lines = ["📋 Cuentas monitoreadas:\n"]
    for acc in accounts:
        count = await db.get_account_video_count(acc["id"])
        last = acc["last_checked"]
        last_str = last.strftime("%Y-%m-%d %H:%M UTC") if last else "nunca"
        lines.append(f"• @{acc['username']} — {count} videos — revisado: {last_str}")

    await update.message.reply_text("\n".join(lines))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = await db.get_active_accounts()
    await update.message.reply_text(
        f"🤖 Bot activo\n📊 {len(accounts)} cuenta(s) monitoreada(s)"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


def build_app() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    return app
