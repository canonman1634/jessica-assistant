# Jessica Setup Guide

Follow these steps in order to get Jessica running.

---

## Step 1 — Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

---

## Step 2 — Create your `.env` file

Copy the template and fill in your keys:

```bash
copy .env.example .env
```

Open `.env` and fill in:

| Variable | Where to find it |
|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys |
| `TWILIO_ACCOUNT_SID` | https://console.twilio.com → Account Info |
| `TWILIO_AUTH_TOKEN` | https://console.twilio.com → Account Info |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number in E.164 format (e.g. `+12145551234`) |
| `MY_PHONE_NUMBER` | Your personal cell number in E.164 format |
| `BLAND_API_KEY` | https://app.bland.ai → Settings → API Keys |
| `FLASK_SECRET_KEY` | Run: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `BASE_URL` | Your Railway app URL once deployed (e.g. `https://jessica-production.up.railway.app`) — enables automatic call completion notifications |
| `TZ` | Your timezone (e.g. `America/Chicago`) — defaults to `America/Chicago` if omitted |

---

## Step 3 — Set up Google Cloud (Gmail + Calendar)

1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "Jessica Assistant")
3. Enable APIs:
   - Search "Gmail API" → Enable
   - Search "Google Calendar API" → Enable
4. Create OAuth credentials:
   - Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Name: "Jessica"
   - Click **Create** → Download the JSON file
5. Save the downloaded file as `credentials/google_credentials.json`
6. Configure the OAuth consent screen:
   - Go to **APIs & Services → OAuth consent screen**
   - User type: **External**
   - Fill in app name "Jessica", your email
   - Add scopes: Gmail (read/send) + Calendar (full access)
   - Add your Gmail address as a test user

**Authorize Jessica to access your Google account (run once locally):**

```bash
python -c "from tools._google_auth import get_google_credentials; get_google_credentials()"
```

This opens a browser window. Sign in with your Gmail account and grant access.
A `credentials/google_token.json` file will be created — keep it secret (it's gitignored).

---

## Step 4 — Enable My Bright Day email notifications

In the My Bright Day app:
1. Open the app → Settings → Notifications
2. Make sure email notifications are turned **on**
3. Confirm your Gmail address is registered

Jessica will find updates by searching your Gmail for Bright Horizons emails.

---

## Step 5 — Deploy to Railway

1. Initialize git and push to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial Jessica setup"
   # Create a GitHub repo and push to it
   git remote add origin https://github.com/YOUR_USERNAME/jessica-assistant.git
   git push -u origin main
   ```

2. In Railway (https://railway.app):
   - New Project → Deploy from GitHub repo → select your repo
   - Add environment variables (copy from your `.env` file)
   - **Important**: Also add `GOOGLE_TOKEN_JSON` — see note below

3. **Google token on Railway**: Since Railway can't run the browser OAuth flow, you need to encode your token:
   ```bash
   # On your local machine after completing Step 3:
   python -c "
   import json, base64
   token = open('credentials/google_token.json').read()
   print(base64.b64encode(token.encode()).decode())
   "
   ```
   Add this as `GOOGLE_TOKEN_B64` in Railway environment variables.
   
   Then update `tools/_google_auth.py` to handle this — or just use Railway's volume mount for the credentials folder.
   
   **Easiest approach**: Use Railway's persistent volume and upload the token file via Railway CLI:
   ```bash
   railway run -- python -c "from tools._google_auth import get_google_credentials; get_google_credentials()"
   ```

4. Railway will auto-detect the `Procfile` and deploy. Your app URL will be something like:
   `https://jessica-assistant-production.up.railway.app`

---

## Step 6 — Connect Twilio webhook

1. Go to https://console.twilio.com
2. Phone Numbers → Manage → your number
3. Under **Messaging** → **A message comes in**:
   - Webhook URL: `https://YOUR-RAILWAY-URL.up.railway.app/sms`
   - Method: `HTTP POST`
4. Save

---

## Step 7 — Set your BASE_URL (enables automatic call summaries)

Once Railway gives you an app URL, add it as an environment variable:

```
BASE_URL = https://YOUR-RAILWAY-URL.up.railway.app
```

This tells Jessica to register a webhook with Bland.ai so she automatically texts you a call summary (outcome, appointment details, notes) the moment a call finishes — no need to ask.

---

## Step 8 — Test it!

Text your Twilio WhatsApp number from your personal phone:

```
Hello Jessica!
```

You should get a warm reply back. Then try:

- "Check my email"
- "What's on my calendar this week?"
- "Any updates from daycare?"
- "Call [provider name] at [number] to schedule a checkup for Graham"

---

## Adding providers to context.json

Edit `context.json` to add your doctors, dentists, etc.:

```json
"providers": {
  "contacts": [
    { "name": "Dr. Smith", "type": "pediatrician", "phone": "+12145551234" },
    { "name": "Downtown Dental", "type": "dentist", "phone": "+12145555678" }
  ]
}
```

Redeploy after editing, or use Railway's file editor.

---

## Adding VIP email senders

Edit `context.json` → `vip_senders.list`:

```json
"vip_senders": {
  "list": [
    "brighthorizons.com",
    "spouse@gmail.com",
    "boss@company.com"
  ]
}
```

---

## Estimated monthly cost

| Service | Cost |
|---|---|
| Twilio phone number | ~$1.00/mo |
| Twilio SMS | ~$0.0079/message |
| Bland.ai (free tier) | $0.14/connected minute for calls |
| Claude API | ~$5–20/mo |
| Railway | Free tier (500 hrs/mo), or $5/mo for always-on |
| Gmail + Calendar API | Free |
| **Total** | **~$10–25/mo** |
