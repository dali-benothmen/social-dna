# Literature-backed, bounded psychological research

Available in `0.0.11`, database head `0011_research`. R7 adds one complete **offline,
human-specified assessment path**, not autonomous psychological discovery. It reuses
[creative annotations](creative-analysis.md), [audience evidence](audience-analysis.md),
[behavioral metrics](behavioral-analysis.md), [version-2 analytics](versioned-analytics.md)
and [persistent memory](research-memory.md). No new dependency, hosted model, server,
download or automatic publishing is required.

## Working workflow

1. Import authorized local media, account exports, supplied outcomes and reviewed
   content/reaction annotations through the existing commands. Include ordinary and
   unsuccessful posts, not just semantic-search hits.
2. Register a question and at least two rival draft hypotheses using `research register`.
3. Import a small reviewed corpus with `research import-literature`.
4. Prepare a protocol binding the exact question/hypothesis, construct, measurement-plan
   and study-excerpt revisions, with reviewed applicability and falsifiable predictions.
5. Run an explicit version-2 account/post comparison using the declared feature recipe,
   outcome/window, population, family and cutoff. R7 also accepts a previously frozen
   analysis, but **never labels retrospective preparation as preregistration**.
6. Evaluate the prepared protocol against those frozen runs and optional in-population
   media/reaction/behavioral citations. Review the immutable findings and proposed
   discriminating experiment. Reopen reports in a new process or retrieve their citations.

Actual commands (bound specification files must use refs returned by your own library):

```bash
socialdna research register --spec examples/research/question.json --format json
socialdna research import-literature --spec examples/research/literature.json --format json
socialdna research prepare --spec protocol.json --format json
socialdna research evaluate --spec evaluation.json --format json
socialdna research show ASSESSMENT_ID --format json
socialdna research report ASSESSMENT_ID --report-format markdown --format json
socialdna evidence resolve EVIDENCE_ID --revision EVIDENCE_REVISION --format json
socialdna query curiosity --family research_knowledge --format json
```

`research register` still writes R1-compatible **drafts**; preparation is an additive
operation and does not reinterpret those drafts or their historical citation reports.
`research show` accepts exact revisions of protocols, assessments, findings and briefs.
`research report QUESTION_ID` retains the unevaluated registration-report contract;
use the assessment identity to request an evaluated report.

Copy [the protocol template](../examples/research/protocol-template.json), replace its
library-local question/hypothesis/construct/measurement-plan/evidence refs with actual
returned refs and the outcome key with your source definition, and record your actual
reviewer/context/design. It is deliberately **not runnable with placeholder identities**.
It matches all five rivals in the draft question example; unsupported explanations
stay unsupported. The schema is executable documentation through
`ResearchProtocol.model_json_schema()` and `EvaluationSpec.model_json_schema()`.

## Corpus contract and source verification

`LiteratureCorpus` in [`domain/investigation.py`](../src/socialdna/domain/investigation.py)
is a strict `1.0` document, limited to 1 MB and 30 sources. Each source has a DOI,
HTTPS primary URL, title/authors/year, current/corrected/retracted publication status,
reviewed/unverified status, reviewer, verification note, permission basis and a bounded
captured text excerpt. Findings bind an exact Unicode span and named page/section,
design, population, exposure, outcome, direction and limitations. Quote/bounds and
within-corpus finding/construct references are validated atomically.

Imports return exact source/finding/construct/operationalization refs and finding
citations. Stable paper identity follows DOI; source authority/provenance and every
captured edition remain pinned. A construct's definition/exclusions cite actual study
findings. An operationalization binds the exact construct, procedure, indicator,
population, validation status and limitations; a proposed instrument is not data.

DOI identity folds ASCII case only, following the [DOI Handbook](https://www.doi.org/doi-handbook/html/).
One corpus cannot supply conflicting editions of the same DOI; import corrections
as separate immutable revisions. Non-ASCII characters are not incorrectly case-folded.

**Human review is an explicit trust boundary.** Offline import cannot establish that
a plausible DOI exists, that a reviewer is truthful, or that a paper has no unreported
correction. Syntax, exact captured excerpts and internal bindings are checked; external
bibliographic authenticity and applicability are reviewer attestations. Unverified or
retracted sources cannot support a new assessment. A later imported retraction,
correction or rescinded review makes affected old inputs ineligible without rewriting
the historical assessment. This is eligibility handling, not R8 reevaluation.

The [seed corpus](../examples/research/literature.json) contains two real, narrowly
curated curiosity studies, not evidence that finished-meal openings work:

- A trivia-task study reports curiosity-related activity and behavior; its laboratory
  setting and outcomes do not directly transfer to social-video openings. Metadata and
  a minimal excerpt were checked on the [publisher's primary page](https://journals.sagepub.com/doi/10.1111/j.1467-9280.2009.02402.x).
- A numerical-fact experiment compares generating predictions with examples. It
  distinguishes increased curiosity from a nonsignificant overall memory contrast;
  it does not establish a social-video mediator. The [primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6803639/)
  supplies the reviewed abstract/results/discussion.

The corpus does not establish sensory appeal, anticipated reward or fluency for cooking
viewers. Those explanations may be registered as explicitly unsupported rivals until
appropriate reviewed evidence is imported. These summaries and their transfer limits
are project interpretations, not guaranteed effects. No full-text mirror or scientific
validity benchmark is bundled.

## Prepared protocol

`ResearchProtocol` requires an exact registered question, two to ten distinct hypotheses,
population, canonical-SQL-manifest selection policy, four context statements, and a
proposed experiment design with two to four treatment variants. Context statements must
disclose production, distribution, publishing and profile alternatives or unknowns;
they do not require the future C1 extractors.

Preparation must retain every registered rival for that question, rather than silently
dropping an inconvenient explanation. The bounded slice supports at most ten rivals;
larger investigations need a separately scoped question, not selective omission.

Each `HypothesisPlan` binds:

- Exact hypothesis revision belonging to that question; psychological or contextual
  explanation, confounders and scope conditions.
- A prediction with exact feature and metric keys, positive/negative direction, contrast,
  contrary result/falsifier and discriminating measurement proposal.
- For a grounded psychological explanation, a `construct_ref` and its actual
  `operationalization`, plus study-excerpt applicability reviews (`direct`, `indirect`,
  `not_applicable`) with reviewer and rationale. Unsupported explanations may omit these;
  no construct is invented to fill a missing field. Contextual rivals use no fake psychology.

Example evaluation document shape (substitute real returned IDs):

```json
{
  "schema_version": "1.0",
  "protocol": {"kind": "research_protocol", "id": "PROTOCOL_ID", "revision_id": "PROTOCOL_REVISION"},
  "analysis_run_ids": ["VERSION_2_ANALYSIS_RUN_ID"],
  "evidence": [],
  "expected_claim_level": "hypothesis"
}
```

`expected_claim_level: "association"` requests a stronger gate, not an instruction
to produce an association. Causal claims and arbitrary extra fields are rejected.
The [integration fixture](../tests/integration/test_psychological_research.py) constructs
complete protocols from actual returned references and runs the media-to-report path.

## What evaluation actually computes

Up to four explicit **frozen version-2 runs**, each at most 10,000 selected/reference
rows, supply the original SQL populations, source/feature lineage, method versions,
outcome/denominator/maturity policy, matching diagnostics and test-family/holdout
history. Old unversioned analyses are rejected. Evaluation checks completed attempt
ownership, resolves actual statistical citations and does not fit a second statistical
engine, consume another holdout or count repeated rows as independent confirmation.

For each matching feature/outcome prediction, the evaluator retains the actual fitted
term, interval and family-adjusted p-value, model status, comparison and ledger.
Only an inferentially fitted result with adjusted p ≤ .05 and an interval excluding
zero receives `consistent` or `contrary`; other results are inconclusive/unavailable.
Opposing results across supplied analyses are `conflicting`, not selectively discarded.
A null result is not proof of no effect. Directional interpretation retains the original
specification and scientific limitations; it is not a new family-wide confirmatory test.

Findings persist explicit `supporting`, `contradicting`, `non_discriminating` and
literature-`context` citation links in `evidence_links`, scoped to the registered
question. Statistical support targets the **local prediction only**, not psychological
mediation. Reports retain the original statistical limitations plus the reviewed
source finding's design, population, exposure, outcome and limitations.

The assessment separately records actual feature availability/coverage/blinding and
value IDs, original validation scope, reviewed literature applicability, local
association, confounders, counterexamples and `causal_identification: not_identified`.
The extraction summary uses one snapshot per post from the last supplied run;
original run-specific lineage remains available through the frozen analyses.
`mechanism_status` remains non-discriminating, unsupported-literature or not-applicable.
An association can support a prediction without demonstrating its psychological mediator.

Counterexamples are bounded within-population outcome-quartile exemplars: unsuccessful
binary technique uses and successful absences, with unknown labels preserved. They
are illustrative IDs, never a replacement sample. Same/cross-creator designs use R2's
actual eligibility/overlap rules and can honestly refuse for insufficient support.

Optional supplementary citations must belong to posts/accounts/media in the frozen
population. R4 collection/reaction records retain sampling/review and noncausal-link
qualifications. R5 retention series retain source grid/denominator/cohort/replay semantics;
they are contextual observations, **not new retention regressions or measured curiosity**.
Public scalar outcomes remain an explicitly separate, more limited evidence path.

## Persistence, reports and operations

SQLite owns versioned source/finding/construct/measurement-plan/protocol/assessment/
finding/brief documents. Only usable protocol, assessment/dependency and typed citation
bindings have new projections. `0011_research` expands the locator CHECK through an
atomic parent rebuild preserving immutable guards and R6's insertion journal; released
migrations `0001`–`0010` are unchanged. Empty-store downgrade works; populated research
stores with captured history require verified backup/restore rather than destructive downgrade.

Retries reuse the same assessment/findings/brief identities for identical inputs.
Reports store escaped JSON/Markdown artifacts with exact bibliography, citations,
populations, attempts, uncertainty and proposed-not-executed experiments. R6 indexes
the new canonical producers in existing families/spaces; graph links remain qualified
structural references to reified findings, not direct causal technique→success edges.

Withdrawal/retraction/expiry makes dependent content unavailable in current reads and
report generation. Authorized audience erasure propagates through assessment payloads,
derived artifacts and memory; a historical artifact is not permission to retain erased
text. Existing backup/restore reconciliation remains mandatory.

## Verification boundaries and next work

Automated tests use actual FFmpeg media, imports/annotations, SQLite/FTS, subprocess
CLI reload, frozen report artifacts, source withdrawal/correction, erasure, legacy
upgrade/rollback and the selected R2 model pipeline. A controlled 22-creator fixture
tests directional association and an opposing prediction; small/noisy/null fixtures
must withhold unsupported conclusions. These verify software behavior, not real-world
psychological validity, representative audience inference or model-label accuracy.

R8 will add population/dependency staleness, successive assessment histories and explicit
reevaluation. R9 owns broader discovery/transfer; R10 owns actual experiment registration,
outcomes and qualified recommendations. C1 and U1/U2 remain separately planned. No
background researcher, autonomous literature validation or creator-account action is added.
