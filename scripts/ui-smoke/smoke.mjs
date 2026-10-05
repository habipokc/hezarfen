// Headless-browser acceptance check for the live map (Phase 5). Runs in the official
// Playwright image with host networking (`make ui-smoke`); screenshots go to $OUT.
//
// Checks: the socket goes live and gets a snapshot; after zoom + pan a new subscribe is sent
// and nothing outside its bbox arrives; clicking an aircraft selects it (feature-state) and
// loads REST details; at 375 px there is no horizontal overflow and the bottom sheet works;
// no console errors.
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
    check(loaded, 'details panel loads REST fields (province, nearest airport)')
    log('  details:', (await page.textContent('.details')).replace(/\s+/g, ' ').slice(0, 200))
    const state = await page.evaluate((id) => window.__map.getFeatureState({ source: 'aircraft', id }), target.id)
    check(state.selected === true, 'selected aircraft has feature-state selected')
    await page.evaluate((t) => window.__map.jumpTo({ center: window.__map.unproject([t.x, t.y]), zoom: 11 }), target)
    await page.waitForTimeout(3000)
    await page.screenshot({ path: `${OUT}/desktop-selected.png` })
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
