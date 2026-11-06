# URL comparisons and exact evidence audits

The delivered lane compares **existing independently permitted library evidence**.
Instagram, TikTok and YouTube URL shapes are supported; no new native account,
media or analytics acquisition adapter is added. A cold URL still needs permitted
observations through the existing source producers. Restricted native-only API
captures cannot be copied into an independent analytical source to bypass policy.

```sh
socialdna workflow plan --mode compare \
  --url https://www.instagram.com/creator_a/ \
  --against https://www.instagram.com/creator_b/ \
  --goal 'Compare the available content and observed performance' --max-posts 10
socialdna workflow run WORKFLOW_ID
socialdna workflow report WORKFLOW_ID --format markdown --output comparison.md
```

Repeat `--left-url`/`--against` for up to five subjects per group. Choose either
account or post scopes, not mixed units. Canonical aliases resolving to the same
identity or overlapping post groups are rejected. The sample is recent publication
order with stable-ID ties, never ranked by outcomes. The plan pins exact revisions,
counts and omissions. Known library inventory is not complete platform history.
Dry-run planning never initializes a library or makes requests.

Without a statistical design the result is an honest partial, cited inventory.
`--comparison-spec PATH` accepts the existing R2 `CorrectedPerformanceSpec` v2
(inspect `skill schema comparison`). The host can prepare this engine configuration
after discussing the estimand, metric/denominator, outcome window, cutoffs, source
permissions, feature timing, sampling frame and design with the user. It must not
invent observations or search designs until an appealing result appears.

The workflow executes the actual `performance_service.compare` pipeline over the
exact selected **post IDs**, including bounded account samples; it never expands
an account into unselected targets. The existing required historical baseline
population remains independently frozen by R2. Incompatible definitions, maturity,
denominators, feature timing, source permissions and overlap retain their existing
gates. Cross-platform pooling is withheld. Descriptive output, model diagnostics,
missingness, counterexamples and qualification remain visible. A supported matched
description is not statistical significance, generalization or a causal effect;
sparse creator support never licenses inference.
Cross-creator groups below R2's existing twenty-cluster inferential engineering
gate remain partial with inference withheld, even when a matched description is
available. This threshold is not a power guarantee. The bounded URL workflow is
primarily a descriptive comparison, not a replacement for a large declared research corpus.

An atomic callback commits the actual run checkpoint with the statistical result.
Retrying a completed/checkpointed workflow does not fit again or consume another
test attempt. Reproduce the exact frozen run with `compare reproduce RUN_ID`;
the existing engine/library/version and eligibility checks apply. Reproduction is
not independent confirmation. A new comparison is explicit, not a report-read side effect.

`--support-revision` and `--contrary-revision` select exact existing qualified
outputs. Measured associations, reviewed literature hypotheses, official guidance,
qualitative profile reviews, measured funnels, exploratory patterns and proposals
retain separate lanes and citations. Applicability is **not** automatically inferred
from retrieval or the fact that a record is attachable. The workflow can consume
prepared R7–R10 outputs; it does not automatically prepare literature, adjudicate
psychology, run discovery or forge human review. Those specialist UX deliveries
remain separate. `--recommendation-spec PATH` uses the real R10 qualified writer;
missing prerequisites withhold the proposal without losing the useful basic report.

## Audit the exact conclusion

```sh
socialdna workflow plan --mode evidence --from COMPARISON_WORKFLOW \
  --goal 'Which exact observations and counterexamples support this report?'
socialdna workflow run AUDIT_WORKFLOW
socialdna workflow report AUDIT_WORKFLOW --format markdown
```

Alternatively select `--entity-revision REVISION`, or an exact `--evidence-id ID`
and `--evidence-revision REVISION` pair. No implicit latest-version substitution.
Canonical SQL and the real typed resolver expose source URI/permission, provenance,
producer run, locator, exact revisions, declared relationships and duplicate exact
locators. Duplicate locators are not independent observations; absence of a match
does not establish independence or rule out near-duplicates. Declared support and
counterevidence roles are not adjudicated evidence strength.

Traversal bounds are depth0–5, nodes1–100 and edges1–200. The report marks truncation
as partial, including depth frontiers; use a child revision for narrower follow-up.
Version listings retain up to ten revisions per visited identity and mark overflow.
R8 history is separately bounded to twenty records per category, with its own
truncation marker. It preserves competing/changed assessments; no reevaluation runs.
Optional `--include-graph` adds the actual bounded SQLite-backed NetworkX historical
view and index backlog. It does **not** reconcile/index, require Qdrant, or replace
canonical evidence when projections are missing or stale. Paths do not prove causes.

Saved JSON/Markdown artifacts are immutable and checksummed. Report freshness is
a separate current-library view; corrections never rewrite old conclusions.
Eligibility is checked on every reuse. Withdrawal/confirmed erasure blocks protected
descendants; a new denied-root audit returns a required action without the source body.
Managed canonical/artifact copies use the existing erasure/restore journal; external
exports, original files and backup bytes remain the operator's responsibility.
Erasure scope remains the existing registered audience/context/composition lanes;
this delivery does not add a generic raw account-export deletion subsystem.

`social-dna-compare` and `social-dna-evidence` export independently with the shared
contract, alongside the six previously delivered task bundles. No new dependency,
SQL migration, vector collection, graph database, scheduler or model is required.
Native multi-URL acquisition, consented live checks and actual host conversational
behavior remain open acceptance gates, not established by fixture/package tests.
