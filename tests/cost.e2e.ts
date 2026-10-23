import { beforeEach, describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';
import { readFile } from 'node:fs/promises';
import { isolateNetwork, isPng } from './helpers.ts';

describe('留学费用计算器', () => {
  beforeEach(async ({ browser }) => {
    await isolateNetwork(browser);
    await browser.onDialog('accept');
  });

  test('默认美国硕士：三档预估与费用明细', async ({ app, screen }) => {
    await app.open('/cost');

    // US master (授课型), unsure school, NYC, dorm, 1.5 years:
    // total medium = 540000 + 334368 + 2000 + 15000 = 891368
    await expect(screen.getByText('71.0 万')).toBeVisible();
    await expect(screen.getByText('89.1 万')).toBeVisible();
    await expect(screen.getByText('116.7 万')).toBeVisible();

    // Breakdown of the medium tier.
    await expect(screen.getByText('54.0 万')).toBeVisible(); // 学费
    await expect(screen.getByText('33.4 万')).toBeVisible(); // 生活费
    await expect(screen.getByText('2,000 元')).toBeVisible(); // 申请阶段费用
    await expect(screen.getByText('1.5 万')).toBeVisible(); // 隐性费用

    // Budget tier is above 50 万 RMB, so the CTA shows the premium pitch.
    await expect(screen.getByText('预算有限？不确定选哪个国家？')).toBeVisible();
    await expect(screen.getByRole('button', '免费规划')).toBeVisible();
  });

  test('切换国家会重置城市与学制，报告随之更新', async ({ app, screen }) => {
    await app.open('/cost');

    await screen.getByRole('button', { name: /英国/ }).tap();

    // City resets to the first UK city; duration resets to the UK master default (1 year).
    await expect(screen.getByRole('combobox').nth(0)).toHaveValue('uk-london');
    await expect(screen.getByRole('spinbutton')).toHaveValue('1');
    // medium = 227500 + 222768 + 1500 + 12000 = 463768
    await expect(screen.getByText('46.4 万')).toBeVisible();

    // Below the 50 万 threshold, the CTA switches copy.
    await expect(screen.getByText('如何用更少的钱获得更好的录取？')).toBeVisible();
    await expect(screen.getByRole('button', '获取免费指南')).toBeVisible();

    // Switching degree resets duration to the UK bachelor default (3 years).
    await screen.getByRole('combobox').nth(1).selectOption({ label: '本科' });
    await expect(screen.getByRole('spinbutton')).toHaveValue('3');
  });

  test('切换学校类型与住宿偏好会改变预估', async ({ app, screen }) => {
    await app.open('/cost');

    // Public school: tuition 40000*1.5*7.2 = 432000
    await screen.getByRole('combobox').nth(2).selectOption({ label: '公立' });
    await expect(screen.getByText('43.2 万')).toBeVisible();
    // total medium = 432000 + 334368 + 2000 + 15000 = 783368
    await expect(screen.getByText('78.3 万')).toBeVisible();

    // Solo housing: living = (1800*1.5 + 600*1.3)*12*1.5*7.2 = 451008
    await screen.getByRole('button', '校外独住').tap();
    await expect(screen.getByText('45.1 万')).toBeVisible();
    // total medium = 432000 + 451008 + 2000 + 15000 = 900008
    await expect(screen.getByText('90.0 万')).toBeVisible();
  });

  test('学制支持键盘输入小数（2.5 年）', async ({ app, screen }) => {
    await app.open('/cost');

    const duration = screen.getByRole('spinbutton');
    await duration.fill('2');
    // Typing the decimal point must not wipe it: the field ends at 2.5.
    await duration.pressSequentially('.5');
    await expect(duration).toHaveValue('2.5');

    // tuition 50000*2.5*7.2 = 900000; living 2580*12*2.5*7.2 = 557280;
    // total medium = 900000 + 557280 + 2000 + 15000 = 1474280
    await expect(screen.getByText('90.0 万')).toBeVisible();
    await expect(screen.getByText('55.7 万')).toBeVisible();
    await expect(screen.getByText('147.4 万')).toBeVisible();
  });

  test('生成费用报告会下载 PNG 文件', async ({ app, screen, browser }) => {
    await app.open('/cost');

    const file = await browser.waitForDownload(() =>
      screen.getByRole('button', '生成费用报告').tap(),
    );
    const bytes = await readFile(file.absolutePath);
    expect(bytes.byteLength).toBeGreaterThan(1000);
    expect(isPng(bytes)).toBe(true);
  });
});
