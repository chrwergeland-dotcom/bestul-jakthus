"""Henter Lailas Google-kalender (iCal) og skriver opptatt.json for nettsiden.
Bare datoene lagres – aldri navn, titler eller beskrivelser."""
import json, os, re, urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Lim inn kalenderens offentlige iCal-adresse her (slutter på basic.ics):
ICS_URL = os.environ.get("KALENDER_ICS") or ""

OSLO = ZoneInfo("Europe/Oslo")

def unfold(txt):
    return re.sub(r"\r?\n[ \t]", "", txt).splitlines()

def parse_dt(line):
    key, _, val = line.partition(":")
    val = val.strip()
    if "VALUE=DATE" in key or re.fullmatch(r"\d{8}", val):
        return datetime.strptime(val[:8], "%Y%m%d").date(), False
    if val.endswith("Z"):
        dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    else:
        m = re.search(r"TZID=([^;:]+)", key)
        tz = ZoneInfo(m.group(1)) if m else OSLO
        dt = datetime.strptime(val[:15], "%Y%m%dT%H%M%S").replace(tzinfo=tz)
    return dt.astimezone(OSLO), True

def main():
    ut = {"aktiv": False, "oppdatert": datetime.now(timezone.utc).isoformat(timespec="minutes"), "opptatt": []}
    if not ICS_URL:
        print("Ingen ICS_URL satt – kalenderen vises ikke på nettsiden.")
    else:
        req = urllib.request.Request(ICS_URL, headers={"User-Agent": "bestuljakthus-kalender"})
        txt = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        idag = date.today()
        fra, til = idag - timedelta(days=31), idag + timedelta(days=560)
        dager = set()
        ev = None
        for line in unfold(txt):
            if line == "BEGIN:VEVENT": ev = {}
            elif line == "END:VEVENT":
                if ev and "s" in ev and ev.get("status") != "CANCELLED" and ev.get("transp") != "TRANSPARENT":
                    (s, st), (e, et) = ev["s"], ev.get("e", ev["s"])
                    if st:  # klokkeslett: merk netter, ikke utsjekkingsdagen før kl. 12
                        sd, ed = s.date(), e.date()
                        if ed > sd and (e.hour, e.minute) <= (12, 0): ed -= timedelta(days=1)
                    else:   # heldag: sluttdato er eksklusiv i iCal
                        sd, ed = s, max(s, e - timedelta(days=1))
                    d = sd
                    while d <= ed:
                        if fra <= d <= til: dager.add(d.isoformat())
                        d += timedelta(days=1)
                ev = None
            elif ev is not None:
                if line.startswith("DTSTART"): ev["s"] = parse_dt(line)
                elif line.startswith("DTEND"): ev["e"] = parse_dt(line)
                elif line.startswith("STATUS:"): ev["status"] = line[7:].strip()
                elif line.startswith("TRANSP:"): ev["transp"] = line[7:].strip()
        ut.update(aktiv=True, opptatt=sorted(dager))
        print(f"{len(dager)} opptatte datoer")
    gammel = None
    try: gammel = json.load(open("opptatt.json", encoding="utf-8"))
    except Exception: pass
    if gammel and gammel.get("opptatt") == ut["opptatt"] and gammel.get("aktiv") == ut["aktiv"]:
        print("Ingen endring."); return
    json.dump(ut, open("opptatt.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

if __name__ == "__main__":
    main()
