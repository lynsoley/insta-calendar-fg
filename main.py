from playwright.sync_api import sync_playwright
import re
import os
import hashlib
from datetime import datetime, timedelta

URL = "https://www.instagram.com/fg_genderstudies/"

events = []
seen = set()

# =========================
# Events extrahieren
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
        title = re.sub(r"\s+", " ", title)

        # 🔥 FIX: "Uhr " entfernen
        title = re.sub(r"^Uhr\s*", "", title)

        title = title[:80]

        if len(title) < 5:
            title = "FG Gender Studies Event"

        results.append({
            "title": title,
            "start": start,
            "end": end,
            # 🔥 FIX: saubere Beschreibung (kein Instagram Müll)
            "description": title
        })

    return results

# =========================
# ICS Escape
# =========================
def escape_ics(text):
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

# =========================
# UID erstellen (gegen Duplikate)
# =========================
def create_uid(event):
    base = f"{event['title']}-{event['start']}"
    return hashlib.md5(base.encode()).hexdigest() + "@fg-genderstudies"

# =========================
# Browser
# =========================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(URL)
    page.wait_for_timeout(5000)

    html = page.content()

    alts = re.findall(r'alt="([^"]+)"', html)

    print("Gefundene ALT Texte:", len(alts))

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

    browser.close()

print("\nGefundene Events:", len(events))

# =========================
# ICS erstellen
# =========================
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