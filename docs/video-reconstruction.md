# Finished-video reconstruction

Delivered in `0.0.23`, reusing migration `0019_content`. The independently exported
`social-dna-reconstruct` skill composes actual available finished-video evidence.
It does not recover an inaccessible original screenplay or invent missing content.

## Run it

From an existing assisted video analysis:

```sh
socialdna --offline --format json workflow plan --mode reconstruct \
  --from ANALYZED_VIDEO_WORKFLOW_ID --allow-verbatim
socialdna --offline --format json workflow run RECONSTRUCTION_WORKFLOW_ID
socialdna --offline workflow report RECONSTRUCTION_WORKFLOW_ID \
  --format markdown --output script.md
```

Or supply the authorized original directly; the engine performs the existing
deterministic analysis first:

```sh
socialdna --offline --format json workflow plan --mode reconstruct \
  --url https://www.youtube.com/shorts/EaYRjrQuxEk \
  --media /absolute/path/owned-video.mp4 \
  --permission-basis creator_owned_original \
  --subtitles /absolute/path/owned.srt --allow-verbatim
```

The same assisted route recognizes Instagram/TikTok post URLs. This does **not**
fetch their media or supply three live platform connectors. No key, timer, downloader,
remote model transfer or model preparation occurs. A key/public URL is not media
or reproduction permission. `authorized_analysis` is available for a genuinely
authorized original. These are user declarations, not verified ownership/licenses.

`--allow-verbatim` declares permitted reproduction of source words. Only use it when
that authority actually exists. Without it the report is structural-only and partial,
with text and word arrays withheld. Do not use another report to circumvent this.
Independently supplied caption tracks also need permission.

## Outputs and selection

- `--reconstruction-output transcript`: distinct speech and supplied-subtitle lanes.
- `--reconstruction-output audiovisual-script`: ordered text/shot/frame/measurement/
  selected reviewed-cue rows.
- `--reconstruction-output combined`: both views over the same actual cue rows (default).

`--track ID` selects actual text tracks, repeatable; default selects available tracks.
Find IDs in the engine's saved analysis timeline/reconstruction `source_tracks`.
Unknown/cross-run IDs fail. Explicit OCR selection requires audiovisual output;
visible text is not speech. `--start-ms`/`--end-ms` select overlapping source spans
in the original presentation clock, not time in a transcoded preview. Whole native
segments and their words remain intact, including null word times; text is not
trimmed with fabricated word alignment. The requested window and original spans
are both recorded.

`--creative-revision REVISION_ID` explicitly selects an existing reviewed creative
annotation-set revision for audiovisual output. Proposed/disputed events are omitted,
not promoted. Exact/nominal times and uncertainty anchors remain distinguishable.
Human review is imported evidence, not an action the reconstruction engine pretends
to have performed. Unavailable observations remain unavailable.

For direct media only, explicit `--transcribe`, `--ocr` or `--align` requests existing
prepared local providers. Otherwise no model runs. Missing providers yield partial
results, not downloads. Reconstructing saved evidence never invokes providers.
To add a new track, make a new permitted analysis and select its saved workflow.

## What the report means

Source subtitles are not independently verified speech or guaranteed visible text.
ASR/alignment/OCR and their confidences are model estimates. Unknown word timings
are null, languages stay original, and no translation or speaker identity is invented.
Overlapping differing selected speech/subtitle tracks are candidate disagreements,
not adjudicated transcription errors; screening caps at 100 differences or 10,000
overlapping candidate pairs and reports truncation.

No audio stream is a captured probe fact. Missing ASR, empty speech estimates, music,
instrumental/tone audio or failed detection are **not** proof of silence. A no-audio
clip has no invented dialogue. Supplied captions may still exist as separately labeled
text. Missing speech can leave a useful caption/structure report partial.

AV rows cite detected shot intervals, sampled evidence frames, color/motion/audio
proxies and explicitly selected reviewed cues. This is not exhaustive semantic scene
understanding, named transitions, camera settings, off-screen action, music identity,
intent or an explanation of virality. Original adaptations belong to a separate task.
Unsupported custom goals remain partial instead of being silently treated as achieved.

## Persistence, recovery and validation

The plan pins its saved input revision. A typed `video_reconstruction` producer binds
actual media/run/checkpoint revisions, selected track/task/segment/word snapshot
hashes and exact native segment/region citations. Track snapshots are not a claim
that legacy text-track/word rows have independent canonical revision identities.
Use `skill schema video_reconstruction` for the full engine-generated contract.

JSON/escaped Markdown are managed checksum-verified artifacts. Every read rechecks
eligibility. A new selection/window/output creates a new composition while preserving
the prior output and reusing primitive analyses. Interrupted composition resumes;
an intermediate analysis report cannot masquerade as the missing finished script.
Exports use exclusive creation and never overwrite an existing file.

The existing SQLite content projections, `ContentLocator`, erasure journal and
withdrawal-authority restore cover scripts and eligible indexed derivatives. Parent
source dependency is intentionally conservative; source withdrawal can withhold the
whole descendant report, not merely a selected row. No new vector collection, graph
backend or database server is required. Indexing remains explicit. External exported
copies and unmanaged originals remain the operator's responsibility.

Automated fixtures exercise real decoding/caption processing and controlled provider
contracts, not real ASR/OCR accuracy, human review accuracy, live URL access or actual
host skill selection. Those acceptance gates remain open and separately labeled.
