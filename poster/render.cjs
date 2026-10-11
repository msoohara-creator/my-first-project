// Render poster.html to print-ready PNGs and a B3 PDF with headless Chromium.
//   node render.cjs            -> output/poster_B3.png (x8), output/poster_preview.png (x2), output/poster_B3.pdf
const path = require("path");
const fs = require("fs");
let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (e) {
  ({ chromium } = require("/opt/node22/lib/node_modules/playwright"));
}

const W = 546, H = 773;
const out = path.join(__dirname, "output");
const url = "file://" + path.join(__dirname, "poster.html") + "?render";

async function shot(browser, scale, file) {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "*{animation:none!important}" });
  await page.waitForTimeout(300);
  await page.locator("#poster").screenshot({ path: path.join(out, file) });
  await page.close();
}

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  await shot(browser, 8, "poster_B3.png");
  await shot(browser, 2, "poster_preview.png");

  // B3 PDF (364 x 515 mm) built from the high-resolution render
  const page = await browser.newPage();
  const png = fs.readFileSync(path.join(out, "poster_B3.png")).toString("base64");
  await page.setContent(
    `<style>@page{size:364mm 515mm;margin:0}html,body{margin:0}img{width:364mm;height:515mm;display:block}</style>` +
    `<img src="data:image/png;base64,${png}">`
  );
  await page.pdf({ path: path.join(out, "poster_B3.pdf"), width: "364mm", height: "515mm", printBackground: true });
  await browser.close();
  console.log("rendered to", out);
})();
