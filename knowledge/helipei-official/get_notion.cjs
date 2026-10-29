const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('https://aumarsdu.notion.site/c01e0e829f554d509464dcafa441e881');
  await page.waitForTimeout(5000);
  const text = await page.innerText('main');
  console.log(text);
  await browser.close();
})();
