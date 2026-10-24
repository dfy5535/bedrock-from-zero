// netbot — a headless Bedrock player over the `nethernet` transport
//
// Two steps, in this order:
//   1. broadcast-discover the server's networkId  (UDP, host-global discovery port)
//   2. connect over nethernet/WebRTC using that networkId
//
// Usage:
//   node netbot.js                                            # connect + probe, then exit
//   BOT_NAME=probe1 node netbot.js                            # named one-shot probe
//   HOLD=1 BOT_NAME=alice BOT_PORT=20031 NETH_DISCOVERY_PORT=7551 \
//     node netbot.js                                          # stay online
//
// Environment:
//   MC_VERSION            default 1.26.51
//   BOT_HOST              default 127.0.0.1
//   BOT_PORT              the slot's game port (default 20031)
//   BOT_NAME              player name
//   NETH_DISCOVERY_PORT   discovery port; if unset, the nethernet default is used
//   HOLD=1                keep the connection alive after probing
//
// ---------------------------------------------------------------------------
// Two traps this file exists to avoid:
//
// 1. If NETH_DISCOVERY_PORT is not set, the broadcast may reach *another* server
//    that won the default discovery port, and the bot then connects into the wrong
//    world. Slots must always pass it explicitly.
//    (The slot board reads the real port out of `ss -ulnp`; it never guesses.)
//
// 2. An unconditional "exit after 90s" kills HOLD-mode bots, which makes them vanish
//    from tmux and makes every downstream status check report "not running".
//    The watchdog below explicitly exempts a spawned HOLD bot.
// ---------------------------------------------------------------------------

const path = require('path')

const bedrock = require(path.join(__dirname, 'pb-src', 'node_modules', 'bedrock-protocol'))
const { Client } = require(path.join(__dirname, 'pb-src', 'node_modules', 'nethernet'))

const VERSION = process.env.MC_VERSION || '1.26.51'
const HOST = process.env.BOT_HOST || '127.0.0.1'
const PORT = parseInt(process.env.BOT_PORT || '20031', 10)
const NAME = process.env.BOT_NAME || 'BF_NET_' + Math.random().toString(36).slice(2, 5).toUpperCase()
const HOLD = process.env.HOLD === '1'
const DISCOVERY_PORT = process.env.NETH_DISCOVERY_PORT
  ? parseInt(process.env.NETH_DISCOVERY_PORT, 10)
  : undefined

const t0 = Date.now()
let spawned = false

const log = (...a) => console.log(`[${((Date.now() - t0) / 1000).toFixed(2)}s]`, ...a)

log(`nethernet bot starting | target ${HOST}:${PORT} | version ${VERSION} | name ${NAME} | HOLD=${HOLD}`)
log(`discovery port: ${DISCOVERY_PORT ?? '(default)'}`)

// ---------------------------------------------------------------- step 1: discover ---

log('step 1: broadcasting for networkId ...')

const scanOpts = {}
if (DISCOVERY_PORT) scanOpts.port = DISCOVERY_PORT

const scanner = new Client(0n, '255.255.255.255', scanOpts)
let discovered = false

scanner.on('pong', (params) => {
  if (discovered) return
  discovered = true
  const networkId = BigInt(params.sender_id)
  log(`discovered networkId=${networkId}`)
  try { scanner.close() } catch {}
  connectBot(networkId)
})

scanner.on('error', (e) => log('scan error:', e.message))

setTimeout(() => {
  if (!discovered) {
    log('ERROR: no server discovered within 30s')
    log('       check: is the BDS up? is NETH_DISCOVERY_PORT correct?')
    process.exit(2)
  }
}, 30000)

// ---------------------------------------------------------------- step 2: connect ---

function connectBot(networkId) {
  log('step 2: connecting over nethernet ...')

  const client = bedrock.createClient({
    host: HOST,
    port: PORT,
    username: NAME,
    offline: true,
    version: VERSION,
    transport: 'nethernet',
    nethernet: { networkId, signalling: 'lan' },
    skipPing: true,
    connectTimeout: 20000,
    worldDecodeEnabled: true,
  })

  client.on('connect_allowed', () => log('connect_allowed'))
  client.on('session', () => log('session'))
  client.on('join', () => log('join'))

  client.on('spawn', () => {
    spawned = true
    log(`SPAWNED as ${NAME}`)
    setTimeout(() => probe(client), 3000)
  })

  client.on('text', (p) => {
    try { log('chat:', p.message) } catch {}
  })

  client.on('kick', (r) => log('kicked:', JSON.stringify(r)?.slice(0, 200)))
  client.on('error', (e) => log('error:', e.message))

  client.on('close', () => {
    log('connection closed')
    if (!HOLD) process.exit(0)
  })

  // ------------------------------------------------------------ step 3: probe ---

  function probe(c) {
    log('step 3: capability probe')

    try {
      // `entities` is Map-like in this stack; Object.keys() on it returns [] and makes
      // every entity-dependent test look like a failure.
      const ents = c.entityIds ? c.entityIds : (c.entities || {})
      const count = typeof ents.size === 'number' ? ents.size : Object.keys(ents).length
      log(`  entities: ${count}`)

      if (c.entity?.position) {
        const p = c.entity.position
        log(`  position: ${p.x?.toFixed(1)}, ${p.y?.toFixed(1)}, ${p.z?.toFixed(1)}`)
      }

      if (c.inventory) log(`  inventory slots: ${c.inventory.slots?.length || 'n/a'}`)

      try {
        c.queue?.('text', {
          type: 'chat',
          needs_translation: false,
          source_name: NAME,
          message: `${NAME} online`,
        })
      } catch {}

      log('  probe complete')
    } catch (e) {
      log('  probe error:', e.message)
    }

    if (!HOLD) {
      log('one-shot probe done, exiting in 3s')
      setTimeout(() => process.exit(0), 3000)
    } else {
      log('HOLD mode: staying online (heartbeat every 30s, Ctrl-C to quit)')
      let beat = 0
      setInterval(() => {
        beat++
        log(`heartbeat ${beat} | online ${((Date.now() - t0) / 1000).toFixed(0)}s | ` +
            `state ${spawned ? 'SPAWNED' : '?'}`)
      }, 30000)
    }
  }
}

// ------------------------------------------------------------------- watchdog ---
//
// A one-shot probe should not hang forever. But a HOLD bot that has already spawned is
// *supposed* to live indefinitely, so it must be exempt — otherwise every long-running
// session silently dies at the 90s mark.

setTimeout(() => {
  if (HOLD && spawned) {
    log('90s checkpoint: HOLD and spawned — staying alive')
    return
  }
  log('total timeout 90s')
  process.exit(3)
}, 90000)