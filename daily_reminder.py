#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "reminder_config.json")

MEMPOOL_API = "https://mempool.757btc.org/api"
POSTER_DATA_URL = "https://raw.githubusercontent.com/757btc/757btc.github.io/main/assets/data/poster-data.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def fetch_bitcoin_data():
    """Fetch block height, price, and fees from mempool API."""
    data = {}

    try:
        with urllib.request.urlopen(f"{MEMPOOL_API}/blocks/tip/height") as resp:
            data["block_height"] = resp.read().decode().strip()
    except Exception:
        data["block_height"] = "N/A"

    try:
        with urllib.request.urlopen(f"{MEMPOOL_API}/v1/prices") as resp:
            prices = json.loads(resp.read().decode())
            data["price_usd"] = prices.get("USD", "N/A")
    except Exception:
        data["price_usd"] = "N/A"

    try:
        with urllib.request.urlopen(f"{MEMPOOL_API}/v1/fees/recommended") as resp:
            fees = json.loads(resp.read().decode())
            data["fees"] = fees
    except Exception:
        data["fees"] = None

    return data

def fetch_meetup_data():
    """Fetch meetup and link data from poster-data.json."""
    try:
        with urllib.request.urlopen(POSTER_DATA_URL) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Failed to fetch poster data: {e}")
        return None

def format_meetup_message(poster_data):
    """Format meetup data into message text."""
    lines = []

    meetups = poster_data.get("meetups", {})
    if meetups.get("list"):
        title = meetups.get("title", "Meetups")
        lines.append(title)
        for m in meetups["list"]:
            parts = []
            if m.get("frequency"):
                parts.append(m["frequency"])
            if m.get("schedule"):
                parts.append(m["schedule"])
            if m.get("location"):
                parts.append(f"at {m['location']}")
            if m.get("time"):
                parts.append(m["time"])
            lines.append(f"- {' '.join(parts)}")

    links = poster_data.get("links", [])
    if links:
        lines.append("")
        for link in links:
            text = link.get("text", link.get("label", ""))
            url = link.get("url", "")
            if text and url:
                lines.append(f"{text} {url}")
            elif url:
                lines.append(url)

    return "\n".join(lines)

def format_bitcoin_header():
    """Format Bitcoin data as message header."""
    data = fetch_bitcoin_data()

    lines = []
    lines.append(f"Block: {data['block_height']:,}" if isinstance(data['block_height'], int) else f"Block: {data['block_height']}")

    if isinstance(data['price_usd'], int):
        lines.append(f"Price: ${data['price_usd']:,}")
    else:
        lines.append(f"Price: ${data['price_usd']}")

    if data['fees']:
        f = data['fees']
        lines.append(f"Fees: {f.get('fastestFee', '?')}/{f.get('halfHourFee', '?')}/{f.get('hourFee', '?')} sat/vB")

    return "\n".join(lines)

def send_message():
    config = load_config()
    recipient = config.get("recipient", {"type": "self"})
    recipient_type = recipient.get("type", "self")
    recipient_value = recipient.get("value")

    # Build message with Bitcoin data header
    message_header = "<><><>- DailyDrop757 -<><><>"
    bitcoin_header = format_bitcoin_header()

    # Fetch meetup data dynamically, fall back to static config message
    poster_data = fetch_meetup_data()
    if poster_data:
        meetup_message = format_meetup_message(poster_data)
    else:
        meetup_message = config.get('message', '')

    full_message = f"{message_header}\n\n{bitcoin_header}\n\n{meetup_message}"

    url = f"{config['signal_service']}/v2/send"

    if recipient_type == "self":
        payload = {
            "message": full_message,
            "number": config["phone_number"],
            "recipients": [config["phone_number"]]
        }
    elif recipient_type == "contact":
        payload = {
            "message": full_message,
            "number": config["phone_number"],
            "recipients": [recipient_value]
        }
    elif recipient_type == "group":
        payload = {
            "message": full_message,
            "number": config["phone_number"],
            "recipients": [recipient_value]
        }
    else:
        print(f"Unknown recipient type: {recipient_type}")
        return

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            print("Message sent successfully")
    except urllib.error.HTTPError as e:
        print(f"Failed to send: {e.read().decode()}")

def list_groups():
    config = load_config()
    url = f"{config['signal_service']}/v1/groups/{config['phone_number']}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            groups = json.loads(response.read().decode())
            print("Available groups:")
            for g in groups:
                print(f"  Name: {g.get('name', 'Unknown')}")
                print(f"  ID: {g.get('id')}")
                print()
    except urllib.error.HTTPError as e:
        print(f"Failed to get groups: {e.read().decode()}")

def install_cron():
    config = load_config()
    hour = config["schedule"]["hour"]
    minute = config["schedule"]["minute"]
    script_path = os.path.abspath(__file__)
    python_path = sys.executable

    cron_line = f"{minute} {hour} * * * {python_path} {script_path} send"

    # Get existing crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    # Remove old entries for this script
    lines = [l for l in existing.strip().split('\n') if l and script_path not in l]
    lines.append(cron_line)

    # Install new crontab
    new_crontab = '\n'.join(lines) + '\n'
    process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    process.communicate(new_crontab)

    print(f"Cron job installed: daily at {hour:02d}:{minute:02d}")
    print(f"Cron entry: {cron_line}")

def show_config():
    config = load_config()
    recipient = config.get("recipient", {"type": "self"})
    print(f"Config file: {CONFIG_FILE}")
    print(f"Signal service: {config['signal_service']}")
    print(f"Phone number: {config['phone_number']}")
    print(f"Schedule: {config['schedule']['hour']:02d}:{config['schedule']['minute']:02d}")
    print(f"Recipient type: {recipient.get('type', 'self')}")
    if recipient.get('value'):
        print(f"Recipient value: {recipient['value']}")
    print(f"Message:\n{config['message']}")

def print_usage():
    print("Usage: daily_reminder.py <command>")
    print("Commands:")
    print("  send     - Send the reminder message now")
    print("  install  - Install/update the cron job based on config")
    print("  config   - Show current configuration")
    print("  groups   - List available groups and their IDs")
    print(f"\nEdit {CONFIG_FILE} to change settings")
    print("\nRecipient types in config:")
    print('  "type": "self"              - Send to Note to Self')
    print('  "type": "contact", "value": "+1234567890"  - Send to contact')
    print('  "type": "group", "value": "group_id_here" - Send to group')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "send":
        send_message()
    elif cmd == "install":
        install_cron()
    elif cmd == "config":
        show_config()
    elif cmd == "groups":
        list_groups()
    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)
