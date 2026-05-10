import React, { useState } from 'react';
import { ArrowRight, MessageCircle } from 'lucide-react';
import { useCostStore } from '../../store/costStore';

export const CostCta: React.FC = () => {
  const [showQR, setShowQR] = useState(false);
  const { getCalculatedCosts } = useCostStore();
  const { total } = getCalculatedCosts();

  const getCtaMessage = (totalBudget: number) => {
    // 根据节省方案的总预算来定文案
    if (totalBudget > 500000) {
      return {
        title: "预算有限？不确定选哪个国家？",
        desc: "获取 1v1 背景评估，让规划师帮你找到高性价比方案。",
        button: "免费规划"
      };
    } else {
      return {
        title: "如何用更少的钱获得更好的录取？",
        desc: "加微获取全额奖学金申请秘籍与高性价比名校推荐。",
        button: "获取免费指南"
      };
    }
  };

  const cta = getCtaMessage(total.budget);

  return (
    <div className="bg-brand-blue-light rounded-xl p-6 border border-blue-200 mt-6 relative overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-br from-white/40 to-transparent pointer-events-none"></div>
      
      {!showQR ? (
        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between">
          <div className="mb-4 md:mb-0 md:mr-6">
            <h3 className="text-xl font-bold text-neutral-900 mb-2">{cta.title}</h3>
            <p className="text-sm text-neutral-700">{cta.desc}</p>
          </div>
          <button 
            onClick={() => setShowQR(true)}
            className="w-full md:w-auto px-6 py-3 bg-brand-blue text-white rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors shadow-md flex items-center justify-center whitespace-nowrap"
          >
            {cta.button}
            <ArrowRight className="w-4 h-4 ml-2" />
          </button>
        </div>
      ) : (
        <div className="relative z-10 flex flex-col items-center justify-center py-4 animate-in fade-in zoom-in duration-300">
          <div className="flex items-center text-brand-blue mb-4">
            <MessageCircle className="w-6 h-6 mr-2" />
            <h3 className="text-lg font-bold">添加规划师微信</h3>
          </div>
          
          <div className="bg-white p-4 rounded-xl shadow-sm border border-neutral-200 mb-4 w-48 h-48 flex items-center justify-center">
            {/* 模拟二维码的占位图 */}
            <div className="w-full h-full border-2 border-dashed border-neutral-300 rounded flex items-center justify-center text-neutral-400">
              <span className="text-sm font-medium">企微二维码</span>
            </div>
          </div>
          
          <p className="text-sm text-neutral-600 mb-4 text-center max-w-xs">
            添加微信，发送您的【费用报告】截图，获取 1v1 定制留学选校方案。
          </p>
          
          <button 
            onClick={() => setShowQR(false)}
            className="text-sm font-medium text-neutral-500 hover:text-neutral-700 underline"
          >
            返回
          </button>
        </div>
      )}
    </div>
  );
};
