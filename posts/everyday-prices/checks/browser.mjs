// Optional browser verification of the actual self-contained review copy.
// Requires Playwright and a local Chrome installation; see README.md.
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve, join } from 'node:path';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const post = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const summary = JSON.parse(await readFile(join(post, 'results/summary.json'), 'utf8'));
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ executablePath: chrome, headless: true });
const context = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
await context.route('**/*', route => {
  const protocol = new URL(route.request().url()).protocol;
  return ['file:', 'data:', 'blob:'].includes(protocol) ? route.continue() : route.abort();
});
const page = await context.newPage();
const errors = [];
const failedRequests = [];
page.on('pageerror', e => errors.push({ message: e.message, stack: e.stack?.slice(0, 150) }));
page.on('requestfailed', request => failedRequests.push({ url: request.url(), reason: request.failure()?.errorText }));
const preview = join(post, 'preview/Blog-Post-7.html');
const checks = [];
try {
  await page.goto(pathToFileURL(preview).href);
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')?.data?.length === 6);
  const plot = page.locator('.js-plotly-plot');
  await plot.scrollIntoViewIfNeeded();
  const original = await plot.evaluate(el => ({
    y: el.data.map(t => t.y.at(-1)), range: el._fullLayout.xaxis.range,
    height: el.getBoundingClientRect().height
  }));
  for (let i = 0; i < 6; i++) assert(Math.abs(original.y[i] - summary.series[i].cumulative_pct) < 1e-8);
  checks.push('All six initial trace endpoints match the saved cumulative estimates.');
  const legends = plot.locator('.legend .traces');
  await legends.nth(1).click();
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').data[1].visible === 'legendonly');
  await plot.locator('.updatemenu-header').click();
  await plot.getByText('Year-over-year', { exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')._fullLayout.yaxis.title.text === 'Price change from 12 months earlier');
  const annual = await plot.evaluate(el => ({
    y: el.data.map(t => t.y.at(-1)), hidden: el.data[1].visible,
    title: el._fullLayout.yaxis.title.text, ticksuffix: el._fullLayout.yaxis.ticksuffix
  }));
  for (let i = 0; i < 6; i++) assert(Math.abs(annual.y[i] - summary.series[i].annual_pct) < 1e-8);
  assert.equal(annual.hidden, 'legendonly');
  assert.equal(annual.ticksuffix, '%');
  checks.push('The actual selector updates every annual series and axis label while preserving hidden categories.');
  await legends.nth(1).click();
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').data[1].visible !== 'legendonly');
  // Finish the single-click gesture before starting a separate double-click.
  await page.waitForTimeout(400);
  await legends.nth(1).dblclick({ delay: 80 });
  await page.waitForFunction(() => {
    const d = document.querySelector('.js-plotly-plot').data;
    return d[1].visible !== 'legendonly' && d.filter(t => t.visible !== 'legendonly').length === 1;
  });
  const isolatedRange = await plot.evaluate(el => el._fullLayout.yaxis.range);
  assert(isolatedRange[1] < 20, 'The isolated grocery view should rescale to reveal its variation.');
  checks.push('Double-click isolates the selected grocery series.');
  const hover = await plot.evaluate(el => {
    const x = el._fullLayout.xaxis, y = el._fullLayout.yaxis;
    return { x: x._offset + x.d2p('2024-12-01') - 1,
      y: y._offset + y.d2p(el.data[1].y.at(-1)) };
  });
  const box = await plot.boundingBox();
  await page.mouse.move(box.x + hover.x, box.y + hover.y);
  await page.waitForSelector('.hoverlayer .hovertext');
  const hoverText = await plot.locator('.hoverlayer').textContent();
  assert(hoverText.includes('Groceries') && hoverText.includes('Dec 2024') && hoverText.includes('27.6%') && hoverText.includes('1.8%'));
  checks.push('Mouse hover displays the correct month and both cumulative and annual grocery values.');
  await page.mouse.move(5, 5);
  const drag = await plot.locator('.nsewdrag').boundingBox();
  await page.mouse.move(drag.x + drag.width * 0.2, drag.y + drag.height * 0.3);
  await page.mouse.down();
  await page.mouse.move(drag.x + drag.width * 0.8, drag.y + drag.height * 0.7, { steps: 15 });
  await page.mouse.up();
  await page.waitForFunction(old => document.querySelector('.js-plotly-plot')._fullLayout.xaxis.range[0] !== old, original.range[0]);
  await plot.getByText('Reset dates', { exact: true }).click();
  await page.waitForFunction(() => {
    const r = document.querySelector('.js-plotly-plot')._fullLayout.xaxis.range;
    return Date.parse(r[0]) <= Date.parse('2019-12-02') && Date.parse(r[1]) >= Date.parse('2024-11-30');
  });
  checks.push('Drag zoom changes the date range and Reset dates restores the full window.');
  await plot.locator('.updatemenu-header').click();
  await plot.getByText('Since Dec 2019', { exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')._fullLayout.yaxis.title.text === 'Price change since Dec 2019');
  await legends.nth(1).dblclick({ delay: 80 });
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').data.every(t => t.visible !== 'legendonly'));
  const restored = await plot.evaluate(el => el.data.map(t => t.y.at(-1)));
  for (let i = 0; i < 6; i++) assert(Math.abs(restored[i] - summary.series[i].cumulative_pct) < 1e-8);
  checks.push('Switching back restores cumulative values and the legend can restore all categories.');
  await mkdir(join(post, 'preview'), { recursive: true });
  await page.screenshot({ path: join(post, 'preview/desktop.png'), fullPage: true });
  await plot.screenshot({ path: join(post, 'preview/chart-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').getBoundingClientRect().width < 400);
  const mobile = await page.evaluate(() => ({
    viewport: innerWidth, document: document.documentElement.scrollWidth,
    plot: document.querySelector('.js-plotly-plot').getBoundingClientRect().width
  }));
  assert(mobile.document <= mobile.viewport + 1, 'The page overflows the mobile viewport.');
  await plot.scrollIntoViewIfNeeded();
  await plot.screenshot({ path: join(post, 'preview/chart-mobile.png') });
  await plot.locator('.updatemenu-header').click();
  await plot.getByText('Year-over-year', { exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')._fullLayout.yaxis.title.text === 'Price change from 12 months earlier');
  checks.push('At 390px the page fits the viewport and the metric selector remains functional.');
  assert.equal(errors.length, 0, JSON.stringify({ errors, failedRequests }));
  const articleText = await page.locator('main').innerText();
  assert(!articleText.includes('`r '), 'Unresolved inline R was rendered.');
  assert(articleText.includes('Unpublished draft for review'));
  checks.push('Self-contained HTML loads offline without page JavaScript errors or unresolved inline R.');
  const report = { status: 'passed', browser: await browser.version(),
    desktop_viewport: { width: 1200, height: 900 }, mobile_viewport: mobile,
    offline_request_policy: 'All HTTP and HTTPS requests blocked', checks, page_errors: errors,
    limits: ['Mouse controls tested; no touchscreen device or screen-reader audit performed.'] };
  await writeFile(join(post, 'results/browser-validation.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  console.error(JSON.stringify({ errors, failedRequests }));
  await page.screenshot({ path: join(post, 'preview/browser-check-failure.png'), fullPage: true });
  throw error;
} finally {
  await browser.close();
}
