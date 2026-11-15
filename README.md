# Africa policy monitor

A working monitor over the institutional sources that matter to youth-centred
digital health policy in Africa: the African Union, Africa CDC, ECOWAS and WAHO,
and the WHO processes that intersect with them.

It runs on a daily schedule, compares each source against what it saw last
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
.github/workflows/           daily cron; commits each note back to the repo
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


## Delivery tracker and dashboard

The repository now includes a companion discovery scanner and delivery tracker:

- `docs/index.html`: self-contained dashboard; download and open locally. GitHub file view shows source, and GitHub Pages has not been enabled.
- `data/actions.csv`: verified opportunities, recommendations and next actions.
- `data/deliverables.csv`: role commitments, proposed habits, status and evidence links.
- `scripts/monitor.py`: a standard-library index scanner, separate from the original root `monitor.py`; tracks new/retitled matching links and reports source failures.
- `data/source_health.json`: source coverage and access failures.
- `briefs/latest.md`: latest companion scan summary; the original monitor continues to write `signal-notes/`.
- `templates/`: concise policy brief and engagement evidence templates.
- `docs/operating-plan.md`: inception priorities and a suggested allocation within two working days per month.
- `.github/ISSUE_TEMPLATE/policy-opportunity.md`: turn a verified signal into a tracked action.

The workflow runs daily at **06:37 UTC / 07:37 WAT**, with manual runs available in Actions. Both monitors run within the same serialized job; the companion dashboard and source-health diagnostics are uploaded as a run artifact. Scheduled Actions can be delayed.

A separate ChatGPT research automation is configured for approximately **08:00 WAT**. It interprets and verifies policy developments. This repository's scripts use title/index matching; they do not establish policy adoption, open consultation status, publication dates or deadlines. A matching link is a candidate for verification. ChatGPT and the scripts do not yet share automatic writeback; verified recommendations can be copied into Issues or the action register.

To edit the tracker, update the CSV files then run the workflow, or run `python scripts/monitor.py --render-only` locally. Run `python -m unittest discover -s tests -v` for the companion's behavior checks. Its baseline fetched 12 of 13 configured pages on 15 November 2026; COMESA showed a possible access challenge. CEN-SAD has no verified automatic source configured; cross-host redirects are blocked by the companion scanner.

The ToR's required commitments are distinguished from proposed reporting habits. No appointment, completed deliverable or institutional access is assumed. The repository contains monitoring tools only; application documents are excluded.
