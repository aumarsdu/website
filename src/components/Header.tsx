import React from 'react';
import { Calculator } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              {/* Logo 占位 */}
              <div className="w-8 h-8 rounded-lg bg-brand-blue flex items-center justify-center mr-3 shadow-sm">
                <span className="text-white font-black text-lg">H</span>
              </div>
              <span className="text-xl font-bold text-neutral-900 tracking-tight">河狸陪</span>
            </div>
            <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
              <span className="border-brand-blue text-brand-blue inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                <Calculator className="w-4 h-4 mr-1.5" />
                GPA 换算器
              </span>
            </div>
          </div>
          <div className="hidden sm:ml-6 sm:flex sm:items-center">
            <button className="bg-neutral-50 hover:bg-neutral-100 text-neutral-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-neutral-200">
              了解更多
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
