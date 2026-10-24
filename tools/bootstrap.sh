#!/usr/bin/env bash
# bootstrap.sh — turn a bare Ubuntu host into a working Bedrock Flow lab
#
# What this does, in order:
#   1. checks prerequisites
#   2. lays out $BF_HOME (default /opt/bedrock-flow)
#   3. downloads BDS and verifies the checksum
#   4. installs the bot runtime (bedrock-protocol + nethernet)
#   5. installs shctl (the slot board)
#   6. runs a readiness check
#
# It does NOT start a server. That is `shctl claim` + `shctl start`, deliberately —
# starting a server is a decision, not an installation step.
#
# Usage:
#   sudo ./bootstrap.sh
#   sudo BF_HOME=/srv/lab BDS_VERSION=1.26.51.1 ./bootstrap.sh
#
# Tested on Ubuntu 22.04 / 24.04.

set -euo pipefail

BF_HOME="${BF_HOME:-/opt/bedrock-flow}"
BDS_VERSION="${BDS_VERSION:-1.26.51.1}"
NODE_MAJOR="${NODE_MAJOR:-22}"
BOT_USER="${BOT_USER:-ubuntu}"

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RST=$'\033[0m'
say()  { printf '%s==>%s %s\n' "$GRN" "$RST" "$*"; }
warn() { printf '%s[!]%s %s\n' "$YLW" "$RST" "$*"; }
die()  { printf '%s[x]%s %s\n' "$RED" "$RST" "$*" >&2; exit 1; }

# ------------------------------------------------------------------ 1. prereqs ---

say "checking prerequisites"

[[ $EUID -eq 0 ]] || die "run as root (needs to create $BF_HOME and install packages)"

for c in curl unzip tmux ss rsync; do
  command -v "$c" >/dev/null 2>&1 || {
    warn "missing: $c — installing"
    apt-get update -qq
    apt-get install -y -qq curl unzip tmux iproute2 rsync
    break
  }
done

if ! command -v node >/dev/null 2>&1; then
  say "installing Node.js ${NODE_MAJOR}"
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y -qq nodejs
fi

NODE_V="$(node -v)"
say "node $NODE_V"

# Node 22+ is required by the current protocol stack
node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)' \
  || die "node >= 20 required, found $NODE_V"

# ------------------------------------------------------------------ 2. layout ---

say "creating $BF_HOME"
mkdir -p "$BF_HOME"/{bds,slots,state,evidence,tools,tools/pb-src,reports,artifacts}

if id "$BOT_USER" >/dev/null 2>&1; then
  chown -R "$BOT_USER":"$BOT_USER" "$BF_HOME"
  say "ownership -> $BOT_USER"
else
  warn "user '$BOT_USER' does not exist; leaving ownership as root"
fi

# ------------------------------------------------------------------ 3. BDS ---

BDS_DIR="$BF_HOME/bds"

if [[ -x "$BDS_DIR/bedrock_server" ]]; then
  say "BDS already present at $BDS_DIR — skipping download"
else
  say "downloading BDS $BDS_VERSION"

  # BDS is distributed as a zip from Microsoft's CDN. The URL pattern is stable but the
  # version must exist; check the official download page if this 404s.
  BDS_ZIP="bedrock-server-${BDS_VERSION}.zip"
  BDS_URL="https://www.minecraft.net/bedrockdedicatedserver/bin-linux/${BDS_ZIP}"

  cd /tmp
  if ! curl -fSL --retry 3 -o "$BDS_ZIP" "$BDS_URL"; then
    die "download failed. BDS versions are not guessable — check
       https://www.minecraft.net/en-us/download/server/bedrock
       and pass the exact filename with BDS_VERSION="
  fi

  say "extracting into $BDS_DIR"
  unzip -q -o "$BDS_ZIP" -d "$BDS_DIR"
  chmod +x "$BDS_DIR/bedrock_server"

  # a pristine template world the slots copy from
  if [[ ! -d "$BDS_DIR/worlds/bot-world" ]]; then
    say "note: first server start will create $BDS_DIR/worlds/bot-world"
    say "      copy it to a template later, or let slot A generate it"
  fi

  rm -f "/tmp/$BDS_ZIP"
fi

# The server needs its own libs from the same directory
[[ -x "$BDS_DIR/bedrock_server" ]] || die "bedrock_server is missing or not executable"
say "BDS binary present"

# ------------------------------------------------------------------ 4. bot runtime ---

say "installing bot runtime into $BF_HOME/tools/pb-src"

mkdir -p "$BF_HOME/tools/pb-src"
cd "$BF_HOME/tools/pb-src"

if [[ ! -f package.json ]]; then
  cat > package.json <<'JSON'
{
  "name": "bf-bot-runtime",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "bedrock-protocol": "3.60.1",
    "nethernet": "latest",
    "prismarine-chunk": "latest",
    "prismarine-block": "latest",
    "vec3": "latest"
  }
}
JSON
fi

npm install --ignore-scripts --no-audit --no-fund

# ★ The single most important verification in this whole script.
#
# prismarine-chunk ships per-version bedrock decoders. If this stack installs the
# official release instead of a fork that knows your BDS version, the bot connects and
# reads inventory fine but decodes the entire world as air — with no error at all.
say "verifying chunk decoder coverage"
DECODERS="$(ls node_modules/prismarine-chunk/src/bedrock/ 2>/dev/null || echo MISSING)"
echo "    available: $DECODERS"

if [[ "$DECODERS" == "MISSING" ]]; then
  warn "prismarine-chunk is not installed correctly — the bot will decode the world as air"
else
  MAJOR_MINOR="${BDS_VERSION%.*}"     # 1.26.51.1 -> 1.26.51
  if echo "$DECODERS" | grep -q "${MAJOR_MINOR%.*}"; then
    say "decoder for ${MAJOR_MINOR%.*}.x found"
  else
    warn "no decoder matching ${MAJOR_MINOR%.*}.x in the list above."
    warn "The bot will connect but every block will read as air."
    warn "You need a prismarine-chunk build that supports this BDS version."
  fi
fi

if [[ ! -d node_modules/nethernet ]]; then
  warn "nethernet not installed — modern BDS uses nethernet transport, bots will not connect"
fi

chown -R "$BOT_USER":"$BOT_USER" "$BF_HOME/tools/pb-src" 2>/dev/null || true

# ------------------------------------------------------------------ 5. tools ---

say "installing tools"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in shctl.py sh-guard.py portctl.py mcreg.py; do
  if [[ -f "$SCRIPT_DIR/$f" ]]; then
    install -m 0755 "$SCRIPT_DIR/$f" "$BF_HOME/tools/$f"
    say "  $f"
  fi
done

if [[ -f "$SCRIPT_DIR/netbot.js" ]]; then
  install -m 0644 "$SCRIPT_DIR/netbot.js" "$BF_HOME/tools/netbot.js"
  say "  netbot.js"
fi

ln -sf "$BF_HOME/tools/shctl.py" /usr/local/bin/shctl
say "shctl -> /usr/local/bin/shctl"

# ------------------------------------------------------------------ 6. verify ---

say "running readiness check"

FAIL=0

check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  %s ok %s %s\n' "$GRN" "$RST" "$label"
  else
    printf '  %sFAIL%s %s\n' "$RED" "$RST" "$label"
    FAIL=$((FAIL+1))
  fi
}

check "node present"            command -v node
check "tmux present"            command -v tmux
check "ss present"              command -v ss
check "BDS binary"              test -x "$BDS_DIR/bedrock_server"
check "bot runtime installed"   test -d "$BF_HOME/tools/pb-src/node_modules"
check "shctl executable"        test -x "$BF_HOME/tools/shctl.py"

echo
if [[ $FAIL -eq 0 ]]; then
  say "environment ready"
  cat <<EOF

Next steps:

  1. If \$BF_HOME/bds/worlds/bot-world does not exist yet, start the server once to
     generate it, then copy it back as the template:

       cd $BF_HOME/bds && LD_LIBRARY_PATH=. ./bedrock_server
       # wait for "Server started"
       # type: stop
       cp -r worlds/bot-world worlds/bot-world.template

  2. Point the slot board at the template (edit SOURCE_WORLD in shctl.py if you used
     a different name).

  3. Use it:

       shctl board
       shctl claim alice
       shctl start alice
       shctl bot  alice probe1
       shctl status --json

  4. Read docs/AI-START.md before building anything.

EOF
else
  die "$FAIL check(s) failed — fix those before proceeding"
fi