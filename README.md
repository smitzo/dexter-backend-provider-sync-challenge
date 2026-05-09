# Backend Assignment: Provider Sync Reliability Challenge

## Context

At Dexter Health, our backend connects with third-party healthcare software
providers and synchronizes operational care data into our internal systems.

In this assignment, you will work with a small existing Python codebase that
simulates a resident data sync from a third-party provider into a Firestore-like
repository.

The current implementation is a thin happy-path skeleton. Your job is to make
it production-grade enough to be trusted with real care data.

## Setup

Python 3.11 or newer required. On macOS and many Linux distros the system
`python3` is older than 3.11 and the editable install will fail with a
confusing setuptools error — use `python3.11` explicitly to be safe.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

No cloud accounts, Docker, Postgres, Redis, or external services. Everything
runs locally and deterministically.

After setup, `pytest` should report **6 passed, 5 failed**. That is your
starting line — the failing public tests are part of the spec.

## Your Task

Make the running sync trustworthy. The failing public tests and
`docs/PROVIDER_API.md` together describe the gap between what the starter
does and what we need.

In broad strokes:

1. **Reliability** — pagination, retries, rate-limit handling, no infinite
   loops, no silent error swallowing.
2. **Data integrity** — idempotent re-runs, no duplicate residents, no stale
   data overwriting newer internal records, partial failures must not corrupt
   valid data.
3. **Validation & mapping** — read the provider docs carefully. Some fields
   are messier than the starter assumes. Surface validation errors with
   enough context to debug. Map provider `first_name` + `lastName` into the
   internal `full_name` field.
4. **Tests** — add at least 3 meaningful tests beyond the public suite.
   Cover edge cases that aren't already exercised.
5. **Notes & decision memo** — write up your approach, tradeoffs, and the
   design decisions you made when the docs were ambiguous (see
   "Decision memo" at the bottom of this file).

## Assumptions you can make

These corners are intentionally underspecified — exactly like real provider
integrations. Pick a defensible answer and document it. You will not be
punished for a reasonable choice.

- **Stale-write protection:** treating `existing.updated_at >= incoming.updated_at`
  as "skip" is acceptable. Strict `>` is also acceptable. Be consistent.
- **Counter semantics:** `created` for fresh inserts, `updated` for
  newer-overwrites, `skipped` for stale-protected, `failed` for malformed or
  validation errors. A stale-skip increments `skipped`, not `updated=0`.
- **Retry budget:** ≥ 3 attempts on transient / 429 errors is expected.
  Exponential backoff is a plus but not required.
- **Retry timing:** the test simulator uses `retry_after = 0` so retries do
  not wait. If your retry helper layers its own backoff on top, keep the
  per-attempt sleep small (≤ ~1s) — the test grader has a per-test timeout
  and a backoff that ignores `retry_after` may flake.
- **Permanent error mid-pagination:** record it in `result.errors` and stop
  the run cleanly. Do not retry. Do not silently continue.
- **Sync entrypoint signature:** keep
  `run_sync(provider, repository) -> SyncResult` so the grading harness can
  call your code unchanged.

## Timebox

Please block a focused **4-hour window** for the assignment. The timer starts
when you open the PandaDoc briefing we sent you.

It is fine — and expected — that you make tradeoffs to fit the timebox. If
setup issues or life interruptions materially affect your available time, just
note that in your submission. Tell us what you chose to prioritise and what
you would improve with more time.

## AI Tools

You are encouraged to use Claude Code, Codex, Cursor, Copilot, ChatGPT, or
similar tools. Use whatever you would use in a real job.

We evaluate the **final outcome**: reliability, data integrity, tests,
judgment, and your ability to explain the solution. We do not penalise AI
usage.

We will, however, ask you to walk through and defend your solution in the
next interview round, so make sure you understand what you submitted.

## What We Care About

- Correctness and end-to-end reliability
- Data integrity and idempotency
- Validation and graceful failure handling
- Meaningful tests, including for edge cases
- Simple, maintainable code
- Clear tradeoffs, documented decisions, and honest communication

## What We Don't Care About

- Avoiding AI tools
- Perfect architecture
- Unnecessary frameworks
- Real cloud deployment
- Building a full production system
- Adding unrelated features

## Codebase Tour

```
src/dexter_sync/
  models.py            # Pydantic models + provider->internal mapping
  exceptions.py        # Error hierarchy: provider, rate-limit, malformed-record
  provider_client.py   # Mock provider — reads JSON fixtures, simulates failures
  repository.py        # In-memory Firestore-like store + conditional write guard
  sync.py              # Orchestrator — your main focus
tests/
  conftest.py
  test_public_sync.py            # behavioural tests — several are red
  test_public_provider_client.py # simulator sanity checks (already green)
docs/
  PROVIDER_API.md      # synthetic provider docs — read this carefully
data/
  provider_page_*.json           # paginated provider fixtures
  provider_page_with_errors.json # malformed records
  provider_page_judgment.json    # ambiguity fixtures (see PROVIDER_API.md)
  existing_residents.json        # pre-seeded internal state for staleness test
logs/
  failed_sync.log                # example log shape — read for context
```

## Submission

Submit either:
1. A GitHub repository link (private or public, both fine), or
2. A zip file with your solution.

Please include in your README:
- What you changed and why
- Tradeoffs you made
- What you would improve with more time
- How you used AI tools (if applicable) and how you verified output
- How you ran and validated your solution
- Your honest time spent

---

## Your Notes

### What changed

- Added full pagination in `run_sync`, including retry handling for 429/5xx
  failures, clean stop on permanent provider errors, and a repeated-cursor
  guard to avoid infinite loops.
- Added idempotent conditional write behavior in the repository: fresh
  residents increment `created`, newer provider records increment `updated`,
  stale or equal provider records increment `skipped`, and invalid records
  increment `failed` without blocking valid records.
- Hardened provider mapping in `Resident.from_provider_payload`: required
  identifiers and names, `first_name` + `lastName` to `full_name`, ISO `dob`
  parsing, polymorphic `care_level` normalization, `deleted_at` precedence,
  and contextual `MalformedRecordError`s.
- Added edge-case tests in `tests/test_sync_reliability.py` for retries,
  duplicate cursor handling, the judgment fixture mapping rules, ignoring
  `last_modified_by_caregiver` for stale-write protection, and repository-level
  stale-write protection.

### Tradeoffs and known gaps

- Retry behavior uses three total attempts with tiny local backoff for 5xx and
  capped `Retry-After` sleeps for rate limits. That keeps tests deterministic
  and avoids long local runs while still exercising the provider's transient
  failure contract.
- Unknown or out-of-range `care_level` values fail the individual record
  instead of coercing them. I chose data quality over guessing because care
  level is clinically meaningful.
- Stale-write protection lives in `InMemoryRepository.upsert_resident_if_newer`
  and uses a lock around read/compare/write. In Firestore, this same boundary
  would map to a transaction or conditional document write.

### AI usage and verification

I used Chatgpt and Claude to inspect the codebase, verify the sync reliability changes,
think about edge cases, and update this memo. I used AI to quickly learn about
threading, locks and timezone implementation for this project as well.

Validation run:

```bash
venv\Scripts\pytest.exe
venv\Scripts\ruff.exe check .
venv\Scripts\mypy.exe --no-incremental src  # mypy internal error
```

Honest time spent: 40 mins for understanding existing codebase and figuring out
what is missing, 30 mins to understand the edge cases and what I need to implement,
1 hour for final code implementation and verificaiton (manual + AI) and 30 mins for 
updating and verifying documentation (using AI)

### Decision memo
1. How did you handle the polymorphic `care_level` field documented in
   `docs/PROVIDER_API.md`?
- **Polymorphic `care_level`:** I normalize the documented provider variants
   into one internal shape: integers, numeric strings like `"3"`, and
   case-insensitive prefixed strings like `"level_3"` or `"Level_3"` all become
   `int`, while `null` becomes `None`. I also validate the final value is in the
   documented `0..5` range. I intentionally reject unknown forms such as
   `"assisted"` or out-of-range values as malformed records instead of guessing,
   because care level is operationally important care data and a silent wrong
   value would be worse than a visible record-level failure.

2. When a record carries both `is_active` and `deleted_at`, which wins, and
   why?
- **`is_active` vs `deleted_at`:** If both fields are present, `deleted_at`
   wins. The provider docs make `deleted_at` the newer authoritative removal
   signal, while `is_active` can be a legacy or temporary status flag. In code,
   the effective internal value is `is_active=False` whenever `deleted_at` is
   set, even if the provider also sends `is_active=true`.

3. Did you use `last_updated` or `last_modified_by_caregiver` for stale-write
   protection? Why?
- **Stale-write timestamp:** I use provider `last_updated` for stale-write
   protection and compare it against the internal `updated_at`. I ignore
   `last_modified_by_caregiver` for this decision because the docs explicitly
   call it informational and say `last_updated` remains canonical for sync.
   Practically, this means a provider record only overwrites an existing
   resident when its canonical server-side timestamp is newer; equal or older
   records are skipped to keep sync re-runs idempotent.

4. **Past the table.** The Binding rules section of `docs/PROVIDER_API.md`
   resolves the documented cases. For each of the three above, name **one
   edge case the docs do NOT pin down** (e.g., an unknown `care_level`
   variant; `deleted_at` arriving in the future or being un-set on a later
   sync; a real situation in which `last_modified_by_caregiver` should
   matter for staleness) and how your code handles it.
- **Ambiguous edge cases beyond the table:** For an unknown `care_level`
   variant such as `"assisted"`, the code fails only that record and continues
   syncing valid residents. For a future `deleted_at`, the code still treats
   the resident as inactive because the docs do not define scheduled deletion
   semantics, and the safest consistent interpretation is "set means removed."
   For a real caregiver-tablet edit where `last_modified_by_caregiver` is newer
   than `last_updated`, the code still skips or updates based only on
   `last_updated`; if the provider later decides caregiver edits should affect
   staleness, I would change the binding rule in one place rather than mixing
   timestamp precedence ad hoc in the sync.
