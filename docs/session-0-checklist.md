# Session 0 checklist — things to find out from the docs, not guess

The scripts are deliberately empty of API specifics. Fill these in from the
NTSB's own documentation, then copy the answers into `config.yaml`.

Start at: https://data.ntsb.gov/avdata (bulk data page) and the CAROL query tool.
Look for the API documentation the NTSB references alongside the 2027 migration notice.

- [ ] Exact base URL and path for `GetCasesByDateRangeV2`
- [ ] Authentication: none / key / login? If key, where to get one, any terms
- [ ] Request/response format (JSON? XML?) — save one raw response verbatim
- [ ] Pagination: page size, how to request the next page, max range per call
- [ ] Rate limit stated or observed
- [ ] Date parameters: event date or modification date? Timezone?
- [ ] Which fields distinguish: closed vs open; GA vs other; preliminary vs final
- [ ] Where narratives live: separate fields for factual / analysis / probable cause?
- [ ] Where codes live: occurrence, phase of flight, findings — separate fields? lists?
- [ ] Docket: is there an endpoint that lists a case's documents? Direct PDF URLs?
- [ ] Migration: date, what is retired, what replaces it, is V2 the post-migration API
- [ ] Licence/terms: any statement beyond "US government work"
- [ ] `avall.zip`: URL, size, table names for narratives / events / findings / aircraft
