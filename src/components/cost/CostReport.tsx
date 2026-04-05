import React, { useRef, useState } from 'react';
import { useCostStore } from '../../store/costStore';
import { COST_DATA } from '../../utils/cost/data';
import { toPng } from 'html-to-image';
import { Share2, PieChart, Loader2, Info } from 'lucide-react';

export const CostReport: React.FC = () => {
  const { country, getCalculatedCosts } = useCostStore();
  const { tuition, living, application, hidden, total } = getCalculatedCosts();
  const currentCountry = COST_DATA[country];
  
  const cardRef = useRef<HTMLDivElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleShare = async () => {
    if (!cardRef.current) return;
    try {
      setIsGenerating(true);
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const filter = (node: HTMLElement) => {
        const exclusionClasses = ['exclude-from-share'];
        return node.classList ? !exclusionClasses.some(c => node.classList.contains(c)) : true;
      };

      const dataUrl = await toPng(cardRef.current, { 
        quality: 1, 
        pixelRatio: 2,
        filter: filter as any,
        backgroundColor: '#ffffff'
      });
      
      const link = document.createElement('a');
      link.download = `留学费用评估_${currentCountry.name}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error('生成图片失败:', error);
      alert('生成分享卡片失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  const formatRMB = (num: number) => {
    if (num >= 10000) {
      return (num / 10000).toFixed(1) + ' 万';
    }
    return num.toLocaleString() + ' 元';
  };

  return (
    <div 
      ref={cardRef}
      className="bg-white rounded-xl shadow-lg border border-brand-blue-light p-6 md:p-8 relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-32 h-32 bg-brand-blue-light rounded-bl-full -mr-10 -mt-10 z-0 pointer-events-none"></div>
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-neutral-900 flex items-center">
            <PieChart className="w-6 h-6 text-brand-blue mr-2" />
            预估总花费 (RMB)
          </h2>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-700 border border-neutral-200">
            {currentCountry.flag} {currentCountry.name}
          </span>
        </div>

        {/* 核心总计三档 */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          <div className="bg-brand-green-light rounded-lg p-4 border border-green-200 text-center">
            <div className="text-xs text-brand-green font-semibold mb-1">节省方案</div>
            <div className="text-xl md:text-2xl font-black text-brand-green">{formatRMB(total.budget)}</div>
          </div>
          <div className="bg-brand-blue-light rounded-lg p-4 border border-blue-200 text-center shadow-sm transform scale-105">
            <div className="text-xs text-brand-blue font-bold mb-1 flex items-center justify-center">
              适中方案
              <span className="ml-1 inline-flex w-2 h-2 rounded-full bg-brand-blue animate-pulse"></span>
            </div>
            <div className="text-2xl md:text-3xl font-black text-brand-blue">{formatRMB(total.medium)}</div>
          </div>
          <div className="bg-orange-50 rounded-lg p-4 border border-orange-200 text-center">
            <div className="text-xs text-brand-orange font-semibold mb-1">宽裕方案</div>
            <div className="text-xl md:text-2xl font-black text-brand-orange">{formatRMB(total.comfort)}</div>
          </div>
        </div>

        {/* 明细拆解 */}
        <h3 className="text-sm font-bold text-neutral-900 mb-3 border-b border-neutral-200 pb-2">费用结构明细 (适中方案)</h3>
        <div className="space-y-3">
          <div className="flex justify-between items-center text-sm">
            <span className="text-neutral-500">学费 (总计)</span>
            <span className="font-semibold text-neutral-900">{formatRMB(tuition.medium)}</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-neutral-500">生活费 (含住宿、餐饮等)</span>
            <span className="font-semibold text-neutral-900">{formatRMB(living.medium)}</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-neutral-500 flex items-center">
              申请阶段费用
              <Info className="w-3 h-3 ml-1 text-neutral-400" title="包含考试费、申请费、公证费等" />
            </span>
            <span className="font-semibold text-neutral-900">{formatRMB(application)}</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-neutral-500 flex items-center">
              隐性费用
              <Info className="w-3 h-3 ml-1 text-neutral-400" title="包含往返机票、签证、体检、保险等" />
            </span>
            <span className="font-semibold text-neutral-900">{formatRMB(hidden)}</span>
          </div>
        </div>

        <div className="mt-4 text-xs text-neutral-400 italic">
          * 按汇率 1 {currentCountry.currency} ≈ {currentCountry.exchangeRate} CNY 计算。数据仅供参考，实际费用以官方为准。
        </div>

        <div className="mt-6 text-center text-xs font-medium text-neutral-400 hidden-in-ui" style={{ display: isGenerating ? 'block' : 'none' }}>
          由 河狸陪 留学费用计算器 生成
        </div>

        <div className="mt-8 pt-6 border-t border-neutral-200 flex justify-center exclude-from-share">
          <button 
            onClick={handleShare}
            disabled={isGenerating}
            className="flex items-center px-4 py-2.5 bg-brand-green-light text-brand-green border border-green-200 hover:bg-green-100 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Share2 className="w-4 h-4 mr-2" />
            )}
            {isGenerating ? '生成中...' : '生成费用报告'}
          </button>
        </div>
      </div>
    </div>
  );
};
