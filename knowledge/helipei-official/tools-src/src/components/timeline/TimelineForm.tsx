import React from 'react';
import { useTimelineStore } from '../../store/timelineStore';
import { Sparkles } from 'lucide-react';

export const TimelineForm: React.FC = () => {
  const { formData, setFormData, generateTimeline, isGenerated } = useTimelineStore();

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData({ country: e.target.value });
  };

  const handleLevelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    // 重置下级依赖项
    setFormData({ level: e.target.value, grade: '', round: '' });
  };

  const isFormValid = formData.country && formData.level && formData.grade && formData.major;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sm:p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-slate-900">填写基础信息</h2>
          <p className="text-sm text-slate-500 mt-1">获取您的专属留学规划时间线</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* 目标国家/地区 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            目标国家/地区 <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.country}
            onChange={handleCountryChange}
            className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
          >
            <option value="">请选择目标国家</option>
            <option value="美国">美国</option>
            <option value="英国">英国</option>
            <option value="中国香港">中国香港</option>
            <option value="新加坡" disabled>新加坡 (即将上线)</option>
            <option value="加拿大" disabled>加拿大 (即将上线)</option>
            <option value="澳大利亚" disabled>澳大利亚 (即将上线)</option>
          </select>
        </div>

        {/* 申请层级 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            申请层级 <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.level}
            onChange={handleLevelChange}
            className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
          >
            <option value="">请选择申请层级</option>
            <option value="本科">本科</option>
            <option value="硕士">硕士</option>
            <option value="博士">博士</option>
          </select>
        </div>

        {/* 当前年级 (动态展示) */}
        {formData.level && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700">
              当前年级 <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.grade}
              onChange={(e) => setFormData({ grade: e.target.value })}
              className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
            >
              <option value="">请选择当前年级</option>
              {formData.level === '本科' && (
                <>
                  <option value="初二">初二</option>
                  <option value="初三">初三</option>
                  <option value="高一">高一</option>
                  <option value="高二">高二</option>
                  <option value="高三">高三</option>
                  <option value="已毕业">已毕业</option>
                </>
              )}
              {(formData.level === '硕士' || formData.level === '博士') && (
                <>
                  <option value="大一">大一</option>
                  <option value="大二">大二</option>
                  <option value="大三">大三</option>
                  <option value="大四">大四</option>
                  <option value="已毕业">已毕业</option>
                </>
              )}
            </select>
          </div>
        )}

        {/* 目标专业方向 */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            目标专业方向 <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.major}
            onChange={(e) => setFormData({ major: e.target.value })}
            className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
          >
            <option value="">请选择目标专业</option>
            <option value="理工科">理工科</option>
            <option value="商科">商科</option>
            <option value="社科人文">社科人文</option>
            <option value="艺术设计">艺术设计</option>
            <option value="医学/生命科学">医学/生命科学</option>
            <option value="计算机/AI">计算机/AI</option>
            <option value="未确定">未确定</option>
          </select>
        </div>

        {/* 目标院校层级 (非必填) */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            目标院校层级 <span className="text-slate-400 font-normal">(选填)</span>
          </label>
          <select
            value={formData.tier}
            onChange={(e) => setFormData({ tier: e.target.value })}
            className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
          >
            <option value="">不确定</option>
            <option value="Top 10">Top 10</option>
            <option value="Top 30">Top 30</option>
            <option value="Top 50">Top 50</option>
            <option value="Top 100">Top 100</option>
          </select>
        </div>

        {/* 申请轮次 (仅本科显示) */}
        {formData.level === '本科' && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700">
              申请轮次 <span className="text-slate-400 font-normal">(选填)</span>
            </label>
            <select
              value={formData.round}
              onChange={(e) => setFormData({ round: e.target.value })}
              className="w-full h-11 px-4 rounded-xl border border-slate-200 bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all text-slate-900 outline-none"
            >
              <option value="">不确定</option>
              <option value="EA/ED">EA/ED（提前批）</option>
              <option value="RD">RD（常规轮）</option>
              <option value="滚动录取">滚动录取</option>
            </select>
          </div>
        )}
      </div>

      <div className="mt-8 flex justify-center">
        <button
          onClick={() => {
            generateTimeline();
            if (window.gtag) {
              window.gtag('event', 'generate_timeline', {
                'event_category': 'Engagement',
                'event_label': `${formData.country}_${formData.level}_${formData.grade}`
              });
            }
          }}
          disabled={!isFormValid}
          className={`
            w-full sm:w-auto px-12 py-3.5 rounded-xl font-medium shadow-sm transition-all
            ${isFormValid 
              ? 'bg-primary-600 hover:bg-primary-700 text-white hover:shadow-md hover:-translate-y-0.5' 
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'}
          `}
        >
          {isGenerated ? '重新生成时间线' : '一键生成专属时间线'}
        </button>
      </div>
    </div>
  );
};
