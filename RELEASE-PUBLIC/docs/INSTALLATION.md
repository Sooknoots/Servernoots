# Servernoots Suite Installation Guide

This guide will help you set up your own instance of the Servernoots suite, including all required services and credentials. Follow each section to generate your own API keys, tokens, and configuration values.

---

## 1. Prerequisites
- Linux server (Debian/Ubuntu recommended)
- Docker & Docker Compose
- Python 3.8+
- Node.js (if using stoat-server frontend)
- Git

---

## 2. Clone the Repository
```
git clone https://github.com/Sooknoots/Servernoots.git
cd Servernoots/RELEASE-PUBLIC
```

---

## 3. Environment Configuration
Copy all `.env.example` files to `.env` and fill in your own values:
```
cp master-suite/phase1/ai-control/.env.example master-suite/phase1/ai-control/.env
cp stoat-server/.env.example stoat-server/.env
```

---

## 4. Required Services & Credentials

### Telegram Bot
- Create a bot at [BotFather](https://t.me/BotFather)
- Get your `TELEGRAM_BOT_TOKEN` and add it to `.env`
- Add your Telegram user ID(s) to `TELEGRAM_ALLOWED_USER_IDS`

### Overseerr
- Deploy Overseerr: [Overseerr Docs](https://docs.overseerr.dev/)
- Generate an API key in Overseerr settings
- Set `OVERSEERR_URL` and `OVERSEERR_API_KEY` in `.env`

### Tautulli
- Deploy Tautulli: [Tautulli Docs](https://tautulli.com/)
- Generate an API key in Tautulli settings
- Set `TAUTULLI_URL` and `TAUTULLI_API_KEY` in `.env`

### Nextcloud
- Deploy Nextcloud: [Nextcloud Docs](https://docs.nextcloud.com/)
- Set up admin user and database
- Fill in `NEXTCLOUD_DB_USER`, `NEXTCLOUD_DB_PASSWORD`, `NEXTCLOUD_ADMIN_USER`, `NEXTCLOUD_ADMIN_PASSWORD` in `.env`

### SMTP (Email)
- Use your own SMTP provider (Gmail, Mailgun, etc.)
- Fill in `TEXTBOOK_SMTP_USER` and `TEXTBOOK_SMTP_PASSWORD` in `.env`

### Stoat Server Auth
- Set `STOAT_AUTH_USER` and `STOAT_AUTH_PASS` in `stoat-server/.env`

---

## 5. Deploying the Stack
- Use Docker Compose to start all services:
```
docker compose up -d
```
- For individual modules, see their README.md for details.

---

## 6. Additional Setup
- Review each module's README for further configuration.
- For Discord/Telegram integration, follow the bot setup instructions.
- For AI/LLM features, see the AI Control README and ensure Ollama or other LLM backends are running.

---

## 7. Troubleshooting
- See `TROUBLESHOOTING.md` for common issues.
- Join the community or open an issue on GitHub for help.

---

## 8. Security
- Never commit your `.env` files with real secrets to public repos.
- Rotate credentials regularly.

---

## 9. Useful Links
- [Telegram BotFather](https://t.me/BotFather)
- [Overseerr](https://overseerr.dev/)
- [Tautulli](https://tautulli.com/)
- [Nextcloud](https://nextcloud.com/)
- [Mailgun](https://www.mailgun.com/)
- [Gmail SMTP](https://support.google.com/mail/answer/7126229?hl=en)
- [Ollama](https://ollama.com/)

---

For more, see the full documentation in the `/docs` folder.
