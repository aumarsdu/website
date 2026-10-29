import React, { useState, useEffect } from 'react';
import { useStore } from '../store';
import { ArrowRight, MessageCircle, Copy, CheckCircle2 } from 'lucide-react';

export const CtaCard: React.FC = () => {
  const { getResults } = useStore();
  const { gpa } = getResults();
  const [showQR, setShowQR] = useState(false);
  const [copied, setCopied] = useState(false);
  const wechatId = "helipei001"; // TODO: 替换为真实的微信号

  useEffect(() => {
    const handleShowQR = () => setShowQR(true);
    window.addEventListener('show-gpa-qr', handleShowQR);
    return () => window.removeEventListener('show-gpa-qr', handleShowQR);
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(wechatId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      
      // 触发复制成功事件埋点
      if (window.gtag) {
        window.gtag('event', 'copy_wechat_id', {
          'event_category': 'Conversion',
          'event_label': 'GPA Calculator',
        });
      }
    } catch (err) {
      console.error('复制失败:', err);
    }
  };

  const getCtaMessage = (gpaValue: number) => {
    if (gpaValue >= 3.8) {
      return {
        title: "你的 GPA 极具竞争力！",
        desc: "测测你的 GPA 能申哪些世界 Top 30 名校？",
        button: "获取选校报告"
      };
    } else if (gpaValue >= 3.3) {
      return {
        title: "GPA 表现良好",
        desc: "想知道如何冲刺更高层次院校？",
        button: "定制背景提升方案"
      };
    } else if (gpaValue > 0) {
      return {
        title: "GPA 仍有提升空间",
        desc: "低 GPA 如何逆袭？获取专属补救策略。",
        button: "查看逆袭方案"
      };
    } else {
      return {
        title: "开始你的评估",
        desc: "换算 GPA 并获取你的专属竞争力分析报告。",
        button: "免费评估"
      };
    }
  };

  const cta = getCtaMessage(gpa);

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
            onClick={() => {
              setShowQR(true);
              if (window.gtag) {
                window.gtag('event', 'click_cta_button', {
                  'event_category': 'Engagement',
                  'event_label': cta.button,
                  'value': gpa
                });
              }
            }}
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
            <h3 className="text-lg font-bold">添加顾问微信</h3>
          </div>
          
          <div className="bg-white p-4 rounded-xl shadow-sm border border-neutral-200 mb-4 w-48 h-48 flex items-center justify-center">
            {/* 模拟二维码的占位图 */}
            <div className="w-full h-full border-2 border-dashed border-neutral-300 rounded flex items-center justify-center text-neutral-400">
              <span className="text-sm font-medium">企微二维码</span>
            </div>
          </div>
          
          <div className="w-full max-w-[200px] mb-4">
            <button 
              onClick={handleCopy}
              className="w-full flex items-center justify-center px-4 py-2.5 bg-neutral-100 hover:bg-neutral-200 border border-neutral-200 rounded-lg text-sm font-medium text-neutral-700 transition-colors"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2 text-green-500" />
                  <span className="text-green-600">微信号已复制</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 mr-2" />
                  复制微信号 ({wechatId})
                </>
              )}
            </button>
            <div className="mt-2 flex justify-center">
              <a 
                href={`weixin://dl/chat?${wechatId}`} 
                className="text-xs text-brand-blue hover:underline md:hidden"
              >
                点此尝试直接唤起微信
              </a>
            </div>
          </div>
          
          <p className="text-sm text-neutral-600 mb-4 text-center max-w-xs">
            添加微信，发送您的 GPA 换算结果截图，获取详细选校评估。
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
