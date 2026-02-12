# PayPal Rain Bot - Railway Deploy

Simple 1-click deployment to Railway.app

## Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

## Setup Steps

### 1. Click "Deploy on Railway" button above

### 2. Add Environment Variables

In Railway dashboard, add these variables:

```
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token
```

### 3. Get Credentials

- **API_ID & API_HASH**: https://my.telegram.org/apps
- **BOT_TOKEN**: Create bot with [@BotFather](https://t.me/BotFather)

### 4. Deploy

Railway will automatically:
- Install dependencies
- Start the bot
- Keep it running 24/7

## Manual Deploy

```bash
# Clone repo
git clone <your-repo>
cd paypal-rain-bot

# Push to Railway
railway login
railway init
railway up
```

## Commands

- `/start` - Start bot
- `/pp card|month|year|cvv` - Check single card
- Send `.txt` file - Mass check

## Owner

👤 @TomanSamurai (7926510116)
