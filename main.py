from playwright.sync_api import sync_playwright
import re
import os
import hashlib
from datetime import datetime, timedelta
from datetime import datetime, UTC

URLS = [
    "https://www.instagram.com/fg_genderstudies/",
    "https://www.instagram.com/bildungbrenntbasel/"
]

events = []
seen = set()

# =========================
# Events extrahieren (ROBUST)
# =========================
def extract_events(text):
    results = []

    month_map = {
        "januar": 1, "februar": 2, "märz": 3, "maerz": 3,
        "april": 4, "mai": 5, "juni": 6, "juli": 7,
        "august": 8, "september": 9, "oktober": 10,
        "november": 11, "dezember": 12
    }

    # =========================
    # 1. Standard-Pattern (dd.mm.)
    # =========================
    pattern = re.finditer(
        r"(\d{1,2})\.(\d{1,2})\.\s*(?:um|ab)?\s*(\d{1,2})[:：](\d{2})",
        text
    )

    for match in pattern:
        day = int(match.group(1))
        month = int(match.group(2))
        hour = int(match.group(3))
        minute = int(match.group(4))

        if hour > 23:
            continue

        try:
            start = datetime(2026, month, day, hour, minute)
        except:
            continue

        end = start + timedelta(hours=2)

        start_idx = match.end()
        title = text[start_idx:]

        title = title.strip()
        title = re.split(r"(ERREICHE|UNTER|@)", title)[0]
        title = re.sub(r"^Uhr\s+", " ", title)
        title = title[:80]

        if len(title) < 5:
            title = "FG Gender Studies Event"

        results.append({
            "title": title,
            "start": start,
            "end": end,
            "description": title
        })

    # =========================
    # 2. Pattern für "12. Mai 18:00"
    # =========================
    pattern_text = re.finditer(
        r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s*(\d{1,2})[:：](\d{2})",
        text.lower()
    )

    for match in pattern_text:
        day = int(match.group(1))
        month_str = match.group(2).lower()
        hour = int(match.group(3))
        minute = int(match.group(4))

        if hour > 23 or month_str not in month_map:
            continue

        month = month_map[month_str]

        try:
            start = datetime(2026, month, day, hour, minute)
        except:
            continue

        end = start + timedelta(hours=2)

        # 🔥 WICHTIG: Titel VOR dem Datum
        start_idx = match.start()
        title = text[:start_idx]

        # Müll entfernen
        title = re.split(r"(Photo by .*?\.|May be an image of.*?says)", title)[-1]
        title = re.split(r"(ERREICHE|UNTER|@)", title)[0]

        title = title.strip()

        # relevante letzten Wörter
        words = title.split()
        title = " ".join(words[-12:])

        if len(title) < 5:
            title = "Event"

        results.append({
            "title": title,
            "start": start,
            "end": end,
            "description": title
        })

    return results

# =========================
# ICS Escape (WICHTIG)
# =========================
def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

# =========================
# Browser
# =========================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        storage_state="state.json",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        viewport={"width": 1280, "height": 800}
    )

    page = context.new_page()

    for URL in URLS:
        print(f"\n🔎 Lade: {URL}")

        page.goto(URL, timeout=60000)

        page.wait_for_selector("img", timeout=15000)
        
        print("✅ Seite geladen")

        for _ in range(3):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)

        html = page.content()

        alts = re.findall(r'alt="([^"]+)"', html)

        print("Gefundene ALT Texte:", len(alts))

        for alt in alts[:3]:
            print("ALT SAMPLE:", alt[:120])
            
        for alt in alts:
            if "Photo by" not in alt:
                continue

            extracted = extract_events(alt)

            for e in extracted:
                key = (e["start"].date(), e["start"].hour, e["start"].minute)

                if key in seen:
                    continue

                seen.add(key)

                print("Event:", e["title"], "|", e["start"])

                events.append(e)

# =========================
# ICS erstellen (FIXED TIMEZONE)
# =========================
def create_uid(event):
    base = f"{event['title']}-{event['start']}"
    return hashlib.md5(base.encode()).hexdigest() + "@fg-genderstudies"

def create_ics(events):
    content = """BEGIN:VCALENDAR
VERSION:2.0
CALSCALE:GREGORIAN
PRODID:-//FG Gender Studies//Instagram Calendar//EN
BEGIN:VTIMEZONE
TZID:Europe/Zurich
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
"""
    
    now = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')

    for e in events:
        uid = create_uid(e)

        content += f"""BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
SUMMARY:{escape_ics(e['title'])}
DTSTART;TZID=Europe/Zurich:{e['start'].strftime('%Y%m%dT%H%M%S')}
DTEND;TZID=Europe/Zurich:{e['end'].strftime('%Y%m%dT%H%M%S')}
DESCRIPTION:{escape_ics(e['description'])}
END:VEVENT
"""

    content += "END:VCALENDAR"

    with open("events.ics", "w") as f:
        f.write(content)

# =========================
# Run
# =========================
create_ics(events)

os.system("git add events.ics")
os.system("git commit -m 'update events' || true")
os.system("git push")

print("\nICS erstellt")