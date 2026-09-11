# trias-lab validation comment blocks — github-secret-hunt

> Cut verbatim from `soul/skills/web2/github-secret-hunt/SKILL.md` during the
> 2026-09-07 skills cull (S2b-1): target-specific validation annotations from
> the trias-lab 2026-08-17 session. The generic pattern library and the
> IP-with-context technique remain in the skill body.

# IP-with-context extraction (validated trias-lab 2026-08-17): capture the ~60 chars
# around each IP to identify what it documents. Config files often hardcode complete
# deployment topology (MySQL @192.168.1.210:3306, geth @192.168.1.175:8545, private
# Docker registry @172.31.23.215:5000, k8s master @192.168.50.128:6443, etc.):
IP_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::(\d+))?\b')

# Always scan committed `.coveralls.yml`, `.travis.yml`, `conf/*.json`, `appsettings.json`,
# and `src/environments/*.ts` (frontend env files leak live backend hostnames — the
# trias-lab wallet repo's prod.ts exposed `tbws.trias.one:3232` as the BWS backend).
#
# **Frontend env files as live-hostname yield (validated trias-lab 2026-08-17):**
# `src/environments/prod.ts` in Angular/Copay wallets contains rate API URLs pointing
# to the production backend — `http://tbws.trias.one:3232/bws/api/v1/rates/eth`. Even
# when the domain is NXDOMAIN, this reveals: (1) the intended hostname, (2) the port,
# (3) the API path pattern, (4) protlocation (http vs https = no TLS). Always check
# ALL env files: environment.ts, environment.prod.ts, prod.ts, dev.ts, schema.ts.
#
# **Deploy scripts as SSH user/key leak (validated trias-lab StreamNet 2026-08-17):**
# `scripts/iota_deploy/iota_deploy_prod.py` contained SSH usernames + hardcoded IPs:
#   - `stplaydog@192.144.152.140` (no key path = password auth)
#   - `stplaydog@52.221.236.50` (no key path = password auth)
#   - `ubuntu@54.179.133.32` with `-i dag.pem` (key file = key likely in deploy env)
# The key file `dag.pem` is NOT committed, but the USERNAME + IP is — enough for
# targeted SSH brute-force or social engineering. Always grep deploy scripts for:
# `pssh -H`, `sshpass`, `ssh -i`, `StrictHostKeyChecking=no`, `scp`, `rsync`.
# These scripts also leak: IRI API ports (13700), P2P ports (13600), Docker image names.
