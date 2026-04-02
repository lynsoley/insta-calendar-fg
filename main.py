from playwright.sync_api import sync_playwright
import re
import os
from datetime import datetime, timedelta

URL = "https://www.instagram.com/fg_genderstudies/"

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

        # Sicherheit
        if hour > 23:
            continue

        try:
            start = datetime(2026, month, day, hour, minute)
        except:
            continue

        end = start + timedelta(hours=2)

        # =========================
        # Titel = Text NACH Match
        # =========================
        start_idx = match.end()
        next_match = re.search(r"\d{1,2}\.\d{1,2}\.", text[start_idx:])

        if next_match:
            title = text[start_idx:start_idx + next_match.start()]
        else:
            title = text[start_idx:]

        # säubern
        title = title.strip()
        title = re.split(r"(ERREICHE|UNTER|@)", title)[0]
        title = re.sub(r"\s+", " ", title)
        title = title[:80]

        if len(title) < 5:
            title = "FG Gender Studies Event"

        results.append({
            "title": title,
            "start": start,
            "end": end,
            "description": text.strip()
        })

    return results

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
# ICS
# =========================
def create_ics(events):
    content = "BEGIN:VCALENDAR\nVERSION:2.0\n"

    for e in events:
        content += f"""BEGIN:VEVENT
SUMMARY:{e['title']}
DTSTART:{e['start'].strftime('%Y%m%dT%H%M%S')}
DTEND:{e['end'].strftime('%Y%m%dT%H%M%S')}
DESCRIPTION:{e['description']}
END:VEVENT
"""

    content += "END:VCALENDAR"

    with open("events.ics", "w") as f:
        f.write(content)

create_ics(events)

os.system("git add events.ics")
os.system("git commit -m 'update events' || true")
os.system("git push")

print("\nICS erstellt")