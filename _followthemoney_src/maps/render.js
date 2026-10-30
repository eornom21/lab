// Renders each SVG named on the command line to a PNG next to it, at 2x.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch();
  for (const f of process.argv.slice(2)) {
    const svg = fs.readFileSync(f, 'utf8');
    const m = svg.match(/viewBox="0 0 (\d+) (\d+)"/); const w = +m[1], h = +m[2];
    const p = await b.newPage({viewport: {width: w, height: h}, deviceScaleFactor: 1});
    await p.setContent(`<html><body style="margin:0">${svg}</body></html>`);
    await p.screenshot({path: f.replace(/\.svg$/, '.png'), clip: {x: 0, y: 0, width: w, height: h}});
    await p.close();
  }
  await b.close(); console.log('rendered', process.argv.length - 2);
})();
