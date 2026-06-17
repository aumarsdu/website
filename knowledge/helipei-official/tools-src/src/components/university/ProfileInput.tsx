import React from 'react';
import { useUniversityStore } from '../../store/universityStore';

export const ProfileInput: React.FC = () => {
  const { profile, updateProfile, resetProfile } = useUniversityStore();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateProfile({ [name]: value === '' ? null : Number(value) });
  };

  return (
    <div className="bg-neutral-50 p-6 rounded-xl border border-neutral-200 shadow-sm">
      <h3 className="text-xl font-bold text-neutral-900 mb-4">测测你的匹配度</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">GPA (4.0 scale)</label>
          <input
            type="number"
            name="gpa"
            step="0.1"
            min="0"
            max="4.0"
            value={profile.gpa || ''}
            onChange={handleChange}
            className="w-full p-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
            placeholder="e.g. 3.8"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-neutral-700 mb-1">SAT</label>
          <input
            type="number"
            name="sat"
            step="10"
            min="400"
            max="1600"
            value={profile.sat || ''}
            onChange={handleChange}
            className="w-full p-2 border border-neutral-300 rounded-md focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
            placeholder="e.g. 1450"
          />
        </div>
      </div>
      <button
        onClick={resetProfile}
        className="mt-4 text-sm text-neutral-500 hover:text-neutral-700"
      >
        清空数据
      </button>
    </div>
  );
};