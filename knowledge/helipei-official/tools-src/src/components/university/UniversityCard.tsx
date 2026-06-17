import React from 'react';
import { University } from '../../types/university';
import { useUniversityStore } from '../../store/universityStore';
import { calculateMatchLevel } from '../../utils/matchingAlgorithm';

interface Props {
  university: University;
}

export const UniversityCard: React.FC<Props> = ({ university }) => {
  const profile = useUniversityStore((state) => state.profile);
  const matchLevel = calculateMatchLevel(university, profile);

  const getMatchBadge = () => {
    if (matchLevel === 'Unknown') return null;

    const styles = {
      Safe: 'bg-green-50 text-green-600 border-green-200',
      Match: 'bg-blue-50 text-blue-700 border-blue-200',
      Reach: 'bg-orange-50 text-orange-500 border-orange-200',
    };

    const labels = {
      Safe: '保底 (Safe)',
      Match: '匹配 (Match)',
      Reach: '冲刺 (Reach)',
    };

    return (
      <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${styles[matchLevel as keyof typeof styles]}`}>
        {labels[matchLevel as keyof typeof labels]}
      </span>
    );
  };

  return (
    <div className="bg-white p-6 rounded-xl border border-neutral-200 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-bold text-neutral-900">{university.nameZh}</h3>
          <p className="text-sm text-neutral-500">{university.nameEn}</p>
        </div>
        {getMatchBadge()}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <span className="px-2 py-1 bg-neutral-100 text-neutral-700 text-xs rounded-md font-medium">{university.tier}</span>
        {university.tags.map(tag => (
          <span key={tag} className="px-2 py-1 bg-neutral-100 text-neutral-600 text-xs rounded-md">{tag}</span>
        ))}
      </div>

      <div className="space-y-2 text-sm text-neutral-600">
        <div className="flex justify-between">
          <span>录取 GPA (25%-75%):</span>
          <span className="font-medium">{university.admissionProfile.gpa.min} - {university.admissionProfile.gpa.max}</span>
        </div>
        {university.admissionProfile.sat && (
          <div className="flex justify-between">
            <span>录取 SAT:</span>
            <span className="font-medium">{university.admissionProfile.sat.min} - {university.admissionProfile.sat.max}</span>
          </div>
        )}
      </div>
    </div>
  );
};