# Production, distribution, discoverability and conversion capability audit

Delivery update (`0.0.13`): C1-A now implements reviewed professional v2 annotation
imports and eight craft recipes through existing comparison, evidence and incremental
research services. See [actual operations and limits](production-evidence.md).
C1-B (`0.0.14`) adds [publishing-context imports and reports](publication-context.md).
C1-C (`0.0.15`) adds [platform/source-specific evidence and descriptive reports](platform-research.md).
C1-D remains pending. The original audit below records the earlier baseline;
it is not a claim that all four intelligence areas or empirical validity are complete.

Reviewed: 2026-11-05 against package `0.0.10`, SQLite head `0010_memory`, the active roadmap, design documents and implementation. This is a documentation-only revision: R1–R6 remain delivered; R7 remains next. **None of the four requested areas is complete today.** Existing extensibility is not an implemented capability or empirical validation.

This document supplements, rather than rewrites, the historical [architecture audit](architecture-audit.md). It defines the future C1 extension track in [PLAN.md](../PLAN.md), using the existing [architecture](../ARCHITECTURE.md), [research contracts](research-contracts.md), [statistical design](statistical-design.md) and [migration strategy](migration-strategy.md). Names of new records, services and files below are **planned responsibility boundaries, not existing APIs, tables or commands**.

## 1. Coverage against working code

“Full” below means the narrowly named software behavior works; it does not mean an entire intelligence area is complete, a detector is scientifically validated, or a recommendation is causally established. “Partial” means an operational foundation exists but necessary semantics, inputs or analysis are missing. “Missing” means no dedicated producer/contract/service exists; arbitrary JSON and model prose do not count.

### 1.1 Professional filmmaking and editing — partial overall

| Requested capability | Current coverage and explicit boundary | Delivery owner |
|---|---|---|
| Shot boundaries, durations and cut rate | **Full for deterministic measurements.** Scene detection provides candidate boundaries and durations, not a human-validated edit interpretation. | Delivered media foundation; C1-A validation/extensions |
| Camera angles, shot size, composition and movement | **Partial.** Frame geometry, edges and optical flow exist; no typed shot grammar, composition rubric or separation of subject motion from camera motion. | C1-A; comparisons R9 |
| Lighting, grading, color, focus | **Partial.** Brightness/contrast, HSV/LAB summaries and blur proxies exist. No lighting setup, grading/look, depth-of-field or focus-pull analysis. | C1-A |
| Editing rhythm, pacing, cuts and transitions | **Partial.** Cut timing and limited order/conjunction recipes exist. No complete transition taxonomy, beat structure, pacing arcs or validated montage continuity analysis. | C1-A; interactions R9 |
| Subtitles and visual effects | **Partial.** Supplied subtitles and optional OCR/alignment preserve text/timing. No subtitle layout/readability/style analysis or typed VFX/compositing events. | C1-A; static assets U1 |
| Music, sound and synchronization | **Partial.** RMS, pitch/spectral/onset proxies, optional audio labels and limited event proximity recipes exist. No validated music/beat alignment, mixing/ducking or audiovisual reinforcement model. | C1-A; interactions R9 |
| Technique interactions and cross-creator performance | **Partial.** Eleven pinned recipes and declared statistical interactions/comparison designs work, but broad craft features are unavailable. Temporal proximity is not reinforcement or causation. | C1-A inputs; R9 analysis |
| Actionable filming/editing strategies | **Missing as an evidence-qualified recommendation service.** Descriptions are not validated shot lists or editing advice. | R10, surfaced through U2 |

Implementation evidence: [`media/scenes.py`](../src/socialdna/media/scenes.py), [`analyzers/visual.py`](../src/socialdna/analyzers/visual.py), [`analyzers/audio.py`](../src/socialdna/analyzers/audio.py), [`domain/creative.py`](../src/socialdna/domain/creative.py), [`analytics/creative_recipes.py`](../src/socialdna/analytics/creative_recipes.py), [`domain/research.py`](../src/socialdna/domain/research.py). The released creative annotation vocabulary is a **closed ten-label literal**, oriented toward the cooking use case. `unclassified` descriptions do not implement additional typed techniques. Existing [creative integration tests](../tests/integration/test_creative_analysis.py) validate lineage, timing and joins, not professional cinematography accuracy.

### 1.2 Platform recommendation and distribution — partial overall

| Requested capability | Current coverage and explicit boundary | Delivery owner |
|---|---|---|
| Platform-specific metric definitions, windows and denominators | **Full for supplied, source-defined records.** Ownership/platform checks, cohorts, retention bins and qualified comparisons work. Metric availability is not guaranteed. | Delivered R5 |
| Separate platform/surface research models | **Missing.** A platform comparison stratum and a free-form traffic cohort do not define Instagram Feed/Explore/Reels, TikTok For You/Search, or YouTube Home/Suggested/Search/Shorts models. | C1-C; R9 |
| Official documentation and changing guidance | **Missing as versioned research evidence.** Existing draft hypothesis citations do not provide an official-document claim lifecycle, applicability or dated policy history. | C1-C; R8 dependencies |
| Longitudinal distribution observations | **Partial.** R5 stores dated metrics, but source-surface mappings, exposure maturity, search traffic and eligibility context are not a dedicated distribution pipeline. | C1-C; R9 |
| Retention, shares, saves, engagement, relevance and audience response | **Partial.** Several measurements/reactions can be imported; no platform-specific interpretation or identified ranking effect follows. A metric may be unavailable or not a documented signal on a particular surface. | C1-C; R9/R10 |
| Creator experiments and bounded distribution advice | **Missing as execution-ready research.** Registration/outcome analysis and recommendation validation remain planned. | R10 |

Implementation evidence: [`domain/behavioral.py`](../src/socialdna/domain/behavioral.py), [`storage/behavioral_repository.py`](../src/socialdna/storage/behavioral_repository.py), [`domain/research.py`](../src/socialdna/domain/research.py), [behavioral integration tests](../tests/integration/test_behavioral_analysis.py), [`memory/graph.py`](../src/socialdna/memory/graph.py). Current graph relations are structural citations/context, not learned algorithm weights or evaluated ranking claims.

### 1.3 Publishing, discoverability and metadata — partial overall

| Requested capability | Current coverage and explicit boundary | Delivery owner |
|---|---|---|
| Dates, formats, titles, captions and hashtags | **Full for current v1 storage fields and captured revisions.** This is ingestion/history, not title optimization, keyword relevance or every platform's native format taxonomy. | Delivered imports/R1/R3 |
| Posting time and frequency | **Partial.** A UTC-hour feature exists. The importer normalizes timestamps and writes `source_timezone="UTC"`; it does not retain an operational creator IANA zone, original offset, DST schedule or completeness-aware cadence. | C1-B; R9 |
| Thumbnails, packaging variants and metadata edits | **Partial.** Title/caption history exists, but no thumbnail asset/variant identity, placement or tested title-thumbnail combination contract. Exact post-text locators currently cover caption/hashtag only. | C1-B with U1; R9/R10 |
| Keywords, language, topic relevance and trends | **Partial.** Tags/topics can be stored. Search query matching, language-aware extraction, trend source/window/locale and dated relevance models are missing. | C1-B/C1-C; R9 |
| Search vs recommendations vs conversion | **Missing as distinct analysis objectives/services.** Scalar engagement cannot substitute for any of these channels. | C1-B/C1-C/C1-D; R9/R10 |
| Context-specific publishing strategies | **Missing as qualified recommendations.** Platform, niche, language, audience and uncertainty must jointly constrain advice. | R10; U2 |

Implementation evidence: [`ingestion/tabular.py`](../src/socialdna/ingestion/tabular.py), [`application/account_import_service.py`](../src/socialdna/application/account_import_service.py), [`analytics/features.py`](../src/socialdna/analytics/features.py), [`domain/evidence.py`](../src/socialdna/domain/evidence.py), [versioned analytics tests](../tests/integration/test_versioned_analytics.py). Do not relabel UTC hour as the creator's or audience's local posting time.

### 1.4 Profile and account conversion — partial overall

| Requested capability | Current coverage and explicit boundary | Delivery owner |
|---|---|---|
| Handle, supplied profile data and history | **Partial.** Concrete handle/creator/niche fields and arbitrary profile JSON are saved in captured account revisions. Profile history is not absent, but field semantics and field-level completeness are missing. | Delivered import substrate; C1-D |
| Username/display name/photo/bio/links/pins | **Missing as a complete typed audit.** No ordered pin/link identities, image evidence, profile-text locators, field-validity clocks or profile-audit service. | C1-D, image path U1 |
| Branding, pillars, positioning and consistency | **Missing as rubric-backed analysis.** Owner declarations must remain distinct from human/model interpretations. | C1-D; R9 |
| Visits, follows, clicks, conversions and attribution | **Partial.** Source-defined post/account measurements can store supplied values. Current account outcomes are exact follower endpoint differences or supplied signed net growth. Conversion credits refer to posts; a campaign string is not a typed campaign/link/profile subject. | Delivered R5; extensions C1-D |
| Profile funnel, sustained followers and business results | **Missing as joined/cohort analysis.** No validated multi-stage funnel, new-follower retention or business-outcome service. Aggregate counts do not reveal individual journeys. | C1-D; R9/R10 |
| Profile and growth recommendations | **Missing as evidence-qualified output.** Public profiles alone cannot establish private conversion rates or competitor revenue. | R10; U2 |

Implementation evidence: [`application/account_import_service.py`](../src/socialdna/application/account_import_service.py), [`domain/behavioral.py`](../src/socialdna/domain/behavioral.py), [`application/performance_service.py`](../src/socialdna/application/performance_service.py), [behavioral analysis](behavioral-analysis.md). Preserve the current prohibition on nearest-post growth attribution.

## 2. Shared extension architecture — planned, not implemented

Do not build four separate engines. Reuse canonical revision/evidence records, content-addressed artifacts, existing media tasks, feature materialization, comparison specifications, and R6 memory. SQLite owns facts; FTS/Qdrant/NetworkX remain qualified derived projections. No new server, crawler, graph database, model requirement or automatic publishing is introduced.

The common path is: authorized import/annotation → immutable context or technique revision → typed evidence resolution → versioned feature recipe → frozen eligible comparison population → R7/R9 assessment or explicit insufficiency → R8 revision when inputs change → R10 qualified test/recommendation. Simple single-account/media descriptions stop before research when appropriate.

All new schemas carry source authority, exact subject/revision, schema/hash, author/provider/review status, coverage, missingness, capture/knowledge time and applicable world-validity interval. **Observed, inferred, owner-declared and experimentally assigned values are distinct.** Unknown historical validity is not backdated to publication. Contracts below are logical payloads; introduce indexed projections only with actual query workloads and writers.

### 2.1 C1-A: professional production evidence

Extend the creative vocabulary through an explicit new schema/registry version, preserving R3 v1 readers, rejects, recipes and frozen values. Add rubric definitions for shot size/angle/composition; camera versus subject motion; lighting appearance; color/look; focus/depth cues; cut/transition types; pacing; subtitle design; VFX; music/mixing; and sound-image timing. Each annotation retains exact event/shot/region anchors, uncertain boundaries, sampling coverage, evidence and outcome-blinding/review provenance.

Begin with human-reviewed imports and a small useful recipe set: shot-duration distribution and pacing change, angle/shot-size sequence, subtitle occupancy/readability, cut-to-beat proximity and declared technique combinations. Optional detectors need held-out agreement/calibration and abstention; passing synthetic software tests is not detector validation. Retain numeric proxies separately from subjective aesthetic judgments.

Low-resolution frames, sparse sampling and compressed audio cannot reliably recover lens settings, lighting rigs, focus technique, original grades or musical intent. A new task can request bounded native-resolution crops or denser/full-clip timing only with recorded transforms, coordinate maps and resource budgets. Do not infer a camera move from optical flow, call every onset a musical beat, or equate synchronization with narrative reinforcement. Rendering/HDR/color-space limitations accompany measurements. No universal “professional quality” score.

### 2.2 C1-B: publication, packaging and discoverability evidence

Add versioned `PublicationContext`/`MetadataSnapshot` payloads bound to actual post/account revisions: native platform format, language and confidence/source, title/caption/tag/keyword fields, thumbnail variant and asset refs, placement, publication/capture/effective times and field availability. New typed text locators support exact title/description spans; U1 supplies static thumbnail asset/region locators without fake video time. Preserve supplied asset bytes/hashes only when permitted; an expiring URL alone is not reproducible visual evidence.

Preserve original supplied offset and separately supplied IANA creator/audience timezone; handle DST ambiguity explicitly. Unknown timezone remains unknown. Cadence recipes require an observed account window and completeness statement, including whether deleted/omitted posts or other formats may be missing. Selected successful posts cannot establish posting frequency or an optimal schedule.

Search/discoverability questions declare platform/surface, query or keyword source, language/locale, niche, audience and dated trend window. Search positions are personalized observations, not universal ranks. Trend evidence is a dated permitted export, reviewed official source or explicit observation—not a forecast inferred from future data. Hashtags, titles, thumbnails and captions are candidate features, not guaranteed distribution levers.

### 2.3 C1-C: platform-specific distribution research evidence

`PlatformSurfaceDefinition`/`PlatformResearchSpec` declare platform, surface, format, market/language, audience cohort, objective, observation window, applicable source versions, metric definitions and available evidence. Start with separate templates for Instagram Feed/Explore/Reels/Search, TikTok For You/Search and YouTube Home/Suggested/Search/Shorts; a shared validator does not imply shared ranking rules or fit one pooled algorithm. Unknown surface mappings stay unknown.

`PlatformDocumentVersion`/`PlatformStatement` preserve official publisher/URL, retrieved content hash, retrieval time, published/effective dates when known, exact excerpt locator, surface/scope, review and supersession. A documentation statement is **not** a peer-reviewed study finding, observed effect or empirical ranking-weight estimate. R7 uses a domain-neutral question/hypothesis envelope with optional psychological operationalizations; C1 adds platform-specific source/claim types, not an artificial psychological construct for every distribution question.

`DistributionObservation` binds permitted metrics to real subjects, source-defined traffic-surface codes, collection/report windows, eligibility, cohort and organic/paid/collaboration/unknown context. Preserve raw source code plus versioned mapping; unknown is not recommendation traffic. Distinguish impressions, unique reach, views, replays, watch time, retention, shares, saves and denominators. Query aggregates/traffic breakdowns exist only when the source actually supplies them. Privacy suppression, report compatibility, access scope, lag and unavailable fields are explicit capability-manifest entries.

Official statements, local longitudinal associations and creator experiments form separate evidence lanes, joined through scoped claims. Model early-window responses against a later non-overlapping distribution window only when timestamps/availability support that question. Same-window engagement can be an effect of exposure, not an independent cause of it. Hidden satisfaction and eligibility signals remain unobserved; do not infer recommendation penalties from a view drop. Never claim proprietary weight recovery, bypass, guaranteed reach or virality.

### 2.4 C1-D: profiles and attention-to-outcome evidence

`AccountProfileSnapshot` captures exact account revision, handle, display name, bio, profile-photo asset, ordered links/destinations, ordered pinned-post refs, visible CTA/category and platform-specific fields. Distinguish not collected, unavailable, absent, explicitly empty and removed; preserve source/capture/known validity per field. Never infer historical profile exposure from today's snapshot. Profile images use U1 static asset evidence; profile text/link/pin locators bind typed snapshot fields and Unicode spans rather than overloading post-caption locators.

Branding/positioning/content-pillar/consistency assessments use frozen rubrics and a declared post sample/time window. Owner-declared goals/audience/pillars remain distinct from interpretations, with contrary examples and unknowns. Profile-photo analysis concerns visible branding/readability, not sensitive attributes or hidden personality. Links are evidence, not authorization to follow destinations, disclose tracking tokens or access private analytics.

`FunnelDefinition`/`FunnelStageObservation` specify actual source metrics, windows, cohorts, units/uniqueness, denominators and allowed joins. Attention → profile visit → follow and attention/profile → link click → business conversion are possible **branches**, not one mandatory linear path. A valid stage rate needs compatible populations, timing and deduplication; unmatched aggregate totals remain separate summaries. Source-reported attribution retains model/window/credit/dedup evidence and unassigned outcomes. Do not reconstruct individual paths from aggregates or grant causality to last-touch credits.

Extend R5's post/account subject registry only with actual typed profile-version/link/campaign producers and FK bindings; never create a fake post or silently reinterpret its campaign string. Sustained growth needs actual returning-viewer/new-follower retention/cohort or churn measurements where available, not stock changes alone. Business results require authorized conversion/revenue definitions, units/currency, lag and attribution limits; private competitor funnels remain unavailable. A public-only profile audit can still report visible consistency and missing evidence without invented rates.

## 3. Research and recommendation safeguards

R7 keeps the bounded cooking slice, adding only an explicit checklist of production, distribution, publication and profile alternatives/missing context. It need not implement C1 extraction to report an unresolved confounder. Psychological hypotheses are one subtype of a broader research system, not the only acceptable explanation.

R8 extends dependency selection to new context/recipe/document versions **when their C1 producers exist**. A documentation update can request review; it does not prove the platform changed, retroactively replace a historical policy version, or automatically reverse an empirical result.

R9 uses C1 features only after their slice passes tests. Analyze production interactions, separate platform/surface distribution, local-time cadence/packaging/search, and profile/funnel outcomes as separately registered questions. Declare platform, format, niche, language, audience, creator/time/duplicate groups, policy period, maturity and paid exposure. Preserve missing context, correlated features, all attempts, null findings and failed transfer. Cross-platform evidence is not pooled merely because metrics share a name. Recommendations and retrieval never define the analysis population through top-K similarity.

R10 recommendations specify objective/channel, applicable platform/surface/format/niche/language/audience, exact feature/profile variant, supporting and contradicting findings, evidence date, uncertainty, feasibility/cost and a measurable next test. Label craft heuristics, official advice, observational associations and eligible experiments distinctly. Useful outputs can include a shot list/edit timeline, subtitle/music alternatives, title-thumbnail test, schedule comparison or profile/link/pin checklist; unsupported claims say “test first,” not “will grow.”

Experiments declare their real assignment unit: creative variant/post, packaging impression when an authorized native test actually supplies assignment, or account/period for schedule/profile changes. Address creator clustering, carryover, audience spillover, concurrent changes and calendar effects. Sequential uploads and profile pre/post comparisons are not viewer randomization. No external publishing, audience recruitment or spend without separate authorization. An attention lift does not establish a psychological mediator or sustained business value.

## 4. Bounded delivery and verification

The **C1 track is planned after R7, alongside U1/R8 as dependencies permit**, not a new prerequisite for R7 or a single all-at-once delivery. Complete and test each slice before the next; a domain-specific R9 branch requires its respective C1 slice, not every unrelated slice. C1-D can use existing R5 source metrics without C1-C when attribution does not require distribution surfaces. R10 consumes only delivered branches. Existing research-preview gates remain unchanged; a complete four-area capability claim additionally requires the applicable C1/U1/R9/R10 deliveries and empirical validity evidence.

| Slice | Working acceptance demonstration | Required automated and empirical checks |
|---|---|---|
| C1-A | Import reviewed shot/craft annotations for an authorized clip; reproduce a pinned pacing/synchronization/combination feature with exact citations; compare supplied eligible outcomes through existing R2 design or report insufficiency. | V1 compatibility/unknown-label rejection; new schema/locator bounds; camera-vs-subject ambiguity; sparse/occluded/unobserved coverage; timing tolerance; recipe cache/selective invalidation; no-provider reload; held-out annotation agreement before accuracy claims. |
| C1-B | Import dated packaging/language/timezone revisions and a completeness-qualified account window; compute a local schedule/cadence feature; cite title/thumbnail revisions and label search/distribution/conversion objectives separately. | UTC/original-offset preservation; IANA DST gaps/folds; missing zones; omitted-post windows; Unicode title spans; thumbnail asset hash/variant/placement; no backdated metadata or future trends; v1 import preservation. Static visual lane requires U1. |
| C1-C | Import reviewed official statements and authorized source-surface metric windows; reproduce distinct platform/surface research manifests and an early-response/later-distribution descriptive comparison or honest refusal. | Surface/source mapping; unknown traffic; platform/metric/window mismatch; paid/organic separation; document revision/availability and exact excerpts; inaccessible/private/suppressed metrics; lag; leakage/feedback fixture; restart/memory/withdrawal; no-weight/virality claim gates. |
| C1-D | Compare two dated public profile snapshots with typed evidence; import compatible owner-authorized funnel stages and report permitted rates or incompatibility; retain source-reported/unassigned conversion credit and growth definitions. | Field-presence/order/validity; exact bio/photo/link/pin locators; broken ownership; no historical exposure guess; incompatible cohorts/uniqueness/windows; repeated/overlapping credits; branching funnel; missing private data; no individual journey or nearest-post attribution; sensitive-data/erasure checks. Static visual lane requires U1. |

All slices require real CLI/service round trips, deterministic import idempotency, new-process reload, artifact/reference/foreign-key verification, frozen report reproduction and erasure propagation through FTS/Qdrant/graph where relevant. No statistical significance fixture substitutes for adequate independent creators, representative source coverage or external replication. Use the existing embedding spaces and document-family registration; add canonical builders only when writers exist, not one vector collection or graph per capability.

## 5. Official platform grounding and access limits

Sources checked 2026-11-05. Published dates below are not inferred effective dates. Mutable help pages must be captured/versioned by C1-C before operational research relies on them; this Markdown audit is not that runtime corpus. The templates and safeguards above are **design inferences from these sources**, not statements that SocialDNA already implements them.

- **Instagram:** Meta describes multiple ranking systems and predictions across connected and recommended content. Its June 2023 explanation supports separate surface models, not universal current ranking weights. Treat it as a dated source and recheck applicable current guidance during delivery. [Meta: How AI ranks content on Facebook and Instagram](https://about.fb.com/news/2023/06/how-ai-ranks-content-on-facebook-and-instagram/).
- **TikTok:** Official help distinguishes For You recommendation factors from Search, where query/content matching has its own role; factor importance can change. Do not transfer a For You hypothesis to Search without evidence. [TikTok: How content is recommended](https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content).
- **YouTube:** Official help distinguishes Home, Up Next and Shorts and describes surface-dependent signals, including satisfaction information. This justifies scoped templates rather than a shared platform ranking score. [YouTube: How recommendations work](https://support.google.com/youtube/answer/16089387?hl=en).
- **Publishing/search:** YouTube discusses title/description/content relevance for Search, limits the role of tags, and does not identify publish time as a general long-term performance lever. This is platform-specific guidance, not evidence for a universal best posting hour. [YouTube performance FAQ](https://support.google.com/youtube/answer/141805?hl=en).
- **Analytics access:** YouTube defines report-specific dimensions, including traffic sources; their availability/compatibility must be validated for the authorized report, not assumed across all APIs. [YouTube Analytics dimensions](https://developers.google.com/youtube/analytics/dimensions).
- **Public fields are not private funnels:** TikTok's Video Object documents basic content/count fields and a time-limited cover-image URL. It does not by itself supply owner retention or conversion journeys. Capture permitted assets explicitly and verify richer access separately. [TikTok Video Object](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object).

The Meta developer Insights page could not be retrieved through the research tool in this audit; no current field/scopes guarantee is made from it. All future adapters must verify then-current official permissions, account eligibility, supported fields, pagination, quotas, lag, retention and terms. Authorized exports/manual reviewed imports remain the required path; API connectors are optional. No unrestricted crawling, access bypass, private competitor analytics, user-level tracking reconstruction or guaranteed complete platform coverage.
