"""Docket shape: how big are NTSB dockets, and how much readable text do they hold?

Question: is a docket small enough that "fetch every readable document, one model call"
is a sufficient design, or large enough that choosing what to read is a real decision
for an agent? The spike's A6 (agency 38%) shows that fetching changes the answer; it
does not show that choosing what to fetch does. This measures the precondition.

Sample: development split only (event year 2015-2019; the held-out years are not
touched), stratified by the class letters in the NTSB number and fatality — CA, LA
non-fatal, LA fatal, FA — 40 dockets each. Overall figures are weighted back to the
dev-split population of each stratum (all dev years).

Stage `listings`: one request per docket page. Document count, pages, photo pages, file
type, and a coarse title category (a judgement, not an NTSB taxonomy).
Stage `text`: for 8 dockets per stratum, download every PDF that is not a pure photo
set and extract all pages with pypdf. Readable characters, scanned pages.
Stage `report`: prints every number quoted in the session log; no network.

Tokens are ESTIMATED as characters / 4. No model is called. Downloads are not kept:
only per-document statistics are cached, in data/raw/docket_probe/ (git-ignored).

Usage:
    .venv/bin/python scripts/docket_shape_probe.py listings
    .venv/bin/python scripts/docket_shape_probe.py text
    .venv/bin/python scripts/docket_shape_probe.py report
"""

from __future__ import annotations

import html
import io
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "processed" / "filtered.parquet"
OUT = ROOT / "data" / "raw" / "docket_probe"
BASE = "https://data.ntsb.gov"
UA = {"User-Agent": "ntsb-spike research probe (docket shape measurement)"}
SEED = 20260913
PER_STRATUM_LISTINGS = 40
PER_STRATUM_TEXT = 8
MAX_DOCS_PER_CASE = 80
SLEEP = 0.6

# Input-token budget implied by the £0.05/case line, if the whole line went on input:
# Sonnet 5 input $2/MTok (the corrected price), 0.74 GBP per USD (the rate in cost.py/A7).
# An upper bound: the one-shot run's cost was dominated by thinking tokens (A7).
CAP_GBP = 0.05
INPUT_GBP_PER_MTOK = 2.0 * 0.74
CAP_INPUT_TOKENS = int(CAP_GBP / INPUT_GBP_PER_MTOK * 1_000_000)

ROW_RE = re.compile(
    r"<tr>\s*<td><b>(?P<idx>\d+)</b></td>\s*<td>(?P<title>.*?)</td>\s*"
    r"<td><b>(?P<pages>\d+)</b></td>\s*<td>(?P<photos>\d+)</td>\s*<td>(?P<dtype>.*?)</td>\s*"
    r"<td>\s*(?:<a target=\"_blank\" href=\"(?P<href>/Docket/Document/docBLOB[^\"]*)\">)?",
    re.S,
)
ITEMS_RE = re.compile(r"Docket Items:\s*(\d+)")

# Title categories, first match wins. Order matters: "Weather Study Report" is weather,
# "MAINTENANCE RECORDS -- ENGINE" is maintenance, "Medical Factual Report" is medical.
CATEGORIES = [
    ("pilot_form_6120", r"6120|pilot/operator|pilot operator|pilot.s aircraft accident|operator.s aircraft accident"),
    ("photos", r"photo|image|picture|video still"),
    ("weather", r"weather|metar|meteorolog|forecast|sigmet|airmet|carburetor icing"),
    ("maintenance_records", r"maintenance|logbook|log book|loogbook|engine log|aircraft log|airframe log|work order|invoice|annual inspection"),
    ("medical_tox", r"autopsy|toxicolog|medical|pathology|coroner|medical examiner"),
    ("specialist_factual", r"factual report|specialist|group chair|laboratory|metallurg|performance|study|recorded flight data|engine data monitor"),
    ("exam_site", r"exam|wreckage|teardown|site|inspection|memorandum for record"),
    ("conversation_statement", r"record of conversation|conversation|roc|interview|statement|witness|correspondence|email"),
    ("atc_radar_data", r"atc|air traffic|radar|ads-b|track|audio|transcript|video|tower|gps|recorder|csv|data"),
    ("manuals_reference", r"manual|poh|handbook|excerpt|specification|airport information|chart|map|advisory"),
]


def categorize(title: str) -> str:
    t = title.lower()
    for name, pattern in CATEGORIES:
        if re.search(pattern, t):
            return name
    return "other"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def sample_cases() -> pd.DataFrame:
    df = pd.read_parquet(PARQUET)
    df["yr"] = pd.to_datetime(df.eventDate).dt.year
    dev = df[df.yr <= 2019].copy()
    dev["cls"] = dev.ntsbNumber.str.extract(r"^[A-Z]{3}\d{2}([A-Z]{2})\d+")[0]
    fatal = dev.highestInjuryLevel.eq("Fatal")
    dev["stratum"] = None
    dev.loc[dev.cls.eq("CA"), "stratum"] = "CA"
    dev.loc[dev.cls.eq("LA") & ~fatal, "stratum"] = "LA_nonfatal"
    dev.loc[dev.cls.eq("LA") & fatal, "stratum"] = "LA_fatal"
    dev.loc[dev.cls.eq("FA"), "stratum"] = "FA"
    weights = dev.stratum.value_counts()
    pool = dev[dev.stratum.notna() & dev.yr.between(2015, 2019)]
    sample = pd.concat(
        [pool[pool.stratum == s].sample(PER_STRATUM_LISTINGS, random_state=SEED) for s in sorted(pool.stratum.unique())]
    ).reset_index(drop=True)
    sample["pop_weight"] = sample.stratum.map(weights)
    return sample[["ntsbNumber", "mKey", "stratum", "yr", "highestInjuryLevel", "pop_weight"]]


def parse_listing(page: str) -> tuple[int | None, list[dict]]:
    m = ITEMS_RE.search(page)
    declared = int(m.group(1)) if m else None
    rows = []
    for r in ROW_RE.finditer(page):
        title = html.unescape(re.sub(r"<[^>]+>", "", r.group("title"))).strip()
        href = html.unescape(r.group("href") or "")
        ext = ""
        if href:
            ext = href.split("FileExtension=")[-1].split("&")[0].strip(".").lower()
            if not ext:
                ext = href.rsplit(".", 1)[-1].lower()
        rows.append({
            "title": title, "pages": int(r.group("pages")), "photos": int(r.group("photos")),
            "dtype": r.group("dtype").strip(), "ext": ext, "href": href,
        })
    return declared, rows


def is_photo_only(row: dict) -> bool:
    return row["photos"] > 0 and row["photos"] >= row["pages"]


def stage_listings() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sample = sample_cases()
    sample.to_csv(OUT / "sample.csv", index=False)
    path = OUT / "listings.json"
    listings = json.loads(path.read_text()) if path.exists() else {}
    for _, c in sample.iterrows():
        if c.ntsbNumber in listings:
            continue
        try:
            page = fetch(f"{BASE}/Docket?ProjectID={int(c.mKey)}").decode("utf-8", "replace")
            declared, rows = parse_listing(page)
            listings[c.ntsbNumber] = {"mKey": int(c.mKey), "stratum": c.stratum, "declared": declared, "rows": rows}
        except Exception as e:  # noqa: BLE001 - record and continue
            listings[c.ntsbNumber] = {"mKey": int(c.mKey), "stratum": c.stratum, "error": str(e)}
        path.write_text(json.dumps(listings, indent=1))
        print(c.ntsbNumber, c.stratum, len(listings[c.ntsbNumber].get("rows", [])), flush=True)
        time.sleep(SLEEP)


def classify_pdf(data: bytes) -> dict:
    """chars/page > 300 born-digital, < 50 scan, else partial (thresholds from A9)."""
    reader = PdfReader(io.BytesIO(data))
    chars_by_page = []
    for p in reader.pages:
        try:
            chars_by_page.append(len((p.extract_text() or "").strip()))
        except Exception:  # noqa: BLE001 - a broken page counts as unreadable
            chars_by_page.append(0)
    n = len(chars_by_page)
    total = sum(chars_by_page)
    cpp = total / (n or 1)
    label = "born-digital" if cpp > 300 else ("scan" if cpp < 50 else "partial")
    return {"pdf_pages": n, "chars": total, "scan_pages": sum(1 for c in chars_by_page if c < 50),
            "chars_per_page": round(cpp), "label": label}


def text_subsample(listings: dict) -> list[str]:
    by_stratum: dict[str, list[str]] = {}
    for k, v in sorted(listings.items()):
        if "rows" in v:
            by_stratum.setdefault(v["stratum"], []).append(k)
    rng = random.Random(SEED)
    return [k for s in sorted(by_stratum) for k in rng.sample(by_stratum[s], PER_STRATUM_TEXT)]


def stage_text() -> None:
    listings = json.loads((OUT / "listings.json").read_text())
    path = OUT / "text.json"
    text = json.loads(path.read_text()) if path.exists() else {}
    for key in text_subsample(listings):
        if key in text:
            continue
        docs = []
        for r in listings[key]["rows"][:MAX_DOCS_PER_CASE]:
            d = {k: r[k] for k in ("title", "pages", "photos", "ext")}
            if is_photo_only(r):
                d["skipped"] = "photo-only"
            elif not r["href"] or r["ext"] != "pdf":
                d["skipped"] = f"non-pdf ({r['ext'] or 'no link'})"
            else:
                try:
                    data = fetch(BASE + r["href"])
                    d["bytes"] = len(data)
                    d.update(classify_pdf(data))
                except Exception as e:  # noqa: BLE001 - record and continue
                    d["error"] = str(e)[:200]
                time.sleep(SLEEP)
            docs.append(d)
        text[key] = {"stratum": listings[key]["stratum"], "n_rows": len(listings[key]["rows"]), "docs": docs}
        path.write_text(json.dumps(text, indent=1))
        print(key, listings[key]["stratum"], len(docs), flush=True)


def stats(g: pd.core.groupby.SeriesGroupBy) -> pd.DataFrame:
    return pd.DataFrame({"n": g.size(), "median": g.median(), "p75": g.quantile(0.75),
                         "p90": g.quantile(0.9), "max": g.max()})


def stage_report() -> None:
    sample = pd.read_csv(OUT / "sample.csv")
    weights = sample.groupby("stratum").pop_weight.first()
    listings = json.loads((OUT / "listings.json").read_text())
    errors = [k for k, v in listings.items() if "error" in v]
    mismatch = [k for k, v in listings.items()
                if "rows" in v and v["declared"] is not None and v["declared"] != len(v["rows"])]
    print(f"LISTINGS: {len(listings)} dockets, {len(errors)} fetch errors, "
          f"{len(mismatch)} where parsed rows != 'Docket Items' count")

    rows, docs_all = [], []
    for k, v in listings.items():
        if "rows" not in v:
            continue
        docs = v["rows"]
        for d in docs:
            d["category"] = categorize(d["title"])
            docs_all.append({"case": k, "stratum": v["stratum"], **d})
        non_photo = [d for d in docs if not is_photo_only(d)]
        rows.append({
            "case": k, "stratum": v["stratum"], "docs": len(docs), "non_photo_docs": len(non_photo),
            "pages": sum(d["pages"] for d in docs), "non_photo_pages": sum(d["pages"] for d in non_photo),
            "has_6120": any(d["category"] == "pilot_form_6120" for d in docs),
            "has_non_pdf": any(d["ext"] and d["ext"] != "pdf" for d in docs),
            "has_party_submission": any("party" in d["title"].lower() for d in docs),
            "empty": not docs,
        })
    t = pd.DataFrame(rows)
    c = pd.DataFrame(docs_all)

    print("\nSTAGE 1 — docket size per case, by stratum")
    for col in ("docs", "non_photo_docs", "non_photo_pages"):
        print(f"\n  {col}\n" + stats(t.groupby("stratum")[col]).to_string())
    print("\n  share of dockets: empty / containing a pilot Form 6120 / a party submission / any non-PDF file")
    print(t.groupby("stratum")[["empty", "has_6120", "has_party_submission", "has_non_pdf"]].mean().round(2).to_string())

    t["w"] = t.stratum.map(weights) / t.stratum.map(t.stratum.value_counts())

    def weighted_quantile(col: str, q: float) -> float:
        s = t.sort_values(col)
        return s.loc[(s.w.cumsum() / s.w.sum()) >= q, col].iloc[0]

    print("\n  weighted to dev-split population (" + ", ".join(f"{s}={int(n)}" for s, n in weights.items()) + ")")
    for col in ("docs", "non_photo_pages"):
        print(f"    {col}: median {weighted_quantile(col, .5)}, p75 {weighted_quantile(col, .75)}, "
              f"p90 {weighted_quantile(col, .9)}")

    print("\n  file types (documents) by stratum")
    print(pd.crosstab(c.stratum, c.ext.replace("", "(no link)")).to_string())
    print("\n  title categories: documents (share) and pages, by stratum")
    agg = c.groupby(["stratum", "category"]).agg(docs=("pages", "size"), pages=("pages", "sum")).reset_index()
    agg["doc_share"] = (agg.docs / agg.groupby("stratum").docs.transform("sum")).round(2)
    for s, g in agg.groupby("stratum"):
        print(f"\n  [{s}]\n" + g.drop(columns="stratum").sort_values("docs", ascending=False).to_string(index=False))
    final_like = c[c.title.str.contains(r"final report|aviation.*factual|analysis|probable cause", case=False, regex=True)
                   & ~c.category.isin(["medical_tox", "specialist_factual"])]
    print(f"\n  titles suggesting a case-level final/factual report or analysis: {len(final_like)}")
    if len(final_like):
        print(final_like[["case", "title"]].to_string(index=False))

    tpath = OUT / "text.json"
    if not tpath.exists():
        return
    text = json.loads(tpath.read_text())
    trows, per_doc = [], []
    for k, v in text.items():
        read = [d for d in v["docs"] if "label" in d]
        readable = [d for d in read if d["label"] in ("born-digital", "partial")]
        trows.append({
            "case": k, "stratum": v["stratum"], "docs": len(v["docs"]), "pdfs_read": len(read),
            "errors": sum(1 for d in v["docs"] if "error" in d),
            "skipped_non_pdf": sum(1 for d in v["docs"] if d.get("skipped", "").startswith("non-pdf")),
            "readable_docs": len(readable),
            "readable_tok_est": sum(d["chars"] for d in readable) // 4,
            "largest_doc_tok_est": max([d["chars"] for d in readable] or [0]) // 4,
            "scan_pages": sum(d["scan_pages"] for d in read),
            "scan_only": bool(read) and not readable,
        })
        for d in read:
            per_doc.append({"case": k, "stratum": v["stratum"], "title": d["title"][:60],
                            "category": categorize(d["title"]), "label": d["label"],
                            "pages": d["pdf_pages"], "scan_pages": d["scan_pages"], "tok_est": d["chars"] // 4})
    tt = pd.DataFrame(trows)
    print(f"\nSTAGE 2 — text volume, {len(tt)} dockets (tokens ESTIMATED as chars/4)")
    print(tt.sort_values(["stratum", "readable_tok_est"]).to_string(index=False))
    g = tt.groupby("stratum")
    print("\n  by stratum")
    print(pd.DataFrame({
        "n": g.size(), "readable_docs_median": g.readable_docs.median(),
        "tok_median": g.readable_tok_est.median(), "tok_max": g.readable_tok_est.max(),
        "largest_doc_tok_median": g.largest_doc_tok_est.median(),
        "scan_pages_median": g.scan_pages.median(), "scan_only_share": g.scan_only.mean().round(2),
    }).to_string())
    print(f"\n  input-token budget if the whole £{CAP_GBP} line went on input: {CAP_INPUT_TOKENS:,} (upper bound)")
    for thr in (5_000, 10_000, 20_000, CAP_INPUT_TOKENS, 100_000, 200_000):
        share = g.readable_tok_est.apply(lambda x, thr=thr: (x <= thr).mean())
        weighted = sum(share[s] * weights[s] for s in share.index) / sum(weights[s] for s in share.index)
        print(f"  share of dockets with readable text <= {thr:>7,} est. tokens: "
              + ", ".join(f"{s}={v:.2f}" for s, v in share.items()) + f"; dev-weighted={weighted:.2f}")
    d = pd.DataFrame(per_doc)
    print("\n  downloaded PDFs: extraction label by title category")
    print(pd.crosstab(d.category, d.label, margins=True).to_string())
    print("\n  estimated readable tokens by title category (born-digital + partial), by stratum")
    rd = d[d.label != "scan"]
    print(rd.pivot_table(index="category", columns="stratum", values="tok_est", aggfunc="sum", fill_value=0).to_string())
    cols = ["case", "title", "category", "label", "pages", "scan_pages", "tok_est"]
    print("\n  12 largest documents by estimated readable tokens")
    print(rd.nlargest(12, "tok_est")[cols].to_string(index=False))
    print("\n  8 largest documents by scanned pages")
    print(d.nlargest(8, "scan_pages")[cols].to_string(index=False))


if __name__ == "__main__":
    {"listings": stage_listings, "text": stage_text, "report": stage_report}[sys.argv[1]]()
