import json
import os
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
url = f"https://api.telegram.org/bot{token}/getUpdates"

with urllib.request.urlopen(url, timeout=15) as resp:
    data = json.load(resp)

results = data.get("result", [])
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
