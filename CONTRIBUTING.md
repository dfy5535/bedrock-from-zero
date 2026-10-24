# Contributing

Thanks for considering it. This project has an unusual contribution rule, so read this first.

---

## The one rule that overrides everything

**A contribution that adds a claim must add evidence for it.**

Not a link. Not "works on my machine". An excerpt, a schema path, or a runtime log line that a
reviewer can inspect.

```
❌  "fixed the loot table format"
✅  "loot table path is relative to the BP root — schema says so (L2, block_components.json
     #minecraft:loot), verified against a running server (L0, evidence/bds-A.log:11842)"
```

This is not bureaucracy. The entire value of this framework is that it refuses to assert things
it cannot prove. A contribution that asserts without proof erodes exactly that.

---

## What kinds of contributions are welcome

| Type | Notes |
|---|---|
| **New skills** | A repeatable process gap you hit repeatedly. Follow the six-question template. |
| **Bug fixes in `tools/`** | Must include the reproduction and the failing output. |
| **Case studies** | A real failure, its root cause, and the minimal fix. Highest value per line. |
| **Docs corrections** | Especially where a version number has drifted. |
| **Test harnesses** | New ways to prove behaviour on the server. |
| **Translations** | Keep the technical terms in English to preserve searchability. |

## What will be rejected

| Type | Why |
|---|---|
| Undocumented "magic" fixes | Unreviewable, unreproducible |
| Skills containing hard-coded Minecraft knowledge | Violates the core design; knowledge is fetched at runtime |
| Anything with credentials, IPs, or keys | See `SECURITY.md` |
| Whole-project rewrites as fixes | Destroys attribution |
| PRs that report layer C as PASS without client evidence | Non-negotiable |
| Bundled Microsoft sample repositories | Licensing; fetch them at setup time |

---

## Skill template

Every `skills/<name>/SKILL.md` must answer exactly six questions and nothing more:

```markdown
---
name: <skill-name>
description: <one paragraph: what it does, and when it is the right tool>
whenToUse: <the user phrasings and situations that should trigger it>
---

# <skill-name> — <one-line purpose>

This skill defines **process only**. It carries no Minecraft knowledge.
All API/format facts must be resolved from official sources at runtime.

## 0. Authoritative sources (read-only)
<table of where truth lives in this deployment>

## 1. When to use
<bullet list of triggers>
**Not applicable**: <the adjacent cases that belong elsewhere>

## 2. Check order (strictly serial)
<numbered steps, each with a PASS condition>

## 3. Tool invocation order
<exact commands>

## 4. Forbidden
<numbered list — be specific and blunt>

## 5. Output format
<exact file paths and structures produced>

## 6. PASS criteria
<checklist; any unchecked item means FAIL or PARTIAL, never PASS>
```

Rules for skill content:

- **No version numbers as facts.** If a version appears, it is labelled "last observed" and the
  skill instructs a re-read.
- **No API names as truth.** Reference the lookup, not the value.
- **Every forbidden item must cite a real failure** it prevents.

---

## Code style for `tools/`

- Python 3.8+, standard library only unless justified.
- Node 18+ for bot tooling.
- **No hard-coded hosts.** Read from env or a config file.
- **Never guess a port.** Return `None` and fail loudly; a wrong guess silently corrupts state.
- `flock`-protect every state mutation.
- Every destructive operation supports `--dry-run` where feasible.
- Write state atomically (temp file + `os.replace`).

---

## Commit messages

```
<scope>: <imperative summary>

Why: <the failure this prevents>
Evidence: <level + path or excerpt>
```

Example:

```
tools/shctl: return None when discovery port detection fails

Why: defaulting to 7551 pointed bots into whichever server won the race,
     causing cross-slot world joins and corrupted test results.
Evidence: L0 — reproduced with two BDS instances; bot with unset
          NETH_DISCOVERY_PORT joined slot B while owned by slot A.
```

---

## Review process

1. **Reproducibility check** — can a reviewer reproduce the evidence from the PR alone?
2. **Evidence check** — is every claim levelled and cited?
3. **Scope check** — is this a minimal change, or a rewrite?
4. **Secret scan** — automated; a hit blocks merge.
5. **Honesty check** — does anything claim `PASS` without proof?

---

## Reporting bugs

Include:

- What you expected, in observable terms.
- What happened, with the raw output.
- The exact command sequence.
- Your runtime triple (runtime / samples / schema / script API).
- Whether layer C was involved.

A bug report that says "doesn't work" cannot be acted on and will be closed with a request for
the above.

---

## Licensing of contributions

By contributing you agree your work is licensed under the repository's MIT license.
Do not submit code you cannot license.