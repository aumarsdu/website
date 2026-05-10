import React from 'react';
import { TimelineStage } from '../../utils/timeline/data';
import { Calendar, AlertTriangle, Lightbulb, CheckCircle2, Lock } from 'lucide-react';

interface Props {
  stage: TimelineStage;
  index: number;
  total: number;
}

export const TimelineStageCard: React.FC<Props> = ({ stage, index, total }) => {
  const isLast = index === total - 1;

  if (stage.isLocked) {
    return (
      <div className="relative flex gap-6 w-full opacity-60 pointer-events-none select-none">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 rounded-full bg-slate-200 border-4 border-white shadow-sm flex items-center justify-center text-slate-400 z-10">
            <Lock className="w-5 h-5" />
          </div>
          {!isLast && <div className="w-0.5 h-full bg-slate-200 mt-2" />}
        </div>
        
        <div className="flex-1 pb-10">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 filter blur-[2px]">
            <h3 className="text-lg font-bold text-slate-800">{stage.timeRange}</h3>
            <p className="text-slate-500 mt-2">核心任务与规划</p>
            <div className="h-20 bg-slate-100 rounded-lg mt-4 w-full" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex gap-4 sm:gap-6 w-full">
      {/* Timeline Node */}
      <div className="flex flex-col items-center">
        <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-primary-50 border-4 border-white shadow-sm flex items-center justify-center text-xl sm:text-2xl z-10 shrink-0">
          {stage.icon || '📍'}
        </div>
        {!isLast && <div className="w-0.5 h-full bg-primary-100 mt-2" />}
      </div>

      {/* Content Card */}
      <div className="flex-1 pb-10 pt-1">
        <div className="bg-white p-5 sm:p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 mb-4">
            <h3 className="text-lg sm:text-xl font-bold text-slate-800">
              {stage.timeRange}
            </h3>
            <span className="inline-flex px-3 py-1 rounded-full bg-primary-50 text-primary-700 text-sm font-medium whitespace-nowrap self-start sm:self-auto">
              {stage.stageName}
            </span>
          </div>

          <div className="space-y-4 sm:space-y-5">
            {/* Core Tasks */}
            <div>
              <h4 className="flex items-center gap-2 text-sm font-bold text-slate-700 mb-3">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                核心任务
              </h4>
              <ul className="space-y-2">
                {stage.coreTasks.map((task, i) => (
                  <li key={i} className="flex items-start gap-2 text-slate-600 text-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 shrink-0" />
                    <span>{task}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Background Enhancement */}
            <div className="bg-amber-50/50 p-3 sm:p-4 rounded-xl border border-amber-100/50">
              <h4 className="flex items-center gap-2 text-sm font-bold text-amber-700 mb-2">
                <Lightbulb className="w-4 h-4" />
                背景提升建议
              </h4>
              <p className="text-sm text-amber-900/80 leading-relaxed">
                {stage.bgEnhancement}
              </p>
            </div>

            {/* Deadlines & Risks */}
            {(stage.deadline || stage.riskWarning) && (
              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                {stage.deadline && (
                  <div className="flex-1 flex items-start gap-2 text-sm text-rose-600 bg-rose-50 px-3 py-2 rounded-lg">
                    <Calendar className="w-4 h-4 shrink-0 mt-0.5" />
                    <span className="font-medium">{stage.deadline}</span>
                  </div>
                )}
                {stage.riskWarning && (
                  <div className="flex-1 flex items-start gap-2 text-sm text-slate-600 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-slate-400" />
                    <span>{stage.riskWarning.replace('⚠️ ', '')}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
