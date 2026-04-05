import React from 'react';
import { Header } from '../components/Header';

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="min-h-screen bg-neutral-50 font-sans text-neutral-900 selection:bg-brand-blue-light selection:text-brand-blue">
      <Header />
      
      <main>
        {children}
      </main>

      <footer className="bg-white border-t border-neutral-200 py-12 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center">
          <div className="flex items-center mb-4 md:mb-0">
            <span className="text-sm text-neutral-500">© 2026 河狸陪 (Heilipei). All rights reserved.</span>
          </div>
          <div className="flex space-x-6 text-sm text-neutral-500">
            <a href="/about.html" className="hover:text-brand-blue transition-colors">关于我们</a>
            <a href="/privacy-policy.html" className="hover:text-brand-blue transition-colors">隐私政策</a>
            <a href="/user-agreement.html" className="hover:text-brand-blue transition-colors">用户协议</a>
          </div>
        </div>
      </footer>
    </div>
  );
};
