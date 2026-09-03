import json
import os
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]

def call(method):
    url = f"https://api.telegram.org/bot{token}/{method}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)

me = call("getMe")
print(f"::notice title=Bot Info::{me}")

wh = call("getWebhookInfo")
print(f"::notice title=Webhook Info::{wh}")

data = call("getUpdates")
results = data.get("result", [])
print(f"::notice title=Update Count::{len(results)} update(s) found")

if not results:
    print("::warning::Belum ada pesan masuk ke bot. Kirim pesan ke bot dulu di Telegram, lalu jalankan ulang workflow ini.")
else:
    seen = set()
    for u in results:
        chat = u.get("message", {}).get("chat", {})
        cid = chat.get("id")
        if cid and cid not in seen:
            seen.add(cid)
            label = chat.get("first_name") or chat.get("title") or ""
            print(f"::notice title=Telegram Chat ID::{cid} (type: {chat.get('type')}, name: {label})")
