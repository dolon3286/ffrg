# FFRG Extractor Bot

A Pyrogram/pyrofork Telegram bot for extracting course media and PDF links from supported education-platform APIs.

## VPS deployment with Docker Compose

1. Copy the example environment file and fill in your real values:

   ```bash
   cp .env.example .env
   nano .env
   ```

2. Build and start the bot:

   ```bash
   docker compose up -d --build
   ```

3. View logs:

   ```bash
   docker compose logs -f extractor-bot
   ```

4. Stop the stack:

   ```bash
   docker compose down
   ```

The compose stack runs the bot container and a MongoDB container. Bot session files are stored in the `extractor_sessions` Docker volume, and MongoDB data is stored in the `mongo_data` Docker volume.

## Required environment variables

See `.env.example` for the complete list. At minimum, set Telegram API credentials, bot token, owner/sudo user IDs, log channel IDs, and MongoDB URL.
