import React from 'react';

const sections = [
  { id: 'section-1', title: '整体合作流程总览' },
  { id: 'section-2', title: '阶段 1：合作方初步筛选（准入评估）' },
  { id: 'section-3', title: '阶段 2：签署前——公司与产品服务尽调 → 合作协议' },
  { id: 'section-4', title: '阶段 3：签署后——客户画像对齐 & 对接流程制定' },
  { id: 'section-5', title: '阶段 4：合作中——线索跟进与沟通节奏' },
  { id: 'section-6', title: '阶段 5：成交确认与返佣结算' },
  { id: 'section-7', title: '阶段 6：合作复盘与续约决策' },
];

const SidebarNav: React.FC = () => {
  return (
    <nav className="sticky top-24">
      <h3 className="text-sm font-semibold text-neutral-900 mb-4 px-3 uppercase tracking-wider">
        目录
      </h3>
      <ul className="space-y-1 border-l border-neutral-200 ml-3">
        {sections.map((section) => (
          <li key={section.id}>
            <a
              href={`#${section.id}`}
              className="block py-2 pl-4 -ml-[1px] border-l border-transparent hover:border-blue-700 text-sm text-neutral-600 hover:text-blue-700 transition-colors"
            >
              {section.title}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
};

export default SidebarNav;
