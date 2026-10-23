import { beforeEach, describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';
import { isolateNetwork } from './helpers.ts';

describe('首页', () => {
  beforeEach(async ({ browser }) => {
    await isolateNetwork(browser);
  });

  test('展示三个工具入口，未上线的院校匹配器不可点击', async ({ app, screen }) => {
    await app.open('/');

    await expect(screen.getByRole('heading', { name: /河狸陪 留学工具箱/ })).toBeVisible();

    // Header navigation.
    await expect(screen.getByRole('link', '首页')).toBeVisible();
    await expect(screen.getByRole('link', 'GPA 换算器')).toBeVisible();
    await expect(screen.getByRole('link', '费用计算器')).toBeVisible();
    await expect(screen.getByRole('link', '时间线生成器')).toBeVisible();

    // Tool cards on the landing page.
    await expect(screen.getByRole('link').filter({ hasText: '开始换算' })).toBeVisible();
    await expect(screen.getByRole('link').filter({ hasText: '开始计算' })).toBeVisible();
    await expect(screen.getByRole('link').filter({ hasText: '开始生成' })).toBeVisible();

    // The fourth card is a placeholder, not a link.
    await expect(screen.getByText('敬请期待')).toBeVisible();
    await expect(screen.getByRole('link').filter({ hasText: '院校匹配器' })).toHaveCount(0);
  });

  test('点击首页卡片可进入对应工具页', async ({ app, screen, browser }) => {
    await app.open('/');

    await screen.getByRole('link').filter({ hasText: '开始换算' }).tap();
    await expect(browser).toHaveURL('/gpa');
    await expect(screen.getByRole('heading', { name: 'GPA 换算器', level: 1 })).toBeVisible();

    await app.open('/');
    await screen.getByRole('link').filter({ hasText: '开始计算' }).tap();
    await expect(browser).toHaveURL('/cost');
    await expect(screen.getByRole('heading', { name: '留学费用计算器', level: 1 })).toBeVisible();

    await app.open('/');
    await screen.getByRole('link').filter({ hasText: '开始生成' }).tap();
    await expect(browser).toHaveURL('/timeline');
    await expect(screen.getByRole('heading', { name: '申请时间线生成器', level: 1 })).toBeVisible();
  });

  test('顶部导航可在各工具页之间切换', async ({ app, screen, browser }) => {
    await app.open('/cost');
    await expect(browser).toHaveURL('/cost');

    await screen.getByRole('link', '时间线生成器').tap();
    await expect(browser).toHaveURL('/timeline');

    await screen.getByRole('link', 'GPA 换算器').tap();
    await expect(browser).toHaveURL('/gpa');

    await screen.getByRole('link', '首页').tap();
    await expect(browser).toHaveURL('/');
    await expect(screen.getByRole('heading', { name: /河狸陪 留学工具箱/ })).toBeVisible();
  });
});
