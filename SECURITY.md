# Security Policy

This repository is a **framework**, not a deployment. It contains no credentials and no live
infrastructure. However, it orchestrates servers, so a few risks are inherent to how it is used.

---

## What is never in this repository

| Category | Status |
|---|---|
| Passwords, API keys, tokens | **Never** |
| SSH private keys | **Never** |
| Public IP addresses | **Never** — replaced with `<CONTROL_HOST>` style placeholders |
| Internal hostnames | **Never** |
| Private domains / panels | **Never** |
| Proxy credentials | **Never** |
| World saves, BDS binaries | Not included (size + licensing) |

If you find any of the above in this repository, **that is a vulnerability.** Report it as such.

---

## Reporting a vulnerability

Open a **private security advisory** rather than a public issue if the report involves:

- A leaked credential or host identifier in the repo or its history.
- A code path that could allow command injection through slot names, bot names, or paths.
- A way to make `shctl` / `portctl` / `mcreg` corrupt state or escape its write boundary.
- Privilege escalation via a symlink or a crafted state file.

Include the reproduction: the exact input, the observed effect, and the expected behaviour.

---

## Threat model for the tooling

These tools run as a **privileged local user** on a machine that also runs game servers.
The realistic threats are:

### 1. Command injection through names

`shctl claim <name>`, `shctl bot <name> <botname>`, and `wbot` all interpolate user-supplied
strings into shell commands.

**Requirement:** names must be validated against `^[A-Za-z0-9_-]{1,32}$` before use.
Anything else is rejected, not escaped.

```python
NAME_RE = re.compile(r'^[A-Za-z0-9_-]{1,32}$')
if not NAME_RE.match(name):
    sys.exit("rejected: invalid name")
```

Escaping is a fallback, not a substitute. Validate first.

### 2. Path traversal in slot directories

A slot's directory is derived from configuration, never from user input. If you extend the
system to accept a custom path, resolve it and verify it stays under the configured root:

```python
root = os.path.realpath(ROOT)
target = os.path.realpath(os.path.join(root, user_value))
if not target.startswith(root + os.sep):
    sys.exit("rejected: path escapes root")
```

`realpath` (not `abspath`) matters — it resolves symlinks, which is the actual attack vector.

### 3. State file tampering

`state/*.json` is read and trusted. If an attacker can write it, they can reassign slots or
trigger a stop of another user's server.

**Mitigations in place:** state directory is `0700`, files are written atomically with
`os.replace`, and all mutations are `flock`-protected. Do not loosen these permissions.

### 4. Bedrock server exposure

The framework starts **Bedrock Dedicated Server**, which is a game server with a remote console.

> **Critical:** a BDS configured with `online-mode=false` and `allow-cheats=true` will accept
> commands from any player. **Never expose its UDP port to the public internet in that state.**

Recommended for any non-local use:

```properties
online-mode=true
allow-cheats=false
```

And never publish the discovery port. Discovery is a LAN mechanism; exposing it invites joiners.

### 5. Token and key handling in agent environments

If an AI agent runs these tools, note:

- Agent logs frequently capture stdout. **Never echo secrets.** Read from a file, not from the
  command line, so the value never enters shell history or a log.
- The framework's tools never print credentials; keep it that way when extending them.

```bash
# good: password never appears in `ps`, history, or logs
printf '%s' "$PASS" > ~/.netrc-mc && chmod 600 ~/.netrc-mc
sshpass -f ~/.netrc-mc ssh user@host

# bad: visible in the process list to every local user
sshpass -p "$PASS" ssh user@host
```

---

## Executing untrusted Add-Ons

Layer B tests **load a pack into a running server**. A malicious pack can:

- Run arbitrary script API code in the server context.
- Read or write files the server process can reach.
- Exhaust memory or CPU (crash the host, and via OOM, your SSH session).

**Rule: test untrusted packs only in a disposable slot, on a machine you can reset, with resource
limits.** If you automate this, put the BDS under a cgroup:

```bash
systemd-run --scope -p MemoryMax=3G -p MemorySwapMax=1G -p TasksMax=768 \
  ./bedrock_server
```

This is not theoretical. An unconstrained pack plus a memory-constrained host is the standard
recipe for taking down `sshd` and losing access to the machine.

---

## Hardening checklist for a deployment

```bash
# 1. state directory permissions
chmod 700 /opt/bedrock-flow/state

# 2. no secrets in world-readable files
grep -rlE '(password|token|api[_-]?key)\s*[:=]' /opt/bedrock-flow/ 2>/dev/null

# 3. BDS not publicly exposed with cheats on
grep -E '^(online-mode|allow-cheats|enable-lan-visibility)' \
  /opt/bedrock-flow/slots/*/server.properties

# 4. resource cap on the server process
systemctl show bedrock-flow-slotA -p MemoryMax

# 5. no world-readable key material
find /opt/bedrock-flow -name '*.pem' -o -name 'id_*' | xargs -r ls -l
```

---

## Supported versions

This is a framework; security fixes apply to the current `main`. If you fork it for a private
deployment, you own the patching.

---

## Disclosure

We will credit reporters in the advisory unless asked otherwise. There is no bounty —
this is a small independent project.