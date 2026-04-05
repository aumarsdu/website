import React from 'react';
import { useCostStore } from '../../store/costStore';
import { COST_DATA, DEGREE_TYPES, SCHOOL_TYPES, ACCOMMODATION_TYPES } from '../../utils/cost/data';

export const CostForm: React.FC = () => {
  const { country, city, degree, schoolType, duration, accommodation, setField } = useCostStore();
  const currentCountry = COST_DATA[country];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-300 p-6 mb-6">
      <h2 className="text-xl font-bold text-neutral-900 mb-6">基本信息录入</h2>
      
      <div className="space-y-5">
        {/* 1. 国家选择 */}
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-2">目标国家/地区</label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.values(COST_DATA).map(c => (
              <button
                key={c.id}
                onClick={() => {
                  setField('country', c.id);
                  if (window.gtag) {
                    window.gtag('event', 'select_country', {
                      'event_category': 'Engagement',
                      'event_label': c.name
                    });
                  }
                }}
                className={`
                  flex items-center justify-center px-3 py-2 rounded-lg border text-sm font-medium transition-all
                  ${country === c.id 
                    ? 'bg-brand-blue-light border-brand-blue text-brand-blue shadow-sm' 
                    : 'bg-white border-neutral-300 text-neutral-700 hover:border-neutral-500 hover:bg-neutral-50'
                  }
                `}
              >
                <span className="mr-2 text-lg">{c.flag}</span>
                {c.name}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* 2. 城市选择 */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">目标城市/地区</label>
            <select
              value={city}
              onChange={(e) => setField('city', e.target.value)}
              className="w-full px-3 py-2.5 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent text-sm text-neutral-900"
            >
              {currentCountry?.cities.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* 3. 学位层次 */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">学位层次</label>
            <select
              value={degree}
              onChange={(e) => setField('degree', e.target.value)}
              className="w-full px-3 py-2.5 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent text-sm text-neutral-900"
            >
              {DEGREE_TYPES.map(d => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          
          {/* 4. 学校类型 */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">学校类型</label>
            <select
              value={schoolType}
              onChange={(e) => setField('schoolType', e.target.value)}
              className="w-full px-3 py-2.5 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent text-sm text-neutral-900"
            >
              {SCHOOL_TYPES.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          {/* 5. 学制 */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">学制 (年)</label>
            <input
              type="number"
              min="0.5"
              step="0.5"
              value={duration}
              onChange={(e) => setField('duration', parseFloat(e.target.value) || 1)}
              className="w-full px-3 py-2.5 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent text-sm text-neutral-900"
            />
          </div>
          
          {/* 6. 住宿偏好 */}
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-neutral-700 mb-2">住宿偏好</label>
            <div className="grid grid-cols-3 gap-3">
              {ACCOMMODATION_TYPES.map(a => (
                <button
                  key={a.id}
                  onClick={() => {
                    setField('accommodation', a.id);
                    if (window.gtag) {
                      window.gtag('event', 'select_accommodation', {
                        'event_category': 'Engagement',
                        'event_label': a.name
                      });
                    }
                  }}
                  className={`
                    px-3 py-2 rounded-lg border text-sm font-medium transition-all
                    ${accommodation === a.id 
                      ? 'bg-brand-blue-light border-brand-blue text-brand-blue shadow-sm' 
                      : 'bg-white border-neutral-300 text-neutral-700 hover:border-neutral-500 hover:bg-neutral-50'
                    }
                  `}
                >
                  {a.name}
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-neutral-500">
              💡 提示：更改以上选项，右侧的费用预估结果将实时自动更新。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
