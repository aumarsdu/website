import React, { useRef, useState } from 'react';
import { useTimelineStore } from '../../store/timelineStore';
import { TimelineStageCard } from './TimelineStageCard';
import { TimelineCta } from './TimelineCta';
import { Share2, Clock, MapPin, GraduationCap, Sparkles } from 'lucide-react';
import { toPng } from 'html-to-image';

export const TimelineResult: React.FC = () => {
  const { timelineData, formData, isGenerated } = useTimelineStore();
  const resultRef = useRef<HTMLDivElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  if (!isGenerated || !timelineData) {
    return null;
  }

  const handleShare = async () => {
    if (!resultRef.current) return;
    try {
      setIsGenerating(true);
      // Give UI time to update loading state
      await new Promise(resolve => setTimeout(resolve, 100));

      const filter = (node: HTMLElement) => {
        const exclusionClasses = ['exclude-from-share'];
        const classes = node.classList;
        if (classes) {
          return !exclusionClasses.some(classname => classes.contains(classname));
        }
        return true;
      };

      const dataUrl = await toPng(resultRef.current, {
        quality: 1,
        pixelRatio: 2,
        filter: filter as any,
        backgroundColor: '#f8fafc' // slate-50 to match bg
      });

      const link = document.createElement('a');
      link.download = `留学申请时间线_${formData.country}_${formData.level}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error('生成图片失败:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // 找到第一个被锁定的阶段索引
  const firstLockedIndex = timelineData.findIndex(stage => stage.isLocked);
  
  return (
    <div 
      ref={resultRef}
      className="bg-slate-50 sm:bg-white sm:rounded-3xl sm:shadow-sm sm:border border-slate-200 overflow-hidden relative mt-8 transition-all duration-500 animate-in slide-in-from-bottom-8 fade-in"
    >
      {/* Header Banner */}
      <div className="bg-gradient-to-br from-primary-900 via-primary-800 to-slate-900 px-6 sm:px-10 py-10 sm:py-12 relative overflow-hidden text-white">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-white via-transparent to-transparent" />
        
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-sm font-medium mb-6">
            <Sparkles className="w-4 h-4 text-primary-300" />
            <span>为您量身定制</span>
          </div>
          
          <h2 className="text-3xl sm:text-4xl font-extrabold mb-4 leading-tight">
            {formData.country} {formData.level} 申请时间线
          </h2>
          
          <div className="flex flex-wrap gap-4 text-sm sm:text-base text-slate-200">
            <div className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg backdrop-blur-sm border border-white/10">
              <GraduationCap className="w-4 h-4 text-primary-300" />
              <span>{formData.major}</span>
            </div>
            <div className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg backdrop-blur-sm border border-white/10">
              <Clock className="w-4 h-4 text-primary-300" />
              <span>当前：{formData.grade}</span>
            </div>
            {formData.tier && (
              <div className="flex items-center gap-1.5 bg-white/5 px-3 py-1.5 rounded-lg backdrop-blur-sm border border-white/10">
                <MapPin className="w-4 h-4 text-primary-300" />
                <span>目标：{formData.tier}</span>
              </div>
            )}
          </div>
        </div>

        {/* Share Button (Top Right) */}
        <button
          onClick={() => {
            handleShare();
            if (window.gtag) {
              window.gtag('event', 'share_timeline_image', {
                'event_category': 'Engagement',
                'event_label': `${formData.country}_${formData.level}`
              });
            }
          }}
          disabled={isGenerating}
          className="absolute top-6 right-6 p-3 rounded-full bg-white/10 hover:bg-white/20 text-white backdrop-blur-md border border-white/20 transition-all exclude-from-share"
          title="生成分享图片"
        >
          <Share2 className="w-5 h-5" />
        </button>
      </div>

      {/* Timeline Content */}
      <div className="p-6 sm:p-10 max-w-3xl mx-auto">
        <div className="space-y-0 relative">
          {timelineData.map((stage, index) => (
            <React.Fragment key={stage.id}>
              <TimelineStageCard 
                stage={stage} 
                index={index} 
                total={timelineData.length} 
              />
              
              {/* Insert CTA Lock immediately after the last unlocked item if there are locked items */}
              {firstLockedIndex !== -1 && index === firstLockedIndex - 1 && (
                <TimelineCta type="mid-lock" />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Bottom CTA Download */}
        <TimelineCta type="bottom-download" />

        {/* Watermark for Share Image (Only visible in exported image) */}
        <div className="hidden share-watermark mt-12 pt-8 border-t border-slate-200 flex items-center justify-between opacity-0">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-primary-100 rounded-xl flex items-center justify-center">
              <span className="text-2xl">🎓</span>
            </div>
            <div>
              <div className="font-bold text-slate-800 text-lg">河狸陪留学</div>
              <div className="text-slate-500 text-sm">扫码获取你的专属时间线及定制规划</div>
            </div>
          </div>
          <div className="w-20 h-20 bg-white p-1 rounded-lg border border-slate-200 shadow-sm">
            {/* Placeholder QR Code for exported image */}
            <div className="w-full h-full border border-dashed border-slate-300 rounded flex items-center justify-center text-slate-400">
              <span className="text-[10px]">企微二维码</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
