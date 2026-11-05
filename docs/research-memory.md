# Persistent research memory

Implemented in `0.0.10`, SQLite head `0010_memory`. SQLite entities, evidence,
sources and artifacts are authoritative. Search documents, FTS, Qdrant points and
graph rows are derived projections, not new facts or evaluated hypotheses.

## Start without a model

Use the existing import/analyze/review commands first. Only canonical producers
that actually exist are indexed. Exact comment/post spans, transcript/OCR text,
reviewed/proposed creative descriptions, audience annotations/clusters, behavioral
observations and scoped statistical citations retain their original qualifications.
Questions and hypotheses remain registrations, not findings. Bare frames do not
acquire invented image descriptions. Source files and arbitrary author/protocol
metadata are not searched wholesale.

```sh
socialdna --data-dir ./library --offline storage reconcile
socialdna --data-dir ./library --offline query 'finished dish opening'
socialdna --data-dir ./library --offline query 'literal phrase' --mode sql
socialdna --data-dir ./library --offline memory status
```

FTS treats query words as quoted literal tokens joined by OR. It does not execute
user-supplied FTS operators. SQL mode is an escaped literal substring search.
`query` defaults to 10 results, at most 300 scoped candidates, and processes at
most 1,000 canonical changes before searching. Bounds are explicit; a partial
result is not exhaustive coverage. `--candidate-limit` allows 10–5,000 candidates.
`--owner-kind`, `--owner-id`, `--source` and `--family` narrow the SQL scope before
the retrieval candidate budget. `--as-of` selects revisions known at an explicit
timezone-aware cutoff, while current permission/expiry/erasure still applies.
Unknown availability is not backdated. `--revision` explicitly inspects one exact
owner revision; it never overrides withdrawal or erasure.

Every hit returns its owner reference, document revision, representation/chunk
coordinates and resolved canonical citations. Draft records without citations
return their exact entity reference and an empty citation list, not fabricated
support. A chunk's character positions refer to the representation text, **not**
to a video's timeline or a new comment span. Original uncertain anchors, exact
Unicode spans, bins and measurement definitions are obtained through the citations:

```sh
socialdna --data-dir ./library evidence resolve CITATION_ID --revision CITATION_REVISION
socialdna --data-dir ./library query 'opening' --owner-kind creative_event --graph-depth 1
```

Results deduplicate owner revisions and fuse rankings with reciprocal-rank fusion
(`k=60`). Scores are discovery ranks, not probabilities, truth, confidence,
independent observations, effect estimates or comparison populations. Semantic
neighbors can include unrelated eligible records: absence of literal word overlap
does not mean withdrawal failed. Use exact IDs/citations to check withdrawal.

## Qualified, persistent graph

```sh
socialdna --data-dir ./library graph neighbors ENTITY_REVISION --depth 2
socialdna --data-dir ./library graph path ENTITY_REVISION OTHER_REVISION --depth 2
```

SQLite `graph_nodes` identifies exact canonical revisions. `graph_edges` records
registered structural relations: declared references, citations, media/post
context, measured subjects and definitions. Each edge carries its exact owner,
optional evidence revision, canonical field path, claim level and scope revision.
A post/account FK context join pins an account revision already captured when
that post was captured; it never binds an old post to today's edited account row.
Fine-grained media nodes are introduced only for actual cited relationships.

Only a bounded NetworkX `MultiDiGraph` view is loaded, default depth 2 and at most
2,000 nodes / 4,000 edge examinations. `--max-nodes` / `--max-edges` can lower these
bounds; depth cannot exceed 5. Truncation is explicit. Paths are undirected
structural paths within that view, not global shortest paths or causal chains.
Canonical edge owners must be current in the default view; exact referenced
context can be an older revision without silently substituting today's value.
`--historical` permits eligible historical owners; current withdrawal always wins.

Hypotheses are nodes with qualified references, not flattened technique→success
edges. No `causes`, evaluated `supports`, or association edges are synthesized.
R7's [study/assessment/finding producers](psychological-research.md) now register their
qualified builders in the same memory architecture; findings retain scoped prediction
support/contradiction data, not identified psychological mediators. Graph edges remain
structural references to those reified records. A graph path is not independent confirmation.

## Optional prepared embeddings

Install the optional runtime explicitly, normally in an isolated interpreter:

```sh
pip install 'socialdna[embeddings]'
socialdna --data-dir ./library models prepare MODEL_NAME --manifest model-manifest.json --from-dir ./verified-model-files
socialdna --data-dir ./library models status
```

The existing model manifest records local provider `sentence-transformers`,
capability `text_embedding`, exact model/revision/license/languages and **every**
file's checksum/size. This initial adapter accepts only the standard two-module
Transformer + mean-pooling recipe (`modules.json`, `1_Pooling/config.json`),
safe-tensor weights, local tokenizer/config files and no unverified auxiliary
files. Remote/custom module code and pickle weights are refused. Models with a
different module recipe need a separately reviewed adapter, not renamed files.

Provide `space.json` matching the `EmbeddingSpace` schema in
[`domain/memory.py`](../src/socialdna/domain/memory.py). Required fields are
`model_name`, `model_revision`, `manifest_hash`, `license`, `dimensions`,
`max_tokens`, `languages`, and exact installed `runtime_version` (Sentence
Transformers), plus `runtime_dependencies` with exact `torch`, `transformers`,
`tokenizers` and `numpy` versions. `manifest_hash` is SocialDNA's `hash_config` of the parsed model
manifest's JSON-mode model dump, not a hash of its pretty-printed file. Defaults
pin cosine distance, mean pooling, unit normalization, `query: ` / `passage: `
prefixes, `citation-text-v1` and 800-Unicode-character, nonoverlapping chunks.
Prefixes must be set for the actual model; do not assume every model uses E5
prefixes. Any specification change yields a different immutable space ID and
separate physical collection namespace. No model is selected or downloaded by a
query or index maintenance command.

```sh
socialdna --data-dir ./library --offline memory register-space space.json
socialdna --data-dir ./library --offline storage reconcile --space SPACE_ID --vectors
socialdna --data-dir ./library --offline query 'meal preview' --mode hybrid --space SPACE_ID
```

Configure `provider_pythons.text_embedding` in TOML for a separate runtime. Files
and manifest are verified, then inference runs in the existing bounded subprocess
with network denied, `local_files_only=True`, no remote code and safe-tensor-only
loading. Dimensions, finiteness and unit norms are checked before indexing. The
worker refuses token-budget overflow rather than silently truncating a chunk.
Fixed character chunks can overflow for some languages/models; use a compatible
space or a future versioned chunk policy, not silent re-encoding in the same space.

Hybrid falls back to qualified FTS hits and reports partial/unavailable semantic
coverage if weights, runtime or the derived vector index are unavailable. Pure
semantic search returns explicit unavailable/partial, never hash/fake vectors.
Vector points index current revisions only; historical/as-of search uses SQL/FTS.
An empty semantic result or a successfully loaded model is not evidence of
retrieval quality. No pretrained multilingual model/corpus quality target has yet
been accepted by this repository's controlled storage tests.

## Recovery, incremental work and deletion

1. SQL insert triggers append `memory_changes` in the canonical writer's own
   transaction, including withdrawal/tombstone changes. Rollback cannot leave
   phantom indexing work. Existing writers never import a model or depend on Qdrant.
2. A lock-owning reconciler projects a bounded manifest. Document revisions,
   exact evidence bindings, FTS, graph rows, vector desired generations and outbox
   jobs commit together, and only then are their canonical change jobs removed.
3. Native inference and Qdrant I/O happen outside SQL transactions. Up to 32
   eligible texts share an isolated inference invocation to amortize model startup;
   each job is still gated/acknowledged separately. Point UUIDs
   are deterministic per logical chunk and space. The worker checks current
   generation and eligibility before inference and again before writing; SQL
   acknowledgement is compare-and-swap. Jobs remain pending after a crash and
   replay idempotently. The single-directory process lock replaces worker leases;
   no distributed transaction, concurrent writers or message broker is claimed.
4. Search/graph hydration always applies canonical lineage and eligibility, so
   stale queued jobs or stale vector/FTS payloads cannot authorize revoked use.
   Eligibility sweeps and vector repair use persisted keyset cursors, not an
   indefinitely repeated first page. Status reports canonical lag and per-space
   pending/deleted/ready counts independently of write success.

```sh
socialdna --data-dir ./library storage reconcile --limit 1000
socialdna --data-dir ./library storage reconcile --space SPACE_ID --repair --vectors
socialdna --data-dir ./library storage reindex --limit 1000
socialdna --data-dir ./library storage reindex --space SPACE_ID --vectors
socialdna --data-dir ./library storage verify
```

`reindex` starts a full SQL/FTS/graph rebuild from canonical inputs, recreating a
missing FTS table. If its budget is exhausted, continue with **reconcile**, not
another reindex. Rebuild initialization/clearing and enqueueing are atomic; a
partial generation is explicitly labeled. Model changes do not force a rebuild
on basic commands. `--repair` checks acknowledged point identities/generations and
requeues missing or mismatched points, including after a canonical-only restore.
An unreadable Qdrant metadata file may require an operator to preserve/quarantine
that derived directory before recreating it; commands do not delete unknown files
or touch canonical storage to repair an index.

Use the existing `audience redact` preview/confirmation workflow for authorized
audience erasure. Its deny-first journal scrubs affected document revisions and
FTS text (rebuilding surviving FTS segments to remove deleted terms), removes graph relations/nodes, issues dominating vector delete
generations, deletes points and secure-vacuums the dedicated closed Qdrant Local
SQLite files, then completes the active-library erasure journal. A failure leaves
erasure pending and startup retries before exposure. Audience redaction closes a
previously opened application vector client first. SQL canonical tombstones and
the resolver prevent old queued work/rebuilds from restoring text or vectors.

Withdrawals revoke current use but do not alone promise active-byte erasure.
Backups omit Qdrant and model weights; SQLite-backed FTS/documents/graph remain
inside the verified SQLite checkpoint and are subject to the same restore
reconciliation and audience scrub as canonical content. Separate-directory
restores require the latest same-lineage withdrawal/erasure authority. Existing
backup retention/export obligations and external originals remain explicit;
untracked copied files and arbitrary backups are not automatically erased.

## Verification and limits

Automated tests use real SQLite/FTS/Qdrant Local and separate CLI processes, plus
clearly labeled deterministic **test-only** embeddings for replay/space isolation.
They cover rollback, restart, corrections/as-of history, graph qualifications and
bounds, missing index repair, stale generations, withdrawal during inference,
audience erasure and restore/rebuild non-resurrection. Existing audience and
behavioral integration tests also exercise searchable reactions, series/bins and
their graph provenance. Installed wheel/sdist checks exercise public memory commands.

The opt-in `test_real_embeddings.py` needs `SOCIALDNA_TEST_MODEL_LIBRARY` and
`SOCIALDNA_TEST_EMBEDDING_SPACE`; `SOCIALDNA_TEST_EMBEDDING_PYTHON` optionally
selects its prepared interpreter. Without these, it explicitly skips and downloads
nothing. It validates real adapter/index/restart integration, not empirical corpus
relevance, multilingual fairness, annotation quality or psychological inference.
This delivery does not implement literature ingestion, evaluated mechanisms,
automatic discoveries/reevaluation, graph servers or multi-writer indexing.

Implementation references: [Sentence Transformers local loading/encoding](https://sbert.net/docs/package_reference/sentence_transformer/model.html),
[Qdrant Python Local Mode](https://github.com/qdrant/qdrant-client),
and [SQLite FTS5 deletion/rebuild behavior](https://www.sqlite.org/fts5.html).

R8 integration (`0.0.12`): [incremental research](incremental-research.md) adds
current-retrieval freshness gates for stale/superseded assessment-derived documents.
The R6 `memory_changes` queue is still drained; a distinct deduplicated
`research_changes` journal preserves research invalidation history. Index rebuilds
do not constitute new evidence. Existing SQL/FTS/graph/vector hydration gates
exclude obsolete current findings even if an old indexing job finishes late.
Explicit historical retrieval still enforces source eligibility and erasure.
