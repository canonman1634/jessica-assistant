# Jessica Setup Guide

Follow these steps in order to get Jessica running. Jessica is used through
Claude Code sessions in this repo — there's no standalone server or phone
number to connect.

---

## Step 1 — Install Python dependencies

```bash
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
playwright install --with-deps chromium
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
| `BLAND_API_KEY` | https://app.bland.ai → Settings → API Keys |

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

## Step 5 — Run memory consolidation

`dreamer.py` deduplicates semantic memory and distills the day's staged
activity into episodic memory — previously run nightly by a background
scheduler, now run on demand:

```bash
python dreamer.py
```

Set up a Claude Code Routine if you want this on a recurring cadence instead
of running it manually.

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
| Bland.ai (free tier) | $0.14/connected minute for calls |
| Claude API | ~$5–20/mo |
| Gmail + Calendar API | Free |
| **Total** | **~$5–20/mo** |
