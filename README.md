# Jessica — AI Personal Assistant

A personal executive assistant that lives in your WhatsApp. Text her like a real person and she handles your email, calendar, phone calls, and family logistics.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/canonman1634/jessica-assistant)

---

## What she can do

- **Email** — read, search, and send Gmail
- **Calendar** — check availability, create and update Google Calendar events
- **Phone calls** — make AI voice calls on your behalf via Bland.ai (schedules appointments, leaves voicemails, reports back with a summary)
- **Daycare updates** — monitors Bright Horizons / My Bright Day emails and flags anything urgent
- **Morning briefing** — proactive 7am summary of your day sent via WhatsApp
- **Urgent alerts** — background monitor fires a WhatsApp ping if a priority email lands

## How it works

Jessica runs as a Flask app on Railway. Twilio forwards your WhatsApp messages to it, Claude processes them and calls tools, and the reply comes back to your phone. Background jobs handle the morning briefing and urgent email monitoring.

## Accounts you'll need

| Service | Purpose | Link |
|---|---|---|
| Anthropic | AI brain | https://console.anthropic.com |
| Twilio | WhatsApp messaging | https://console.twilio.com |
| Bland.ai | AI voice calls | https://app.bland.ai |
| Google Cloud | Gmail + Calendar | https://console.cloud.google.com |
| Railway | Hosting | https://railway.app |

## Deploy

Click the button above or follow the full step-by-step guide in [SETUP.md](SETUP.md).

## Estimated cost

~$10–25/month depending on usage. See the cost breakdown at the bottom of [SETUP.md](SETUP.md).
