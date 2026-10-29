import React, { useState } from 'react';
import { Target, Search, AlertTriangle, CheckCircle2, Copy } from 'lucide-react';
import projectsData from '../data/projects.json';

export const ExtracurricularActivityPlannerPage: React.FC = () => {
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [showResult, setShowResult] = useState(false);
  const [copied, setCopied] = useState(false);
  const wechatId = "dnomad003";

  const project = projectsData.find(p => p.id === selectedProject);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(wechatId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="max-w-[800px] mx-auto">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center p-3 bg-brand-blue-light rounded-2xl mb-4">
          <Target className="w-8 h-8 text-brand-blue" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-neutral-900 mb-4">
          美本课外活动规划器
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          背景提升项目「排雷」体检器。大数据剥离机构包装，真实评估项目的藤校认可度、时间性价比与避坑风险。
        </p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-neutral-200 p-6 md:p-8 mb-8">
        <div className="mb-6">
          <label className="block text-sm font-semibold text-neutral-700 mb-2">选择您正在考虑的课外活动 / 背景提升项目</label>
          <div className="relative">
            <select
              className="w-full p-4 pl-12 border border-neutral-300 rounded-xl focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none appearance-none bg-white text-neutral-900"
              value={selectedProject}
              onChange={(e) => {
                setSelectedProject(e.target.value);
                setShowResult(false);
              }}
            >
              <option value="">-- 请选择或搜索项目 --</option>
              {projectsData.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <Search className="w-5 h-5 text-neutral-400 absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        <button
          onClick={() => selectedProject && setShowResult(true)}
          disabled={!selectedProject}
          className="w-full py-4 bg-brand-blue text-white rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-lg shadow-md hover:shadow-lg"
        >
          免费生成体检报告
        </button>
      </div>

      {showResult && project && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-neutral-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-neutral-200 px-6 py-4">
              <h2 className="text-xl font-bold text-neutral-900 flex items-center gap-2">
                <span className="w-2 h-6 bg-brand-blue rounded-full"></span>
                「{project.name}」测评结果
              </h2>
            </div>

            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                <div className="bg-slate-50 p-6 rounded-xl border border-neutral-200 flex flex-col justify-center items-center text-center">
                  <p className="text-sm text-neutral-500 mb-2 font-medium">藤校 / G5 认可度</p>
                  <div className="text-4xl font-black text-brand-blue">
                    {project.recognition} <span className="text-xl text-neutral-400 font-normal">/ 5.0</span>
                  </div>
                </div>
                <div className={`p-6 rounded-xl border flex flex-col justify-center items-center text-center ${project.riskLevel === 'high' ? 'bg-red-50 border-red-100' : 'bg-green-50 border-green-100'}`}>
                  <p className="text-sm text-neutral-500 mb-2 font-medium">避坑预警指数</p>
                  <div className={`text-2xl font-bold flex items-center gap-2 ${project.riskLevel === 'high' ? 'text-red-600' : 'text-green-600'}`}>
                    {project.riskLevel === 'high' ? <AlertTriangle className="w-6 h-6" /> : <CheckCircle2 className="w-6 h-6" />}
                    {project.riskLevel === 'high' ? '高风险 (谨慎入局)' : '低风险 (推荐冲刺)'}
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-8 border border-blue-100 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
                <div className="relative z-10 text-center">
                  <h3 className="text-xl font-bold text-blue-900 mb-3">解锁该项目的深度背调报告</h3>
                  <p className="text-blue-700 mb-8">包含：真实耗时预估、同类高性价比平替推荐、历年录取者硬核避坑建议。</p>

                  <div className="bg-white p-6 rounded-xl shadow-sm inline-block mx-auto">
                    <img
                      src="https://helipei.com/assets/images/qr-code.png"
                      alt="规划师二维码"
                      className="w-40 h-40 mx-auto mb-4"
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'%3E%3Crect width='160' height='160' fill='%23f1f5f9'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%2394a3b8' font-family='sans-serif' font-size='14'%3E二维码加载失败%3C/text%3E%3C/svg%3E";
                      }}
                    />
                    <div className="text-sm text-neutral-500 mb-4">
                      扫码添加规划师，回复 <strong className="text-brand-blue">[{project.name}]</strong>
                    </div>
                    <button
                      onClick={handleCopy}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
                    >
                      <Copy className="w-4 h-4" />
                      {copied ? '已复制微信号' : `复制微信号: ${wechatId}`}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
