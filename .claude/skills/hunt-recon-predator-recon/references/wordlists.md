# WORDLISTS — Predator Recon
# Curated for Calculus efficiency: High signal, low noise

---

## SUBDOMAIN ENUMERATION

### Assetnote (Best-in-class, updated daily)
```bash
# Best DNS (2.5M+ subdomains)
wget https://wordlists.assetnote.io/best-dns-wordlist.txt -O wordlists/best-dns-wordlist.txt

# Subdomains only (1M+)
wget https://wordlists.assetnote.io/subdomains.txt -O wordlists/subdomains.txt

# All combined (huge)
wget https://wordlists.assetnote.io/all.txt -O wordlists/assetnote-all.txt
```

### SecLists (Daniel Miessler)
```bash
git clone https://github.com/danielmiessler/SecLists.git wordlists/SecLists

# Key files:
wordlists/SecLists/Discovery/DNS/subdomains-top1million-5000.txt
wordlists/SecLists/Discovery/DNS/subdomains-top1million-20000.txt
wordlists/SecLists/Discovery/DNS/dns-Jhaddix.txt
wordlists/SecLists/Discovery/DNS/namelist.txt
```

### Specialized
```bash
# Cloud-specific
wget https://raw.githubusercontent.com/rbsec/dnscan/master/subdomains-10000.txt

# Tech-specific
wordlists/SecLists/Discovery/DNS/subdomains-top1million-110000.txt
```

---

## PARAMETER MINING

### SecLists
```bash
wordlists/SecLists/Discovery/Web-Content/burp-parameter-names.txt
wordlists/SecLists/Discovery/Web-Content/burp-parameter-names.txt
wordlists/SecLists/Discovery/Web-Content/common.txt
```

### Arjun (Auto-discovery)
```bash
arjun -u https://target.com/api/endpoint -w wordlists/param-names.txt
```

### Custom High-Value (DeFi/Web3)
```text
# Auth
token,access_token,refresh_token,jwt,bearer,authorization
api_key,apikey,secret,private_key,seed,mnemonic

# Web3
address,wallet,contract,tx,hash,nonce,signature,signed_msg
chain_id,chainId,network,network_id,rpc_url,provider
gas,gas_price,gasPrice,gas_limit,gasLimit,nonce

# DeFi
amount,amount_in,amount_out,amountIn,amountOut,min_amount,max_amount
slippage,deadline,path,route,pool,pair,token0,token1
swap,swapExactTokensForTokens,swapTokensForExactTokens
add_liquidity,remove_liquidity,mint,burn
stake,unstake,claim,reward,deposit,withdraw
vote,propose,execute,queue,cancel
multicall,multicall2,batch

# Bridge
source_chain,dest_chain,source_token,dest_token,recipient,fee
message,proof,relayer,adapter,handler

# Admin/Governance
admin,owner,governor,proposer,executor,guardian,pauser
role,grant_role,revoke_role,renounce_role
timelock,delay,eta,salt,proposal_id
```

---

## DIRECTORY / FILE FUZZING

### SecLists
```bash
wordlists/SecLists/Discovery/Web-Content/raft-large-directories.txt
wordlists/SecLists/Discovery/Web-Content/raft-large-files.txt
wordlists/SecLists/Discovery/Web-Content/raft-large-words.txt
wordlists/SecLists/Discovery/Web-Content/common.txt
wordlists/SecLists/Discovery/Web-Content/big.txt
wordlists/SecLists/Discovery/Web-Content/medium.txt
wordlists/SecLists/Discovery/Web-Content/small.txt

# Tech-specific
wordlists/SecLists/Discovery/Web-Content/CMS/
wordlists/SecLists/Discovery/Web-Content/Frameworks/
```

### Assetnote
```bash
wget https://wordlists.assetnote.io/raft-large-directories.txt
wget https://wordlists.assetnote.io/raft-large-files.txt
wget https://wordlists.assetnote.io/raft-large-words.txt
```

### Custom (Web3/DeFi)
```text
# Admin panels
admin,administrator,panel,dashboard,console,manage,control
api/v1/admin,api/v2/admin,api/admin
internal/admin,internal/panel
staging/admin,dev/admin,test/admin

# Debug/Actuator
actuator,actuator/health,actuator/env,actuator/beans
actuator/metrics,actuator/heapdump,actuator/threaddump
debug,debug/pprof,debug/vars

# Config
.env,.env.production,.env.local,.env.development
config.json,config.yaml,config.yml
docker-compose.yml,docker-compose.yaml
kubernetes.yml,k8s.yml,.kube/config

# Git
.git/HEAD,.git/config,.git/index
.gitignore,.gitmodules

# CI/CD
.github/workflows,.gitlab-ci.yml,.circleci/config.yml
Jenkinsfile,.travis.yml,.drone.yml

# Web3
hardhat.config.js,foundry.toml,truffle-config.js
scripts/,test/,deploy/,ignition/
artifacts/,cache/,out/,broadcast/
```

---

## VULN-SPECIFIC

### XSS (Dalfox/Gxss)
```bash
# Use payloads/xss.txt from this skill
```

### SQLi (SQLMap)
```bash
# Built-in payloads + tamper scripts
# Custom: payloads/sqli.txt
```

### SSTI (tplmap)
```bash
# Built-in payloads
```

### SSRF
```text
http://169.254.169.254/latest/meta-data/
http://169.254.169.254/latest/user-data/
http://169.254.169.254/latest/dynamic/instance-identity/document
http://metadata.google.internal/computeMetadata/v1/
http://metadata.azure.com/metadata/instance?api-version=2021-02-01
http://169.254.169.254/metadata/instance?api-version=2021-02-01
http://localhost:8080
http://localhost:8081
http://127.0.0.1:8080
http://127.0.0.1:8081
http://[::1]:8080
file:///etc/passwd
file:///etc/shadow
file:///proc/self/environ
file:///proc/version
file:///proc/self/cmdline
dict://localhost:11211/stat
dict://localhost:6379/info
gopher://localhost:6379/_INFO
ldap://localhost:389
ldaps://localhost:636
```

---

## RESOLVERS (for puredns)

```bash
# Public resolvers (update monthly)
wget https://raw.githubusercontent.com/trickest/resolvers/main/resolvers.txt -O resolvers.txt

# Or use known good
cat > resolvers.txt << 'EOF'
1.1.1.1
1.0.0.1
8.8.8.8
8.8.4.4
9.9.9.9
149.112.112.112
208.67.222.222
208.67.220.220
EOF
```

---

## INSTALL ALL (One-liner)

```bash
#!/bin/bash
# install-wordlists.sh

mkdir -p wordlists

# Assetnote (best)
cd wordlists
wget -q https://wordlists.assetnote.io/best-dns-wordlist.txt -O best-dns-wordlist.txt
wget -q https://wordlists.assetnote.io/subdomains.txt -O subdomains.txt
wget -q https://wordlists.assetnote.io/raft-large-directories.txt -O raft-large-directories.txt
wget -q https://wordlists.assetnote.io/raft-large-files.txt -O raft-large-files.txt
wget -q https://wordlists.assetnote.io/raft-large-words.txt -O raft-large-words.txt

# SecLists
git clone --depth 1 https://github.com/danielmiessler/SecLists.git SecLists 2>/dev/null || cd SecLists && git pull && cd ..

# Resolvers
wget -q https://raw.githubusercontent.com/trickest/resolvers/main/resolvers.txt -O resolvers.txt

echo "Wordlists installed in $(pwd)/wordlists"
```

---

## CALCULUS USAGE

| Wordlist | When to Use | Calculus |
|----------|-------------|----------|
| `best-dns-wordlist.txt` | Active subdomain bruteforce | High value target, passive exhausted |
| `subdomains.txt` | Passive enrichment | Always (low cost) |
| `raft-large-directories.txt` | Dir fuzzing | High-value app, unknown structure |
| `raft-large-files.txt` | File fuzzing | Config/backup exposure likely |
| `burp-parameter-names.txt` | Param mining | API endpoints with hidden params |
| `SecLists/Discovery/Web-Content/common.txt` | Quick dir fuzz | Time-boxed (< 5 min) |

**RULE:** Never run a wordlist without Calculus justification. Document in `assumptions.log`.

---

**Remember:** Wordlists are ammunition. The Calculus decides when to fire.

*"Amateur sprays all wordlists. Predator picks the right list for the right target at the right time."*