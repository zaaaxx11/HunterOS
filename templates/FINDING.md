# Finding: [judul singkat]

- **id**: F-[N]
- **target**: [target id/url]
- **class**: [Access | Oracle | Reentrancy | Sig | Arithmetic | ExternalCall | Logic | Upgradeable | Web2 | Unknown]

  New classes are born only at retro via `hunt klass add` — never at insert. Use `Unknown` as the quarantine class for anything the taxonomy hasn't learned yet.
- **severity**: [critical | high | medium | low | info]
- **ladder**: [theoretical | in-code | proven-live | overturned]
- **poc_path**: [path to PoC file or EMPTY]
- **evidence_ref**: [tx hash / fork receipt / HTTP exchange ref or EMPTY]
- **ENTRY**: [pre-auth | post-auth | unauth]
- **CHAIN**: [Step 1 → Step 2 → ... → impact]
- **IMPACT**: [RCE | theft | escalation | bypass] — quantified when applicable: "X instances, $Y max, Z days window"

  ENTRY, CHAIN, IMPACT mirror the operator's proven output format: where you got in, the steps that chained, what it is worth. They describe the attack — the ladder and falsifier fields still govern what you have earned and what kills the claim.

## Claim

[Satu kalimat: apa yang bisa dilakukan dan siapa yang bisa melakukannya.]

## Impact chain

[Trigger → Effect → Trust boundary crossed → siapa terdampak, nilai apa, kaskade apa]

## Falsifier

**Falsifier (recorded)**: <the observation that would prove this wrong>

[Apa yang jika ditemukan membatalkan klaim ini? Ini wajib diisi — finding tanpa falsifier = belum selesai ditulis. The falsifier now has a ledger column: record it at insert with `hunt finding add --falsifier "..."` so the db — and every report generated from it — carries it.]

## Verification steps (reproducible)

1. [exact command / request]
2. [expected observation]
3. [evidence captured]

## Adversary review

- [blind reviewer]: [survived / overturned + reason]
