import React from 'react';
import { useStore } from '../store';
import { ALGORITHMS } from '../utils/gpa';
import { Share2, GraduationCap } from 'lucide-react';

export const ResultCard: React.FC = () => {
  const { getResults, algorithm } = useStore();
  const { gpa, totalCredits } = getResults();
  
  const currentAlgo = ALGORITHMS[algorithm];

  return (
    <div className="bg-white rounded-xl shadow-lg border border-brand-blue-light p-6 md:p-8 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-32 h-32 bg-brand-blue-light rounded-bl-full -mr-10 -mt-10 z-0"></div>
      
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
        </div>

        <div className="mt-8 pt-6 border-t border-neutral-200 flex justify-center">
          <button 
            className="flex items-center px-4 py-2.5 bg-brand-green-light text-brand-green border border-green-200 hover:bg-green-100 rounded-lg text-sm font-medium transition-colors"
          >
            <Share2 className="w-4 h-4 mr-2" />
            生成分享卡片
          </button>
        </div>
      </div>
    </div>
  );
};
