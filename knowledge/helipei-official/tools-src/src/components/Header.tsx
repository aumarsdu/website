import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Calculator, DollarSign, Home, Calendar, FileText, Target } from 'lucide-react';

export const Header: React.FC = () => {
  const location = useLocation();

  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <Link to="/" className="flex-shrink-0 flex items-center mr-8 group">
              <div className="w-8 h-8 rounded-lg bg-brand-blue flex items-center justify-center mr-3 shadow-sm group-hover:bg-blue-800 transition-colors">
                <span className="text-white font-black text-lg">H</span>
              </div>
              <span className="text-xl font-bold text-neutral-900 tracking-tight group-hover:text-brand-blue transition-colors">河狸陪</span>
            </Link>
            
            <div className="hidden sm:flex sm:space-x-8">
              <Link 
                to="/"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <Home className="w-4 h-4 mr-1.5" />
                首页
              </Link>
              <Link 
                to="/gpa"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/gpa' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <Calculator className="w-4 h-4 mr-1.5" />
                GPA 换算器
              </Link>
              <Link 
                to="/cost"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/cost' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <DollarSign className="w-4 h-4 mr-1.5" />
                费用计算器
              </Link>
              <Link 
                to="/timeline"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/timeline' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <Calendar className="w-4 h-4 mr-1.5" />
                时间线生成器
              </Link>
              <Link 
                to="/visa-checklist"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/visa-checklist' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <FileText className="w-4 h-4 mr-1.5" />
                签证清单
              </Link>
              <Link 
                to="/school-matcher"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  location.pathname === '/school-matcher' 
                    ? 'border-brand-blue text-brand-blue' 
                    : 'border-transparent text-neutral-500 hover:border-neutral-300 hover:text-neutral-700'
                }`}
              >
                <Target className="w-4 h-4 mr-1.5" />
                智能选校
              </Link>
            </div>
          </div>
          <div className="hidden lg:ml-6 lg:flex lg:items-center">
            <a 
              href="/"
              className="bg-neutral-50 hover:bg-neutral-100 text-neutral-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-neutral-200"
            >
              返回河狸陪首页
            </a>
          </div>
        </div>
      </div>
    </header>
  );
};
