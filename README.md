# Signal Daily Reminder

A script to send scheduled messages via Signal using signal-cli REST API.

## Prerequisites

- signal-cli REST API running (in json-rpc mode for bot operations)
 - https://github.com/bbernhard/signal-cli-rest-api
- A linked Signal account
- Python 3

## Files

- `daily_reminder.py` - Main script
- `reminder_config.json` - Configuration file

## Usage

```bash
# Show help
python daily_reminder.py

# Show current configuration
python daily_reminder.py config

# Send message now (for testing)
python daily_reminder.py send

# List available groups and their IDs
python daily_reminder.py groups

# Install/update cron job based on config schedule
python daily_reminder.py install
```

## Configuration

Edit `reminder_config.json` to customize the reminder:

```json
{
  "signal_service": "http://localhost:8080",
  "phone_number": "+1234567890",
  "schedule": {
    "hour": 17,
    "minute": 30
  },
  "recipient": {
    "type": "self",
    "value": null
  },
  "message": "Your message here"
}
```

### Fields

| Field | Description |
|-------|-------------|
| `signal_service` | URL of signal-cli REST API |
| `phone_number` | Your registered Signal phone number |
| `schedule.hour` | Hour to send (0-23, 24-hour format) |
| `schedule.minute` | Minute to send (0-59) |
| `recipient` | Where to send the message (see below) |
| `message` | Message text (use `\n` for newlines) |

### Recipient Types

**Note to Self:**
```json
"recipient": {
  "type": "self",
  "value": null
}
```

**Contact (by phone number):**
```json
"recipient": {
  "type": "contact",
  "value": "+1234567890"
}
```

**Group:**
```json
"recipient": {
  "type": "group",
  "value": "group.1235d2ZWN3B5cy9xWjh1Vkd0RTBaSTc3MTNHQThmQXlMbXRhUk1pbWIzUT0="
}
```

To find group IDs, run:
```bash
python daily_reminder.py groups
```

Use the **full** ID including the `group.` prefix.

## Examples

### Change time to 9:00 AM

Edit `reminder_config.json`:
```json
"schedule": {
  "hour": 9,
  "minute": 0
}
```

Then reinstall the cron job:
```bash
python daily_reminder.py install
```

### Change message

Edit `reminder_config.json`:
```json
"message": "Line one\nLine two\nLine three"
```

Test it:
```bash
python daily_reminder.py send
```

### Send to a group instead of Note to Self

1. Find the group ID:
   ```bash
   python daily_reminder.py groups
   ```

2. Edit `reminder_config.json`:
   ```json
   "recipient": {
     "type": "group",
     "value": "group.YOUR_GROUP_ID_HERE"
   }
   ```

3. Test it:
   ```bash
   python daily_reminder.py send
   ```

## Managing the Cron Job

View installed cron jobs:
```bash
crontab -l
```

Remove the cron job:
```bash
crontab -e
# Delete the line containing daily_reminder.py
```

## Troubleshooting

**"Failed to send" error:**
- Ensure signal-cli REST API is running: `curl http://localhost:8080/v1/about`
- Ensure it's in json-rpc mode (check the `mode` field in response)
- For groups, make sure you're using the full ID including `group.` prefix

**Message not sending at scheduled time:**
- Verify cron is running: `systemctl status cron`
- Check cron job is installed: `crontab -l`
- Ensure signal-cli REST API is running at the scheduled time
