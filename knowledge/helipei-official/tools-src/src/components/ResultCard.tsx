import React, { useRef, useState } from 'react';
import { useStore } from '../store';
import { ALGORITHMS } from '../utils/gpa';
import { Share2, GraduationCap, Loader2 } from 'lucide-react';
import { toPng } from 'html-to-image';

export const ResultCard: React.FC = () => {
  const { getResults, algorithm } = useStore();
  const { gpa, totalCredits } = getResults();
  
  const currentAlgo = ALGORITHMS[algorithm];
  const cardRef = useRef<HTMLDivElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleShare = async () => {
    if (!cardRef.current) return;
    try {
      setIsGenerating(true);
      
      // 等待 DOM 更新稳定
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // 过滤掉生成卡片按钮本身
      const filter = (node: HTMLElement) => {
        const exclusionClasses = ['exclude-from-share'];
        const classes = node.classList;
        if (classes) {
          return !exclusionClasses.some(classname => classes.contains(classname));
        }
        return true;
      };

      const dataUrl = await toPng(cardRef.current, { 
        quality: 1, 
        pixelRatio: 2,
        filter: filter as any,
        backgroundColor: '#ffffff'
      });
      
      const link = document.createElement('a');
      link.download = `GPA换算结果_${currentAlgo.name}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error('生成图片失败:', error);
      alert('生成分享卡片失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div 
      ref={cardRef}
      className="bg-white rounded-xl shadow-lg border border-brand-blue-light p-6 md:p-8 relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-32 h-32 bg-brand-blue-light rounded-bl-full -mr-10 -mt-10 z-0 pointer-events-none"></div>
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-bold text-neutral-900 flex items-center">
            <GraduationCap className="w-6 h-6 text-brand-blue mr-2" />
            换算结果
          </h2>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-700 border border-neutral-200">
            {currentAlgo.name} (满分 {currentAlgo.maxGPA})
          </span>
        </div>

        <div className="mt-8 flex flex-col items-center justify-center text-center">
          <div className="text-sm font-semibold text-neutral-500 uppercase tracking-wider mb-2">
            总加权 GPA
          </div>
          <div className="text-6xl md:text-7xl font-black text-brand-blue drop-shadow-sm mb-4">
            {gpa.toFixed(2)}
          </div>
          
          <div className="bg-neutral-50 px-4 py-2 rounded-lg border border-neutral-200 flex space-x-6">
            <div className="flex flex-col">
              <span className="text-xs text-neutral-500">总学分</span>
              <span className="text-lg font-bold text-neutral-900">{totalCredits}</span>
            </div>
            <div className="w-px h-full bg-neutral-300"></div>
            <div className="flex flex-col">
              <span className="text-xs text-neutral-500">最高可达</span>
              <span className="text-lg font-bold text-neutral-900">{currentAlgo.maxGPA}</span>
            </div>
          </div>
          
          <div className="mt-4 text-xs text-neutral-400 bg-blue-50 px-3 py-1.5 rounded-md border border-blue-100">
            *该算法与 WES 官方认证逻辑及大多数北美院校网申系统一致
          </div>
        </div>

        {/* 包含品牌水印（仅在截图中显示，因为设置了底部间距，它会被截图包进去，但平时它在按钮下方且不显眼） */}
        <div className="mt-6 text-center text-xs font-medium text-neutral-400 hidden-in-ui" style={{ display: isGenerating ? 'block' : 'none' }}>
          由 河狸陪 GPA 换算器 生成
        </div>

        <div className="mt-8 pt-6 border-t border-neutral-200 flex flex-col sm:flex-row justify-center gap-3 exclude-from-share">
          <button 
            onClick={handleShare}
            disabled={isGenerating}
            className="flex-1 flex items-center justify-center px-4 py-2.5 bg-white text-brand-blue border border-brand-blue hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Share2 className="w-4 h-4 mr-2" />
            )}
            {isGenerating ? '生成中...' : '生成分享卡片'}
          </button>
          
          <button 
            onClick={() => {
              // 触发事件埋点：生成 PDF 报告
              if (window.gtag) {
                window.gtag('event', 'generate_pdf_report', {
                  'event_category': 'Engagement',
                  'event_label': 'GPA Calculator PDF',
                  'value': gpa
                });
              }
              // 触发 CtaCard 显示留资二维码的逻辑（这里简单抛出一个自定义事件，或者后续可以接到全局 Store）
              window.dispatchEvent(new CustomEvent('show-gpa-qr'));
            }}
            className="flex-1 flex items-center justify-center px-4 py-2.5 bg-brand-blue text-white border border-brand-blue hover:bg-blue-700 shadow-sm rounded-lg text-sm font-medium transition-colors"
          >
            获取完整版选校评估 PDF
          </button>
        </div>
      </div>
    </div>
  );
};
