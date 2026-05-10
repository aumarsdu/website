import React from 'react';
import { useStore } from '../store';
import { ALGORITHMS, AlgorithmType } from '../utils/gpa';
import { Calculator } from 'lucide-react';

export const AlgorithmSelect: React.FC = () => {
  const { algorithm, setAlgorithm } = useStore();
  
  const algorithmsList = Object.values(ALGORITHMS);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-300 p-6 mb-6">
      <div className="flex items-center mb-4">
        <Calculator className="w-5 h-5 text-brand-blue mr-2" />
        <h2 className="text-xl font-bold text-neutral-900">选择算法</h2>
      </div>
      
      <p className="text-sm text-neutral-500 mb-5">
        不同院校的 GPA 算法映射规则不同，选择目标算法以查看结果。
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {algorithmsList.map(algo => (
          <button
            key={algo.id}
            onClick={() => setAlgorithm(algo.id as AlgorithmType)}
            className={`
              px-4 py-3 rounded-lg border text-sm font-medium transition-all
              ${algorithm === algo.id 
                ? 'bg-brand-blue-light border-brand-blue text-brand-blue shadow-sm' 
                : 'bg-white border-neutral-300 text-neutral-700 hover:border-neutral-500 hover:bg-neutral-50'
              }
            `}
          >
            {algo.name}
          </button>
        ))}
      </div>
    </div>
  );
};
