import React, { useState } from 'react';
import { useStore } from '../store';
import { ALGORITHMS, AlgorithmType } from '../utils/gpa';
import { Calculator, Info } from 'lucide-react';

export const AlgorithmSelect: React.FC = () => {
  const { algorithm, setAlgorithm } = useStore();
  const [hoveredAlgo, setHoveredAlgo] = useState<string | null>(null);
  
  const algorithmsList = Object.values(ALGORITHMS);
  
  // 为不同算法添加对应的使用场景提示
  const getAlgoTooltip = (id: string) => {
    switch (id) {
      case 'standard4': return '美国 WES 官方最常用的基础 4.0 换算法';
      case 'peking4': return '对 85 分以上非常友好，国内 985/211 申请美研最常用';
      case 'fudan4': return '相对严格，适合高分段（90分以上）较多的同学';
      case 'zhejiang4': return '阶梯式换算，对 80-84 分段的同学较友好';
      case 'sjtu4': return '上海交大算法，整体换算结果适中';
      case 'ustc4': return '上海交大算法的改良版，部分美国公立大学认可';
      case 'ustc43': return '满分 4.3 的特殊算法，适合中科大及部分采用此制的院校';
      default: return '选择适合您目标院校的换算方式';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-300 p-6 mb-6">
      <div className="flex items-center mb-4">
        <Calculator className="w-5 h-5 text-brand-blue mr-2" />
        <h2 className="text-xl font-bold text-neutral-900">选择算法</h2>
      </div>
      
      <p className="text-sm text-neutral-500 mb-5">
        不同院校的 GPA 算法映射规则不同，选择对你最有利的目标算法以查看结果。
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {algorithmsList.map(algo => (
          <div 
            key={algo.id} 
            className="relative"
            onMouseEnter={() => setHoveredAlgo(algo.id)}
            onMouseLeave={() => setHoveredAlgo(null)}
          >
            <button
              onClick={() => {
                setAlgorithm(algo.id as AlgorithmType);
                if (window.gtag) {
                  window.gtag('event', 'switch_algorithm', {
                    'event_category': 'Engagement',
                    'event_label': algo.name
                  });
                }
              }}
              className={`
                w-full px-3 py-3 rounded-lg border text-sm font-medium transition-all flex items-center justify-between
                ${algorithm === algo.id 
                  ? 'bg-brand-blue-light border-brand-blue text-brand-blue shadow-sm' 
                  : 'bg-white border-neutral-300 text-neutral-700 hover:border-neutral-500 hover:bg-neutral-50'
                }
              `}
            >
              <span className="truncate pr-1">{algo.name}</span>
              <Info className={`w-3.5 h-3.5 shrink-0 ${algorithm === algo.id ? 'text-brand-blue opacity-70' : 'text-neutral-400'}`} />
            </button>
            
            {/* Tooltip */}
            {hoveredAlgo === algo.id && (
              <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-neutral-800 text-white text-xs rounded shadow-lg pointer-events-none">
                <div className="text-center">{getAlgoTooltip(algo.id)}</div>
                {/* 倒三角箭头 */}
                <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-neutral-800"></div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
