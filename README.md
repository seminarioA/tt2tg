# tt2tg — TikTok → Telegram Archiver

Archiva cuentas de TikTok y las envía automáticamente a Telegram, de las más antiguas a las más nuevas. Detecta videos nuevos y los envía en tiempo real.

**Bot:** [@TT_Dumper](https://t.me/TT_Dumper)

---

## Características

- Archiva el backlog completo de una cuenta (oldest → newest)
- Detecta y envía videos nuevos automáticamente (polling cada 10-15 min)
- Soporte para múltiples cuentas y múltiples chats/grupos
- Metadata JSON de cada video guardada en disco
- Estado persistente en PostgreSQL (sobrevive reinicios)
- Despliegue con Docker Compose + CI/CD con GitHub Actions

---

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/add @usuario` | Registra una cuenta y envía todos sus videos desde el más antiguo |
| `/stop @usuario` | Pausa el envío (persiste entre reinicios) |
| `/resume @usuario` | Reanuda el envío desde donde quedó |
| `/restart @usuario` | Reenvía todos los videos desde el principio (pide confirmación) |
| `/remove @usuario` | Deja de monitorear la cuenta en este chat |
| `/list` | Lista las cuentas monitoreadas con conteo y última revisión |
| `/status` | Estado rápido del bot |
| `/help` | Muestra la ayuda |

---

## Formato de mensajes

```
@usuario
📅 2025-05-30
❤️ 12.4K
🔁 320
💬 Descripción del video...
🔗 https://www.tiktok.com/@usuario/video/...
```

---

## Despliegue

### Requisitos

- VPS con Linux y Docker instalado
- Bot de Telegram ([@BotFather](https://t.me/BotFather))

### Instalación

```bash
git clone https://github.com/seminarioA/tt2tg.git
cd tt2tg
cp .env.example .env
nano .env  # completar TELEGRAM_BOT_TOKEN y POSTGRES_PASSWORD
mkdir -p data/metadata data/temp
docker-compose up -d --build
```

### Variables de entorno

| Variable | Descripción |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (desde @BotFather) |
| `POSTGRES_PASSWORD` | Contraseña para PostgreSQL |
| `DATA_DIR` | Directorio de datos (default: `/data`) |
| `POLL_INTERVAL_MIN` | Mínimo de minutos entre polls (default: `10`) |
| `POLL_INTERVAL_MAX` | Máximo de minutos entre polls (default: `15`) |
| `COOKIES_FILE` | (Opcional) Ruta a cookies.txt de TikTok en formato Netscape |

### CI/CD

Cada push a `main` despliega automáticamente al VPS via GitHub Actions. Requiere los siguientes secrets en el repo:

- `VPS_HOST` — IP del servidor
- `VPS_USER` — usuario SSH
- `VPS_SSH_KEY` — clave privada RSA

### Comandos útiles

```bash
# Ver logs en vivo
docker-compose logs -f archiver

# Reiniciar el bot
docker-compose restart archiver

# Actualizar manualmente
git pull && docker-compose up -d --build
```

---

## Estructura del proyecto

```
tt2tg/
├── src/
│   ├── main.py         # Punto de entrada
│   ├── bot.py          # Comandos Telegram
│   ├── worker.py       # Loop de polling y archivado
│   ├── downloader.py   # Wrapper de yt-dlp
│   ├── sender.py       # Envío a Telegram y formato de mensajes
│   ├── database.py     # Operaciones PostgreSQL
│   └── config.py       # Variables de entorno
├── migrations/
│   └── 001_init.sql    # Schema inicial de la DB
├── docker-compose.yml
└── Dockerfile
```

---

## Notas

- Los videos se eliminan del disco después de enviarse a Telegram. Los JSON de metadata se conservan.
- El bot respeta el límite de 50 MB de Telegram para archivos de video.
- Si TikTok empieza a bloquear las descargas, exportá las cookies del navegador (extensión "Get cookies.txt LOCALLY") en formato Netscape, subílas al servidor en `data/cookies.txt` y agregá `COOKIES_FILE=/data/cookies.txt` al `.env`.
