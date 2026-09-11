# Session 0 checklist — things to find out from the docs, not guess

The scripts are deliberately empty of API specifics. Fill these in from the
NTSB's own documentation, then copy the answers into `config.yaml`.

Start at: https://data.ntsb.gov/avdata (bulk data page) and the CAROL query tool.
Look for the API documentation the NTSB references alongside the 2027 migration notice.

Answered 2026-09-11 (Session 0). Where "from response" is noted, the source is a
real saved response, not documentation — see docs/session-log.md.

- [x] Exact base URL and path for `GetCasesByDateRangeV2` — `GET https://api.ntsb.gov/public/api/Common/v2/GetCasesByDateRange/` (OpenAPI spec `public.yaml` from the developer portal; verified with real responses). Legacy no-auth alternative still live: `POST data.ntsb.gov/carol-main-public/api/Query/Main` + `Query/FileExport`
- [x] Authentication: **subscription key** (`Ocp-Apim-Subscription-Key` header or `subscription-key` query param) from a developer.ntsb.gov account. Key never stored in the repo — `NTSB_API_KEY` env var, sourced from Andy's password store. CAROL legacy endpoints need none
- [x] Request/response format — GET with query params; JSON response `{startDate, endDate, pageSize, hasMore, nextMarker, data:[...]}`; fully nested case records. Raw saved verbatim in `data/raw/fetched=2026-09-11/`
- [x] Pagination: marker-based — pass back `nextMarker` until `hasMore` is false; up to 1000 records/page (spec text). One month of aviation = 132 records = 1 page
- [x] Rate limit: none stated, none observed (4 requests, ~1.3 s each; Cloudflare-fronted, no challenge). Self-imposed 30/min in config
- [x] Date parameters: `startDate`/`endDate` (YYYY-MM-DD), event date; `GetCasesByModifiedDateRange` exists separately for revision dates. Caution: V2 `eventDate` looks UTC-derived — WPR22LA118 is 2022-03-08 in V2 (eventTimeUtc 02:30) but 2022-03-07T19:30Z in CAROL
- [x] Closed vs open: `completionStatus` "Completed" + bool `caseClosed`. GA: `aircrafts[].ownerOperators[].regulationFlightConductedUnder == "091"`. Prelim vs final: `reportType`/`publishProfile`; `narratives[].prelimNarrative` field exists
- [x] Narratives: **all present in the V2 record** — `narratives[]` per aircraft: `probableCause`, `analysisNarrative`, `concatenatedFactualNarrative` (null on "Basic (no factual)" flavor cases), `prelimNarrative`. Separate fields → good sign for A3
- [x] Codes: structured lists — `aircrafts[].findings[]` (findingCode, 4-tier names, modifier, inProbableCause) and `aircrafts[].events[]` (eventCode, tier names, cicttPhaseSOEGroup, isDefiningEvent). `occurrences[]` empty on post-2008 cases seen so far
- [x] Docket: `https://data.ntsb.gov/Docket?ProjectID={Mkey}` — server-rendered HTML table (parseable, no JS needed); direct PDFs via `Docket/Document/docBLOB?ID=..&FileExtension=pdf&FileName=..` (verified download)
- [x] Migration: **April 5, 2027** — downloadable avdata datasets retire, replaced by "Enterprise API platform"; `GetCasesByDateRangeV2` is the named successor (i.e. the post-migration API). Notice quoted in session log
- [x] Licence/terms: nothing found beyond generic footer links — no statement located on avdata or CAROL pages
- [x] `avall.zip`: `https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip`, 96,148,686 bytes, contains avall.mdb (558 MB). Narratives → `narratives`; events → `events` (31,124 rows); findings → `Findings`; aircraft → `aircraft`; plus Flight_Crew, flight_time, Occurrences, Events_Sequence, injury, engines, …
