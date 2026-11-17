# ADR-010: Offline evaluation harness for intake lead scoring

**Status:** Proposed (November 17, 2026). Not accepted. This record is a design for review. It does not implement a harness, add a dataset, change the intake workflow, or authorize a network call, a model call, or a CRM call.

**Drafted by:** Grok (AI), to write down the offline design the owner asked for on [issue #18](https://github.com/cairo-solutions/cairo-reference-architecture/issues/18). **Reviews so far:** none. **Final decision:** the owner.

Issue #18 is an external-review recommendation (Pat Santora, 16 November 2026, user-supplied). The issue states that its findings are recommendations, not independently verified test results. This ADR does not treat that review as verification.

## How to read this record

| Label | Meaning |
|---|---|
| **[O]** | Observed in this repository on November 17, 2026, by reading the cited file or by running the existing Code-node source under Node with the same stubs as `workflows/client-intake-agent/tests/code-nodes.test.js`. |
| **[U]** | Assumption. Not stated by issue #18 and not established by the workflow. |
| **[P]** | Proposal for the owner to accept, reject, or replace. |

## Context

[Issue #18](https://github.com/cairo-solutions/cairo-reference-architecture/issues/18) asks for three things:

1. 20 synthetic lead examples with human-assigned expected tiers.
2. Regression evaluation for model and prompt changes.
3. A report of ranking and tier metrics, including potential unfair deprioritization.

Its acceptance line is: a reproducible fixture, a baseline, and thresholds, with no real customer data.

The owner approved only the offline design portion of that issue. This record is that design. The part of #18 that re-runs a model or a prompt is outside the approved portion. It is listed under [Open questions](#open-questions), not designed here.

The intake agent is the reference workflow in [`workflows/client-intake-agent/`](../workflows/client-intake-agent/). Its stated purpose, in the [NIST AI RMF mapping](../governance/nist-ai-rmf-mapping.md), is to summarize and score inbound inquiries so a person can prioritize follow-up. The mapping also says the AI makes no binding decision, that a low score could cause a legitimate inquiry to be ignored, and that the control is: no lead is discarded; scores below 40 and high-value leads are flagged for human review. Scoring a lead is an internal, reversible action under [ADR-004](004-human-approval-gates-for-agents.md).

## Decision this design supports

Once the owner accepts a baseline and the thresholds below, a later harness would answer one question:

**After a change to the workflow's Code-node scoring rules, do synthetic leads still get the same validation result, the same emitted tier and score, and the same human-review flag as the frozen baseline?**

That is a regression check on the deterministic rules. It supports a decision to keep or revert a change to those rules.

It does not, by itself, answer whether the hosted model qualifies leads the way a person would. The model is the `LLM: Qualify Lead` node. That node is an HTTP request to `https://api.anthropic.com/v1/messages`. An offline harness does not call it. A tier or score that appears in a fixture is data a person typed in, standing in for a model response. Agreement between that text and a human label measures the fixture, not a live model.

The [NIST mapping](../governance/nist-ai-rmf-mapping.md) lists a separate, unscheduled measurement: periodic manual review of a sample of scored leads against the director's judgment ("Scoring drift"). This design does not carry out that review and does not use customer leads. **[U]** Whether the owner wants this harness to stand in for that row is open. As written here, it does not.

## Scoring logic as it exists today

Source: [`workflows/client-intake-agent/workflow.json`](../workflows/client-intake-agent/workflow.json). **[O]**

The workflow scores one lead at a time. Nothing in it sorts a batch or writes a field named priority.

| Order | Node | Type | Role in scoring |
|---|---|---|---|
| 1 | `Validate & Normalize Input` | Code | Normalizes the webhook body and sets `valid` |
| 2 | `Input Valid?` | If | Routes on `$json.valid` being true. The false branch responds 400 and never scores |
| 3 | `LLM: Qualify Lead` | HTTP Request | Asks the model for `summary`, `recommended_tier`, and `qualification_score`. Out of scope for the harness |
| 4 | `Parse & Validate LLM Output` | Code | Accepts or replaces the model text, and sets `needs_human_review` |
| 5 | `CRM: Upsert Contact` | HTTP Request | Writes the lead, keyed by email. Out of scope for the harness |

`Log CRM Failure` is also a Code node. It does not score.

### `Validate & Normalize Input`

The node reads `$input.first().json.body`. It trims strings and caps lengths: `first_name` 80, `last_name` 80, `email` 254 (then lowercased), `company` 160, `phone` 40, `source` 40, `message` 4000. An empty `source` becomes `web_form`.

`valid` is false when any of these hold:

- the email fails `/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/`
- `first_name` is empty after trim
- `message` is shorter than 10 characters after trim

The node then deletes `<` and `>` from `message`. The length check runs before that deletion. **[O]** A message of exactly `<<<<<<<<<<` is `valid: true`, and the stored message is empty.

`phone` is kept and capped. It is not required, and it does not change `valid`. There is no callback-number field.

The node does not read a ZIP code, a service area, a spam label, or an emergency label. Those strings affect the outcome only when they sit inside a field the checks above already use (for example a too-short `message`).

### `Input Valid?`

This is an n8n If node, not JavaScript. **[O]** The existing test file does not execute it. **[U]** The harness would treat the Code node's `valid` boolean as the routing decision, which matches this node only while the condition stays "boolean true" on `$json.valid`.

### `LLM: Qualify Lead`

The prompt tells the model to return only JSON with `summary` (2–3 factual sentences), `recommended_tier` (`Starter`, `Growth`, `Enterprise`, or `Not a fit`), and `qualification_score` (integer 0–100). The user message includes company, source, and message. It does not include name, email, or phone. **[O]** The prompt does not define the score as a probability, a rank, or a function of ZIP, spam, duplicates, or emergency versus routine.

The harness does not send this prompt anywhere.

### `Parse & Validate LLM Output`

The node reads the lead from `Validate & Normalize Input` and the model text from `$input.first().json.content[0].text`. It does not score the message itself. The tier and the number come from that text.

Accepted text has all of:

- `summary` is a non-empty string (then sliced to 1000 characters)
- `recommended_tier` is one of `Starter`, `Growth`, `Enterprise`, `Not a fit`
- `qualification_score` becomes an integer in 0..100 after `Number(...)`

On success, `reason` is `ok`, and:

```text
needs_human_review = (qualification_score < 40) OR (recommended_tier === "Enterprise")
```

On any parse or validation failure, the node replaces the model text with a fixed fallback: summary `Automatic qualification unavailable. Route to manual review.`, tier `Not a fit`, score `0`, `needs_human_review: true`, `reason: llm_output_invalid`.

Observed with the current source, November 17, 2026 **[O]**:

| Supplied model text | `needs_human_review` | `reason` |
|---|---|---|
| Starter, score 40 | false | `ok` |
| Starter, score 39 or 0 | true | `ok` |
| Growth, score 100 | false | `ok` |
| Enterprise, score 90 or 10 | true | `ok` |
| Not a fit, score 80 | false | `ok` |
| Prose, unknown tier, score 150, score −1, empty summary, empty text, or 72.5 | true | `llm_output_invalid` |
| Growth, score the string `"72"` | false | `ok` (the string is coerced) |
| Growth, score 72, plus an extra key | false | `ok` (the extra key is dropped) |
| Growth, score 72, summary of 1200 `X` characters | false | `ok` (summary stored at 1000 characters) |

A high score on `Not a fit` is not flagged. The NIST mapping's phrase "high-value leads" is implemented only as the tier `Enterprise`.

### Schema file versus the Code node

[`schemas/llm-qualification.schema.json`](../workflows/client-intake-agent/schemas/llm-qualification.schema.json) says `additionalProperties: false`, `summary` max length 1000, and `qualification_score` is an integer. **[O]** `Parse & Validate LLM Output` does not load that file. Extra keys and a numeric string pass the Code node; a too-long summary is truncated there and would fail the schema. The harness evaluates the Code node, because that is the code on the path that writes `needs_human_review`. **[U]** Checking the schema file as a second gate is not requested by issue #18.

### What the existing test already checks

[`tests/code-nodes.test.js`](../workflows/client-intake-agent/tests/code-nodes.test.js) runs both Code nodes outside n8n with stubbed `$input` and `$`. **[O]** It checks that a valid sample passes, that empty and malformed bodies fail validation, that one well-formed model payload is accepted, and that prose, an unknown tier, and a score of 150 fall back to `needs_human_review: true` with `reason: llm_output_invalid`. It does not assert the score-39, score-40, or Enterprise branches. The proposed harness would complement that file. It would not replace it. **[P]**

## What the harness evaluates

Two layers, kept in separate fields so they are not mixed:

| Layer | Question | When it can be computed offline |
|---|---|---|
| **Oracle regression** | Does this Code node still emit the same JSON as the frozen baseline for each fixture? | Always, once a baseline has been recorded from Node. No human label required |
| **Human labels** | Does that output match a tier, a review judgment, or a "legitimate follow-up" mark a person assigned? | Only for cases where the owner has filled those labels |

Issue #18 asks for human-assigned expected tiers. Those labels belong in the human layer. They are not a substitute for the model, and the model is not run.

The boolean issue language might call a "priority flag" is `qualification.needs_human_review`. The workflow has no other priority field. Metrics in this design use that name.

## Synthetic labeled dataset

**[P]** One JSONL file of 20 cases. Twenty is the count written in issue #18. It is not a sample-size calculation. The risk section records what 20 cases cannot support.

No fixture file is added with this ADR.

### Case shape

Each line is one JSON object:

| Field | Purpose |
|---|---|
| `id` | Stable id, for example `L01` |
| `scenario` | Short name of the branch the case is there to exercise |
| `tags` | Strings from the list in the next section. Tags document intent. They are not inputs to the Code nodes |
| `intake` | The object `Validate & Normalize Input` reads, shaped as `{ "body": { ... } }` |
| `model_output` | `null` when the case stops at validation. Otherwise the object the parser reads: `{ "content": [ { "text": "<json string>" } ] }`, the same shape `code-nodes.test.js` uses |
| `human_labels` | Optional. Omitted until the owner assigns them. Proposed keys, all optional: `expected_tier`, `must_review`, `legitimate_follow_up`, `rank` |

`intake.body` uses only the fields the workflow already accepts: `first_name`, `last_name`, `email`, `company`, `phone`, `source`, `message`. Adding ZIP, callback, spam, or emergency fields would describe an intake API the workflow does not have.

The oracle output is not copied into the case. It is stored in a baseline file produced by running Node, so a code change shows up as a diff against that file. **[P]**

### How cases are produced

**[P]** A person writes every case. Data is invented for this fixture and is obviously fake:

- email domains from the reserved set `.test`, `.example`, and `.invalid`
- telephone numbers in the `555-0100` through `555-0199` range
- names and companies that read as samples (`Casey Sample`, `Sample Widget Workshop`)

Cases are not drawn from the CRM, from execution logs, or from `pinData`. The workflow export's `pinData` is empty. **[O]**

Model JSON inside `model_output` is written by hand. It is a stand-in for the HTTP response. Nothing in the approved offline design calls the model to produce it.

**[U]** Issue #18 says the expected tiers are human-assigned. It does not say whether an assistant may draft the fake inquiry text. This design proposes that the owner writes or reviews every line, and that the owner is the only person who sets `human_labels`.

### Proposed mix of 20 cases

This mix is a proposal so the 20 cases cover the branches the Code nodes actually have. The owner can replace any row. The "current code result" column is the behavior read from the nodes on November 17, 2026, not a new rule. The baseline, once recorded, is whichever JSON Node emits.

| # | Scenario | What the case contains | Current code result |
|---|---|---|---|
| 1 | Valid Growth at 72 | Valid body, model tier Growth, score 72 | `valid` true, review false, `reason` ok |
| 2 | Score boundary 40 | Starter, score 40 | review false |
| 3 | Score boundary 39 | Starter, score 39 | review true |
| 4 | Score 0, schema-valid | Starter, score 0 | review true, `reason` ok |
| 5 | Score 100 | Growth, score 100 | review false |
| 6 | Enterprise, high score | Enterprise, score 90 | review true |
| 7 | Enterprise, low score | Enterprise, score 10 | review true |
| 8 | Not a fit, high score | Not a fit, score 80 | review false |
| 9 | Prose model text | Non-JSON text | fallback, review true, `reason` llm_output_invalid |
| 10 | Unknown tier | tier `Platinum` | fallback |
| 11 | Score above 100 | score 150 | fallback |
| 12 | Negative score | score −1 | fallback |
| 13 | Empty summary | summary `""` | fallback |
| 14 | Missing model text | `content` absent | fallback |
| 15 | Non-integer score | score 72.5 | fallback |
| 16 | Invalid email | body email `not-an-email` | `valid` false; parser not run |
| 17 | Short message | message shorter than 10 characters | `valid` false |
| 18 | Missing phone | `phone` omitted, otherwise like case 1 | `valid` true; phone stored as `""`; score unchanged |
| 19 | Angle brackets | message long enough, contains `<` and `>` | `valid` true; those characters removed |
| 20 | Same email as case 1 | second valid body, same email, its own model JSON | scored on its own; the Code nodes do not drop it |

Cases 16 and 17 have `model_output: null`. The runner records validation only.

### Edge cases the current nodes do not score

Issue #18 does not list these situations. They were named in the request for this design. The workflow's behavior is recorded here so the fixture does not grow a rule the code lacks.

| Situation | Where it shows up in the 20 | What the harness must not claim |
|---|---|---|
| Missing callback number | Case 18 omits `phone`. There is no callback field | That a missing number changes the tier, the score, or `valid` |
| Out-of-area ZIP | No ZIP field and no service-area check. Not one of the 20 scored cases | That a ZIP inside `message` moves the score. The parser never reads the message |
| Spam | Case 17 is the only related deterministic check: a too-short message is invalid. A long message is not classified as spam | That the Code nodes detect spam |
| Duplicates | Case 20 repeats case 1's email | That one of the two is suppressed. Dedup is `CRM: Upsert Contact` (`idProperty: email`), and that node is not run |
| Emergency versus routine | No tier, score, or flag for this. Not one of the 20 scored cases | That the words "emergency" or "routine" in `message` change the Code-node output |

**[P]** If the owner wants ZIP, spam, or emergency material present for a future model evaluation, add it as `tags` on extra lines and leave `human_labels` for the owner. Those lines still need a hand-written `model_output` before the parser can return a tier. They do not become scoring rules.

### Illustrative case

This object shows the shape. It is not a fixture file, and it is not one of a committed twenty.

```json
{
  "id": "L01",
  "scenario": "valid_growth_score_72",
  "tags": ["valid", "review_false"],
  "intake": {
    "body": {
      "first_name": "Casey",
      "last_name": "Sample",
      "email": "casey.sample@example.test",
      "company": "Sample Widget Workshop",
      "phone": "555-0100",
      "source": "web_form",
      "message": "Fake workshop, for the fixture only. We schedule four crews in a spreadsheet and want that intake written down."
    }
  },
  "model_output": {
    "content": [
      {
        "text": "{\"summary\":\"Fake workshop asking to write down crew intake. No real customer.\",\"recommended_tier\":\"Growth\",\"qualification_score\":72}"
      }
    ]
  }
}
```

## Metrics and proposed thresholds

Issue #18 names ranking metrics, tier metrics, unfair deprioritization, a baseline, and thresholds. It does not give a formula or a number. Every number below is a **[P]** for the owner to confirm. Until the owner confirms a gate, a future CI job would fail on a broken runner, an invalid fixture, or an oracle mismatch against an accepted baseline. Human-label rates would be printed and would not fail the job.

### Oracle regression

Compare the Node output to the baseline, field by field:

- validation cases: `valid`, `errors`, and the normalized `lead`
- parser cases: `recommended_tier`, `qualification_score`, `needs_human_review`, `reason`, and `summary`

**Proposed gate:** zero mismatched fields. **[P]** That is the acceptance check that matches "reproducible fixture" and "baseline" for the deterministic code. It does not measure model quality.

### Review flag

When `human_labels.must_review` is present, build a 2×2 confusion matrix of `must_review` against `needs_human_review`, and report precision, recall, and the four counts.

**Proposed gate:** none, until the owner sets one. **[P]** A recall of 1.0 would mean every case the owner marked `must_review` is flagged. Issue #18 does not require that number. The NIST mapping describes missed legitimate inquiries as the risk, which is the recall side, and describes Enterprise leads being flagged even when the score is high, which spends precision. Choosing a floor is the owner's decision.

Cases with no `must_review` label are left out of this matrix. The report says how many cases were left out.

### Tier metrics

When `human_labels.expected_tier` is present, report a confusion matrix over `Starter`, `Growth`, `Enterprise`, `Not a fit`, plus the count of cases whose `reason` is `llm_output_invalid`, and the exact-match rate.

**Proposed gate:** none. Report only. **[P]**

Offline, the emitted tier is the hand-written `model_output` when the parser accepts it, and `Not a fit` when the parser falls back. Exact-match against a human tier is then a property of the text the fixture author wrote. The report states that, so the number is not read as a model score.

### Ranking

The workflow does not rank leads. A ranking metric needs an order the owner supplies, in `human_labels.rank` or in a separate ordered list of ids, and a rule for how score and `needs_human_review` combine into a sort key. Neither rule is in the workflow or in issue #18.

**Proposed gate:** do not compute a ranking metric until the owner defines the order and the sort key. **[P]**

### Calibration

`qualification_score` is an integer from 0 to 100 carried through from the model text. The prompt does not define it as a probability. A calibration curve needs a binary event the score is supposed to predict. That event is not defined.

**Proposed gate:** do not compute calibration error, expected calibration error, or a reliability chart until the owner names the event. **[P]** A histogram of the fixture's scores may be printed as a description of the file. It is not a quality metric.

### Unfair deprioritization

The mapping's concrete risk is a legitimate inquiry ignored because of a low score. The concrete control in code is `needs_human_review`, and no lead is deleted by the Code nodes.

**Proposed report, not a gate [P]:**

- List every case with `human_labels.legitimate_follow_up: true` and `needs_human_review: false`. Those are the cases a person who reads only the review queue would not be forced to open.
- List every case with `legitimate_follow_up: true` whose emitted score is below 40. Under the current rule those are flagged, so the list is a check that the control still holds.
- State the counts of unlabeled cases.

The intake fields do not include a demographic attribute. This design does not add group labels, and it does not report a disparity rate. Inventing groups for a public fixture would be a new requirement and a publication choice the issue does not make. If the owner defines groups later, the metric has to be redesigned in an amendment to this ADR.

## Invoking the existing JavaScript

The rules under test are the `jsCode` strings in `workflow.json`. Two ways to run them from Python:

| Option | What runs | Trade-off |
|---|---|---|
| **A. Extract the Code node and run it in Node** | A small runner loads `workflow.json`, selects the node by name, and evaluates that node's `jsCode` with the same `$input` and `$` stubs as `tests/code-nodes.test.js`. Python passes one case on stdin and reads one JSON object from stdout | The system under test is the workflow source. A second copy of the `< 40` rule does not exist. The cost is a Node dependency, already used by the `code-nodes` CI job (Node 20), and a process boundary. The stub must stay aligned with the test file |
| **B. Reimplement the rules in Python** | Pytest calls Python that copies the validation and the review rule | No Node call. The harness can then pass while `workflow.json` has changed, or fail while the workflow is still right. That drift is the wrong failure for a regression check on the workflow |

**Proposed choice: A.** **[P]** Python loads fixtures, starts the runner, and computes metrics. Python does not re-encode the score threshold, the tier list, or the email check.

**[P]** The runner evaluates `jsCode` taken from the workflow file on disk. It does not evaluate strings from the fixture. Fixture data is passed only as the stubbed input JSON. The runner does not read the HTTP nodes and does not open a socket.

**[U]** The stubs match today's nodes, which use `$input.first()` and `$('Validate & Normalize Input').first()`. A later edit that uses other n8n helpers (`$env`, `$item`, HTTP helpers, `Date` in the scoring nodes) would need a stub change. The scoring nodes do not use those today. `Log CRM Failure` uses `Date` and is not part of this harness.

## Proposed file layout and CLI

Nothing in this tree is created by this ADR. **[P]** Place the harness next to the workflow it measures:

```text
workflows/client-intake-agent/eval/
  README.md                         how to run, written when the harness exists
  pyproject.toml                    pytest, ruff, mypy only
  intake_eval/
    __init__.py
    fixtures.py                     load JSONL and check the case shape
    runner.py                       Node subprocess, local files only
    metrics.py                      matrices and rates
    cli.py
  node_runner/run-code-node.mjs     extract jsCode, stub $input and $, print JSON
  fixtures/leads.jsonl              the 20 cases, after the owner reviews them
  baselines/lead-scoring.json       recorded Node output, after the owner accepts it
  tests/                            pytest for the loader, the metrics, and the no-network guard
```

The repository has no Python toolchain today. **[O]** Adding one is part of the later implementation, not part of accepting the idea in the abstract. **[U]** Issue #18 does not name Python. Python is the language this design was asked to use.

**Proposed CLI [P]:**

```text
python -m intake_eval \
  --workflow workflows/client-intake-agent/workflow.json \
  --fixtures workflows/client-intake-agent/eval/fixtures/leads.jsonl \
  --baseline workflows/client-intake-agent/eval/baselines/lead-scoring.json \
  --report-dir <directory>
```

`--check` compares against the baseline and returns a non-zero status on an oracle mismatch. Human-label sections are written into the report and do not change the status until the owner adopts a threshold. The process does not read API keys, does not read a credential file, and has no flag for a model endpoint.

## CI integration

Existing jobs stay as they are **[O]**:

- `.github/workflows/tests.yml` validates JSON and runs `node workflows/client-intake-agent/tests/code-nodes.test.js` on Node 20
- `.github/workflows/secret-scan.yml` runs gitleaks

This ADR does not add a job. A later implementation would add one job, proposed as follows **[P]**:

- `runs-on: ubuntu-latest`, `permissions: contents: read`
- Node 20, matching `tests.yml`
- Python 3.12 **[U]** (the issue does not name a version)
- install pinned `pytest`, `ruff`, and `mypy` only
- `ruff check` and `mypy` on `intake_eval`, with the tool defaults, unless the owner sets stricter flags
- `pytest` with no network: the test process gets no API key in the environment, imports no HTTP client, and a test replaces `socket` creation so an accidental outbound connection fails the run
- the install step may download those pinned packages; the evaluation step may not open a connection
- the job does not call `LLM: Qualify Lead`, the CRM URL, or any other host

`pytest` here tests the loader, the metric arithmetic on a handful of in-memory rows, and the runner's refusal to touch the HTTP nodes. The 20-case regression run is the CLI `--check` step in the same job, after those tests. The in-memory rows in the unit tests are not a second copy of the scoring rule.

## Privacy and security

- The fixture is synthetic and is safe to put in this public repository only if every line stays obviously fake. Publication rules are in [`docs/PUBLICATION-AND-EVIDENCE-POLICY.md`](../docs/PUBLICATION-AND-EVIDENCE-POLICY.md).
- No customer or prospect data, no production `pinData`, no execution dumps, no real phone numbers or mailboxes.
- The runner does not log the case body on failure beyond the case `id` and the field names that mismatched. Summaries in the baseline are the synthetic ones from the fixture.
- The runner does not receive secrets and does not print the workflow's credential placeholders. The reference export already uses placeholders; the harness has no reason to read them.
- `new Function` runs only `jsCode` from the workflow file in the checkout. Fixture `message` text is data.
- Gitleaks already scans pushes. Fixture text must not contain strings shaped like keys, even as jokes.
- The score threshold and the Enterprise rule are already in the public workflow and in the NIST mapping. The harness does not publish a new operational path.
- The harness does not contact a lead, write to a CRM, or approve anything. [ADR-004](004-human-approval-gates-for-agents.md) is unchanged.

## Risks

| Risk | Why it matters |
|---|---|
| The offline harness is read as a model evaluation | Issue #18 asks for regression of model and prompt changes. This design does not run the model. A green `--check` means the Code nodes matched the baseline |
| Oracle labels and human labels get merged | The suite would then "pass" by repeating the code, while looking like a judgment of lead quality. The two layers stay in different files |
| Twenty cases | A confusion matrix, a precision, or a calibration curve on 20 rows moves by a large amount when one label changes. Fine for an exact-match regression. Weak as a quality rate |
| Reimplementation drift | Option B would test a copy. Option A is the proposal |
| Schema and Code node disagree | A fixture that the schema would reject can still be `reason: ok`. The report has to name which artifact was executed |
| String scores and extra keys | Today's parser accepts both. A baseline freezes that unless the owner changes the node |
| `<<<<<<<<<<` is valid | The length check runs before `<` and `>` are removed. A regression oracle preserves that |
| `Not a fit` with score 80 is not reviewed | A human label of `must_review: true` on that pattern would fail a future recall gate without any model being wrong. The code is doing what it says |
| Ranking and calibration reported anyway | Numbers without a defined sort key or a defined event would look like measurements. They are omitted until the owner defines them |
| Group fairness on invented attributes | Would over-claim. Not in this design |
| Real data in a public fixture | The fixture is hand-written and reviewed. There is no import path from the CRM |
| Node stub drift | If a future Code node uses an n8n helper the stub lacks, the runner fails closed rather than guessing |
| Thresholds set before a baseline exists | The first recorded run is the baseline. Gates apply to later diffs, after the owner accepts that file |
| This public design is mistaken for a production control | Status is Proposed. The [build-status](../architecture/build-status.md) document is unchanged, because nothing was implemented |

## Decision (proposed)

1. **[P]** Adopt option A: an offline Python harness that runs the Code-node JavaScript from `workflow.json` under Node, with the stubs already used by `tests/code-nodes.test.js`.
2. **[P]** Evaluate `Validate & Normalize Input` and `Parse & Validate LLM Output` only. Do not call `LLM: Qualify Lead`, `CRM: Upsert Contact`, or `Input Valid?`.
3. **[P]** Use 20 hand-written synthetic cases, human labels optional and owner-assigned, oracle baseline stored separately.
4. **[P]** Gate later CI on exact oracle match only, after the owner accepts the baseline. Report review-flag precision and recall, the tier confusion matrix, and the legitimate-inquiry lists. Do not gate them yet.
5. **[P]** Do not compute ranking or calibration until the open questions on those metrics are answered.
6. **[P]** Do not add demographic group labels.
7. Accepting this ADR, if the owner accepts it, records the design. It does not implement the harness, create the fixture, or change GitHub settings.

## Consequences

- The repository gains a written target for a later implementation pull request. This pull request adds only this record and its row in the decision index.
- Model and prompt regression, as written in issue #18, remains unaddressed until the owner approves a design that is allowed to call a model.
- The existing `code-nodes` test and the secret scan stay the CI for this change.
- No production workflow, credential, or branch protection changes.

## Open questions

These are undecided in issue #18, in the workflow, or in the owner's approval of an offline design only.

1. **Model and prompt regression.** Issue #18 asks for it. The approved work is the offline design. Is a later, separate design for a sandbox model run wanted, or is that request declined?
2. **What a human tier means.** Is `expected_tier` the tier a person would assign from the inquiry text, or the tier the person expects the parser to emit from the hand-written model JSON? Those are different comparisons.
3. **Who writes the stand-in model JSON.** The harness cannot call the model. Does the owner write every `model_output`, or is a one-time capture from a sandbox the owner runs outside this harness allowed? A capture would have to be synthetic and reviewed before commit.
4. **Is 20 required.** Issue #18 says "Create 20". Is that the fixture size, or an illustration the owner may resize?
5. **Which rates gate CI.** The issue says "thresholds" and does not give numbers. Which of review-flag recall, review-flag precision, and tier exact-match, if any, should fail CI, and at what value?
6. **Ranking.** What order should be compared, and what sort key combines `qualification_score` and `needs_human_review`? The workflow defines neither.
7. **Calibration.** If the score is to be treated as predicting an event, what is that event? The prompt does not call the score a probability.
8. **Priority flag.** Confirm that `needs_human_review` is the flag metrics should use. The workflow has no field named priority.
9. **Unscored edge cases.** Should ZIP, spam-like long messages, and emergency-versus-routine text appear as tagged, unscored cases for a possible later model eval? This design leaves them out of the 20 because the Code nodes do not score them. Missing phone and a repeated email are included, with the expectations in the table above.
10. **Legitimate follow-up.** Who may set `legitimate_follow_up`, and is that the same judgment as `must_review`? The issue says "potential unfair deprioritization" and does not define the label.
11. **Protected groups.** Are any group attributes in scope? This design proposes none.
12. **Label authorship.** May an assistant draft fake inquiry text, with the owner assigning every human label, or must a person write the cases unassisted? Issue #18 says human-assigned expected tiers and does not mention draft text.
13. **Schema file.** Should the harness also evaluate `llm-qualification.schema.json`, given the Code node does not load it?
14. **Python.** Confirm Python, pytest, ruff, and mypy as the harness tooling, and confirm the Python version. The repository does not use Python today.
15. **Where the baseline lives.** Is a committed `baselines/lead-scoring.json` in this public repository acceptable, given it will contain the synthetic summaries?
16. **Scoring-drift row.** Does the owner want this harness to count toward the unscheduled "Scoring drift" measurement in the NIST mapping? As specified here, it does not: that row is a manual review of scored leads against the director's judgment.
17. **Relationship to `code-nodes.test.js`.** This design proposes that the harness complements the existing test. Should the score-39, score-40, and Enterprise branches also be added to that test file in the implementation pull request?
18. **Status of the recommendation.** Accepting this ADR would accept a design. It would not, on its own, accept issue #18's recommendation as an implemented control.
