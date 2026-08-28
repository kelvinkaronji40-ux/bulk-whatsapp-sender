# Bulk WhatsApp Sender

Separate tool for bulk WhatsApp messaging: contacts, CSV import, campaigns, queue, and send status.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\pip install -e .
copy .env.example .env
# edit .env with your WhatsApp Cloud API credentials
bulk-whatsapp run
```

Then open:
- http://localhost:8001/ — Dashboard
- http://localhost:8001/static/index.html — Contacts
- http://localhost:8001/static/campaigns.html — Campaigns
- http://localhost:8001/docs — API

## Setup

Requires a WhatsApp Business Phone Number ID and Access Token from Meta.

## Notes

- Set `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN` in `.env`
- Database stored at `~/.bulk_whatsapp/bulk.db`
- CLI: `bulk-whatsapp run` and `bulk-whatsapp init`
