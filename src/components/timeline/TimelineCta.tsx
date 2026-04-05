import React, { useState } from 'react';
import { Lock, FileText, Download, X } from 'lucide-react';

interface Props {
  type: 'mid-lock' | 'bottom-download';
}

export const TimelineCta: React.FC<Props> = ({ type }) => {
  const [showModal, setShowModal] = useState(false);

  const handleCtaClick = () => {
    setShowModal(true);
  };

  const renderModal = () => {
    if (!showModal) return null;

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 exclude-from-share">
        <div className="bg-white rounded-3xl w-full max-w-md p-8 relative shadow-2xl animate-in fade-in zoom-in-95 duration-200">
          <button 
            onClick={() => setShowModal(false)}
            className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
          
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-primary-100 text-primary-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Lock className="w-8 h-8" />
            </div>
            <h3 className="text-2xl font-bold text-slate-900 mb-2">
              解锁完整专属规划
            </h3>
            <p className="text-slate-500">
              扫码添加资深顾问，免费获取完整版时间线及个性化背景提升方案。
            </p>
          </div>

          <div className="bg-slate-50 rounded-2xl p-6 flex flex-col items-center justify-center border border-slate-100">
            {/* Placeholder for QR Code */}
            <div className="w-40 h-40 bg-white rounded-xl shadow-sm border border-slate-200 p-2 mb-4">
              <img 
                src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://example.com/add-wechat" 
                alt="WeChat QR Code" 
                className="w-full h-full object-cover rounded-lg opacity-80"
              />
            </div>
            <p className="text-sm font-medium text-slate-700">微信扫码，立即解锁</p>
          </div>
        </div>
      </div>
    );
  };

  if (type === 'mid-lock') {
    return (
      <>
        <div className="relative -mt-20 z-20 flex justify-center pb-12 w-full exclude-from-share">
          <button 
            onClick={handleCtaClick}
            className="group flex flex-col sm:flex-row items-center gap-3 sm:gap-4 bg-gradient-to-r from-primary-600 to-primary-500 text-white px-6 sm:px-8 py-4 sm:py-5 rounded-2xl shadow-xl shadow-primary-500/25 hover:shadow-primary-500/40 hover:-translate-y-1 transition-all w-[90%] sm:w-auto"
          >
            <div className="w-10 h-10 sm:w-12 sm:h-12 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
              <Lock className="w-5 h-5 sm:w-6 sm:h-6" />
            </div>
            <div className="text-center sm:text-left">
              <div className="font-bold text-base sm:text-lg">解锁完整规划 + 个性化背景提升方案</div>
              <div className="text-primary-100 text-sm mt-0.5">获取适合你的科研/竞赛项目推荐</div>
            </div>
          </button>
        </div>
        {renderModal()}
      </>
    );
  }

  return (
    <>
      <div className="mt-8 pt-8 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-4 exclude-from-share">
        <div className="flex items-center gap-3 text-slate-600">
          <FileText className="w-5 h-5 text-primary-500" />
          <span className="text-sm font-medium">想要保存这份时间线？</span>
        </div>
        <button 
          onClick={handleCtaClick}
          className="w-full sm:w-auto flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-medium transition-all shadow-sm hover:shadow"
        >
          <Download className="w-4 h-4" />
          下载完整 PDF 版时间线
        </button>
      </div>
      {renderModal()}
    </>
  );
};
