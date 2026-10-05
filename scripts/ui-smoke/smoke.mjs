// Headless-browser acceptance check for the map UI (Phases 5–6). Runs in the official
// Playwright image with host networking (`make ui-smoke`); screenshots go to $OUT.
//
// Phase 5: the socket goes live and gets a snapshot; after zoom + pan a new subscribe is sent
// and nothing outside its bbox arrives; clicking an aircraft selects it (feature-state) and
// loads REST details; at 375 px there is no horizontal overflow and the bottom sheet works.
// Phase 6: the selected aircraft gets a track line and live aircraft get tails; history mode
// pauses the socket and replays at ~60×; a zone drawn with the mouse is saved and an aircraft
// entering it raises a toast; the zone is deleted again. No console errors anywhere.
import { chromium } from 'playwright'

const BASE = process.env.BASE ?? 'http://localhost:8800/'
const OUT = process.env.OUT ?? '/out'
const failures = []
const log = (...a) => console.log(...a)
const check = (ok, what) => {
  log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`)
  if (!ok) failures.push(what)
}

// WebGL in a headless container: software rendering through SwiftShader
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })

function watch(page) {
  const frames = []
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('websocket', (ws) => {
    if (!ws.url().includes('/ws/live/')) return
    ws.on('framesent', (f) => frames.push({ dir: 'out', t: Date.now(), m: JSON.parse(f.payload) }))
    ws.on('framereceived', (f) => frames.push({ dir: 'in', t: Date.now(), m: JSON.parse(f.payload) }))
  })
  return { frames, errors }
}

const inside = (b, a) => a.lon >= b[0] && a.lon <= b[2] && a.lat >= b[1] && a.lat <= b[3]

/** Frames after the last subscribe sent since `start`. */
function sinceLastSubscribe(frames, start) {
  const sub = frames.slice(start).filter((f) => f.dir === 'out').at(-1)
  if (!sub) return null
  const incoming = frames.filter((f) => f.dir === 'in' && f.t >= sub.t)
  const snapshot = incoming.find((f) => f.m.type === 'snapshot')?.m
  const deltas = incoming.filter((f) => f.m.type === 'delta')
  const upserts = deltas.flatMap((d) => d.m.upserts)
  const outside = [...(snapshot?.aircraft ?? []), ...upserts].filter((a) => !inside(sub.m.bbox, a))
  const gaps = deltas.slice(1).map((d, i) => d.t - deltas[i].t)
  log(`  bbox ${JSON.stringify(sub.m.bbox)}: snapshot ${snapshot?.aircraft.length ?? '-'}, ${deltas.length} deltas (${upserts.length} upserts), gaps ms [${gaps.join(', ')}]`)
  return { bbox: sub.m.bbox, snapshot, deltas, outside }
}

/** Screen position of a rendered aircraft away from the panel and the edges. */
const aircraftOnScreen = (page) =>
  page.evaluate(() => {
    const m = window.__map
    const c = m.getCanvas()
    const panel = document.querySelector('.panel').getBoundingClientRect()
    for (const f of m.queryRenderedFeatures({ layers: ['aircraft'] })) {
      const p = m.project(f.geometry.coordinates)
      const free = p.x > 60 && p.y > 60 && p.x < c.clientWidth - 60 && p.y < c.clientHeight - 60
      const underPanel = p.x >= panel.left - 20 && p.y >= panel.top - 20
      if (free && !underPanel) return { x: p.x, y: p.y, id: f.properties.icao24 }
    }
    return null
  })

/** Count rendered LineStrings (and their vertices) of a GeoJSON source. */
const sourceLines = (page, source) =>
  page.evaluate((id) => {
    const features = window.__map.querySourceFeatures(id)
    const ids = new Set()
    let points = 0
    for (const f of features) {
      // tiles may split one line into pieces: count distinct features by aircraft id
      ids.add(f.properties.icao24 ?? 'track')
      points += f.geometry.coordinates.length
    }
    return { lines: ids.size, points }
  }, source)

const sliderValue = (page) => page.$eval('.playback-slider', (el) => Number(el.value))

const tileResponse = (page) =>
  page
    .waitForResponse((r) => /\/tiles\/hillshade\/\d+\/\d+\/\d+\.png$/.test(r.url()) && r.status() === 200, { timeout: 15_000 })
    .then(() => true, () => false)

async function terrainChecks(page, devMap) {
  const toggle = page.getByLabel('Hillshade', { exact: true })
  const ready = await toggle.isEnabled().catch(() => false)
  check(ready, 'hillshade layer available (tiles from make dem)')
  if (!ready) return
  if (devMap) {
    // Uludag from the north-west: real relief in the first tiles requested
    const tile = tileResponse(page)
    await page.evaluate(() => window.__map.jumpTo({ center: [29.1, 40.1], zoom: 9.5 }))
    check(await tile, 'hillshade tiles load (HTTP 200)')
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${OUT}/desktop-hillshade.png` })
    const vis = () => page.evaluate(() => window.__map.getLayoutProperty('hillshade', 'visibility'))
    check((await vis()) === 'visible', 'hillshade visible by default')
    await toggle.uncheck()
    check((await vis()) === 'none', 'hillshade toggles off')
    await toggle.check()
    check((await vis()) === 'visible', 'hillshade toggles back on')
    await page.getByLabel('Hillshade opacity').fill('0.9')
    const opacity = await page.evaluate(() => window.__map.getPaintProperty('hillshade', 'raster-opacity'))
    check(opacity === 0.9, `opacity slider drives raster-opacity (${opacity})`)
  } else {
    const tile = tileResponse(page)
    await page.mouse.wheel(0, -600)
    check(await tile, 'hillshade tiles load (HTTP 200)')
  }
}

async function historyChecks(page, frames) {
  await page.click('.mode-switch button:has-text("History")')
  await page.waitForSelector('.status-paused')
  const ready = await page.waitForSelector('.playback-bar .play:not([disabled])', { timeout: 20_000 }).then(() => true, () => false)
  check(ready, 'history window (last hour) loads')
  if (!ready) return
  log('  history:', (await page.textContent('[aria-label="History window"] p')).trim())
  const before = frames.length
  await page.click('.playback-bar [role="radio"]:has-text("60×")')
  const t0 = await sliderValue(page)
  const w0 = Date.now()
  await page.click('.playback-bar .play')
  await page.waitForTimeout(4000)
  const rate = (await sliderValue(page) - t0) / ((Date.now() - w0) / 1000)
  check(rate > 40 && rate < 70, `playback runs at ~60× (measured ${rate.toFixed(1)}×)`)
  const shown = await page.evaluate(() => window.__map.querySourceFeatures('aircraft').length)
  check(shown > 0, `history aircraft on the map (${shown})`)
  await page.screenshot({ path: `${OUT}/desktop-history.png` })
  check(frames.slice(before).filter((f) => f.dir === 'in').length === 0, 'socket is paused in history mode (no frames)')
  await page.click('.mode-switch button:has-text("Live")')
  const back = await page.waitForSelector('.status-live', { timeout: 30_000 }).then(() => true, () => false)
  check(back, 'back to live: socket reconnects')
}

async function zoneChecks(page, frames) {
  const name = `smoke ${Date.now() % 100000}`
  // a 1° box over the busiest part of the region: aircraft cross its edges every few seconds
  await page.evaluate(() => window.__map.jumpTo({ center: [29.0, 41.0], zoom: 7 }))
  await page.waitForTimeout(1000)
  const corners = await page.evaluate(() =>
    [[28.5, 40.5], [29.5, 40.5], [29.5, 41.5], [28.5, 41.5]].map((c) => {
      const p = window.__map.project(c)
      return [p.x, p.y]
    }),
  )
  // start without a selection: the closing click must not select whatever is under it
  const close = await page.$('button[aria-label="Close details"]')
  if (close) await close.click()
  await page.click('button:has-text("Draw a zone")')
  for (const [x, y] of [...corners, corners[0]]) {
    await page.mouse.click(x, y)
    await page.waitForTimeout(250)
  }
  const drawn = await page.waitForSelector('input[aria-label="Zone name"]', { timeout: 5000 }).then(() => true, () => false)
  check(drawn, 'drawing a polygon with the mouse opens the name form')
  if (!drawn) return
  check((await page.$('.details')) === null, 'clicks while drawing do not select aircraft')
  await page.fill('input[aria-label="Zone name"]', name)
  await page.click('button:has-text("Save zone")')
  const saved = await page.waitForSelector(`.zones li:has-text("${name}")`, { timeout: 5000 }).then(() => true, () => false)
  check(saved, 'zone saved (POST) and listed')
  // aircraft already inside get `enter` at once (D-052); then wait for a real boundary crossing
  const w0 = Date.now()
  await page.waitForTimeout(4000)
  const initial = await page.$$eval('.toast', (els) => els.map((e) => e.textContent))
  log(`  ${initial.length} toast(s) for aircraft already inside`)
  const crossed = await page
    .waitForFunction(
      ([zone, seen]) => [...document.querySelectorAll('.toast')].some((e) => e.textContent.includes(zone) && !seen.includes(e.textContent)),
      [name, initial],
      { timeout: 180_000, polling: 250 },
    )
    .then(() => true, () => false)
  check(crossed, `toast for an aircraft crossing into the new zone (${((Date.now() - w0) / 1000).toFixed(1)} s after saving)`)
  await page.screenshot({ path: `${OUT}/desktop-zone.png` })
  // pipeline latency: position timestamp (ingest) → geofence_event frame in the browser
  const lags = frames
    .filter((f) => f.dir === 'in' && f.m.type === 'geofence_event' && f.m.geofence.name === name)
    .map((f) => f.t / 1000 - f.m.ts)
  const worst = Math.max(...lags)
  check(lags.length > 0 && worst < 5, `event latency fix → browser ≤ 5 s (worst ${worst.toFixed(1)} s over ${lags.length} events)`)
  page.once('dialog', (d) => d.accept())
  await page.click(`.zones li:has-text("${name}") button[aria-label^="Delete"]`)
  const gone = await page.waitForSelector(`.zones li:has-text("${name}")`, { state: 'detached', timeout: 5000 }).then(() => true, () => false)
  check(gone, 'zone deleted')
}

// ---- desktop ---------------------------------------------------------------------
{
  log('desktop 1280×800')
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
  const { frames, errors } = watch(page)
  await page.goto(BASE)
  await page.waitForSelector('.status-live', { timeout: 30_000 })
  await page.waitForTimeout(7000)
  await page.screenshot({ path: `${OUT}/desktop.png` })
  const first = sinceLastSubscribe(frames, 0)
  check(first?.snapshot?.aircraft.length > 0, 'snapshot with aircraft after subscribe')
  check(first?.deltas.length > 0, 'deltas keep arriving')

  const start = frames.length
  await page.mouse.move(450, 420)
  for (let i = 0; i < 4; i++) {
    await page.mouse.wheel(0, -300)
    await page.waitForTimeout(250)
  }
  await page.mouse.down()
  await page.mouse.move(600, 500, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(7000)
  const zoomed = sinceLastSubscribe(frames, start)
  const area = (b) => (b[2] - b[0]) * (b[3] - b[1])
  check(zoomed && area(zoomed.bbox) < area(first.bbox), 'zoom + pan sends a new, smaller subscribe bbox')
  check(zoomed?.snapshot !== undefined, 'new subscribe answered with a snapshot')
  check(zoomed?.outside.length === 0, 'no aircraft outside the subscribed bbox')
  await page.screenshot({ path: `${OUT}/desktop-zoomed.png` })

  // the production build does not expose window.__map: map-level checks need the dev server
  const devMap = await page.evaluate(() => '__map' in window)
  const target = devMap ? await aircraftOnScreen(page) : null
  if (devMap) check(target !== null, 'an aircraft is rendered on screen')
  else log('  skip map-level checks (no window.__map: production build)')
  if (target) {
    await page.mouse.click(target.x, target.y)
    await page.waitForSelector('.details h2')
    const loaded = await page
      .waitForFunction(() => [...document.querySelectorAll('.facts dd')].every((d) => d.textContent !== '…'), null, { timeout: 10_000 })
      .then(() => true, () => false)
    check(loaded, 'details panel loads REST fields (province, nearest airport, terrain)')
    const agl = await page.evaluate(() => {
      const dt = [...document.querySelectorAll('.facts dt')].find((d) => d.textContent === 'Above ground')
      return dt?.nextElementSibling?.textContent ?? null
    })
    check(agl !== null && /( m · |on ground)/.test(agl), `details show height above ground (${agl})`)
    log('  details:', (await page.textContent('.details')).replace(/\s+/g, ' ').slice(0, 200))
    const state = await page.evaluate((id) => window.__map.getFeatureState({ source: 'aircraft', id }), target.id)
    check(state.selected === true, 'selected aircraft has feature-state selected')
    await page.evaluate((t) => window.__map.jumpTo({ center: window.__map.unproject([t.x, t.y]), zoom: 11 }), target)
    await page.waitForTimeout(3000)
    await page.screenshot({ path: `${OUT}/desktop-selected.png` })
    const track = await sourceLines(page, 'track')
    check(track.lines === 1 && track.points >= 2, `selected aircraft has a track line (${track.points} points)`)
  }
  await terrainChecks(page, devMap)
  if (devMap) {
    await page.evaluate(() => window.__map.jumpTo({ center: [28.9, 41.0], zoom: 6.5 }))
    await page.waitForTimeout(2500)
    const tails = await sourceLines(page, 'tails')
    check(tails.lines > 0, `live aircraft have tails (${tails.lines} lines)`)
    await historyChecks(page, frames)
    await zoneChecks(page, frames)
  }
  check(errors.length === 0, `no console errors ${errors.length ? JSON.stringify(errors) : ''}`)
  await page.close()
}

// ---- mobile ----------------------------------------------------------------------
{
  log('mobile 375×812')
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 })
  const page = await context.newPage()
  const { errors } = watch(page)
  await page.goto(BASE)
  await page.waitForSelector('.status-live', { timeout: 30_000 })
  await page.waitForTimeout(4000)
  await page.screenshot({ path: `${OUT}/mobile.png` })
  const [scrollWidth, clientWidth] = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth])
  check(scrollWidth <= clientWidth, `no horizontal overflow (${scrollWidth} ≤ ${clientWidth})`)
  check((await page.getAttribute('.panel', 'class')).includes('collapsed'), 'bottom sheet starts collapsed')
  const zoomVisible = await page.evaluate(() => {
    const b = document.querySelector('.maplibregl-ctrl-zoom-in').getBoundingClientRect()
    return document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)?.closest('.maplibregl-ctrl-zoom-in') !== null
  })
  check(zoomVisible, 'zoom buttons are not covered by other controls')

  const target = (await page.evaluate(() => '__map' in window)) ? await aircraftOnScreen(page) : null
  if (target) {
    await page.touchscreen.tap(target.x, target.y)
    const selected = await page.waitForSelector('.details h2', { timeout: 5000 }).then(() => true, () => false)
    check(selected, 'tapping an aircraft opens its details')
    check((await page.getAttribute('.panel', 'class')).includes('expanded'), 'selecting expands the sheet')
    await page.waitForTimeout(1500)
    await page.screenshot({ path: `${OUT}/mobile-details.png` })
  }
  const before = (await page.getAttribute('.panel', 'class')).includes('expanded')
  await page.tap('.sheet-handle')
  await page.waitForTimeout(300)
  const after = (await page.getAttribute('.panel', 'class')).includes('expanded')
  check(before !== after, 'handle toggles the sheet')
  check(errors.length === 0, `no console errors ${errors.length ? JSON.stringify(errors) : ''}`)
}

await browser.close()
log(failures.length ? `\n${failures.length} check(s) failed` : '\nall checks passed')
process.exit(failures.length ? 1 : 0)
