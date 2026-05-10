import React from 'react';
import { CostForm } from '../components/cost/CostForm';
import { CostReport } from '../components/cost/CostReport';
import { CostCta } from '../components/cost/CostCta';

export const CostCalculator: React.FC = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-black text-neutral-900 mb-4 tracking-tight">
          留学费用计算器
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          覆盖全球热门留学目的地，提供节省、适中、宽裕三档消费预估。一键算清你的留学真实花销。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-7 xl:col-span-8 order-2 lg:order-1 space-y-6">
          <CostForm />
        </div>
        
        <div className="lg:col-span-5 xl:col-span-4 order-1 lg:order-2 sticky top-24">
          <CostReport />
          <CostCta />
        </div>
      </div>
    </div>
  );
};
