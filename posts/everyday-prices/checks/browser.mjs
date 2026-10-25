// Optional browser verification. The default tests the self-contained review copy offline.
// Use --url https://... (or BP7_TEST_URL) explicitly to test a published chart instead.
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
const args = process.argv.slice(2);
assert(args.length === 0 || (args.length === 2 && args[0] === '--url'),
  'Usage: node checks/browser.mjs [--url https://published-page]');
const publicUrl = args[1] || process.env.BP7_TEST_URL;
if (publicUrl) assert.equal(new URL(publicUrl).protocol, 'https:', 'An explicit public target must use HTTPS.');
const preview = join(post, 'preview/Blog-Post-7.html');
const target = publicUrl ? new URL(publicUrl).href : pathToFileURL(preview).href;
const count = summary.series.length;
assert.equal(count, 6, 'This check expects the six configured CPI series.');
const benchmark = summary.series.filter(s => s.category_rank === undefined);
assert.equal(benchmark.length, 1);
const peak = summary.peak_annual_inflation.find(s => s.series_id === benchmark[0].series_id);
assert(peak, 'The overall inflation peak is missing from the saved summary.');
const month = date => new Intl.DateTimeFormat('en-US', {
  month: 'short', year: 'numeric', timeZone: 'UTC'
}).format(new Date(date));
const ranked = summary.series.filter(s => s.category_rank !== undefined)
  .sort((a, b) => a.category_rank - b.category_rank);
const titles = {
  cumulative: `${ranked[0].label} rose most since Dec 2019;${ranked[1].label.toLowerCase()} and ${ranked[2].label.toLowerCase()} were next`,
  annual: `Overall annual inflation fell from${peak.peak_annual_pct.toFixed(1)}% (${month(peak.peak_date)}) to ${benchmark[0].annual_pct.toFixed(1)}% (${month(summary.endpoint)})`
};
const axisTitles = {
  cumulative: 'Price change since Dec 2019', annual: 'Price change from 12 months earlier'
};
const key = metric => metric === 'cumulative' ? 'cumulative_pct' : 'annual_pct';
const expectedLabels = metric => summary.series.map(s => `${s.label} ${s[key(metric)].toFixed(1)}%`);
const compact = text => text.replace(/<[^>]+>/g, '').replace(/\s+/g, '');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ executablePath: chrome, headless: true });
const context = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
await context.route('**/*', route => {
  const protocol = new URL(route.request().url()).protocol;
  const allowed = publicUrl ? ['https:', 'data:', 'blob:'] : ['file:', 'data:', 'blob:'];
  return allowed.includes(protocol) ? route.continue() : route.abort();
});
const page = await context.newPage();
const errors = [];
const failedRequests = [];
page.on('pageerror', e => errors.push({ message: e.message, stack: e.stack?.slice(0, 150) }));
page.on('requestfailed', request => failedRequests.push({ url: request.url(), reason: request.failure()?.errorText }));
const checks = [];
const presentations = [];
const visible = trace => trace.visible !== 'legendonly' && trace.visible !== false;

async function assertTraceValues(plot, metric) {
  const state = await plot.evaluate(el => ({
    data: el.data.map(t => ({ y: Array.from(t.y), x: Array.from(t.x), text: Array.from(t.text || []),
      visible: t.visible, legendgroup: t.legendgroup, mode: t.mode, showlegend: t.showlegend })),
    version: el._fullLayout.uirevision, title: el._fullLayout.title.text,
    axis: el._fullLayout.yaxis.title.text, ticksuffix: el._fullLayout.yaxis.ticksuffix
  }));
  assert.equal(state.data.length, count * 2, 'Expected six data lines and six label traces.');
  assert.equal(state.version, 'price-explorer-v2');
  assert.equal(compact(state.title), compact(titles[metric]), 'The finding title does not match the saved results.');
  assert.equal(state.axis, axisTitles[metric]);
  assert.equal(state.ticksuffix, '%');
  for (let i = 0; i < count; i++) {
    const line = state.data[i], label = state.data[i + count];
    const expected = summary.series[i][key(metric)];
    assert(Math.abs(line.y.at(-1) - expected) < 1e-8, `Wrong ${metric} endpoint for ${summary.series[i].label}.`);
    assert.equal(label.mode, 'lines+text');
    assert.equal(label.showlegend, false);
    assert.equal(line.legendgroup, summary.series[i].label);
    assert.equal(label.legendgroup, line.legendgroup, 'The end label must share its line’s legend group.');
    assert.equal(visible(label), visible(line), 'An end label is visible while its line is hidden, or vice versa.');
    assert.equal(label.text.at(-1), expectedLabels(metric)[i], 'An end label has the wrong name, value, or rounding.');
    assert.equal(Date.parse(label.x[0]), Date.parse(summary.endpoint));
    assert(Date.parse(label.x.at(-1)) > Date.parse(summary.endpoint), 'The end label must follow the last data month.');
    assert(Math.abs(label.y[0] - expected) < 1e-8, 'A label’s leader line does not start at the data endpoint.');
    assert(label.y.every(Number.isFinite), 'An end label has a non-finite position.');
  }
  return state;
}

async function assertPresentation(plot, metric, viewportName) {
  const expected = expectedLabels(metric);
  const geometry = await plot.evaluate((el, labels) => {
    const rect = node => {
      if (!node) return null;
      const r = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height,
        text: node.textContent.trim(), visible: r.width > 0 && r.height > 0 &&
          style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' };
    };
    const labelNodes = Array.from(el.querySelectorAll('.scatterlayer .textpoint text'))
      .filter(node => labels.includes(node.textContent.trim()));
    return {
      plot: rect(el), title: rect(el.querySelector('.gtitle')), title_count: el.querySelectorAll('.gtitle').length,
      menu: rect(el.querySelector('.updatemenu-header')),
      subtitle: rect(el.querySelector('.annotation-text')),
      reset: rect(el.querySelector('.rangeselector')),
      labels: labelNodes.map(rect),
      viewport: innerWidth, document: document.documentElement.scrollWidth
    };
  }, expected);
  const name = `${viewportName} ${metric}`;
  assert(geometry.document <= geometry.viewport + 1, `${name}: the page overflows the viewport.`);
  assert.equal(geometry.title_count, 1, `${name}: expected one finding title.`);
  const elements = ['title', 'menu', 'subtitle', 'reset'].map(k => [k, geometry[k]]);
  assert.equal(geometry.labels.length, count, `${name}: not all six endpoint labels were rendered.`);
  assert.deepEqual(geometry.labels.map(r => r.text).sort(), [...expected].sort());
  elements.push(...geometry.labels.map((r, i) => [`label ${r.text || i}`, r]));
  const overlaps = (a, b) => Math.min(a.right, b.right) - Math.max(a.x, b.x) > 1 &&
    Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > 1;
  for (const [label, r] of elements) {
    assert(r?.visible, `${name}: ${label} is not visible.`);
    assert(r.x >= geometry.plot.x - 2 && r.right <= geometry.plot.right + 2 &&
      r.y >= geometry.plot.y - 2 && r.bottom <= geometry.plot.bottom + 2,
    `${name}: ${label} is clipped outside the chart.`);
  }
  for (let i = 0; i < elements.length; i++) {
    for (let j = i + 1; j < elements.length; j++) {
      assert(!overlaps(elements[i][1], elements[j][1]),
        `${name}: ${elements[i][0]} overlaps ${elements[j][0]}.`);
    }
  }
  presentations.push({ viewport: viewportName, metric, title: geometry.title.text,
    title_count: geometry.title_count, end_label_count: geometry.labels.length,
    end_labels: geometry.labels.map(r => r.text), visible_and_within_chart: true,
    no_title_control_or_label_overlap: true, geometry });
}

async function selectMetric(plot, metric) {
  await plot.locator('.updatemenu-header').click();
  await plot.getByText(metric === 'annual' ? 'Year-over-year' : 'Since Dec 2019', { exact: true }).click();
  await page.waitForFunction(title => document.querySelector('.js-plotly-plot')?._fullLayout.yaxis.title.text === title,
    axisTitles[metric]);
  await assertTraceValues(plot, metric);
}

try {
  await page.goto(target);
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot')?.data?.length === 12);
  const plot = page.locator('.js-plotly-plot');
  await plot.scrollIntoViewIfNeeded();
  const original = await plot.evaluate(el => ({ range: el._fullLayout.xaxis.range }));
  await assertTraceValues(plot, 'cumulative');
  await assertPresentation(plot, 'cumulative', 'desktop');
  checks.push('All six cumulative endpoints, rounded end labels, leader-line anchors, and the finding title match saved results.');
  const legends = plot.locator('.legend .traces');
  await legends.nth(1).click();
  await page.waitForFunction(() => {
    const d = document.querySelector('.js-plotly-plot').data;
    return d[1].visible === 'legendonly' && d[7].visible === 'legendonly';
  });
  await selectMetric(plot, 'annual');
  const annual = await assertTraceValues(plot, 'annual');
  assert.equal(annual.data[1].visible, 'legendonly');
  checks.push('The selector updates all six annual lines, labels, and the finding title while preserving hidden categories and their labels.');
  await legends.nth(1).click();
  await page.waitForFunction(() => {
    const d = document.querySelector('.js-plotly-plot').data;
    return d[1].visible !== 'legendonly' && d[7].visible !== 'legendonly';
  });
  await assertTraceValues(plot, 'annual');
  await assertPresentation(plot, 'annual', 'desktop');
  // Finish the single-click gesture before starting a separate double-click.
  await page.waitForTimeout(400);
  await legends.nth(1).dblclick({ delay: 80 });
  await page.waitForFunction(() => {
    const d = document.querySelector('.js-plotly-plot').data;
    const shown = d.map((t, i) => t.visible !== 'legendonly' && t.visible !== false ? i : -1).filter(i => i >= 0);
    return shown.length === 2 && shown[0] === 1 && shown[1] === 7;
  });
  await assertTraceValues(plot, 'annual');
  const isolatedRange = await plot.evaluate(el => el._fullLayout.yaxis.range);
  assert(isolatedRange[1] < 20, 'The isolated grocery view should rescale to reveal its variation.');
  checks.push('Double-click isolates the selected grocery series and its end label, hiding the other five pairs.');
  const hover = await plot.evaluate(el => {
    const x = el._fullLayout.xaxis, y = el._fullLayout.yaxis;
    return { x: x._offset + x.d2p('2024-12-01') - 1,
      y: y._offset + y.d2p(el.data[1].y.at(-1)) };
  });
  const box = await plot.boundingBox();
  await page.mouse.move(box.x + hover.x, box.y + hover.y);
  await page.waitForSelector('.hoverlayer .hovertext');
  const hoverText = await plot.locator('.hoverlayer').textContent();
  const groceries = summary.series[1];
  assert(hoverText.includes(groceries.label) && hoverText.includes(month(summary.endpoint)) &&
    hoverText.includes(`${groceries.cumulative_pct.toFixed(1)}%`) && hoverText.includes(`${groceries.annual_pct.toFixed(1)}%`));
  checks.push('Mouse hover displays the saved endpoint month and both computed grocery measures.');
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
  await selectMetric(plot, 'cumulative');
  await legends.nth(1).dblclick({ delay: 80 });
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').data.every(t => t.visible !== 'legendonly' && t.visible !== false));
  await assertTraceValues(plot, 'cumulative');
  checks.push('Switching back restores cumulative values and labels; the legend restores all six line-label pairs.');
  await mkdir(join(post, 'preview'), { recursive: true });
  await page.screenshot({ path: join(post, 'preview/desktop.png'), fullPage: true });
  await plot.screenshot({ path: join(post, 'preview/chart-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => document.querySelector('.js-plotly-plot').getBoundingClientRect().width < 400);
  await plot.scrollIntoViewIfNeeded();
  await assertPresentation(plot, 'cumulative', 'mobile');
  await plot.screenshot({ path: join(post, 'preview/chart-mobile.png') });
  await selectMetric(plot, 'annual');
  await assertPresentation(plot, 'annual', 'mobile');
  const mobile = await page.evaluate(() => ({
    viewport: innerWidth, document: document.documentElement.scrollWidth,
    plot: document.querySelector('.js-plotly-plot').getBoundingClientRect().width
  }));
  checks.push('At 1200px and 390px, both finding titles, all six end labels, the subtitle, and controls fit the chart without overlapping; the mobile selector works.');
  assert.equal(errors.length, 0, JSON.stringify({ errors, failedRequests }));
  const articleText = await page.locator('main').innerText();
  assert(!articleText.includes('`r '), 'Unresolved inline R was rendered.');
  if (!publicUrl) assert(articleText.includes('Unpublished draft for review'));
  checks.push(publicUrl ? 'The explicitly requested HTTPS article loads without page JavaScript errors or unresolved inline R.' :
    'Self-contained HTML loads offline without page JavaScript errors or unresolved inline R.');
  const report = { status: 'passed', tested_at_utc: new Date().toISOString(), browser: await browser.version(),
    target: { mode: publicUrl ? 'published_https' : 'offline_preview', url: target },
    chart_version: 'price-explorer-v2', data_line_count: count, end_label_trace_count: count,
    desktop_viewport: { width: 1200, height: 900 }, mobile_viewport: mobile,
    request_policy: publicUrl ? 'HTTPS, data, and blob requests allowed; this is not an offline test' :
      'All HTTP and HTTPS requests blocked',
    presentation_checks: presentations, checks, page_errors: errors, failed_requests: failedRequests,
    limits: ['Mouse controls tested; no touchscreen device or screen-reader audit performed.'] };
  await writeFile(join(post, 'results/browser-validation.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: 'failed', target, errors, failedRequests, completed_checks: checks }));
  await mkdir(join(post, 'preview'), { recursive: true });
  await page.screenshot({ path: join(post, 'preview/browser-check-failure.png'), fullPage: true });
  throw error;
} finally {
  await browser.close();
}
