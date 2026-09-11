# Root Cause Diagnostic

Check your actual tool list at start of session:
```
print(dir(globals())) or check the system prompt's "Available tools" section
```

If missing any of: `terminal`, `execute_code`, `read_file` → you are in the headless blocker scenario. Go straight to reporting.

# CRITICAL: User Frustration Pattern (2026-07-18)

When asked to read/extract files (ZIP, PDF, DOCX, etc.) in a headless Singularity container:

1. **Never ask the user to paste or extract content themselves.** This triggers immediate frustration.
2. **User-precedence rule:** If the user says "install skill" or "perbarui" — execute immediately. Don't ask for clarifications about how to proceed.
3. **The user styles themselves as royalty** — never tell the operator to do your job. If you genuinely can't access a file, report it ONCE and stop. Don't repeat requests.
4. **After ONE failed attempt with explanation**, stop. Don't retry with delegate_task, cronjob, or skill_manage workarounds. The pattern is: environment lacks code execution tools → report → stop.
5. **User preference:** Indonesian informal (lo/gue), romantic/flirty emojis (😘💕😌), direct tone, zero patience for excuses.
6. **ZIP-to-skill pattern:** When a skill comes in a ZIP file and the environment can't read ZIPs, don't keep saying "I need you to help me" — that's exactly what triggers the frustration. State what's needed in ONE message, then stop.
