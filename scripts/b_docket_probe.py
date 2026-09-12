"""Probe NTSB dockets for the 14 category-B cases: are their documents born-digital?

For each case, fetch the docket page (https://data.ntsb.gov/Docket?ProjectID={mKey}),
parse the document table, download up to 4 substantive-looking PDFs via the docBLOB
hrefs found in the page, extract text with pypdf, and classify each PDF:
  chars/page > 300 -> born-digital; < 50 -> scan; else partial.

Verdicts per case:
  RICH      >=1 substantive born-digital doc
  SCAN_ONLY docs exist but none extract as born-digital
  EMPTY     no (or nearly no) documents in the docket

Downloads go to the session scratchpad, never the repo.
"""

import html
import io
import re
import statistics
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader

SCRATCH = Path(
    "/private/tmp/claude-501/-Users-floyda-Workspace-ntsb-spike/"
    "fd970ff8-524c-451f-86f4-27a2ebab5e10/scratchpad/b_dockets"
)
BASE = "https://data.ntsb.gov"
UA = {"User-Agent": "ntsb-spike research probe (contact: andyfloyd86@gmail.com)"}

# case_id -> mKey, taken from data/processed/filtered.parquet (see repo history)
CASES = {
    "WPR20CA166": 101384,
    "CEN20CA240": 101469,
    "WPR20CA299": 101932,
    "CEN20CA405": 102006,
    "WPR21LA308": 103661,
    "WPR21LA342": 103850,
    "WPR22LA364": 106045,
    "ERA23LA014": 106098,
    "CEN23LA052": 106371,
    "DCA23LA192": 106806,
    "ERA23LA289": 192536,
    "CEN23LA301": 192618,
    "ANC23LA073": 193051,
    "DCA24FA017": 193297,
}

GOOD_KEYWORDS = [
    "factual",
    "exam",
    "report",
    "transcription",
    "transcript",
    "memo",
    "summary",
    "statement",
]
BAD_KEYWORDS = ["photo", "video", "6120", "image", "figure", "diagram", "picture"]

MAX_PDFS_PER_CASE = 4
MAX_TOTAL_REQUESTS = 80

ROW_RE = re.compile(
    r"<tr>\s*"
    r"<td><b>(?P<idx>\d+)</b></td>\s*"
    r"<td>(?P<title>.*?)</td>\s*"
    r"<td><b>(?P<pages>\d+)</b></td>\s*"
    r"<td>(?P<photos>\d+)</td>\s*"
    r"<td>(?P<dtype>.*?)</td>\s*"
    r"<td>\s*<a target=\"_blank\" href=\"(?P<href>/Docket/Document/docBLOB[^\"]*)\">",
    re.S,
)

request_count = 0


def fetch(url: str) -> bytes:
    global request_count
    if request_count >= MAX_TOTAL_REQUESTS:
        raise RuntimeError("HTTP request budget exceeded")
    request_count += 1
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def score_title(title: str) -> int:
    """Higher = more likely substantive and born-digital."""
    t = title.lower()
    score = 0
    for kw in GOOD_KEYWORDS:
        if kw in t:
            score += 2
    for kw in BAD_KEYWORDS:
        if kw in t:
            score -= 5
    return score


def classify_pdf(data: bytes) -> tuple[str, int, float, str]:
    """Return (label, n_pages, chars_per_page, sample_text)."""
    reader = PdfReader(io.BytesIO(data))
    n_pages = len(reader.pages)
    text = ""
    for page in reader.pages[:10]:  # first 10 pages are enough to classify
        text += page.extract_text() or ""
    pages_read = min(n_pages, 10) or 1
    cpp = len(text.strip()) / pages_read
    if cpp > 300:
        label = "born-digital"
    elif cpp < 50:
        label = "scan"
    else:
        label = "partial"
    sample = re.sub(r"\s+", " ", text.strip())[:250]
    return label, n_pages, cpp, sample


def main() -> None:
    import sys

    cases = CASES
    if len(sys.argv) > 1:  # optional: probe only the named case_ids
        cases = {k: v for k, v in CASES.items() if k in sys.argv[1:]}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = []
    samples = {}  # verdict -> (case_id, title, sample text)

    for case_id, mkey in cases.items():
        page = fetch(f"{BASE}/Docket?ProjectID={mkey}").decode("utf-8", "replace")
        time.sleep(1)
        rows = []
        for m in ROW_RE.finditer(page):
            title = html.unescape(re.sub(r"<[^>]+>", "", m.group("title"))).strip()
            href = html.unescape(m.group("href"))
            ext = href.split("FileExtension=")[-1].split("&")[0].strip(".").lower()
            if not ext:  # some rows leave FileExtension blank; fall back to FileName
                ext = href.rsplit(".", 1)[-1].lower()
            rows.append({"title": title, "href": href, "ext": ext.lower(),
                         "pages": int(m.group("pages")), "dtype": m.group("dtype").strip()})

        total_docs = len(rows)
        pdf_rows = [r for r in rows if r["ext"] == "pdf"]
        pdf_rows.sort(key=lambda r: score_title(r["title"]), reverse=True)

        tested = 0
        born_digital = 0
        substantive_bd = 0
        first_bd_sample = None
        scan_sample = None
        for r in pdf_rows[:MAX_PDFS_PER_CASE]:
            try:
                data = fetch(BASE + r["href"])
            except Exception as e:  # noqa: BLE001 - record and continue
                print(f"  [{case_id}] download failed for {r['title']!r}: {e}")
                continue
            time.sleep(1)
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", r["title"])[:60]
            (SCRATCH / f"{case_id}__{safe}.pdf").write_bytes(data)
            tested += 1
            try:
                label, n_pages, cpp, sample = classify_pdf(data)
            except Exception as e:  # noqa: BLE001
                print(f"  [{case_id}] pypdf failed for {r['title']!r}: {e}")
                label, cpp, sample = "unreadable", 0.0, ""
            print(f"  [{case_id}] {r['title'][:55]!r:57} {label:12} {cpp:7.0f} chars/page")
            if label == "born-digital":
                born_digital += 1
                if score_title(r["title"]) > 0:
                    substantive_bd += 1
                if first_bd_sample is None:
                    first_bd_sample = (r["title"], sample)
            elif label == "scan" and scan_sample is None:
                scan_sample = (r["title"], sample)

        if total_docs == 0:
            verdict = "EMPTY"
        elif substantive_bd >= 1 or (born_digital >= 1 and tested > 0):
            # substantive born-digital doc found (fall back to any born-digital)
            verdict = "RICH" if substantive_bd >= 1 else ("RICH" if born_digital else "SCAN_ONLY")
        else:
            verdict = "SCAN_ONLY"

        if verdict == "RICH" and "RICH" not in samples and first_bd_sample:
            samples["RICH"] = (case_id, *first_bd_sample)
        if verdict == "SCAN_ONLY" and "SCAN_ONLY" not in samples and scan_sample:
            samples["SCAN_ONLY"] = (case_id, *scan_sample)

        results.append((case_id, total_docs, tested, born_digital, verdict))

    print()
    print(f"{'case_id':12} {'docs':>5} {'tested':>7} {'born_dig':>9}  verdict")
    for case_id, total, tested, bd, verdict in results:
        print(f"{case_id:12} {total:>5} {tested:>7} {bd:>9}  {verdict}")

    n = len(results)
    rich = sum(1 for r in results if r[4] == "RICH")
    scan = sum(1 for r in results if r[4] == "SCAN_ONLY")
    empty = sum(1 for r in results if r[4] == "EMPTY")
    med = statistics.median(r[1] for r in results)
    print()
    print(f"SUMMARY: {rich}/{n} RICH, {scan} SCAN_ONLY, {empty} EMPTY; "
          f"median docket size = {med} docs; HTTP requests used = {request_count}")

    for verdict in ("RICH", "SCAN_ONLY"):
        if verdict in samples:
            case_id, title, sample = samples[verdict]
            print(f"\n{verdict} sample ({case_id}, {title!r}):\n  {sample[:250]}")


if __name__ == "__main__":
    main()
