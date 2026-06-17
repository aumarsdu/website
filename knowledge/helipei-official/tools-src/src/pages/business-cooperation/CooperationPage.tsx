import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import SidebarNav from './SidebarNav';
import ContentSections from './ContentSections';
import CtaSection from './CtaSection';

const CooperationPage: React.FC = () => {
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      const id = location.hash.replace('#', '');
      const element = document.getElementById(id);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [location]);

  return (
    <div className="min-h-screen bg-neutral-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-10">
          <h1 className="text-3xl sm:text-4xl font-bold text-neutral-900 tracking-tight">
            商务合作流程说明
          </h1>
          <p className="mt-4 text-lg text-neutral-600 max-w-3xl">
            欢迎了解河狸陪的商务合作流程。我们致力于通过科技和陪伴，帮助学习者获得更好的学习体验和人生成长。
          </p>
        </div>

        <div className="flex flex-col md:flex-row md:space-x-12">
          {/* 左侧导航 - 移动端隐藏，桌面端固定 */}
          <aside className="hidden md:block w-64 flex-shrink-0">
            <SidebarNav />
          </aside>

          {/* 右侧主内容区 */}
          <main className="flex-1 bg-white rounded-xl shadow-sm border border-neutral-200 p-6 sm:p-10">
            <ContentSections />
            <CtaSection />
          </main>
        </div>
      </div>
    </div>
  );
};

export default CooperationPage;
