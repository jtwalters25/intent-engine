/**
 * Screenshot capture script for Intent Engine demo
 *
 * Setup (one-time):
 *   cd frontend
 *   npm install -D playwright
 *   npx playwright install chromium
 *
 * Usage:
 *   node scripts/capture-screenshots.js           # headless
 *   node scripts/capture-screenshots.js --headed  # watch it run
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const BASE_URL = 'https://dist-pied-one-60.vercel.app';
const OUT_DIR  = path.resolve(__dirname, '../../docs/screenshots');
const HEADED   = process.argv.includes('--headed');
const DELAY    = 900; // ms — enough for CSS animations to finish

async function shot(page, name, fullPage = true) {
  await page.waitForTimeout(DELAY);
  const file = path.join(OUT_DIR, name);
  await page.screenshot({ path: file, fullPage });
  console.log(`  ✅  ${name}`);
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: !HEADED, slowMo: HEADED ? 400 : 0 });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page    = await context.newPage();

  console.log(`\n📸  Capturing screenshots → ${OUT_DIR}\n`);

  // ── 01 Intent Setup (homepage / step 0) ──────────────────────────────────
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await shot(page, '01-intent-setup.png');

  // ── 02 Curated Home – parent view (step 1) ───────────────────────────────
  await page.click('button:has-text("Start")');
  await shot(page, '02-curated-home.png');

  // ── 03 Kid Browse (Netflix hero + rows) ──────────────────────────────────
  await page.click('button:has-text("Preview as Kid")');
  await shot(page, '03-kid-browse.png');

  // Return to parent view before navigating further
  await page.click('button:has-text("Back to Parent View")');
  await page.waitForTimeout(500);

  // ── 04 Content Detail (step 2) ───────────────────────────────────────────
  await page.locator('.group.cursor-pointer').first().click();
  await shot(page, '04-content-detail.png');

  // Back to curated home
  await page.click('button:has-text("Back to Browse")');
  await page.waitForTimeout(500);

  // ── 05 PIN Modal ─────────────────────────────────────────────────────────
  await page.click('button:has-text("Parent Controls")');
  await page.waitForSelector('[role="dialog"]');
  await shot(page, '05-pin-modal.png', false);   // viewport only — modal is centered

  // ── 06 Parent Controls (step 3) ──────────────────────────────────────────
  await page.keyboard.type('1234');               // InputOTP is auto-focused
  await shot(page, '06-parent-controls.png');

  // ══════════════════════════════════════════════════════════════════════════
  //  DEMO PAGE SCREENSHOTS (/demo)
  // ══════════════════════════════════════════════════════════════════════════

  // ── 07 Demo Overview — Streaming / Bedtime ─────────────────────────────
  await page.goto(`${BASE_URL}/demo`, { waitUntil: 'networkidle' });
  await shot(page, '07-demo-overview.png', false);

  // ── 08 Scoring Formula — hover the first "After" item ──────────────────
  // The After column items have onHover; hover the first ranked card
  const afterCards = page.locator('h2:has-text("After")').locator('..').locator('.. >> div.space-y-2 >> div.relative');
  const firstAfterCard = afterCards.first();
  if (await firstAfterCard.count() > 0) {
    await firstAfterCard.hover();
    await page.waitForTimeout(DELAY);
  }
  await shot(page, '08-scoring-formula.png', false);

  // ── 09 Music Platform — Wind Down context ──────────────────────────────
  // Click the Music tab
  await page.click('button:has-text("Music")');
  await page.waitForTimeout(DELAY);
  await shot(page, '09-platform-music.png', false);

  // ── 10 E-Commerce Platform — Baby Shower context ───────────────────────
  // Click the E-Commerce tab
  await page.click('button:has-text("E-Commerce")');
  await page.waitForTimeout(DELAY);
  await shot(page, '10-platform-ecommerce.png', false);

  await browser.close();
  console.log(`\n🎉  Done — ${OUT_DIR}\n`);
})().catch(err => { console.error(err); process.exit(1); });
