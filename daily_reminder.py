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

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
DEFAULT_HEADER = "<><><>- DailyDrop757 -<><><>"

# Used only if poster-data.json can't be fetched or has no bitcoinStats.apiUrls
DEFAULT_API_URLS = {
    "blockHeight": f"{MEMPOOL_API}/blocks/tip/height",
    "price": f"{MEMPOOL_API}/v1/prices",
    "fees": f"{MEMPOOL_API}/v1/fees/recommended",
}

def get_bitcoin_settings(poster_data):
    """Return (enabled, api_urls) from poster-data.json's bitcoinStats section."""
    stats = (poster_data or {}).get("bitcoinStats", {})
    enabled = stats.get("enabled", True)
    api_urls = {**DEFAULT_API_URLS, **stats.get("apiUrls", {})}
    return enabled, api_urls

def http_get(url):
    """GET a URL and return the response text, or None on failure.
    Errors are printed so they show up in the terminal / cron log."""
    try:
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        print(f"[bitcoin] {url} -> HTTP {e.code}: {body}")
    except Exception as e:
        print(f"[bitcoin] {url} -> {type(e).__name__}: {e}")
    return None

def test_api_urls(api_urls):
    """Hit each Bitcoin API URL and report status, timing, raw response, and
    whether the response has the shape the message formatter expects."""
    import time

    def check_height(text):
        return int(text.strip()) > 0

    def check_price(text):
        return isinstance(json.loads(text).get("USD"), (int, float))

    def check_fees(text):
        f = json.loads(text)
        return all(isinstance(f.get(k), (int, float)) for k in ("fastestFee", "halfHourFee", "hourFee"))

    checks = {"blockHeight": check_height, "price": check_price, "fees": check_fees}
    results = {}

    for key, url in api_urls.items():
        print(f"\n[{key}] {url}")
        start = time.time()
        try:
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                text = resp.read().decode()
            elapsed = (time.time() - start) * 1000
            print(f"  HTTP {status} in {elapsed:.0f} ms")
            print(f"  Response: {text.strip()[:200]}")
            try:
                ok = checks[key](text) if key in checks else True
            except Exception as e:
                ok = False
                print(f"  Could not parse response: {type(e).__name__}: {e}")
            if not ok:
                print("  Response format is not what the script expects")
        except urllib.error.HTTPError as e:
            ok = False
            print(f"  HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
        except Exception as e:
            ok = False
            print(f"  {type(e).__name__}: {e}")
        print(f"  Result: {'PASS' if ok else 'FAIL'}")
        results[key] = ok

    passed = sum(results.values())
    print(f"\nURL tests: {passed}/{len(results)} passed")
    return results

def fetch_bitcoin_data(api_urls):
    """Fetch block height, price, and fees from the configured API URLs."""
    data = {"block_height": "N/A", "price_usd": "N/A", "fees": None}

    text = http_get(api_urls["blockHeight"])
    if text is not None:
        try:
            data["block_height"] = int(text.strip())
        except ValueError:
            print(f"[bitcoin] unexpected block height response: {text[:200]!r}")

    text = http_get(api_urls["price"])
    if text is not None:
        try:
            data["price_usd"] = json.loads(text).get("USD", "N/A")
        except ValueError:
            print(f"[bitcoin] unexpected price response: {text[:200]!r}")

    text = http_get(api_urls["fees"])
    if text is not None:
        try:
            data["fees"] = json.loads(text)
        except ValueError:
            print(f"[bitcoin] unexpected fees response: {text[:200]!r}")

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

def format_bitcoin_header(api_urls):
    """Format Bitcoin data as message header."""
    data = fetch_bitcoin_data(api_urls)

    lines = []
    lines.append(f"Block: {data['block_height']:,}" if isinstance(data['block_height'], int) else f"Block: {data['block_height']}")

    if isinstance(data['price_usd'], int):
        lines.append(f"Price: ${data['price_usd']:,}")
    else:
        lines.append(f"Price: ${data['price_usd']}")

    if data['fees']:
        f = data['fees']
        lines.append(f"Fees: {f.get('fastestFee', '?')}/{f.get('halfHourFee', '?')}/{f.get('hourFee', '?')} sat/vB")
    else:
        lines.append("Fees: N/A")

    return "\n".join(lines)

def trust_identity(config, number):
    import re
    url = f"{config['signal_service']}/v1/identities/{config['phone_number']}/trust/{number}"
    data = json.dumps({"trust_all_known_keys": True}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='PUT', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Trusted new identity for {number}")
            return True
    except urllib.error.HTTPError as e:
        print(f"Failed to trust identity for {number}: {e.read().decode()}")
        return False

def send_message():
    config = load_config()
    recipient = config.get("recipient", {"type": "self"})
    recipient_type = recipient.get("type", "self")
    recipient_value = recipient.get("value")

    # Fetch poster data first: it drives the header, Bitcoin API URLs, and meetups
    poster_data = fetch_meetup_data()
    message_header = (poster_data or {}).get("header", DEFAULT_HEADER)

    btc_enabled, api_urls = get_bitcoin_settings(poster_data)
    bitcoin_header = format_bitcoin_header(api_urls) if btc_enabled else ""

    # Use meetup data from GitHub, fall back to static config message
    if poster_data:
        meetup_message = format_meetup_message(poster_data)
    else:
        meetup_message = config.get('message', '')

    sections = [message_header, bitcoin_header, meetup_message]
    full_message = "\n\n".join(s for s in sections if s)

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
        error_body = e.read().decode()
        if "Untrusted Identity" in error_body:
            import re
            numbers = re.findall(r'(\+\d+): Untrusted Identity', error_body)
            if numbers:
                print(f"Untrusted identities detected: {numbers}")
                for number in numbers:
                    trust_identity(config, number)
                # Retry send
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req) as response:
                        print("Message sent successfully after trusting new identities")
                except urllib.error.HTTPError as e2:
                    print(f"Failed to send after trusting identities: {e2.read().decode()}")
        else:
            print(f"Failed to send: {error_body}")

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

    # Pull and process the GitHub poster data (nothing is sent)
    print("\n" + "=" * 50)
    print(f"Fetching poster data from:\n  {POSTER_DATA_URL}")
    print("=" * 50)

    poster_data = fetch_meetup_data()

    # Bitcoin stats, using the API URLs from poster-data.json
    btc_enabled, api_urls = get_bitcoin_settings(poster_data)
    print(f"\nHeader: {(poster_data or {}).get('header', DEFAULT_HEADER)}")
    print(f"\n--- Bitcoin API URL tests (enabled: {btc_enabled}) ---")
    test_api_urls(api_urls)
    if btc_enabled:
        print("\n--- Bitcoin stats (as they will appear in Signal) ---")
        print(format_bitcoin_header(api_urls))
    else:
        print("\n(Bitcoin stats are disabled in poster-data.json and will not be sent)")

    if poster_data:
        print("\n--- Raw poster data ---")
        print(json.dumps(poster_data, indent=2))

        meetups = poster_data.get("meetups", {}).get("list", [])
        links = poster_data.get("links", [])
        print(f"\nFound {len(meetups)} meetup(s) and {len(links)} link(s)")

        print("\n--- Formatted meetup message (as it will appear in Signal) ---")
        formatted = format_meetup_message(poster_data)
        print(formatted if formatted else "(formatter produced no output - check the JSON keys)")
    else:
        print("\nGitHub fetch failed. The static fallback message from config would be used:")
        print(config.get('message', '(no fallback message set in config)'))

def print_usage():
    print("Usage: daily_reminder.py <command>")
    print("Commands:")
    print("  send     - Send the reminder message now")
    print("  install  - Install/update the cron job based on config")
    print("  config   - Show current configuration and preview GitHub poster data")
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
