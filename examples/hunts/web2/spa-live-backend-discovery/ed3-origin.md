# ed3.xyz origin story — spa-live-backend-discovery

> Cut verbatim from `soul/skills/web2/spa-live-backend-discovery/SKILL.md` during the
> 2026-09-07 skills cull (S2b-1). Full origin narrative of the 2026-09 ed3.xyz hunt;
> the skill body keeps the generalized class method.

## Why this skill exists (2026-09 ed3.xyz lesson)
A Next.js SPA was fronted by a whole subdomain fleet (`api.<d>.xyz`, `launchpad-dev.<d>.xyz`,
`user.<d>.xyz`, `utility.<d>.xyz`, ...). Guessing which one is the quest/points backend and
probing `/health` burned many rounds: `/health` returned **404 Express `Cannot GET`** on every
candidate, which I misread as "all backends down." The REAL backend (`user.<d>.xyz`) was found
only by **loading the SPA in a browser I controlled and capturing what it actually fetches**.
The user corrected me: *"bukan danlabs cuk tadi, tadi tu ed3.xyz yang bisa"* — the app itself
knows its own backend; static/DNS guesses do not.
