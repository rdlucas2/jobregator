# Running Laya locally

[Laya](https://laya-ai.com) is an open-source decision model that serves the same
`POST /v1/systemone` protocol as TypeSafe's hosted Jev, so jobregator can use it
for the bounded questions (fit score, experience level, remote policy, job type)
with no cloud key. It replaces only the **typed decisions**. Text enrichment
(skills, summary) still needs Claude, so `ANTHROPIC_API_KEY` stays set.

The app runs in Docker Compose; Laya runs directly on the host (here: Windows 11)
and the worker reaches it over `host.docker.internal`. This keeps Laya out of a
container and avoids GPU passthrough entirely. CPU inference is enough: one
forward pass per listing, with all questions batched into one request.

## 1. Install (PowerShell)

Needs Python 3.10+.

```powershell
python -m venv laya-venv
.\laya-venv\Scripts\Activate.ps1
pip install "laya[serve]"
```

The first run downloads the weights (about 2.3 GB for the English checkpoint).

## 2. Start the server

```powershell
$env:LAYA_HOST    = "0.0.0.0"     # containers reach the host over its network address
$env:LAYA_PORT    = "8000"
$env:LAYA_DEVICE  = "cpu"
$env:LAYA_THREADS = "8"           # physical cores, not logical: oversubscribing is a big slowdown
$env:LAYA_MODELS  = "english"     # load one checkpoint, not all three (saves RAM and startup time)
laya-serve
```

Startup takes roughly a minute while the model loads. Windows may prompt to
allow Python through the firewall; allow it on private networks, or Docker will
not be able to connect.

Optional: set `$env:LAYA_API_KEY` to require `Authorization: Bearer <key>`, and
set the same value as `LAYA_API_KEY` for the worker.

## 3. Smoke test the server

```powershell
curl.exe -s localhost:8000/health

curl.exe -s localhost:8000/v1/systemone -H "content-type: application/json" -d '{\"state\": {\"body\": \"Fully remote role, W2, Terraform and Kubernetes\"}, \"questions\": {\"policy\": {\"type\": \"choice\", \"instructions\": \"Where is the work performed?\", \"criteria\": {\"remote\": \"Fully remote\", \"onsite\": \"In an office\"}}}}'
```

You should get an `answers.policy.choice` of `remote`, with probabilities.

## 4. Point jobregator at it

In `.env`:

```
ENRICHMENT_TYPED_PROVIDER=laya
LAYA_BASE_URL=http://host.docker.internal:8000
LAYA_MODEL=laya
ANTHROPIC_API_KEY=...   # still required for text enrichment
```

Then `make fresh`, which wipes the database so every listing is enriched again.
The provider is built lazily, so the worker log prints
`typed decision provider: laya (laya)` when it enriches its first listing, not
at startup. `docker-compose.yaml` already maps `host.docker.internal` to the
host, so this works on Docker Desktop (Windows/WSL2) and plain Linux alike, and
also when `laya-serve` runs inside WSL rather than on Windows.

There is no fallback: if Laya is unreachable, enrichment fails and the listing
is stored raw (`enriched_json` is null). It is not retried, because the
duplicate check skips it next time. Fix the server, then `make fresh`.

`LAYA_MODEL` is informational: Laya auto-routes by script and language when it
does not recognise the name. Stored decisions are labelled `provider: laya`, so
you can compare them with Claude's for the same listings.

## Notes

- **Not validated against a live server yet.** The provider is unit-tested
  against the SDK's response types, and the wire format was checked against
  `laya-serve`'s source. Run the smoke test above, then a real listing, before
  trusting scores.
- **Kubernetes:** `helm/envs/common/worker-values.yaml` exposes `LAYA_BASE_URL`
  and `LAYA_MODEL`, but the cluster has no Laya server. Set a reachable URL
  before selecting `laya` there; the default stays `claude`.
- **GPU:** not used. The RX 6800 has no practical PyTorch path on Windows, and
  CPU is fast enough for this workload.
