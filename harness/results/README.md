# Run files

One JSON file per run: `<model>__<context>__<pattern>__terragoat_mut[__think]__<file>__r<repetition>.json`. 1,080 files: 36 configurations x 6 files x 5 repetitions. A run is one review of one file; a single-call run makes one API call, critic two, debate three, chunked one per chunk.

| Field | Meaning |
|---|---|
| `run_id` | the file name without `.json` |
| `model`, `context`, `pattern`, `corpus`, `file`, `repetition`, `reasoning` | the configuration |
| `resolved_model` | the model identifier the API returned (`deepseek-flash` for every DeepSeek run) |
| `timestamp` | UTC time the run finished |
| `provenance` | hashes of `prompts.py`, `schema.py`, `agents/`, the guidance text, and (from 2026-09-29) `providers.py`; `chunk_chars` |
| `findings` | the claims the model returned, as parsed from the tool call: `resource`, `issue_category`, `description`, `severity`, optional `cwe` and `confidence` |
| `raw_text` | the tool-call payload or text the model returned, before parsing |
| `schema_problems` | schema validation messages, if any |
| `n_calls`, `steps` | API calls made and, for multi-call patterns, per-call tokens, latency, findings count, and cost |
| `chunks` | number of chunks (chunked pattern only) |
| `input_tokens`, `output_tokens`, `latency_s`, `cost_usd` | summed over the run's calls; cost at August 2026 list prices |
| `attempts` | provider attempts for the call (transport-error retries only) |
| `thinking_chars` | length of returned reasoning text where the API exposes it |
| `error` | empty for every reported run |
| `temperature` | `null`: never set; each provider's default applies |
| `measurement_host` | where the harness ran (`linux/vm`, one cloud container) |

Scoring a run: `harness/score.py` (`score_run`) matches `findings` against `data/ground_truth_mut.json` for the run's file with `harness/match.py`. `harness/scored/<configuration>.json` holds the per-run counts and pooled metrics; `harness/rescore.py` regenerates them.
