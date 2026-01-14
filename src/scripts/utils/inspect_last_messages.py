import json
import time

try:
    with open("state.json", "r") as f:
        data = json.load(f)
        msgs = data.get("messages", [])
        print(f"Total messages: {len(msgs)}")
        print("--- LAST 10 MESSAGES ---")
        for m in msgs[-10:]:
            ts = m.get('timestamp', 0)
            time_str = time.strftime('%H:%M:%S', time.localtime(ts))
            sender = m.get('from')
            target = m.get('target', 'all')
            content = m.get('content', '')
            print(f"[{time_str}] {sender} -> {target}: {content[:100].replace(chr(10), ' ')}...")
except Exception as e:
    print(e)
