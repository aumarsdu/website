import React, { useState } from 'react';
import { ProfileInput } from '../components/university/ProfileInput';
import { UniversityCard } from '../components/university/UniversityCard';
import universitiesData from '../data/universities.json';
import { University } from '../types/university';

export const UniversityTieringPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const universities = universitiesData as University[];

  const filteredUniversities = universities.filter(u =>
    u.nameZh.includes(searchTerm) || u.nameEn.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-10 text-center">
        <h1 className="text-3xl md:text-4xl font-bold text-neutral-900 mb-4">Top 200 院校分层与录取画像</h1>
        <p className="text-lg text-neutral-600 max-w-2xl mx-auto">输入你的学术成绩，动态评估你的冲刺、匹配与保底选校策略。</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-6">
          <ProfileInput />

          <div className="bg-white p-6 rounded-xl border border-neutral-200">
             <h3 className="text-lg font-bold text-neutral-900 mb-3">搜索学校</h3>
             <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="输入中英文名称..."
                className="w-full p-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-blue-600"
              />
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredUniversities.map(uni => (
              <UniversityCard key={uni.id} university={uni} />
            ))}
          </div>
          {filteredUniversities.length === 0 && (
            <div className="text-center py-12 text-neutral-500">没有找到匹配的学校</div>
          )}
        </div>
      </div>
    </div>
  );
};