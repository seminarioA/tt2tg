from __future__ import annotations

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import database as db
from worker import archive_account, pause_account, resume_account

logger = logging.getLogger(__name__)

HELP_TEXT = """
📋 *Comandos disponibles*

/add @usuario — registrar cuenta y archivar todos sus videos
/remove @usuario — dejar de monitorear una cuenta
/stop @usuario — pausar envío de backlog
/resume @usuario — reanudar envío desde donde quedó
/list — ver cuentas monitoreadas
/status — estado del bot
/restart @usuario — reenviar todos los videos desde el principio
/help — mostrar esta ayuda
""".strip()


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /add @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    chat_id = update.effective_chat.id

    existing = await db.get_account_by_username_and_chat(username, chat_id)
    if existing and existing["is_active"]:
        await update.message.reply_text(f"@{username} ya está siendo monitoreado en este chat.")
        return

    account = await db.add_account(username, chat_id)
    # Run initial archive as background task so the command returns immediately
    context.application.create_task(archive_account(context.bot, account))


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /remove @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    chat_id = update.effective_chat.id
    removed = await db.remove_account(username, chat_id)

    if removed:
        await update.message.reply_text(f"✅ @{username} eliminado del monitoreo en este chat.")
    else:
        await update.message.reply_text(f"No se encontró @{username} en este chat.")


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
    chat_id = update.effective_chat.id
    account = await db.get_account_by_username_and_chat(username, chat_id)
    if not account or not account["is_active"]:
        await update.message.reply_text(f"@{username} no encontrado en este chat.")
        return
    await pause_account(account)
    await update.message.reply_text(f"⏸️ @{username} pausado. El video en curso termina de enviarse y luego para.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /resume @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    chat_id = update.effective_chat.id
    account = await db.get_account_by_username_and_chat(username, chat_id)

    if not account or not account["is_active"]:
        await update.message.reply_text(f"@{username} no encontrado en este chat.")
        return

    await resume_account(account)
    await update.message.reply_text(f"▶️ @{username} reanudado.")
    context.application.create_task(archive_account(context.bot, account, resuming=True))


async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /restart @usuario")
        return

    username = context.args[0].lstrip("@").lower()
    chat_id = update.effective_chat.id
    account = await db.get_account_by_username_and_chat(username, chat_id)

    if not account or not account["is_active"]:
        await update.message.reply_text(f"@{username} no encontrado en este chat.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar", callback_data=f"restart:confirm:{account['id']}"),
            InlineKeyboardButton("❌ Cancelar",  callback_data="restart:cancel"),
        ]
    ])
    await update.message.reply_text(
        f"⚠️ ¿Reiniciar el envío de @{username}?\nSe reenviarán *todos* los videos desde el principio.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def callback_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()

        if query.data == "restart:cancel":
            await query.edit_message_text("❌ Reinicio cancelado.")
            return

        # data = "restart:confirm:{account_id}"
        account_id = int(query.data.split(":")[-1])
        account = await db.get_account_by_id(account_id)

        if not account:
            await query.edit_message_text("❌ Cuenta no encontrada.")
            return

        await db.reset_account_sent(account["id"])
        await resume_account(account)  # clear pause if it was paused before
        await query.edit_message_text(f"🔄 @{account['username']} — reiniciando envío desde el principio…")
        context.application.create_task(archive_account(context.bot, account))

    except Exception as exc:
        logger.error("callback_restart error: %s", exc)
        try:
            await query.edit_message_text("❌ Error al procesar. Intentá de nuevo.")
        except Exception:
            pass


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
