"""A10 probe: are historical METARs fetchable from the Iowa Mesonet ASOS archive?

Picks 3 NTSB GA cases (different years) that have a stored raw METAR and an
observation facility/time, fetches the archive METARs for a +/-2h window around
the observation time, and prints the closest-in-time archived METAR next to the
NTSB-stored one.

Endpoint params verified against the service's own help page
(https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?help, fetched 2026-09-11):
  station (array), data=metar, sts/ets (ISO, interpreted in tz), tz (IANA),
  format=onlycomma, report_type (1=HFMETAR, 3=Routine, 4=Specials).
Note: help says 1s per-IP throttle; we sleep between requests.
"""
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

PARQUET = "/Users/floyda/Workspace/ntsb-spike/data/processed/filtered.parquet"
ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
# Stored raw METAR strings only appear from ~2019 onward in this dataset
# (2015 has zero cases with a metar field), so the spread is 2019/2022/2024.
TARGET_YEARS = [2019, 2022, 2024]


def pick_cases(df: pd.DataFrame) -> list[dict]:
    picks = []
    for year in TARGET_YEARS:
        sub = df[df["eventDate"].str.startswith(str(year), na=False)]
        for _, row in sub.iterrows():
            wcs = row["weatherConditions"]
            if wcs is None or len(wcs) == 0:
                continue
            wc = wcs[0]
            if (
                wc.get("metar")
                and wc.get("observationFacilityId")
                and wc.get("observationDate")
                and wc.get("observationTimeUtc")
            ):
                picks.append(
                    {
                        "ntsbNumber": row["ntsbNumber"],
                        "eventDate": row["eventDate"],
                        "station": wc["observationFacilityId"].strip(),
                        "obsDate": wc["observationDate"],
                        "obsTimeUtc": wc["observationTimeUtc"],
                        "stored_metar": wc["metar"].strip(),
                    }
                )
                break
    return picks


def mesonet_station(ntsb_station: str, stored_metar: str) -> str:
    """Mesonet US ASOS ids are 3-char without the leading K (e.g. TRK for KTRK).
    NTSB observationFacilityId is usually already 3-char; strip a leading K only
    when it is a 4-char CONUS-style id (K###)."""
    s = ntsb_station.upper()
    if len(s) == 4 and s.startswith("K"):
        return s[1:]
    return s


def fetch_window(station: str, center: datetime) -> list[tuple[datetime, str]]:
    sts = (center - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:00Z")
    ets = (center + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:00Z")
    params = [
        ("station", station),
        ("data", "metar"),
        ("sts", sts),
        ("ets", ets),
        ("tz", "Etc/UTC"),
        ("format", "onlycomma"),
        ("report_type", "3"),
        ("report_type", "4"),
    ]
    r = requests.get(ASOS, params=params, timeout=60)
    r.raise_for_status()
    lines = r.text.strip().splitlines()
    out = []
    for line in lines[1:]:  # header: station,valid,metar
        parts = line.split(",", 2)
        if len(parts) < 3:
            continue
        valid = datetime.strptime(parts[1], "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
        out.append((valid, parts[2].strip().strip('"')))
    return out


def main() -> None:
    df = pd.read_parquet(PARQUET)
    cases = pick_cases(df)
    print(f"Selected {len(cases)} cases\n")
    for c in cases:
        ntsb_time = datetime.fromisoformat(
            f"{c['obsDate']}T{c['obsTimeUtc']}"
        ).replace(tzinfo=timezone.utc)
        # Prefer the METAR's own ddhhmmZ group: NTSB observationTimeUtc is
        # sometimes local time mislabeled as UTC (seen on ERA22LA099).
        m = re.search(r"\b(\d{2})(\d{2})(\d{2})Z\b", c["stored_metar"])
        if m:
            dd, hh, mm = map(int, m.groups())
            center = ntsb_time.replace(day=dd, hour=hh, minute=mm)
            if center != ntsb_time:
                print(f"[note] {c['ntsbNumber']}: METAR timestamp {dd:02d}{hh:02d}{mm:02d}Z"
                      f" != NTSB observationTimeUtc {ntsb_time.isoformat()}")
        else:
            center = ntsb_time
        station = mesonet_station(c["station"], c["stored_metar"])
        print("=" * 78)
        print(f"Case {c['ntsbNumber']}  event {c['eventDate']}")
        print(f"NTSB obs facility: {c['station']}  -> mesonet station: {station}")
        print(f"NTSB obs time (UTC): {center.isoformat()}")
        print(f"STORED : {c['stored_metar']}")
        try:
            obs = fetch_window(station, center)
        except requests.HTTPError as e:
            print(f"FETCH FAILED: {e}\n  body: {e.response.text[:300]}")
            time.sleep(2)
            continue
        if not obs:
            print("FETCHED: <no observations returned in +/-2h window>")
        else:
            best = min(obs, key=lambda t: abs((t[0] - center).total_seconds()))
            gap_min = (best[0] - center).total_seconds() / 60.0
            print(f"FETCHED: {best[1]}")
            print(f"  archive valid {best[0].isoformat()}  gap {gap_min:+.0f} min "
                  f"({len(obs)} obs in window)")
        time.sleep(2)  # respect 1s per-IP throttle
    print("=" * 78)


if __name__ == "__main__":
    main()
