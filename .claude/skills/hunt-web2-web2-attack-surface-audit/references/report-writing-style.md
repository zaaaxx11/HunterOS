# Bug Bounty Report Writing — Human Style

## What the user wants

- **Casual human opener:** "Hey [name], hope you're doing well. I spent some time looking at..."
- **No AI slop:** Avoid "I hope this message finds you well," "Upon further investigation," "I would like to bring to your attention"
- **No dashes/separators:** No `=======` or `---` dividers. Use blank lines only.
- **POC inline:** curl commands or steps right in the report body
- **Concise impact:** One sentence per finding, not CVSS paragraphs
- **English for submission, Indonesian casual (lo/gue) for internal discussion**

## Example opener

```
Hey Harry,

Hope you're doing well. I spent some time looking at Everlyn's security
and found a few things I think you should know about.

The short version: your admin orders page is public and leaks real customer
data, and your video generation API lets anyone create orders using any
email address, including your own admin email.
```

## What to NEVER do

- NEVER start with "Dear Security Team, I am writing to inform you..."
- NEVER use markdown tables in the report body
- NEVER add CVSS labels unless asked
- NEVER add "CONFIDENCE: PROVEN" or "IMPACT: CRITICAL" labels
- NEVER use excessive bullet lists — use natural paragraphs
- NEVER add disclaimers like "I did not access anything beyond..." unless true and relevant