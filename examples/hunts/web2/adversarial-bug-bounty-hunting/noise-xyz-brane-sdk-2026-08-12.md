# Noise.xyz / Brane SDK — 2026-08-12 CDC Sniff (No RCE, 2 DoS PROVEN)

## Target
- Org `noise-xyz`: 3 repos `brane` (Java 21 SDK, 9 stars), `docs`, `brand-kit`. `noise.xyz` Cloudflare Managed Challenge 403.
- `brane` 0.3.0 Maven `sh.brane:*` — 5 modules: `brane-core` (Abi/EIP-712/crypto/tx builders), `brane-rpc` (HttpBraneProvider/WebSocketProvider), `brane-contract` (AbstractContractInvocationHandler / Proxy), `brane-primitives` (Hex/RLP), `brane-kzg` (CKzg JNI).
- Env quirk: `git clone https://` fails `git: 'remote-https' is not a git command` — fallback `curl -L https://codeload.github.com/noise-xyz/brane/legacy.zip/refs/heads/main -o /tmp/brane.zip && unzip -q`.

## Trust Graph
```
Untrusted: Abi JSON (chain) → InternalAbi.MAPPER.readTree → AbiDecoder.decode
           EIP-712 JSON (WalletConnect) → TypedDataJson.MAPPER.readValue → TypedData.fromPayload → TypedDataEncoder.hashStruct/encodeField
           RPC response (malicious node) → HttpBraneProvider.MAPPER.readValue(JsonRpcResponse) → resultAsMap/parseTransaction
           Hex/return data → Hex.decode / Blob
           ↓ trust boundary ↓
Signing: TypedData.hash() → Keccak256 → Signer.sign ; Abi.encodeFunction/decode → Proxy.newProxyInstance (interface-only)
```

## CDC 3 Theories

### A. Jackson Deserialization → RCE — BLOCKED
- Search `ObjectMapper|readValue|enableDefaultTyping|JsonTypeInfo|classForName|Runtime|ProcessBuilder` → 0 in prod.
- `InternalAbi.java:37` `new ObjectMapper()` plain; `TypedDataJson.java:62` `new ObjectMapper().configure(FAIL_ON_UNKNOWN_PROPERTIES,false)` only; `RpcUtils.java: MAPPER = new ObjectMapper()` plain; `JsonRpcResponse.java` `@JsonIgnoreProperties(ignoreUnknown=true)`.
- `setAccessible(true)` only `InternalAbi:1101` on record ctor, not attacker type; `Class.forName` only `WebSocketProviderTest.java` Epoll/KQueue detection.
- Verdict: no polymorphic typing → no gadget → mathematically no Jackson RCE.

### B. EIP-712 Recursion → StackOverflow — PROVEN Pre-auth DoS
- `Eip712TypeParser.java:50-58`:
  ```java
  var dynamicArrayMatch = DYNAMIC_ARRAY_PATTERN.matcher(type);
  if (dynamicArrayMatch.matches()) {
    String elementType = dynamicArrayMatch.group(1);
    return new Eip712Type.Array(parse(elementType, types), null); // recurse per []
  }
  ```
  No `MAX_NESTING`. `uint256 + "[]".repeat(5000)` → 5000 frames → StackOverflowError.
- `TypedDataEncoder.java:108-124` `collectDependencies` DFS no depth/size cap, only `visiting` cycle check.
- `TypedDataJson.java:30-63` lenient mapper accepts any `types`/`field.type`.
- Chain: `Attacker JSON types.Mail[0].type=nested → parseAndValidate → hash()→encodeField→parse recursion → StackOverflow → JVM crash` (WalletConnect/dApp blind-sign).
- POC:
  ```java
  String nested="uint256"+"[]".repeat(5000);
  String json="{\"domain\":{},\"primaryType\":\"Mail\",\"types\":{\"Mail\":[{\"name\":\"content\",\"type\":\""+nested+"\"}]},\"message\":{\"content\":[]}}";
  TypedDataJson.parseAndValidate(json).hash(); // StackOverflowError
  ```
  Variant: chain `T1→T2→...→T1000` via `collectDependencies` same.

### C. AbiDecoder Length → OOM — PROVEN Pre-auth DoS
- `AbiDecoder.java:191-215`:
  ```java
  BigInteger lengthValue = decodeInt(data, offset);
  int length = toIntExact(lengthValue, "array length"); // only >MAX_VALUE check
  List<TypeSchema> elemSchemas = new ArrayList<>(length); // OOM if 2_147_483_647
  ```
  `toIntExact` rejects `> Integer.MAX_VALUE` but `MAX_VALUE` itself passes → `new ArrayList<>(MAX_VALUE)` → 8GB alloc attempt. Same `Bytes/String` `Arrays.copyOfRange(dataOffset, dataOffset+length)`.
- `HttpBraneProvider.java: BodyHandlers.ofString()` no size cap; `WebSocketProvider.java` no maxFrame cap → amplifier.
- POC: `byte[] fake=new byte[64]; wrap fake with length 0x01000000; AbiDecoder.decode(fake, List.of(new ArraySchema(UInt256,-1))) → OOM`.

## Negative Validation (why not RCE)
- `Proxy.newProxyInstance` in `BraneContract.java:220/344` + `MulticallBatch.java:236` only to dev-supplied interface.
- `CKzg.loadTrustedSetup(path)` → `CKZG4844JNI.loadTrustedSetup(path)` file read only.
- `AbiDecoder` offset validation exists but after allocation planning.

## Mitigation
```java
// Eip712TypeParser
static final int MAX_NESTING=32;
Eip712Type parse(String type, Map t, int depth){ if(depth>MAX_NESTING) throw new Eip712Exception("nesting"); ... parse(...,depth+1) }
// TypedDataEncoder
if(deps.size()>64||visiting.size()>64) throw cyclicDependency("too many types");
// AbiDecoder
static final int MAX_ARRAY_LENGTH=10_000, MAX_BYTES_LENGTH=1_000_000;
if(length>MAX_ARRAY_LENGTH) throw new AbiDecodingException("array too large");
validateOffset(data, elemOffset + (long)length*32 -1, "array elements");
// HttpBraneProvider
BodyHandlers.ofString() with max 5MB cap; catch StackOverflowError|OutOfMemoryError→Eip712Exception
```

## Recipe for Future Java/EVM SDK Audits
1. Grep `enableDefaultTyping|JsonTypeInfo|JsonSubTypes|readValue.*Object.class` first — plain `new ObjectMapper()` is safe.
2. Fuzz `field.type` with `[]` nesting + dependency chain length; fuzz ABI `array length`/`bytes length` with `0x7fffffff`.
3. Check `BodyHandlers`/`HttpObjectAggregator` size caps.
4. Headless fallback `codeload.zip` when `remote-https` missing; probe `main`/`master` branches.
