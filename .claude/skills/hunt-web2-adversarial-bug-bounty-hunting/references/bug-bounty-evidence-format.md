# Bug Bounty Evidence Format — the operator Preferences

**Last updated:** 2026-08-13 (Helios + Everlyn sessions)

## Screenshot Rules

When delivering PoC evidence for bug bounty submission:

1. **Pure terminal output only** — no labels, no "IMPACT" lines, no red/green color coding, no explanations on the image itself. The terminal screenshot should look exactly like a real terminal session.

2. **One screenshot per issue** — never combine multiple issues into one image. Each finding gets its own evidence file.

3. **Show the command + the output** — the screenshot should include the curl/httpie command and the raw server response. No truncation unless the output is enormous.

4. **No fabricated styling** — don't add red text, yellow highlights, or "CRITICAL" badges on the screenshot. The recipient should see exactly what you saw.

5. **Use black background** — terminal-style (dark bg, green prompt, white output). This is the most readable format for security reports.

6. **DO NOT generate screenshots unless explicitly asked.** "Gausah screenshot klo ga aku perintah." Trigger words: "screenshot", "ss", "gambar", "kirim gambar".

## Report Style — Human, Not AI Slop

When writing bug bounty reports or disclosure emails:

- **Casual English opener.** "Hey Harry, hope you're doing well." — not "Dear Security Team, I am writing to report..."
- **Natural language.** No excessive `---` separators, no formal headers, no bullet-point walls.
- **Indonesian example:** "Hei, aku menemukan sebuah bug di platform mu, bug nya..., aku harap kau bisa meninjau nya. thanks."
- **`.md` format, not `.txt`.** When sending report files.
- **One-line summaries.** "1 dapet apa, 2 dapet apa, 3 dapet apa" — one line per finding, not paragraphs.

## Terminal Screenshot Generation (Linux)

```python
from PIL import Image, ImageDraw, ImageFont
W, H = 1280, 800
BG = (12, 12, 20)       # dark terminal
WHITE = (210, 210, 210)  # output text
GREEN = (60, 255, 70)    # $ prompt
GRAY = (130, 130, 150)   # comments
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)

# Draw lines as (color, text) tuples
# GREEN for prompt, WHITE for output, GRAY for comments
# NO red, NO yellow, NO labels, NO "IMPACT" lines
```

## Windows Command Equivalents

When the user or bug bounty recipient is on Windows (PowerShell):

| Linux | Windows PowerShell |
|-------|-------------------|
| `head -80` | `Select-Object -First 80` |
| `grep` | `Select-String` |
| `python3` | `python` |
| `curl` | `curl.exe` (not `curl` alias, which is `Invoke-WebRequest`) |
| `jq` | `ConvertFrom-Json \| ConvertTo-Json` |

## Everlyn-Specific: API Response Format Changes

When retesting a previously reported bug:

- `/api/admin/orders` changed from JSON to HTML (Next.js RSC) between reports
- Don't assume the same output format on retest
- Always `curl -sI` first to check Content-Type before parsing
- If HTML, extract data with `grep -oP` patterns instead of `jq`/`python3 -m json.tool`

## Pitfall: Over-Styling Screenshots

**DON'T:**
- Add red text for "critical" findings
- Add "IMPACT: ..." lines on the image
- Add colored borders or badges
- Combine multiple issues into one wide image
- Add explanatory text on the screenshot itself

**DO:**
- Pure terminal: `$ command` + raw output
- One image per issue
- Explanations in the accompanying text/email, not on the image

## "Jelasin Santai" Workflow (the operator Preference)

When the the operator says "jelasin santai" or "aku masih bingung":

1. **Analogies first, technical second** — use casual Indonesian analogies (hotel, resepsionis, brankas, robot room service, satpam, jembatan kurir) to explain the vulnerability concept before diving into curl commands or code.
2. **lo/gue tone** — casual Indonesian with `😘💕😌` emojis
3. **Perumpamaan** — the user prefers hotel analogies (resepsionis = auth middleware, brankas = config files, kunci master = validator key, robot chronos = auto EVM execution, jembatan = bridge)
4. **Only after they understand** — then provide the technical proof (curl commands, screenshots, PoC)

## Complete Pillow Screenshot Script

```python
from PIL import Image, ImageDraw, ImageFont
W, H = 1280, 800
BG = (12, 12, 20)
WHITE = (210, 210, 210)
GREEN = (60, 255, 70)
GRAY = (130, 130, 150)
YELLOW = (230, 220, 100)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)

def draw(img, lines):
    d = ImageDraw.Draw(img)
    for i, (c, t) in enumerate(lines[:38]):
        d.text((16, 10 + i*20), t, fill=c, font=font)

# Usage: lines = [(GREEN, "$ curl ..."), (WHITE, "output"), ...]
```