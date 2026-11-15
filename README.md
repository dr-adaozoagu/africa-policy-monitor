# Africa policy monitor

A working monitor over the institutional sources that matter to youth-centred
digital health policy in Africa: the African Union, Africa CDC, ECOWAS and WAHO,
and the WHO processes that intersect with them.

It runs on a weekday schedule, compares each source against what it saw last
time, classifies anything new against four workstreams — digitally enabled
health systems; digital, data and AI governance; digital determinants of health;
digital citizenship for health — and writes a ranked signal note.

Built by **Dr Adaeze Sandra Ozoagu** (Abuja) ahead of an application to the
DTH-Lab Youth Policy Liaison Officer programme, Africa cluster.

## What it is for

Two days a month cannot cover 55 Member States and four regional bodies by
reading websites. The scarce resource is attention, so the job of this tool is
triage: surface the handful of items where a response could still change
something, and leave the rest in the log.

## What it does not do

It catches what these institutions **publish**. It does not catch what they do
not publish.

AU Specialised Technical Committees and the Permanent Representatives' Committee
do not issue open calls for written input. The Continental Health Data
Governance Framework was drafted well before any public trace of it existed.
A monitor shortens the distance between publication and response; it cannot
reach upstream of publication. That part is relationship work, and the two are
meant to run together rather than one standing in for the other.

Said plainly: this tool makes a two-day month defensible. It does not make
monitoring complete, and no honest tool would claim to.

## Layout

```
sources.yml                  source register, tiered by closeness to a decision
taxonomy.yml                 workstream keywords and opportunity signals
monitor.py                   fetch, diff, classify, rank, write
.github/workflows/           weekday cron; commits each note back to the repo
signal-notes/                dated output, one note per run
docs/2027-decision-calendar.md    where a text can still change, and by when
docs/youth-channel-audit.md       where youth input is provided for, and where it is not
tests/fixtures/              saved HTML, so the pipeline can be tested offline
```

## Running it

```bash
pip install -r requirements.txt
python monitor.py                          # live
python monitor.py --dry-run                # fetch and classify, write nothing
python monitor.py --offline tests/fixtures # no network; runs against saved HTML
```

## Design notes

- **Conditional GET.** ETag and Last-Modified are cached, so unchanged pages
  cost one 304 rather than a download.
- **Polite by default.** Identifying user-agent, two seconds between requests,
  exponential backoff on failure.
- **Generic extraction.** These sites change templates without notice. Brittle
  CSS selectors fail silently, which is worse than failing loudly, so extraction
  is deliberately plain.
- **Transparent classification.** Keyword matching, not a model. A liaison
  officer has to be able to explain why something was flagged.
- **State in the repo.** No database. The commit history is the audit trail.

## Honest limits

- Index pages behind heavy JavaScript return little to a plain fetch; those
  sources need either an RSS feed or a headless browser.
- Keyword classification produces false positives. Ranking is designed so that
  they land in LOW rather than disappear.
- Several items in the calendar are inferred from annual patterns and are
  labelled as such. They are not announcements.
