# Attack Plan: PracticeVault (target #1)

Built from surface_map.md (actual recon of the live app). Three flaw
hypotheses per lane, each tied to a trust boundary from the map. Lanes stay
in their own family; the Chainer gets handoffs, not duplicates.

## Lane 1 - Architect (trust graph)

- H-A1: `/admin` (TB1) decides privilege from a client-asserted cookie with
  no server-side session or signature. Hypothesis: the "validation" is just
  the client's own claim; every privilege decision is attacker-controlled.
- H-A2: `/api/users` (TB3) is an unauthenticated storage->output crossing
  that emits password hashes. Hypothesis: hashes are unsalted/fast-digest
  and crackable, so the leak is credential compromise, not just info noise.
- H-A3: the balance dict (asset) is mutated by `/transfer` (TB2) with no
  visible principal concept anywhere in the app. Hypothesis: there is no
  ownership model at all - any `from` account is impersonable.

## Lane 2 - Red-Teamer (invariant breaker)

- H-R1: invariant "only admins can read /admin" depends on cookie `role`.
  Attack: forge `role=admin` and demand the panel.
- H-R2: invariant "transfers move money between existing accounts with
  permission" depends on authentication existing at all. Attack: bare POST
  with zero credentials, impersonating `vault` as the source.
- H-R3: invariant "the admin panel secret stays internal". Attack: chain
  H-R1 output (admin session) into reading the protected string, then treat
  that string as a weapon (it names transfer keys).

## Lane 3 - Fuzz-Engineer (boundary cases)

- H-F1: `/transfer` type boundary - `amount` accepts junk (`abc`, `1e3`,
  empty). Hypothesis: unguarded parse crashes the request handler; test
  whether impact is a transient 500 or a process kill (DoS or not).
- H-F2: `/transfer` missing-field boundary - omit `from`/`to`/`amount`.
  Hypothesis: unguarded KeyError; transient only (to be cross-corrected).
- H-F3: `/transfer` amount magnitude - `amount=0`, huge values beyond
  balance. Hypothesis: no sufficient-balance check, so a single transfer can
  overdraw the vault (unbounded theft, not just theft of existing funds).

## Lane 4 - Chainer (exploit chains)

- H-C1: `/api/users` output (usernames + hash digests) -> forge admin cookie
  -> `/transfer`: full unauth->admin->theft chain in one script.
- H-C2: leaked hashes crack to reusable passwords -> if any login consumed
  those passwords, replay them. Hypothesis: there is no login endpoint to
  replay against (candidate dead end - verify honestly).
- H-C3: admin panel secret ("internal transfer keys") -> if it named real
  key material, exfiltrate and replay. Hypothesis: the panel string is a
  decoy with no consumable key; verify before claiming.

## Round-1 scope note

Round 1 fuzzes TYPE and MAGNITUDE boundaries on `/transfer`. SIGN boundaries
(negative amounts) are deliberately deferred to the round-2 blind-spot pass
so the blind-spot scanner has an honest question to answer: "what did we not
look at?" (Sign edges are the classic self-transfer mint; if round 1 finds
it anyway, that is a bonus, not the plan.)
