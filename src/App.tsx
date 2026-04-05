import React from 'react';
import { Header } from './components/Header';
import { CourseInput } from './components/CourseInput';
import { AlgorithmSelect } from './components/AlgorithmSelect';
import { ResultCard } from './components/ResultCard';
import { CtaCard } from './components/CtaCard';

function App() {
  return (
    <div className="min-h-screen bg-neutral-50 font-sans text-neutral-900 selection:bg-brand-blue-light selection:text-brand-blue">
      <Header />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-black text-neutral-900 mb-4 tracking-tight">
            GPA 换算器
          </h1>
          <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
            精准、免费的 GPA 换算工具。支持标准 4.0、北大 4.0 等 7 种主流算法，快速评估你的留学竞争力。
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-7 xl:col-span-8 order-2 lg:order-1 space-y-6">
            <AlgorithmSelect />
            <CourseInput />
          </div>
          
          <div className="lg:col-span-5 xl:col-span-4 order-1 lg:order-2 sticky top-24">
            <ResultCard />
            <CtaCard />
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-neutral-200 py-12 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center">
          <div className="flex items-center mb-4 md:mb-0">
            <span className="text-sm text-neutral-500">© 2024 河狸陪 (Heilipei). All rights reserved.</span>
          </div>
          <div className="flex space-x-6 text-sm text-neutral-500">
            <a href="#" className="hover:text-brand-blue transition-colors">关于我们</a>
            <a href="#" className="hover:text-brand-blue transition-colors">隐私政策</a>
            <a href="#" className="hover:text-brand-blue transition-colors">用户协议</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
