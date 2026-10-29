import React from 'react';
import { QrCode, FileText, ArrowRight } from 'lucide-react';

const CtaSection: React.FC = () => {
  return (
    <div className="bg-blue-50 rounded-xl p-8 sm:p-10 mt-16 border border-blue-100 shadow-sm">
      <div className="text-center mb-8">
        <h2 className="text-2xl sm:text-3xl font-bold text-neutral-900 mb-3">
          期待与您共创价值
        </h2>
        <p className="text-neutral-600 text-base sm:text-lg max-w-2xl mx-auto">
          无论您是寻求渠道合作、资源置换还是联合开发，我们都非常欢迎您的交流。请选择以下方式与我们取得联系。
        </p>
      </div>

      <div className="flex flex-col md:flex-row items-center justify-center gap-6 md:gap-10">
        {/* Primary CTA - 填写表单 */}
        <div className="w-full md:w-auto flex flex-col items-center">
          <a
            href="https://shuzimumin.feishu.cn/share/base/form/shrcncNoGzAdSPUKT4gSWJZPked"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full md:w-64 inline-flex items-center justify-center px-6 py-4 bg-blue-700 text-white font-medium rounded-md hover:bg-blue-800 hover:shadow-md transition-all duration-200 group"
          >
            <FileText className="w-5 h-5 mr-2" />
            填写合作意向表单
            <ArrowRight className="w-4 h-4 ml-2 group-hover:tranneutral-x-1 transition-transform" />
          </a>
          <span className="text-xs text-neutral-500 mt-3">
            预计耗时 1 分钟，我们将在 24 小时内回复
          </span>
        </div>

        {/* 分隔符 (仅在桌面端显示) */}
        <div className="hidden md:block h-24 w-px bg-blue-200"></div>

        {/* Secondary CTA - 添加微信 */}
        <div className="w-full md:w-auto bg-white rounded-lg border border-neutral-200 p-4 flex items-center shadow-sm max-w-sm">
          <div className="flex-shrink-0 bg-neutral-50 p-2 rounded-md border border-neutral-100">
            <img
              src="/assets/wechat-qr-cooperate.png"
              alt="商务负责人微信二维码"
              className="w-32 h-32 sm:w-36 sm:h-36 object-contain"
            />
          </div>
          <div className="ml-4 text-left">
            <h4 className="text-base font-semibold text-neutral-900 flex items-center">
              <QrCode className="w-4 h-4 mr-1.5 text-blue-700" />
              添加微信沟通
            </h4>
            <p className="text-sm text-neutral-600 mt-1 mb-2">
              扫码添加商务负责人，获取定制合作方案。
            </p>
            <p className="text-xs font-medium text-neutral-800 bg-neutral-100 inline-block px-2 py-1 rounded">
              微信号：helipei888
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CtaSection;