#!/usr/bin/env node
/*
 * End-to-end demo run in a real browser (Playwright, Chromium).
 *
 * Prerequisites:
 *   1. cd frontend && npm install && npm run build
 *   2. cd backend && TENDERFLOW_DATA_DIR=/tmp/tf-e2e uvicorn app.main:app --port 8765
 *      (use an empty data directory: the run expects a fresh install)
 *   3. Playwright with Chromium available to Node, e.g.:
 *        npm install --no-save playwright && npx playwright install chromium
 *
 * Run from the repository root:
 *   BASE_URL=http://127.0.0.1:8765 node scripts/e2e_demo.cjs
 *
 * It walks the whole demo (sample project → review → mapping → generate → instruction edit → manual price
 * → validation fixes → DOCX export → download) and also the real upload path, asserting on what the UI
 * shows, and saves screenshots to docs/screenshots/ (override with SCREENSHOT_DIR).
 * Exit code 0 means every step passed.
 */
const path = require('node:path')
const fs = require('node:fs')

function loadPlaywright() {
  const candidates = ['playwright', path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright')]
  for (const c of candidates) {
    try {
      return require(c)
    } catch {
      /* try next */
    }
  }
  console.error('Playwright is not installed. Run: npm install --no-save playwright && npx playwright install chromium')
  process.exit(2)
}

const { chromium } = loadPlaywright()
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8765'
const ROOT = path.join(__dirname, '..')
const SHOTS = process.env.SCREENSHOT_DIR || path.join(ROOT, 'docs', 'screenshots')
const SAMPLES = path.join(ROOT, 'samples')
fs.mkdirSync(SHOTS, { recursive: true })

let step = 0
function log(msg) {
  step += 1
  console.log(`✓ ${String(step).padStart(2, '0')} ${msg}`)
}

async function shot(page, name, fullPage = false) {
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage })
}

async function main() {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
  const page = await context.newPage()
  const consoleErrors = []
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
  page.on('pageerror', (e) => consoleErrors.push(String(e)))

  // 1. Overview
  await page.goto(`${BASE}/#/`)
  await page.getByRole('heading', { name: /Welcome to TenderFlow/ }).waitFor()
  await page.getByText('Backend connected').waitFor()
  log('Overview loads and the backend is connected')
  await shot(page, '01-overview')

  // 2. Sample project → extraction review
  await page.getByRole('button', { name: 'Try the sample project' }).click()
  await page.getByRole('heading', { name: 'Review extracted data' }).waitFor()
  await page.getByText('NPI/PROC/2026/017').first().waitFor({ state: 'attached' }).catch(() => {})
  const refInput = page.getByLabel('Tender reference')
  if ((await refInput.inputValue()) !== 'NPI/PROC/2026/017') throw new Error('Tender reference was not extracted')
  await page.getByText('Conflict', { exact: true }).first().waitFor()
  log('Sample tender parsed: reference extracted, deadline conflict shown')
  await page.locator('.evidence .evidence-block.focus').first().waitFor()
  await shot(page, '02-extraction-review')

  // Resolve the conflict, confirm the rest
  await page.getByRole('group', { name: /Conflicting values for Submission deadline/ }).getByRole('button', { name: 'Use this' }).first().click()
  await page.getByText('Chosen by you from 2 conflicting values', { exact: false }).waitFor()
  log('Deadline conflict resolved by choosing a candidate')
  await page.getByRole('button', { name: /Confirm all found values/ }).click()
  await page.getByText('Confirmed all found values').waitFor()
  const addressCard = page.locator('.field-card', { has: page.getByLabel('Issuer address') })
  await addressCard.getByRole('button', { name: 'Confirm' }).click()
  await addressCard.getByText('Confirmed', { exact: true }).waitFor()
  log('All found values confirmed (including the needs-review address)')

  // 3. Mapping
  await page.getByRole('button', { name: /Mark as reviewed & continue/ }).click()
  await page.getByRole('heading', { name: 'Map quotation data to your template' }).waitFor()
  log('Mapping step shows template fields')
  await shot(page, '03-mapping')

  // 4. Generate → editor
  await page.getByRole('button', { name: /Confirm mapping & generate quotation/ }).click()
  await page.getByRole('article', { name: 'Quotation preview' }).waitFor()
  await shot(page, '04-editor')
  // The draft rendered inside the user's own DOCX template (docx-preview, under the app's CSP)
  await page.getByRole('button', { name: 'In your template' }).click()
  const rendered = page.locator('.docx-render .docx-wrapper section').first()
  await rendered.waitFor({ timeout: 20000 })
  if (!(await page.locator('.docx-render').first().innerText()).includes('NPI/PROC/2026/017')) {
    throw new Error('The template preview does not show the tender reference')
  }
  await shot(page, '11-template-preview')
  await page.getByRole('button', { name: 'Editable draft' }).click()
  log('Quotation generated; editor and in-template preview render')

  // 5. Natural-language instruction with preview and confirmation
  await page.getByLabel('Instruction', { exact: true }).fill('Change the delivery period to 30 days.')
  await page.getByRole('button', { name: /Preview change/ }).click()
  await page.getByText('Proposed change').waitFor()
  await page.getByText('Within 30 days of the issuance of the purchase order').first().waitFor()
  const apply = page.getByRole('button', { name: 'Apply change' })
  if (await apply.isEnabled()) throw new Error('Apply must be disabled until the material change is confirmed')
  await shot(page, '05-instruction-preview')
  await page.getByLabel('I have checked these values and want to apply them.').check()
  await apply.click()
  await page.getByText('Change applied — Undo is available').waitFor()
  log('Instruction previewed, confirmation required, then applied')

  // 6. Manual price for the item that had no price
  await page.getByRole('button', { name: 'Add Item 4 unit price' }).click()
  await page.getByLabel('Item 4 unit price').fill('95000')
  await page.getByLabel('Item 4 unit price').press('Enter')
  await page.getByRole('button', { name: /Edit Item 4 amount: 95,000.00/ }).waitFor()
  log('Missing price entered manually; amount recalculated')

  // 7. Validation and quick fixes
  await page.getByRole('button', { name: 'Review & export' }).click()
  await page.getByRole('heading', { name: 'Validate and export' }).waitFor()
  await shot(page, '06-validation')
  for (const name of ['Use PKR', 'Confirm matched prices', 'Confirm the terms']) {
    const btn = page.getByRole('button', { name })
    if (await btn.count()) {
      await btn.first().click()
      await page.getByText(/^Done: /).first().waitFor()
      await page.waitForTimeout(300)
    }
  }
  log('Quick fixes applied (currency, matched prices, terms)')
  // Acknowledge remaining warnings
  for (let i = 0; i < 10; i++) {
    const ack = page.getByRole('button', { name: 'Acknowledge', exact: true })
    if ((await ack.count()) === 0) break
    await ack.first().click()
    await page.waitForTimeout(400)
  }
  await page.getByText('Ready to export').first().waitFor()
  log('All warnings reviewed — status is Ready to export')

  // 8. Export DOCX and download it
  await page.getByRole('button', { name: /^Export DOCX$/ }).click()
  await page.getByText(/\.docx created/).waitFor()
  await shot(page, '07-export')
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Download' }).first().click()])
  const target = path.join(SHOTS, '..', 'e2e-export.docx')
  await download.saveAs(target)
  const bytes = fs.readFileSync(target)
  if (bytes.subarray(0, 2).toString() !== 'PK' || !bytes.includes(Buffer.from('word/document.xml'))) {
    throw new Error('Downloaded file is not a valid DOCX')
  }
  fs.unlinkSync(target)
  // The exported file itself can be previewed in the browser
  await page.getByRole('button', { name: 'Preview file' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.locator('.docx-render .docx-wrapper section').first().waitFor({ timeout: 20000 })
  if (!(await dialog.innerText()).includes('NPI/PROC/2026/017')) throw new Error('Export preview is missing the tender reference')
  await dialog.getByRole('button', { name: 'Close dialog' }).click()
  log(`Exported, previewed and downloaded a valid DOCX (${bytes.length} bytes)`)

  // 9. Real upload path through the file inputs
  await page.goto(`${BASE}/#/new`)
  await page.getByRole('heading', { name: 'Add your source documents' }).waitFor()
  await page.locator('input[type=file]').nth(0).setInputFiles(path.join(SAMPLES, 'sample_tender_network_equipment.docx'))
  await page.getByText('sample_tender_network_equipment.docx').first().waitFor({ timeout: 20000 })
  await page.locator('input[type=file]').nth(1).setInputFiles(path.join(SAMPLES, 'sample_quotation_template.xlsx'))
  await page.getByText('sample_quotation_template.xlsx').first().waitFor({ timeout: 20000 })
  await page.getByText('5 line items found').waitFor()
  log('Uploaded a DOCX tender and an XLSX template through the UI')
  await shot(page, '08-upload')
  // Unsupported file is rejected with a clear message
  const bad = path.join(SHOTS, '..', 'not-a-tender.png')
  fs.writeFileSync(bad, Buffer.from('89504e470d0a1a0a', 'hex'))
  await page.locator('input[type=file]').nth(2).setInputFiles(bad)
  await page.getByText(/Images are not supported/).waitFor()
  fs.unlinkSync(bad)
  log('Unsupported file type rejected with an explanation')

  // 10. Library pages render real data
  await page.goto(`${BASE}/#/projects`)
  await page.getByRole('heading', { name: 'My work' }).waitFor()
  await page.getByText('Sample: IT network equipment tender').first().waitFor()
  await shot(page, '09-my-work')
  await page.goto(`${BASE}/#/settings`)
  await page.getByRole('heading', { name: 'Settings & privacy' }).waitFor()
  await shot(page, '10-settings')
  log('My work and Settings pages render')

  if (consoleErrors.length) {
    console.error('Browser console errors:\n' + consoleErrors.join('\n'))
    throw new Error('The browser reported console errors')
  }
  await browser.close()
  console.log(`\nAll ${step} end-to-end steps passed. Screenshots: ${path.relative(ROOT, SHOTS)}`)
}

main().catch((err) => {
  console.error(`✗ step ${step + 1} failed: ${err.message}`)
  process.exit(1)
})
