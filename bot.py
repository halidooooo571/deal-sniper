import os, json, urllib.request, xml.etree.ElementTree as ET
 from bs4 import BeautifulSoup

TOKEN = os.environ["TG_TOKEN"]
 CHAT_ID = str(os.environ["TG_CHAT_ID"])
 STATE_FILE = "state.json"
 HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def tg_api(method, payload=None):
 url = f"https://telegram.org{TOKEN}/{method}"
 data = json.dumps(payload).encode() if payload else None
 req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
 with urllib.request.urlopen(req, timeout=15) as r:
 return json.loads(r.read().decode())

def send_msg(text):
 tg_api("sendMessage", {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})

def load_state():
 with open(STATE_FILE, "r", encoding="utf-8") as f:
 return json.load(f)

def save_state(state):
 with open(STATE_FILE, "w", encoding="utf-8") as f:
 json.dump(state, f, indent=2, ensure_ascii=False)

def handle_commands(state):
 updates = tg_api(f"getUpdates?offset={state['last_update_id'] + 1}")
 for u in updates.get("result", []):
 state["last_update_id"] = u["update_id"]
 msg = u.get("message", {})
 if str(msg.get("chat", {}).get("id")) != CHAT_ID:
 continue
 parts = msg.get("text", "").strip().split()
 if not parts:
 continue
 cmd = parts[0].lower()

 if cmd == "/add" and len(parts) >= 3:
 url, target = parts[1], float(parts[2].replace(",", "."))
 state["products"].append({"url": url, "target": target, "min_seen": None, "history": []})
 send_msg(f"✅ Produkt hinzugefügt (Ziel: *{target:.2f} €*)")
 elif cmd == "/rss" and len(parts) >= 2:
 kw = " ".join(parts[1:]).lower()
 if kw not in state["rss_keywords"]:
 state["rss_keywords"].append(kw)
 send_msg(f"🔍 RSS-Keyword aktiv: *{kw}*")
 elif cmd == "/list":
 p_list = "\n".join([f"{i}: {p['url'][:40]}... (Ziel: {p['target']}€, Min: {p['min_seen']})" for i, p in enumerate(state["products"])]) or "Keine"
 send_msg(f"📦 *Produkte:*\n{p_list}\n\n🏷️ *Keywords:* {', '.join(state['rss_keywords'])}")
 elif cmd == "/del" and len(parts) == 2 and parts[1].isdigit():
 idx = int(parts[1])
 if 0 <= idx < len(state["products"]):
 removed = state["products"].pop(idx)
 send_msg(f"🗑️ Gelöscht: {removed['url'][:40]}...")

def extract_price_jsonld(html):
 soup = BeautifulSoup(html, "html.parser")
 title = soup.title.string.strip()[:60] if soup.title else "Produkt"
 for script in soup.find_all("script", type="application/ld+json"):
 try:
 data = json.loads(script.string)
 items = data if isinstance(data, list) else [data]
 for item in items:
 if item.get("@type") == "Product" and "offers" in item:
 offers = item["offers"]
 offer = offers[0] if isinstance(offers, list) else offers
 price = float(str(offer.get("price", 0)).replace(",", "."))
 if price > 0:
 return item.get("name", title)[:60], price
 except Exception:
 continue
 return title, None

def check_products(state):
 for p in state["products"]:
 try:
 req = urllib.request.Request(p["url"], headers=HEADERS)
 html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
 name, price = extract_price_jsonld(html)
 if not price:
 continue
 hist = p["history"]
 avg = sum(hist) / len(hist) if hist else price
 is_new_low = p["min_seen"] is None or price < p["min_seen"]

 if price <= p["target"] or (is_new_low and len(hist) >= 3 and price < avg * 0.90):
 send_msg(f"🔥 *Preis-Alarm: {name}*\nAktuell: *{price:.2f} €* (Ziel: {p['target']:.2f} € | Ø: {avg:.2f} €)\n[Zum Angebot]({p['url']})")

 if is_new_low:
 p["min_seen"] = price
 hist.append(price)
 p["history"] = hist[-50:]
 except Exception as e:
 print(f"Fehler bei {p['url']}: {e}")

def check_rss(state):
 feed_url = "https://mydealz.de"
 try:
 req = urllib.request.Request(feed_url, headers=HEADERS)
 xml_data = urllib.request.urlopen(req, timeout=15).read()
 root = ET.fromstring(xml_data)
 for item in root.findall(".//item"):
 title = item.findtext("title", "")
 link = item.findtext("link", "")
 guid = item.findtext("guid", link)
 if guid in state["seen_deals"]:
 continue
 if any(kw in title.lower() for kw in state["rss_keywords"]):
 send_msg(f"⚡ *Hot Deal:* {title}\n[Deal öffnen]({link})")
 state["seen_deals"].append(guid)
 state["seen_deals"] = state["seen_deals"][-200:]
 except Exception as e:
 print(f"RSS Fehler: {e}")

if __name__ == "__main__":
 state = load_state()
 handle_commands(state)
 check_products(state)
 check_rss(state)
 save_state(state)
