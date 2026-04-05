import React from 'react';
import { Link } from 'react-router-dom';
import { Calculator, DollarSign, Calendar, Target, ArrowRight, FileText } from 'lucide-react';

export const Home: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <div className="text-center mb-16">
        <h1 className="text-4xl md:text-6xl font-black text-neutral-900 mb-6 tracking-tight">
          河狸陪 <span className="text-brand-blue">留学工具箱</span>
        </h1>
        <p className="text-xl text-neutral-500 max-w-2xl mx-auto">
          为你提供最专业、最便捷的留学前置评估工具，让每一次选择都有据可依。
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
        <Link 
          to="/gpa" 
          className="group bg-white p-8 rounded-2xl shadow-sm border border-neutral-200 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Calculator className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-xl flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Calculator className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">GPA 换算器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              支持标准4.0、北大4.0等7种主流算法，快速生成专属分享卡片，一键测算你的学术竞争力。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始换算 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        <Link 
          to="/cost" 
          className="group bg-white p-8 rounded-2xl shadow-sm border border-neutral-200 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <DollarSign className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-xl flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <DollarSign className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">留学费用计算器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              覆盖8大热门留学地，提供省钱/适中/宽裕三档消费预估，提前摸底留学真实花销。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始计算 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        <Link 
          to="/timeline" 
          className="group bg-white p-8 rounded-2xl shadow-sm border border-neutral-200 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Calendar className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-xl flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Calendar className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">申请时间线生成器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              输入基础信息，一键获取精准个性化申请时间线。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始生成 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        <Link 
          to="/visa-checklist" 
          className="group bg-white p-8 rounded-2xl shadow-sm border border-neutral-200 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <FileText className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-xl flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <FileText className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">签证材料清单</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              输入国家和身份，30秒生成专属签证材料 Checklist，支持进度勾选与保存。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              生成清单 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        <Link 
          to="/school-matcher" 
          className="group bg-white p-8 rounded-2xl shadow-sm border border-neutral-200 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Target className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-xl flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Target className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">院校匹配器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              输入背景条件，10秒智能生成冲刺、匹配、保底院校专属方案。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始测算 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>
      </div>
    </div>
  );
};
