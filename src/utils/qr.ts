import { toDataURL } from 'qrcode';

/**
 * 本地生成二维码 PNG data URL，替代原先加载自 api.qrserver.com 的远程图片：
 * 用户数据不出设备，弱网/离线环境下也能正常渲染。
 *
 * width 默认 150px（与原 qrserver size=150x150 一致），margin 保持 1 个模块的
 * 静区，视觉输出与原先基本一致。
 */
export function createQrDataUrl(text: string, width = 150): Promise<string> {
  return toDataURL(text, {
    width,
    margin: 1,
    errorCorrectionLevel: 'M',
  });
}
