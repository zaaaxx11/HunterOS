# Meta-ai muse-spark-1.2-contributor — prefix + dotted config set pitfalls 2026-08-13

**Live model list:** `GET https://api.meta.ai/v1/models` → `["muse-spark-1.2-contributor","muse-spark-1.2","muse-spark-1.1"]` (no `Muse/` prefix)

**Prefix pitfall:** `POST /chat/completions {model:"Muse/muse-spark-1.2-contributor"}` → `404 model_not_found`; `{model:"muse-spark-1.2-contributor"}` → `200`. Same for `muse-spark-1.2`. Bare id only.

**Dotted config set pitfall:** `hermes config set "providers.meta-ai.models.Muse/muse-spark-1.2-contributor" '{}'` splits on `.` and creates `Muse/muse-spark-1: {2-contributor: '{}'}` — visible in `read_file` as broken `Muse/muse-spark-1` key (similar class to `default_model    default_model` dup). Never use `hermes config set` for model ids containing `.` or `/`.

**Fix:** `python3 + yaml.safe_load → del broken key if exists → c['providers']['meta-ai']['models']['muse-spark-1.2-contributor']={} → c['providers']['meta-ai']['model']='muse-spark-1.2-contributor' → c['providers']['meta-ai']['default_model']='muse-spark-1.2-contributor' → c['model']['default']='muse-spark-1.2-contributor' → yaml.dump`. Verify `GET /v1/models` then `POST {model:"muse-spark-1.2-contributor", max_tokens:10}` → 200 (may return `content:null` when `max_tokens=10` due to reasoning_tokens; use `max_tokens>=50` for real content).

**Cron drift fix:** `hermes cron edit --help` has no `--provider/--model`; `hermes cron update` → `invalid choice`. Use tool `default.cronjob action=update job_id=6970adc77db3 model={"model":"muse-spark-1.2-contributor","provider":"meta-ai"}`. Sets `provider_snapshot=meta-ai, model_snapshot=muse-spark-1.2-contributor`. Direct `jobs.json` edit of `provider_snapshot/model_snapshot` also works but tool is canonical. Next tick `muse-spark-1.2-contributor -> 200 OK`, previously blocked `RuntimeError: Skipped to prevent unintended spend: global inference config drifted since this job was created (model 'moonshotai/kimi-k3' -> 'deepseek-v4-pro'), and this job is unpinned`.

**User preference:** "jangan apiku, yang meta aja provider nya" — meta-ai is sole inference provider for cron LLM audit per user; do not reintroduce APIKU for LLM calls.
