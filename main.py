from playwright.sync_api import sync_playwright
import re
import os
import hashlib
from datetime import datetime, timedelta

URLS = [
    "https://www.instagram.com/fg_genderstudies/",
    "https://www.instagram.com/fem._kollektiv_winterthur/",
    "https://www.instagram.com/kollektiv.dulifera/",
    "https://www.instagram.com/baselticktbunt/"
]

events = []
seen = set()

# =========================
# Events extrahieren (ROBUST)
# =========================
def extract_events(text):
    results = []

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

        # Titel extrahieren
        start_idx = match.end()
        next_match = re.search(r"\d{1,2}\.\d{1,2}\.", text[start_idx:])

        if next_match:
            title = text[start_idx:start_idx + next_match.start()]
        else:
            title = text[start_idx:]

        # Säubern
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

        # scroll (wichtig für Inhalte)
        for _ in range(3):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(2000)

        html = page.content()

        alts = re.findall(r'alt="([^"]+)"', html)

        print("Gefundene ALT Texte:", len(alts))

        # DEBUG
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

    now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

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