# trias-lab GitHub Deep Scan — Case Study (2026-08-17)

## Context
Target: `github.com/trias-lab` — wallet/explorer backend deployment endpoints, leaked secrets, and infrastructure topology recon. Account is a **GitHub user account, not an org** — the `/orgs/trias-lab/repos` endpoint returned 404; switching to `/users/trias-lab/repos?type=all` recovered all 20 repos.

## Approach (one-pass)
Ran a single Python stdlib-only script (`scripts/org-deep-config-scanner.py`) that:
1. Enumerated repos from both `/orgs/` and `/users/` endpoints, kept whichever returned non-empty.
2. For each repo, fetched the recursive git tree (`git/trees/:branch?recursive=1`) and filtered for deploy/config/docker/nginx/env/k8s/CI file paths.
3. For each matching blob, fetched contents from `raw.githubusercontent.com` and ran the secret regex set + IP-with-context extraction + K8s bootstrap token matcher.
4. Saved structured findings + a per-file content dump as JSON for later forensics.

20 repos → 20 recursive trees → 340+ files fetched and scanned in one pass.

## Key Findings

### Live deployment endpoints (by hostname)
| Endpoint | Source | Role |
|---|---|---|
| `tbws.trias.one:3232` | `wallet/src/environments/prod.ts` | Bitcore Wallet Service backend (`/bws/api/v1/rates/eth\|try`) — production |
| `https://wallet.trias.one/webwallet/` | `web-wallet/dev/README.md` | Web wallet frontend deployment |
| `octahub.8lab.cn:5000` | `upgrader/docker.service` | Internal Docker insecure-registry |
| `trias.one` / `contact@trias.one` | multiple repos | Primary corporate domain |

### Internal IPs hardcoded in config files (wallet + explorer backend)
- `192.168.1.210:3306` — MySQL server, user `8lab`, password `<REDACTED>`, databases `trias_string_9981` (explorer) + `trias_wallet` (wallet). Source: `trias-explorer/conf/conf.json` + `web-wallet/conf/conf.json`.
- `192.168.1.175:8545` — Ethereum/Trias geth JSON-RPC node (also `try.url` in `bitcore-wallet-service/config.js`).
- `192.168.1.206:9981` — UTXO/Bitcoin-like wallet RPC service.
- `192.168.1.125` — Internal octa-apt binary package server (HTTP, no auth) — `upgrader/doc/script/install-trias.conf`.
- `192.168.50.128/129/130:6443` — K8s cluster master + 2 worker nodes (Ubuntu 16.04). Bootstrap token `<REDACTED-K8S-BOOTSTRAP-TOKEN>` leaked in `StreamNet/document/iota_deploy/k8s-deploy-info.md`.

### Cloud deployment IPs (StreamNet IRI cluster)
- `52.221.236.50:14700` — production IRI deploy master, AWS Singapore (`iota_deploy_prod.py`).
- `54.179.133.32` — test/staging IRI master, AWS Singapore (`iota_deploy.py`).
- `140.143.187.24` — StreamNet OPS deployment server, Tencent Cloud (`front_end/web/src/common/config/config.js`).
- `192.144.152.140:5001` — StreamNet deployment server, Tencent Cloud.
- `172.21.0.30:14700` — TEE (Trusted Execution Environment) IRI node (`scripts/tee/config.yaml`).

### Other secrets
- **Django SECRET_KEY (explorer):** `<REDACTED-DJANGO-SECRET>` (`trias-explorer/explorer_ui/settings.py`) — session forgery, CSRF bypass.
- **Django SECRET_KEY (wallet):** `<REDACTED-DJANGO-SECRET>` (`web-wallet/etherwallet/settings.py`).
- **Empty AES passphrase:** `private_key_encrypt_pass=""` in `web-wallet/conf/conf.json` — user private keys are effectively unencrypted at rest.
- **Coveralls.io API tokens** in committed `.coveralls.yml` files across three repos (bitcore-lib, bitcore-wallet-client, bitcore-wallet-service).
- **Travis CI encrypted release-deploy keys** in `web-wallet/.travis.yml` + `StreamNet/.travis.yml`.
- **SSH deploy key:** `~/gitlocal/dag.pem` referenced as identity file in `StreamNet/scripts/iota_deploy/iota_deploy.py` (used with `pssh` for cluster deploy).
- **Docker insecure-registry:** `INSECURE_REGISTRY=octahub.8lab.cn:5000` in `upgrader/docker.service` — plaintext HTTP registry.
- **stplaydog Linux sudo password:** `stplaydog` (hardcoded in `StreamNet/scripts/iota_deploy/iota_deploy_prod.py` as `echo stplaydog | sudo -S`).
- **Conflux mainnet bootnodes:** 30+ cfxnode IP:port pairs with full public keys in `conflux-rust/run/default.toml` (AWS + Azure, all port 32323) — full mainnet peer topology.
- **Internal K8s YAML** in `StreamNet/document/iota_deploy/k8s-create-cluster-yaml.md` reveals the private Docker registry `172.31.23.215:5000` and external IP `172.31.28.12` for the `trias-cli-service` Service.

## File inventory highlights (most informative files)
- `trias-explorer/conf/conf.json` — full MySQL config in plaintext
- `trias-explorer/explorer_ui/settings.py` — Django SECRET_KEY + DB config + log path `/var/log/trias/explorer.log`
- `web-wallet/conf/conf.json` — utxo_url + eth_ip + mysql creds
- `web-wallet/etherwallet/settings.py` — Django SECRET_KEY + DB
- `web-wallet/Dockerfile` — nginx SSL self-signed cert pipeline
- `web-wallet/README.md` — live URL `https://wallet.trias.one/webwallet/`
- `wallet/src/environments/prod.ts` — **live backend hostname `tbws.trias.one:3232`** + BitPay rates API
- `bitcore-wallet-service/config.js` — Mongo `mongodb://localhost:27017/bws`, `try.url='http://192.168.1.175:8545'`, FCM placeholder, EtherScanApiKey placeholder
- `bitcore-wallet-service/start.sh` — launches locker, messagebroker, bcmonitor, bws.js on port 3232
- `StreamNet/docker/ssl/docker-compose.yml` + `docker/ssl/nginx-image/nginx.conf` — nginx + letsencrypt + iri stack
- `StreamNet/scripts/iota_deploy/iota_deploy.py` + `.py` prod variant — full cluster topology
- `StreamNet/scripts/tee/config.yaml` — TEE IRI endpoint + IOTA seed addr
- `StreamNet/scripts/front_end/web/src/common/config/config.js` — inner dashboard config with hardcoded OPS server + deploy server URLs
- `StreamNet/document/iota_deploy/k8s-deploy-info.md` — K8s master + token + worker join recipe
- `StreamNet/document/iota_deploy/k8s-create-cluster-yaml.md` — Deployment + Service YAML with Docker registry
- `StreamNet/.travis.yml` — Travis CI release deploy config with encrypted signing key
- `conflux-rust/run/default.toml` — full bootnode pubkey list for Conflux mainnet
- `upgrader/doc/script/install-trias.conf` — internal apt server IP
- `upgrader/doc/script/install.sh` — Trias binary installer (apt + IMA/TPM setup + systemd)
- `upgrader/doc/script/trias/.ethermint/tendermint/config.toml` — Tendermint P2P 46656, RPC 46657
- `tvm-light/config.yml` — Hyperledger Fabric orderer:7050 + IPFS gateway + port 8088
- `tvm-light/docker-compose-cli.yaml` — Fabric orderer/peer/cli compose

## Lessons Learned
1. **`/orgs/` vs `/users/` 404 trap** — the first instinct (`/orgs/trias-lab/repos`) silently returned 404 because the account is a GitHub user, not an organization. Add the `/users/` fallback as the default second probe.
2. **README + frontend env files are the live-hostname goldmine.** The single most valuable file was `wallet/src/environments/prod.ts`, which exposed `tbws.trias.one:3232` as the production wallet backend. It is not a "secret" file and is ignored by most secret scanners.
3. **Deploy markdown leaks Infra-as-Code.** `StreamNet/document/iota_deploy/k8s-deploy-info.md` is a developer-facing tutorial that incidentally contained the live kubeadm bootstrap token and the internal K8s API server address. Filter for `.md` paths that live under `document/`, `deploy/`, `infra/`, `ops/` — not just `docs/`.
4. **Plaintext `conf.json` is more dangerous than `.env.example`.** Both `trias-explorer/conf/conf.json` and `web-wallet/conf/conf.json` are loaded by Django `settings.py` via `open(CONF_JSON)`. They contained the production MySQL credentials `8lab:<REDACTED>`. Frontend wallet code shipped this template committed to `master`.
5. **Empty passphrases count as findings.** `private_key_encrypt_pass=""` is not a missing value — it's an explicit empty string the wallet honors. Flag empty AES passphrases as a dedicated pattern.
6. **Coveralls tokens are still leaked in 2026.** Three repos had committed `.coveralls.yml` with plaintext `token:` values. Tokenless secret scanners miss these.
7. **Self-signed SSL in `Dockerfile` exposes the openssl pass phrase.** `openssl genrsa -des3 -passout pass:x` in `web-wallet/Dockerfile` reveals that the private key passphrase is `x` — minor, but emblematic of水利工程-style fail-open security.
8. **Tree-walk > Code Search.** One tree-walk pass against 20 repos recovered more findings than the Code Search API would have, because Code Search only indexes HEAD content and is rate-limited even with auth. Tree-walk is also resilient to the recent Code Search 401-unauth change.
9. **Don't filter IPs as "version numbers."** The naive IP filter excluded `1.4.2.3` and `1.4.2.4` as version numbers but they turned out to be IRI jar versions — correctly filtered out. The trias cluster did leak several real internal IPs (`192.168.1.x`) that a stricter filter would have kept.

## Follow-up Actions
- Probe DNS resolution for `tbws.trias.one`, `wallet.trias.one`, and `octahub.8lab.cn` and live-test the BWS API on `:3232/bws/api`.
- Cross-reference the leaked K8s token (`<REDACTED-K8S-BOOTSTRAP-TOKEN>`) against the `192.168.50.x` cluster if reachable.
- Charge historical git commits for the `conf.json` files to look for stronger credentials that may have been rotated out (`/repos/:owner/:repo/commits?path=conf/conf.json` → per-SHA raw fetch).
- Run `trufflehog` across the entire org for git-history-only secret leaks that HEAD scan missed.

## Inventory of session artifacts (kept in /tmp)
- `/tmp/trias_repos.json` — enumerated repo metadata (20 repos).
- `/tmp/trias_deep_scan.json` — structured findings (IPs/secrets/env vars) from the deep scan.
- `/tmp/trias_all_files.json` — full contents of all ~340 scanned config files (cap 50K chars per file).
- `/tmp/key_config_files.json` — hand-picked critical config files (trias-explorer, web-wallet, bitcore-wallet-service, StreamNet, conflux-rust, upgrader, tvm-light).
- `/tmp/trias_lab_deep_scan_report.txt` — 388-line final summary report with categorization.
- `/tmp/scan_trias.py`, `/tmp/scan_trias2.py`, `/tmp/scan_trias3.py`, `/tmp/fetch_key_files.py`, `/tmp/fetch_streamnet.py`, `/tmp/final_report.py` — scan scripts used during the session.
