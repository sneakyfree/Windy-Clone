// Headless browser walkthrough for Wave-11 hardening. Captures screenshots
// of the four main pages plus deep-link gateway entry.
//
// Assumes: API on :8400 (DEV_MODE=true so no auth header needed), web dev
// server on :5173.
//
// Run: node docs/hardening/screenshot.mjs

import { chromium } from 'playwright'
import fs from 'fs'
import path from 'path'

const ROOT = 'http://localhost:5173'
const OUT = path.resolve('docs/hardening/screenshots')
fs.mkdirSync(OUT, { recursive: true })

const targets = [
  { path: '/', slug: '01-root-redirects-to-legacy' },
  { path: '/legacy', slug: '02-legacy' },
  { path: '/discover', slug: '03-discover' },
  { path: '/studio', slug: '04-studio' },
  { path: '/my-clones', slug: '05-my-clones' },
  { path: '/settings', slug: '06-settings' },
  { path: '/?wc=' + encodeURIComponent('windyclone://discover'), slug: '07-deeplink-discover' },
  { path: '/?wc=' + encodeURIComponent('windyclone://order/abc-123'), slug: '08-deeplink-order' },
  { path: '/?wc=' + encodeURIComponent('windyclone://studio/../../etc/passwd'), slug: '09-deeplink-traversal-dropped' },
]

const consoleLogs = []

const browser = await chromium.launch({ headless: true })
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } })
const page = await ctx.newPage()

page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`))
page.on('pageerror', err => consoleLogs.push(`[pageerror] ${err.message}`))

const urls = []
for (const t of targets) {
  const url = ROOT + t.path
  console.log(`→ ${t.slug} :: ${url}`)
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 })
    // Let Vite chunks + hook states settle
    await page.waitForTimeout(800)
    await page.screenshot({ path: path.join(OUT, `${t.slug}.png`), fullPage: true })
    urls.push({ slug: t.slug, requestedPath: t.path, finalUrl: page.url() })
  } catch (err) {
    console.log(`  ✗ ${err.message}`)
    urls.push({ slug: t.slug, requestedPath: t.path, error: err.message })
  }
}

fs.writeFileSync(
  path.join(OUT, '_manifest.json'),
  JSON.stringify({ capturedAt: new Date().toISOString(), urls, consoleLogs }, null, 2),
)

await browser.close()
console.log(`✓ ${urls.length} screenshots in ${OUT}`)
