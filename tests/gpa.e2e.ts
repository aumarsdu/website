import { beforeEach, describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';
import { readFile } from 'node:fs/promises';
import { isolateNetwork, isPng } from './helpers.ts';

const NAME_INPUT = '例如: 高等数学';
const CREDITS_INPUT = '学分';
const SCORE_INPUT = '成绩';

describe('GPA 换算器', () => {
  beforeEach(async ({ browser }) => {
    await isolateNetwork(browser);
    await browser.onDialog('accept');
  });

  test('空状态：默认一行空课程，GPA 与总学分为 0，删除不可用', async ({ app, screen }) => {
    await app.open('/gpa');

    await expect(screen.getByText('0.00')).toBeVisible();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(1);
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveValue('');
    await expect(screen.getByRole('button', { name: '删除课程' })).toBeDisabled();

    // GPA is 0, so the CTA card shows the entry-level message.
    await expect(screen.getByText('开始你的评估')).toBeVisible();
    await expect(screen.getByRole('button', '免费评估')).toBeVisible();
  });

  test('填入示例后可切换算法，GPA 与 CTA 文案联动', async ({ app, screen }) => {
    await app.open('/gpa');

    await screen.getByRole('button', '填入示例').tap();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(3);
    await expect(screen.getByDisplayValue('高等数学')).toBeVisible();
    await expect(screen.getByDisplayValue('大学物理')).toBeVisible();
    await expect(screen.getByDisplayValue('计算机网络')).toBeVisible();

    // 标准 4.0: (3.0*4 + 2.0*3 + 4.0*3) / 10 = 3.00
    await expect(screen.getByText('3.00')).toBeVisible();
    await expect(screen.getByText('10')).toBeVisible();
    await expect(screen.getByText('GPA 仍有提升空间')).toBeVisible();
    await expect(screen.getByRole('button', '查看逆袭方案')).toBeVisible();

    // 北大 4.0: (3.7*4 + 3.0*3 + 4.0*3) / 10 = 3.58
    await screen.getByRole('button', '北大 4.0').tap();
    await expect(screen.getByText('3.58')).toBeVisible();
    await expect(screen.getByText('GPA 表现良好')).toBeVisible();
    await expect(screen.getByRole('button', '定制背景提升方案')).toBeVisible();

    // 加拿大 4.3: (4.0*4 + 3.3*3 + 4.3*3) / 10 = 3.88
    await screen.getByRole('button', '加拿大 4.3').tap();
    await expect(screen.getByText('3.88')).toBeVisible();
    await expect(screen.getByText('你的 GPA 极具竞争力！')).toBeVisible();
    await expect(screen.getByRole('button', '获取选校报告')).toBeVisible();
  });

  test('手动录入成绩，可添加与删除课程行', async ({ app, screen }) => {
    await app.open('/gpa');

    await screen.getByPlaceholder(NAME_INPUT).fill('微积分');
    await screen.getByPlaceholder(CREDITS_INPUT).fill('3');
    await screen.getByPlaceholder(SCORE_INPUT).fill('90');
    await expect(screen.getByText('4.00')).toBeVisible();

    await screen.getByRole('button', '添加课程').tap();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(2);

    await screen.getByPlaceholder(CREDITS_INPUT).last().fill('2');
    await screen.getByPlaceholder(SCORE_INPUT).last().fill('80');
    // (4.0*3 + 3.0*2) / 5 = 3.60
    await expect(screen.getByText('3.60')).toBeVisible();

    await screen.getByRole('button', { name: '删除课程' }).last().tap();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(1);
    await expect(screen.getByText('4.00')).toBeVisible();
    await expect(screen.getByRole('button', { name: '删除课程' })).toBeDisabled();
  });

  test('清空后回到单行空状态', async ({ app, screen }) => {
    await app.open('/gpa');

    await screen.getByRole('button', '填入示例').tap();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(3);

    await screen.getByRole('button', '清空').tap();
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveCount(1);
    await expect(screen.getByPlaceholder(NAME_INPUT)).toHaveValue('');
    await expect(screen.getByPlaceholder(CREDITS_INPUT)).toHaveValue('');
    await expect(screen.getByText('0.00')).toBeVisible();
  });

  test('CTA 按钮可打开顾问二维码并返回', async ({ app, screen }) => {
    await app.open('/gpa');

    await screen.getByRole('button', '填入示例').tap();
    await screen.getByRole('button', '查看逆袭方案').tap();
    await expect(screen.getByText('添加顾问微信')).toBeVisible();
    await expect(screen.getByText('企微二维码')).toBeVisible();

    await screen.getByRole('button', '返回').tap();
    await expect(screen.getByText('GPA 仍有提升空间')).toBeVisible();
  });

  test('生成分享卡片会下载 PNG 文件', async ({ app, screen, browser }) => {
    await app.open('/gpa');
    await screen.getByRole('button', '填入示例').tap();

    const file = await browser.waitForDownload(() =>
      screen.getByRole('button', '生成分享卡片').tap(),
    );
    const bytes = await readFile(file.absolutePath);
    expect(bytes.byteLength).toBeGreaterThan(1000);
    expect(isPng(bytes)).toBe(true);
  });

  test('学分输入支持键盘输入小数（1.5）', async ({ app, screen }) => {
    await app.open('/gpa');

    const credits = screen.getByPlaceholder(CREDITS_INPUT);
    await credits.fill('1');
    // Typing the decimal point must not wipe it: the field ends at 1.5.
    await credits.pressSequentially('.5');
    await expect(credits).toHaveValue('1.5');

    await screen.getByPlaceholder(SCORE_INPUT).fill('90');
    await expect(screen.getByText('1.5')).toBeVisible();
    await expect(screen.getByText('4.00')).toBeVisible();
  });
});
