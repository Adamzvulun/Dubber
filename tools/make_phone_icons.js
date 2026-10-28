// node tools/make_phone_icons.js dubber/assets/logo.svg dubber/web/icons   (Playwright from Node, see docs/STATUS.md)
// Phone icons from dubber/assets/logo.svg: "any" = the rounded logo; maskable/apple = full-bleed square, mark centred
const { chromium } = require('playwright');
const fs = require('fs');
const [svgPath, out] = process.argv.slice(2);
const logo = fs.readFileSync(svgPath, 'utf8');
const mark = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#2F5BFF"/><g transform="translate(16 16) scale(0.72) translate(-16 -16)"><path d="M9 10h6a6 6 0 0 1 0 12H9z" fill="#fff"/><circle cx="23" cy="16" r="3" fill="#FF6369"/></g></svg>`;
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome' });
  for (const [name, svg, size] of [['icon-192.png', logo, 192], ['icon-512.png', logo, 512],
      ['maskable-512.png', mark, 512], ['apple-touch-icon.png', mark, 180]]) {
    const p = await b.newPage({ viewport: { width: size, height: size } });
    await p.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${svg}`);
    await p.screenshot({ path: `${out}/${name}`, omitBackground: true });
    await p.close();
  }
  await b.close();
})();
