import React, { useEffect } from 'react';
import { TimelineForm } from '../components/timeline/TimelineForm';
import { TimelineResult } from '../components/timeline/TimelineResult';
import { useTimelineStore } from '../store/timelineStore';

export const TimelineGenerator: React.FC = () => {
  const reset = useTimelineStore(state => state.reset);

  useEffect(() => {
    // Reset state when component unmounts
    return () => reset();
  }, [reset]);

  return (
    <div className="min-h-screen py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-10">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-4 tracking-tight">
            申请时间线生成器
          </h1>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            输入基础信息即可获得清晰的个性化留学时间线，
            从此告别"什么时候该做什么"的焦虑。
          </p>
        </div>

        <TimelineForm />
        <TimelineResult />
      </div>
    </div>
  );
};
