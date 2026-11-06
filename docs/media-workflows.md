# Assisted post-media analysis

Delivered in `0.0.22`, migration `0019_content`. Associate one recognized YouTube,
Instagram or TikTok post URL with independently authorized local originals. The
URL identifies the post; SocialDNA does not download its media or verify ownership.
No API key, systemd timer or model is required for this assisted lane.

```sh
socialdna --offline --format json workflow plan --mode analyze \
  --url https://www.youtube.com/shorts/EaYRjrQuxEk \
  --media /absolute/path/owned-video.mp4 \
  --permission-basis creator_owned_original --subtitles /absolute/path/owned.srt
socialdna --offline --format json workflow run WORKFLOW_ID
socialdna --offline workflow report WORKFLOW_ID --format markdown --output report.md
```

For a photo use the same command with an image file. Repeat `--media` in slide order
for a carousel (maximum 20 items). Duplicate slides preserve their positions; mixed
video slides remain explicitly unavailable in the existing static-carousel analyzer.
For legitimately authorized third-party originals declare `authorized_analysis`.
These are user declarations, not a verified license or proof of account ownership.

Default video processing measures scenes, sampled frames, visual/audio proxies and
supplied SRT/VTT text. Supplied captions are not independently verified speech.
`--transcribe`, `--ocr` and `--align` opt into already prepared local providers;
missing providers remain partial. No weights are downloaded or remote model transfer
attempted. ASR/alignment/subtitles require one video. `--depth` and `--max-frames`
select existing video budgets. Normal image byte/pixel and combined media byte limits
apply. All measurements retain the existing analyzers' limitations.

Plan pins resolved paths and byte hashes; run rechecks originals and subtitles.
Keep files available at those paths. `--copy-media` explicitly retains managed
originals. A different binding for the same post requires `--replace-media`;
historical reports and source-qualified link history remain separate.

The report binds actual media/run revisions and native timestamp/region evidence.
It labels `media-enriched-assisted` coverage and distinguishes missing modalities,
sampled measurements and uncertain model outputs. It does not prove creative intent,
psychology, performance effects or why a post went viral. Unsupported deeper goals
remain partial with next actions. `--scope profile` is not implemented.

## Persistence and safety

SQLite/artifacts remain authoritative. `ContentLocator` references canonical
`content_binding`, `content_run` and `content_report` revisions; two small immutable
projection tables bind real workflow/run/citation foreign keys. No new Qdrant
collection or NetworkX backend is introduced. Research indexing remains explicit,
not an automatic side effect of describing a post.

The independent original-media source does not copy API counts/title/ownership/time
or treat a public URL/API key as download permission. Unknown owners/publication times
stay null. Ordered carousels use an independently sourced local analysis manifest,
not a cloned API snapshot. Later authorized imports can fill genuinely unknown owners.

Video run checkpoints preserve the exact interrupted run; completed matching tasks
reuse eligible caches. Frozen JSON/Markdown bytes verify checksums and dependency
eligibility on each read. Withdrawal withholds reports. Confirmed source erasure uses
the existing deny-first journal to scrub bound text/cached results and managed report
artifacts; recovery/restore must respect withdrawal authority. External exports and
unmanaged originals remain the operator's responsibility.

## Not shipped

No cold URL-only media fetch, scraper/downloader fallback, account enumeration or
profile audit. The official [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies)
remain separate from rights to original media; official
[caption downloading](https://developers.google.com/youtube/data/reference/rest/v3/captions/download)
also has its own authorization requirements. Prepared-model accuracy and actual
host skill selection are separate acceptance gates, not inferred from synthetic
media fixtures or portable bundle export checks.
