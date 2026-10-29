import React, { useState } from 'react';
import { Search, MapPin, Award, CheckCircle, Copy } from 'lucide-react';
import casesData from '../data/cases.json';

type CaseRecord = (typeof casesData)[number];

export const CaseMatcherPage: React.FC = () => {
  const [background, setBackground] = useState('');
  const [major, setMajor] = useState('');
  const [matchedCase, setMatchedCase] = useState<CaseRecord | null>(null);
  const [copied, setCopied] = useState(false);
  const wechatId = "dnomad003";

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const result = casesData.find((c) => c.bg.includes(background)) || casesData[0];
    setMatchedCase(result);
  };

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
          <Search className="w-8 h-8 text-brand-blue" />
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-neutral-900 mb-4">
          真实录取案例去水罗盘
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          拒绝“保录”忽悠与幸存者偏差。看看与你背景最相似的学长，真实去向是哪里？他们做对了什么？
        </p>
      </div>

      {!matchedCase ? (
        <form onSubmit={onSubmit} className="bg-white rounded-2xl shadow-sm border border-neutral-200 p-6 md:p-8 space-y-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-neutral-700 mb-2">当前就读背景</label>
              <select value={background} onChange={e => setBackground(e.target.value)} className="w-full p-4 border border-neutral-300 rounded-xl focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none bg-white text-neutral-900" required>
                <option value="">请选择...</option>
                <option value="普高">国内普高</option>
                <option value="国际部">国际学校/国际部</option>
                <option value="海高">海外高中</option>
                <option value="本科">本科在读</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-semibold text-neutral-700 mb-2">意向申请专业方向</label>
              <select value={major} onChange={e => setMajor(e.target.value)} className="w-full p-4 border border-neutral-300 rounded-xl focus:ring-2 focus:ring-brand-blue focus:border-brand-blue outline-none bg-white text-neutral-900" required>
                <option value="">请选择...</option>
                <option value="STEM">理工科 (STEM)</option>
                <option value="商科">商科/经济</option>
                <option value="人文社科">人文社科</option>
                <option value="艺术">艺术/设计</option>
                <option value="不确定">尚未确定 (Undecided)</option>
              </select>
            </div>
          </div>

          <button type="submit" className="w-full py-4 bg-brand-blue text-white rounded-xl font-bold hover:bg-blue-700 transition-all text-lg shadow-md">
            匹配相似录取案例
          </button>
        </form>
      ) : (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-neutral-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-neutral-200 px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold text-neutral-900 flex items-center gap-2">
                <span className="w-2 h-6 bg-brand-blue rounded-full"></span>
                最匹配案例: {matchedCase.id}
              </h2>
              <button onClick={() => setMatchedCase(null)} className="text-sm text-brand-blue font-medium hover:underline">
                重新匹配
              </button>
            </div>

            <div className="p-6 md:p-8">
              <div className="flex flex-col md:flex-row gap-8 mb-8">
                <div className="flex-1 space-y-4">
                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-neutral-400 mt-0.5" />
                    <div>
                      <p className="text-sm text-neutral-500 font-medium">背景概览</p>
                      <p className="text-neutral-900 font-semibold">{matchedCase.bg}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Award className="w-5 h-5 text-neutral-400 mt-0.5" />
                    <div>
                      <p className="text-sm text-neutral-500 font-medium">标化成绩</p>
                      <p className="text-neutral-900 font-semibold">
                        GPA {matchedCase.gpa} / {matchedCase.major}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-green-50 border border-green-100 rounded-xl p-5 flex-1 flex flex-col justify-center items-center text-center">
                  <CheckCircle className="w-8 h-8 text-green-500 mb-2" />
                  <p className="text-sm text-green-700 font-medium mb-1">最终录取院校</p>
                  <p className="text-2xl font-bold text-green-800">{matchedCase.admitted}</p>
                </div>
              </div>

              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-8 border border-blue-100 text-center relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
                <div className="relative z-10">
                  <h3 className="text-xl font-bold text-blue-900 mb-3">想知道 TA 是如何做到的吗？</h3>
                  <p className="text-blue-700 mb-6">获取完整案例拆解报告，包含活动列表、文书主线与录取官偏好分析。</p>

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
                      扫码添加规划师，回复 <strong className="text-brand-blue">[{matchedCase.id}]</strong> 获取完整案例解析
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
