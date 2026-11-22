# Exactly-Once Deploys Against an Unreliable API

Part 2 of a two-part technical screen. Both parts ask the same question: when is
a system entitled to say it succeeded?
[Part 1](https://github.com/ibuianov-dev/ai-agent-quality-verification) audits an AI
pipeline that reported a job complete when it wasn't.

Here the question is: **when is a system entitled to tell an operator a
deployment succeeded?** I answered it under a real two-hour clock, against a live
API that fails in more than one way, directing an AI coding agent (Claude Code)
through discovery and implementation. The full unedited session is in
[SESSION.md](SESSION.md).

## The problem

A marketer approved 300 assets (landing pages, emails, forms and CTAs) and asked
for them to be pushed into their account. The destination is a stand-in for
HubSpot, which will happily accept the same email twice and keep both.

- **The work has an order.** Some assets belong to others: a form belongs to a
  landing page, and a CTA belongs to an email. The destination rejects a child
  until its parent is really there. 22 of the 300 assets had a parent.
- **Each asset must land exactly once.** Not at least once. Scoring was +1 per
  asset (+2 for a dependent one), −1 for a miss and **−5 for every extra copy**.
  A duplicate is five times worse than a miss, because an operator told "not
  deployed" just deploys it again. An operator with two live landing pages
  splitting their traffic finds out from analytics a week later.
- **Nothing is documented.** How the API fails and what it offers to make retries
  safe had to be discovered from its responses. A write that doesn't answer
  hasn't necessarily failed.
- **The clock was real.** It started on the first authenticated request, and the
  run sealed at two hours.
- **The report is not evidence.** I got one shot at submitting the report, and
  the score came from what was actually in the destination. The two were allowed
  to disagree.

## What discovery turned up

| Finding | Why it mattered |
|---|---|
| Auth takes two steps. `POST /auth/start` returns a bearer token that expires after 5 minutes, plus the minutes left on the run. Every other request needs both the candidate key and the token. | The client has to refresh the token proactively, about 30 times over a run. |
| **There is no way to read deploy state.** Every read route I tried returned 404, and the asset catalog never changes. | Proof can only come from the write response itself. |
| A plain resend with no extra header returns `409 duplicate_write_refused`. | Unkeyed retries are safe, but only if the original response arrived. |
| The same `X-CQ-Idempotency-Key` sent again returns `200` with `replayed: true` and the original timestamp. | A stored key, reused exactly, makes a retry safe. I proved this on one asset before trusting it on the rest. |
| **A different key creates a brand-new write**, even for an asset that already exists. | One mistyped key creates a duplicate. This happened to me once during discovery (see below). |
| A key that already belongs to another asset replays *that* asset's data. The asset you asked for is never written. | A `2xx` status code is not proof. The response body has to name the same asset ID. |

## The answer: when is it entitled to say "deployed"?

**Only when a response proves it for that exact asset ID.** That means a fresh
`201`, a replayed `200`, or a `409`, and in every case the response body has to
echo back the same `asset_id`. A status code alone isn't enough.

A timeout, a dropped connection or an unexpected `5xx` proves nothing. The asset
is retried with the same stored key. If it's still unresolved at the hard stop,
it's reported **blocked**, even if it probably went through. "Probably" isn't
good enough when a duplicate costs five times more than a miss.

## How the code enforces it

| Module | Job |
|---|---|
| [src/client.py](src/client.py) | The only module that talks to the API. It handles auth refresh, backoff and the User-Agent, and sorts every response into one of six outcomes. It refuses to send any write without an idempotency key. |
| [src/journal.py](src/journal.py) | Stores each asset's state in SQLite. Each asset's idempotency key is stored before its first send and reused on every retry, never regenerated. Each asset is marked in-flight before the request goes out, so a crash leaves a record of what to resolve. |
| [src/reconcile.py](src/reconcile.py) | The single definition of proof. It turns each response into confirmed, refused or unresolved. |
| [src/deploy.py](src/deploy.py) | Runs the deploy in passes. Each pass tries every pending or unresolved asset whose parent is already confirmed, so dependency chains of any depth resolve without a separate sort step. It stops new writes at 15 minutes left and stops everything at 5. |
| [src/report.py](src/report.py) | Builds the report from the journal. Only confirmed assets become `deployed`, and everything else is `blocked` with a reason. Sending the report is a separate command that asks you to type `SUBMIT`. |

## Results

- **All 300 assets confirmed by proof**: 265 fresh `201`s and 35 replayed `200`s.
- **34 of those replays came from the automated loop.** In each case a write came
  back unclear, the loop resent it with the same stored key, and the server
  confirmed the original instead of creating a second copy.
- **The `409` fallback was never needed.** Every write after discovery used its
  stored key.
- **The report was built with 14 minutes left on the clock.**

## The mistake, and what it changed

During manual discovery I retried `as-0001` with a mistyped idempotency key. The
server accepted it as a new write, so `as-0001` probably exists twice. With no read
endpoint, I can't confirm the count either way.

I reported it as `deployed`, because it does exist. Reporting it `blocked` would
be false and would invite an operator to deploy a third copy. The report format
has no way to say "deployed, possibly twice", so I disclosed the uncertainty in
[NOTES.md](NOTES.md) instead of hiding it in the report.

That mistake is where the core rule came from: **each asset gets one fixed key,
stored before the first send and never typed by hand.** No duplicates came from
the automated run.

## How I worked with the agent

- I read the brief and wrote my own notes and architecture plan before starting
  the clock. Then I asked Claude Code to find gaps. Its best catch was that the
  brief hinted at a retry-safety mechanism I hadn't planned to look for.
- I did the API discovery by hand and corrected the agent when its assumptions
  were wrong, for example about where the run timer comes from and how auth
  works.
- I ran the idempotency experiments myself on single assets (`as-0002` and
  `as-0012`) before letting the loop write the other 297.
- I reviewed the generated code and fixed some type issues in `deploy.py`. I also
  found two gaps myself: token refresh skipped the retry logic, and my notes
  contradicted the code about how `as-0001` was reported.
- I ran the one-shot report submission myself, after reviewing `report.json`.

## Known limits

- **No mock server.** I planned one for rehearsal but didn't build it. The
  remaining discovery ran live, limited to small single-asset tests.
- **No unit tests** for the state machine in `reconcile.py`. Confidence comes from
  the controlled experiments matching the model, not from tests.
- **Hardcoded config.** Settings live in `CONSTANTS.py` instead of environment
  variables. That was fine for a two-hour screen but isn't production practice.
  After the screen, I moved the candidate key into an environment variable so
  it isn't committed.

## Files

| File | What it is |
|---|---|
| [ORIGINAL REQUIREMENTS.md](ORIGINAL%20REQUIREMENTS.md) | The brief as it was sent |
| [NOTES.md](NOTES.md) | My notes from before the clock, discovery findings, and the final answer with a self-critique |
| [SESSION.md](SESSION.md) | The raw Claude Code session transcript |
| [src/](src/) | The client, journal, reconcile, deploy and report modules |
| [report.json](report.json) | The report built from the journal |
| [journal.sqlite3](journal.sqlite3) | The journal from the real run: every asset, its key, outcome and attempts |
| [CONSTANTS.py](CONSTANTS.py) | Endpoints, header names, time limits and other settings |

## Running it

Python 3.14 with [uv](https://docs.astral.sh/uv/). The run needs a per-candidate
key for the screening server, read from the `CQ_CANDIDATE_KEY` environment
variable, so this repo is meant to be read rather than re-run.

```bash
uv run python src/deploy.py           # deploy everything, resumable from the journal
uv run python src/report.py           # build report.json locally (dry run)
uv run python src/report.py --submit  # one-shot submit; asks you to type SUBMIT
```
