from __future__ import annotations

import asyncio
import logging
import os
import signal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import database as db
from worker import archive_account, pause_account, resume_account, is_paused

logger = logging.getLogger(__name__)

HELP_TEXT = """
📋 *Comandos disponibles*

/add @usuario — registrar cuenta y archivar todos sus videos
/remove @usuario — dejar de monitorear una cuenta
/stop @usuario — pausar envío de backlog
/resume @usuario — reanudar envío desde donde quedó
/list — ver cuentas monitoreadas
/status — estado del bot
/restart — reiniciar el bot
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


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /stop @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    pause_account(username)
    await update.message.reply_text(f"⏸️ @{username} pausado. El video en curso termina de enviarse y luego para.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /resume @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    account = await db.get_account_by_username(username)

    if not account or not account["is_active"]:
        await update.message.reply_text(f"@{username} no encontrado en el monitoreo.")
        return

    resume_account(username)
    await update.message.reply_text(f"▶️ @{username} reanudado.")
    context.application.create_task(archive_account(context.bot, account, resuming=True))


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="restart:confirm"),
            InlineKeyboardButton("❌ Cancelar",  callback_data="restart:cancel"),
        ]
    ])
    await update.message.reply_text("⚠️ ¿Reiniciar el bot?", reply_markup=keyboard)


async def callback_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "restart:cancel":
        await query.edit_message_text("❌ Reinicio cancelado.")
        return

    await query.edit_message_text("🔄 Reiniciando…")
    # Docker tiene restart: unless-stopped, así que al salir vuelve solo
    os.kill(os.getpid(), signal.SIGTERM)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


def build_app() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(callback_restart, pattern="^restart:"))
    return app
