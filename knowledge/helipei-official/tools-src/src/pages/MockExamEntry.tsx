import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useExamStore } from '../store/examStore';
import { getMockQuestions } from '../data/examData';
import { COMPETITIONS, COMPETITION_CATEGORIES } from '../data/competitions';

export const MockExamEntry: React.FC = () => {
  const navigate = useNavigate();
  const startExam = useExamStore((state) => state.startExam);

  const handleStart = (examId: string, examName: string) => {
    startExam(examName, getMockQuestions(examId));
    navigate('/mock-exam/play');
  };

  return (
    <div className="max-w-5xl mx-auto py-12 px-4">
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold text-neutral-900 mb-4">国际竞赛全真模考</h1>
        <p className="text-lg text-neutral-600 max-w-2xl mx-auto">
          汇集顶尖国际学校热门竞赛真题，覆盖数学、物理、化学、商科等全赛道。随时随地进行全真模考，智能出具排位预估报告。
        </p>
      </div>

      {COMPETITION_CATEGORIES.map(category => {
        const categoryComps = COMPETITIONS.filter(c => c.category === category);
        if (categoryComps.length === 0) return null;

        return (
          <div key={category} className="mb-12">
            <h2 className="text-2xl font-bold text-neutral-800 mb-6 flex items-center border-b border-neutral-200 pb-2">
              <span className="w-1.5 h-6 bg-blue-600 rounded mr-3"></span>
              {category} 竞赛
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {categoryComps.map(comp => (
                <div
                  key={comp.id}
                  className={`bg-white p-6 rounded-xl border transition-all ${
                    comp.isAvailable
                      ? 'border-neutral-200 shadow-sm hover:shadow-md hover:border-blue-300'
                      : 'border-neutral-100 opacity-60'
                  }`}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-lg font-bold text-neutral-900 line-clamp-1" title={comp.enName}>{comp.enName}</h3>
                      <p className="text-sm text-neutral-500 line-clamp-1" title={comp.name}>{comp.name}</p>
                    </div>
                    {comp.isAvailable ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        可用
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-600">
                        敬请期待
                      </span>
                    )}
                  </div>

                  {comp.isAvailable ? (
                    <button
                      onClick={() => handleStart(comp.id, comp.enName)}
                      className="w-full mt-4 px-4 py-2 bg-blue-50 text-blue-700 font-medium rounded hover:bg-blue-100 transition-colors"
                    >
                      开始模考
                    </button>
                  ) : (
                    <button
                      disabled
                      className="w-full mt-4 px-4 py-2 bg-neutral-50 text-neutral-400 font-medium rounded cursor-not-allowed"
                    >
                      题库准备中
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};