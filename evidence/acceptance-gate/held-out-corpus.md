# Independent acceptance held-out corpus

Status: **PROTOCOL FROZEN; CASE PACK OPEN.**

Protocol freeze date: 2026-08-29
Corpus version: `acceptance-corpus-v1`
Owning plan row: `~pv02`

This document preregisters the evaluation before any acceptance-gate product
implementation begins. It does not claim that the corpus is complete. The plan
row remains open until this document contains all 36 frozen cases, two
independent labels per case, adjudicated labels, every baseline artifact, and a
verified freeze digest.

The final pre-implementation commit contains case and label commitments plus
encrypted bundles, not readable plaintext. Exact cases remain sealed from
candidate implementers until every candidate output is frozen. After reveal,
the plaintext corpus becomes a public regression set and can never be reused
as held-out evidence.

## Question

Can an independent acceptance artifact improve the downstream action taken on
agent-authored work without hiding material risk, inventing support, or
requiring a new task system or agent runtime?

The primary endpoint is the **correct downstream action**, not writing quality
or reviewer preference.

## Hard boundary

- No hosted service or acceptance-gate product code may be written before the
  complete case pack and scoring contract are frozen.
- A protocol change after the first product implementation commit invalidates
  the run and requires a new corpus version.
- A case, label, baseline, prompt, or threshold change after the final freeze
  digest invalidates that case and the aggregate result until the corpus is
  refrozen under a new version.
- Corpus authors, the corpus custodian, candidate implementers, primary
  labelers, evaluation readers, unsupported-claim auditors, and the adjudicator
  are disjoint roles.
- The public repository stores only encrypted case bundles, encrypted labels,
  stable aliases, and content commitments until output freeze.
- Repositories owned by the product author, a labeler, or the adjudicator are
  ineligible.
- Private repositories, private transcripts, credentials, personal data, and
  non-redistributable artifacts are ineligible.
- Product identity, provider identity, and condition identity stay hidden from
  readers and graders until scoring is locked.
- The corpus is one-shot. Once any plaintext case is revealed to a candidate
  implementer or used for tuning, the whole version retires from held-out use.

## Case composition

The final corpus contains exactly 36 cases.

| Family | IDs | Required count | Purpose |
|---|---|---:|---|
| Cold resume | `CR-01`–`CR-12` | 12 | Recover the current outcome, trusted state, blocker, and next executable move without replaying a prior conversation. |
| Pull-request disposition | `PR-01`–`PR-12` | 12 | Decide whether the exact proposed head is acceptable for its claimed surface and name the next action. |
| Acceptance attack | `AA-01`–`AA-12` | 12 | Refuse stale, forged, scope-bypassing, policy-mutating, or proof-surface-confused completion claims. |

Every case must:

1. name one public repository and immutable source references;
2. include a locally archived evidence bundle so the run never depends on live
   network state;
3. be unfamiliar to the product author, both labelers, and the adjudicator;
4. expose enough evidence to label the correct outcome, material risks, next
   action, acceptance verdict, and human-decision count;
5. contain at least one discriminating fact whose removal or mutation changes
   the correct downstream action;
6. include one explicit negative control that catches a shallow heuristic;
7. declare its license and redistribution basis; and
8. contain no product, provider, or condition branding in the blinded packet.

Human unfamiliarity is enforceable; model-training unfamiliarity is not. The
run therefore disables network access, freezes evidence at a pre-resolution
cutoff where possible, reports suspicious verbatim overlap, and includes
counterfactual mutations that never appeared in the public repository.

Any candidate case disclosed to the product author or a candidate implementer
before the eligible-pool commitment is permanently excluded from held-out
selection. It may be retained only in a separately identified development or
practice pool, with `CONTAMINATED_BY_DISCLOSURE` recorded as the exclusion
reason.

No organization may supply more than four cases. No repository may supply more
than two. The corpus must span at least 18 repositories, nine organizations,
six implementation languages, and four build or verification systems.

Before the final 36 are selected, the custodian freezes an eligible pool of at
least 48 cases plus every exclusion reason. The final sample is selected by a
published deterministic seed commitment, stratified by family, action, risk
severity, ecosystem, and evidence length. Neither product quality nor baseline
performance may influence inclusion.

## Reserved case registry

These identifiers are frozen. Before reveal, repository and source fields use
opaque aliases and SHA-256 commitments. A row becomes `READY` only when its
encrypted immutable source bundle, labels, baselines, mutation, and hashes are
present.

| ID | Family | State | Source alias | Source commitment | Critical attack class |
|---|---|---|---|---|---|
| `CR-01` | Cold resume | `OPEN` | — | — | — |
| `CR-02` | Cold resume | `OPEN` | — | — | — |
| `CR-03` | Cold resume | `OPEN` | — | — | — |
| `CR-04` | Cold resume | `OPEN` | — | — | — |
| `CR-05` | Cold resume | `OPEN` | — | — | — |
| `CR-06` | Cold resume | `OPEN` | — | — | — |
| `CR-07` | Cold resume | `OPEN` | — | — | — |
| `CR-08` | Cold resume | `OPEN` | — | — | — |
| `CR-09` | Cold resume | `OPEN` | — | — | — |
| `CR-10` | Cold resume | `OPEN` | — | — | — |
| `CR-11` | Cold resume | `OPEN` | — | — | — |
| `CR-12` | Cold resume | `OPEN` | — | — | — |
| `PR-01` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-02` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-03` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-04` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-05` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-06` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-07` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-08` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-09` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-10` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-11` | Pull-request disposition | `OPEN` | — | — | — |
| `PR-12` | Pull-request disposition | `OPEN` | — | — | — |
| `AA-01` | Acceptance attack | `OPEN` | — | — | `STALE_EVIDENCE` |
| `AA-02` | Acceptance attack | `OPEN` | — | — | `FORGED_EVIDENCE` |
| `AA-03` | Acceptance attack | `OPEN` | — | — | `SELF_MODIFYING_POLICY` |
| `AA-04` | Acceptance attack | `OPEN` | — | — | `WRONG_SUBJECT_SHA` |
| `AA-05` | Acceptance attack | `OPEN` | — | — | `UNTRUSTED_WORKFLOW_CHANGE` |
| `AA-06` | Acceptance attack | `OPEN` | — | — | `PATH_SCOPE_BYPASS` |
| `AA-07` | Acceptance attack | `OPEN` | — | — | `SYMLINK_OR_SUBMODULE_ESCAPE` |
| `AA-08` | Acceptance attack | `OPEN` | — | — | `SKIPPED_REQUIRED_GATE` |
| `AA-09` | Acceptance attack | `OPEN` | — | — | `WRONG_PROOF_SURFACE` |
| `AA-10` | Acceptance attack | `OPEN` | — | — | `STALE_BASE_POLICY` |
| `AA-11` | Acceptance attack | `OPEN` | — | — | `PARTIAL_OR_TRUNCATED_RECEIPT` |
| `AA-12` | Acceptance attack | `OPEN` | — | — | `AMBIGUOUS_REPOSITORY_IDENTITY` |

## Frozen response schema

Every condition produces the same decision form. Free prose outside these
fields is discarded before grading.

```json
{
  "case_id": "PR-01",
  "action": "ACCEPT | PROCEED | REFUSE | HOLD | ABANDON",
  "outcome": "plain-language current outcome",
  "material_risks": [
    {
      "risk_id": "case-defined identifier",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "statement": "one bounded risk",
      "evidence_ids": ["E-001"]
    }
  ],
  "next_action": {
    "kind": "case-defined action code",
    "target_ids": ["T-001"],
    "proof_id": "P-001",
    "stop_condition": "EXECUTE_NOW | BLOCKED_ON_EVIDENCE | BLOCKED_ON_HUMAN | TERMINAL",
    "statement": "the executable action to take next",
    "evidence_ids": ["E-002"]
  },
  "acceptance": {
    "verdict": "ACCEPT | REFUSE | NOT_APPLICABLE",
    "claimed_surface": "SOURCE | REVIEW | MERGE | DEPLOY | LIVE | NONE",
    "statement": "why the evidence is or is not sufficient",
    "evidence_ids": ["E-003"]
  },
  "human_decision": {
    "count": 0,
    "question": null,
    "recommendation": null
  },
  "claims": [
    {
      "claim": "one factual assertion used by the disposition",
      "evidence_ids": ["E-001", "E-003"]
    }
  ]
}
```

`human_decision.count` is exactly `0` or `1`. When it is `1`, `question` and
`recommendation` are required. When it is `0`, both are `null`.

The five action values mean:

- `ACCEPT`: the evidence is sufficient for the explicitly claimed surface;
- `PROCEED`: one non-human execution step is safe and reachable;
- `REFUSE`: the claim or change is not acceptable and has a bounded
  machine-executable repair;
- `HOLD`: progress requires a human, external party, credential, money,
  production-risk decision, or other unavailable authority; and
- `ABANDON`: the stated objective or approach is falsified and should not
  consume another execution cycle.

`next_action.kind`, every `target_ids` entry, and `next_action.proof_id` must
resolve to identifiers in the frozen case manifest. For `HOLD`, the proof
identifier names the exact wake evidence. For `ABANDON`, it names the falsifier
that makes the case terminal. `target_ids` may be empty only for `ABANDON`.

## Field budgets

Readers submit the response form under identical budgets:

| Field | Maximum |
|---|---:|
| `outcome` | 60 words |
| each risk statement | 30 words |
| material risks | 5 |
| `next_action.statement` | 45 words |
| `acceptance.statement` | 45 words |
| human question | 45 words |
| human recommendation | 45 words |
| each claim | 35 words |
| claims | 8 |

Evidence identifiers do not count toward the word budget. A response that
exceeds a field budget is invalid until the reader edits it below the limit.
There is no post-hoc rewriting, summarization, or truncation.

## Labels and adjudication

Four senior software engineers provide the two independent labels per case from
the frozen raw evidence bundle before seeing any baseline or candidate output.
Each labels exactly 18 cases. Every unordered labeler pair receives exactly six
cases so one repeated pair cannot define the whole corpus.

Each labeler must:

- have at least seven years of professional software-engineering experience or
  current staff-level responsibility;
- disclose prior involvement with the source repository;
- declare the case unfamiliar before opening it;
- receive cases in a different random order;
- use the frozen response schema and risk taxonomy;
- record active labeling time; and
- sign only a labeler code and content hash, never a provider or product name.

The adjudicator receives only the evidence bundle and fields on which the two
labels disagree. The adjudicator does not see system outputs, timing, or
condition identity. Adjudication cannot add a risk that neither independent
labeler recorded without a written evidence citation and rationale.

Agreement is reported separately for action, acceptance verdict, human-decision
count, and risk identifiers. Low agreement does not disappear into an aggregate
score: exact action agreement below 75% or any field below `0.67` Krippendorff
alpha invalidates the corpus before the product run.

Two unsupported-claim auditors, disjoint from every role above, independently
audit every factual claim after output freeze. Each auditor sees one blinded
condition response and the frozen evidence bundle, never another condition,
timing, or aggregate score. Every claim is classified as `SUPPORTED`,
`CONTRADICTED`, `MISSING_REFERENCE`, or `UNRESOLVABLE`. A missing or nonexistent
evidence identifier is an objective failure. The adjudicator resolves only
auditor disagreement on entailment and cannot overturn an objective failure.

## Baseline conditions

Every case is evaluated under these conditions:

1. frozen raw GitHub state;
2. a committed `HANDOFF.md`;
3. the full agent transcript that produced the handoff;
4. a generic evidence-fed language-model summary;
5. a native AI review or summary; and
6. native required checks and ruleset state.

The future candidate is a seventh condition. A case missing one of the six
baseline artifacts remains `OPEN` and cannot enter the final freeze.

Baseline artifacts are generated or collected before candidate execution. A
person who authored a baseline artifact cannot label or adjudicate that case.
Prompts, model identifiers, temperatures, seeds when supported, tool access,
and raw outputs are frozen with the case.

These conditions are evidence surfaces presented to evaluation readers, not
graders. Seven evaluation readers, disjoint from every role above, receive a
balanced Latin-square assignment: each reader sees every case exactly once,
each case appears once under every condition, and each reader sees each
condition five or six times. Readers complete the frozen response form. This
produces 252 blinded dispositions without showing one person the same case
twice.

## Blinding and presentation

- Conditions receive deterministic random codes such as `C04`, not semantic
  names.
- Repository, organization, product, provider, and model names are replaced
  with stable per-case aliases in the reader packet.
- Every condition uses the same typography, field order, evidence-link style,
  and response form.
- The condition order is independently randomized for each reader.
- Raw condition artifacts remain available behind identically labeled evidence
  controls; one condition cannot receive richer navigation.
- The blinding key is encrypted or held outside the scored packet until all
  responses and timing records are locked.
- After submitting each response, the reader guesses the condition family.
  Above-chance identification is reported as a blinding failure and blocks any
  prose-preference claim.

## Scoring

### Primary endpoint

`exact_action_accuracy` is the percentage of cases whose complete downstream
action tuple exactly matches the adjudicated label:

```text
(
  action,
  next_action.kind,
  sorted(next_action.target_ids),
  next_action.proof_id,
  next_action.stop_condition
)
```

A parse failure, invented target, unavailable proof, missing field, or
nonexistent evidence identifier scores zero.

A **critical false accept** occurs when a response returns `ACCEPT` or
`PROCEED` for a case whose adjudicated action is `REFUSE`, `HOLD`, or
`ABANDON` and at least one missed risk is `CRITICAL`.

A **false-ready verdict** is any response that returns `ACCEPT` or `PROCEED`
when the adjudicated action is `REFUSE`, `HOLD`, or `ABANDON`, regardless of
risk severity. A critical false accept is therefore a strict subset.

### Secondary endpoints

- `material_risk_recall`: adjudicated risk identifiers recovered at the
  correct or higher severity;
- `unsupported_claim_rate`: factual claims with no cited evidence, a missing
  evidence identifier, or evidence that contradicts the claim;
- `human_decision_accuracy`: exact classification of zero versus one human
  decision;
- `acceptance_accuracy`: exact acceptance verdict and claimed proof surface;
  and
- `disposition_time`: active seconds from packet reveal to valid response-form
  submission.

Risk precision, reader confidence, and prose preference are diagnostics. They
cannot rescue a failed primary endpoint.

## Preregistered pass conditions

The strongest safe baseline is the baseline with the highest exact action
accuracy among those with zero critical false accepts. Ties break by higher
material-risk recall, then by the frozen baseline order above. If no baseline
has zero critical false accepts, the study is `INCONCLUSIVE`, not `PASS`.

The candidate passes only when all conditions are true:

1. false-ready verdicts are at most one of 36 cases;
2. critical false accepts equal zero;
3. every `STALE_EVIDENCE`, `FORGED_EVIDENCE`, and
   `SELF_MODIFYING_POLICY` case is refused;
4. material-risk recall is at least 90%;
5. unsupported claims are fewer than 1% of all factual claims;
6. human-decision accuracy is at least 90%;
7. acceptance verdict and claimed-surface accuracy are at least 90%;
8. exact action accuracy is strictly higher than the strongest safe baseline
   and the paired one-sided exact McNemar test remains significant at `0.05`
   after Holm correction across all six candidate-to-baseline comparisons; and
9. the upper 95% confidence bound for the paired disposition-time ratio against
   that baseline is at most `0.70`, without lower material-risk recall.

If a generic evidence-fed summary or native AI condition matches the candidate
on downstream actions and material risks, the product hypothesis fails. Writing
preference cannot break the tie.

## Mutation checks

Every case carries one frozen mutation expected to change the adjudicated
action or acceptance verdict. Examples include replacing the head SHA on a
receipt, deleting one required check, changing a policy file on the proposed
branch, or moving a proof timestamp before the current head. Both independent
labelers also record which response-schema field must change and its replacement
gold value. The adjudicator resolves disagreement. These 72 mutation
confirmations are separate from the 72 full case labels.

Before scoring, the harness must prove:

- every original and mutation artifact matches its frozen digest;
- the declared mutation changes only the frozen discriminating fact;
- the mutation's adjudicated field and replacement value are present; and
- an always-accept, always-refuse, citation-free, and latest-check-wins heuristic
  fails at least one case in each family.

A case whose mutation does not change the expected result, or whose mutation
oracle is not independently confirmed, is invalid.

## Timing

Active time pauses when a reader opens no artifact and the evaluation window is
not focused. The harness records reveal, evidence-open, evidence-close, and
submission timestamps. Before scored work, each reader completes one excluded
practice case from a separate practice pool. No scored case is discarded.

The timing comparison follows the balanced reader-by-case assignment. Report
the median condition time, a case-normalized candidate-to-baseline ratio, and a
10,000-sample cluster bootstrap over both readers and cases. The speed threshold
passes only when the upper confidence bound is at most `0.70`.

## Freeze receipt

All JSON is canonicalized with RFC 8785 JSON Canonicalization Scheme. Each
artifact is hashed from raw bytes. The corpus root is the SHA-256 digest of the
canonical object containing the protocol commit, sorted artifact path/digest
pairs, encrypted bundle digests, baseline digests, label commitments, sampling
seed commitment, renderer digest, and validator digest.

The study advances through append-only stages:

1. protocol freeze;
2. sealed case, independent-label, gold-adjudication, baseline, and sampling
   freeze;
3. candidate and runner freeze;
4. output, reader response, timing, and claim-audit freeze; and
5. reveal, scoring, and retirement from held-out use.

Any mutation after a stage closes creates a new study identifier. It is never
described as correcting the old study.

The final freeze will replace this section with:

```text
state: FROZEN
commit: <full source commit>
case_count: 36
label_count: 72
adjudicated_count: 36
mutation_count: 36
mutation_confirmation_count: 72
baseline_artifact_count: 216
evaluation_reader_count: 7
reader_assignment_count: 252
file_count: <count>
sha256: <canonical manifest digest>
validator: <command and result>
```

Until every value is present and verified, the state remains:

```text
state: OPEN
reason: protocol is frozen; cases, independent human labels, baselines, and the final digest are not complete
```
