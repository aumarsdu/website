import { beforeEach, describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';
import type { Screen } from 'e2e';
import { isolateNetwork } from './helpers.ts';

const GENERATE_BUTTON = '一键生成专属时间线';
const REGENERATE_BUTTON = '重新生成时间线';

// Form selects, in DOM order. 当前年级 only renders after 申请层级 is chosen;
// 申请轮次 only for 本科.
const select = (screen: Screen, index: number) => screen.getByRole('combobox').nth(index);

async function fillAndGenerate(
  screen: Screen,
  level: '本科' | '硕士',
  grade: string,
  major: string,
  country: string = '美国',
) {
  await select(screen, 0).selectOption({ label: country });
  await select(screen, 1).selectOption({ label: level });
  await select(screen, 2).selectOption({ label: grade });
  await select(screen, 3).selectOption({ label: major });
  await screen.getByRole('button', GENERATE_BUTTON).tap();
}

describe('申请时间线生成器', () => {
  beforeEach(async ({ browser }) => {
    await isolateNetwork(browser);
  });

  test('必填未选时生成按钮禁用，年级选择按层级动态出现', async ({ app, screen }) => {
    await app.open('/timeline');

    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();
    // Initially: 目标国家, 申请层级, 目标专业, 目标院校层级 (年级 hidden until
    // 申请层级 chosen; 申请轮次 only for 本科).
    await expect(screen.getByRole('combobox')).toHaveCount(4);

    await select(screen, 0).selectOption({ label: '美国' });
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();

    await select(screen, 1).selectOption({ label: '硕士' });
    await expect(screen.getByRole('combobox')).toHaveCount(5);
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();

    await select(screen, 2).selectOption({ label: '大四' });
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();

    await select(screen, 3).selectOption({ label: '计算机/AI' });
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeEnabled();
  });

  test('生成美国硕士时间线：未锁定阶段完整展示，后半段锁定', async ({ app, screen }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '硕士', '大四', '计算机/AI');

    await expect(screen.getByRole('heading', { name: '美国 硕士 申请时间线' })).toBeVisible();
    await expect(screen.getByText('计算机/AI', { visible: true })).toBeVisible();
    await expect(screen.getByText('当前：大四')).toBeVisible();

    // US master timeline has 4 stages; floor(4*0.6)=2 → first 2 unlocked.
    await expect(screen.getByText('规划与准备期')).toBeVisible();
    await expect(screen.getByText('背景提升期')).toBeVisible();
    await expect(screen.getByText('大三上学期')).toBeVisible();
    await expect(screen.getByText('大三下学期')).toBeVisible();
    await expect(screen.getByText('核心任务')).toHaveCount(2);

    // Locked stages keep their time range but hide stage name and tasks,
    // showing a blurred placeholder card instead.
    await expect(screen.getByText('核心任务与规划')).toHaveCount(2);
    await expect(screen.getByText('申请材料准备期')).toHaveCount(0);
    await expect(screen.getByText('冲刺与提交期')).toHaveCount(0);

    // The mid-lock CTA sits between unlocked and locked stages.
    await expect(screen.getByRole('button', { name: /解锁完整规划 \+ 个性化背景提升方案/ })).toBeVisible();
    // The generate button now offers regeneration.
    await expect(screen.getByRole('button', REGENERATE_BUTTON)).toBeVisible();
  });

  test('美国本科时间线包含七个阶段，其中三个锁定', async ({ app, screen }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '本科', '高一', '理工科');

    await expect(screen.getByRole('heading', { name: '美国 本科 申请时间线' })).toBeVisible();
    await expect(screen.getByText('理工科', { visible: true })).toBeVisible();
    // 7 stages, floor(7*0.6)=4 → 4 unlocked, 3 locked.
    await expect(screen.getByText('核心任务')).toHaveCount(4);
    await expect(screen.getByText('核心任务与规划')).toHaveCount(3);
    await expect(screen.getByText('收尾决策期')).toHaveCount(0);
    await expect(screen.getByText('等待录取结果')).toHaveCount(0);
  });

  test('切换申请层级会重置年级与申请轮次', async ({ app, screen }) => {
    await app.open('/timeline');

    await select(screen, 0).selectOption({ label: '美国' });
    await select(screen, 1).selectOption({ label: '本科' });
    await expect(screen.getByRole('combobox')).toHaveCount(6); // + grade + round

    await select(screen, 2).selectOption({ label: '高一' });
    await select(screen, 5).selectOption({ label: 'EA/ED（提前批）' });
    await select(screen, 3).selectOption({ label: '商科' });
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeEnabled();

    // Switching level wipes grade and round, disabling generation again.
    await select(screen, 1).selectOption({ label: '硕士' });
    await expect(select(screen, 2)).toHaveValue('');
    await expect(screen.getByRole('combobox')).toHaveCount(5); // round removed
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();
  });

  test('解锁弹窗展示顾问二维码，且二维码为本地生成的 data URL', async ({ app, screen }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '硕士', '大四', '计算机/AI');

    await screen.getByRole('button', { name: /解锁完整规划/ }).tap();
    await expect(screen.getByText('解锁完整专属规划')).toBeVisible();
    await expect(screen.getByText('微信扫码，立即解锁')).toBeVisible();

    // The QR image is generated on-device (PNG data URL) — no request to
    // api.qrserver.com or any other external host (guard sees to that).
    const qr = screen.getByRole('img', { name: 'WeChat QR Code' });
    await expect(qr).toBeVisible();
    await expect(qr).toHaveAttribute('src', /^data:image\/png;base64,/);
  });

  test('英国本科时间线展示 UCAS 等英国专属节点，不出现美本内容', async ({ app, screen }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '本科', '高二', '理工科', '英国');

    await expect(screen.getByRole('heading', { name: '英国 本科 申请时间线' })).toBeVisible();
    // Unlocked UK stages surface UCAS / A-Level / IELTS milestones.
    await expect(screen.getByText(/UCAS 申请机制/)).toBeVisible();
    await expect(screen.getByText(/确定课程体系（A-Level\/IB）/)).toBeVisible();
    await expect(screen.getByText(/雅思（IELTS）首考/)).toBeVisible();

    // The former US fallback content must be gone entirely: 7 UK stages,
    // floor(7*0.6)=4 → 4 unlocked, 3 locked.
    await expect(screen.getByText('核心任务')).toHaveCount(4);
    await expect(screen.getByText('核心任务与规划')).toHaveCount(3);
    await expect(screen.getByText('SAT')).toHaveCount(0);
    await expect(screen.getByText('Common App')).toHaveCount(0);
  });

  test('英国硕士时间线使用英国数据而非美本回退', async ({ app, screen }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '硕士', '大四', '商科', '英国');

    await expect(screen.getByRole('heading', { name: '英国 硕士 申请时间线' })).toBeVisible();
    // 5 UK master stages, floor(5*0.6)=3 → 3 unlocked, 2 locked.
    await expect(screen.getByText('核心任务')).toHaveCount(3);
    await expect(screen.getByText('核心任务与规划')).toHaveCount(2);
    // Unlocked stage-1 is UK-specific planning, not the US fallback.
    await expect(screen.getByText('规划与准备期')).toBeVisible();
    await expect(screen.getByText(/G5\/罗素集团/)).toBeVisible();
    await expect(screen.getByText('等待录取结果')).toHaveCount(0);
  });

  test('离开页面再回来，表单与结果重置', async ({ app, screen, browser }) => {
    await app.open('/timeline');
    await fillAndGenerate(screen, '硕士', '大四', '计算机/AI');
    await expect(screen.getByRole('heading', { name: '美国 硕士 申请时间线' })).toBeVisible();

    await screen.getByRole('link', '首页').tap();
    await expect(browser).toHaveURL('/');

    await screen.getByRole('link', '时间线生成器').tap();
    await expect(browser).toHaveURL('/timeline');
    await expect(screen.getByRole('button', GENERATE_BUTTON)).toBeDisabled();
    await expect(screen.getByRole('heading', { name: '美国 硕士 申请时间线' })).toHaveCount(0);
  });
});
