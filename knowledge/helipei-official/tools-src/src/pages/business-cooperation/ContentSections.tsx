import React from 'react';

const ContentSections: React.FC = () => {
  return (
    <div className="prose prose-slate max-w-none">
      {/* 引言模块 */}
      <div className="bg-neutral-50 border-l-4 border-blue-700 p-4 rounded-r-lg mb-10">
        <p className="text-neutral-700 m-0 text-sm sm:text-base">
          <strong>合作初衷：</strong>河狸陪致力于与各界优秀机构、企业建立长期互信的合作伙伴关系。本说明旨在明确合作评估标准、推进流程及各方责任节奏，确保合作高效落地。
        </p>
      </div>

      {/* 整体合作流程总览 */}
      <section id="section-1" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          整体合作流程总览
        </h2>
        <p className="text-neutral-700 leading-relaxed mb-6">
          我们的商务合作流程共分为 6 个核心阶段，从初步评估到最终的复盘续约，全链路保障合作质量与效率。
        </p>
        <figure className="my-8">
          <img
            src="https://placehold.co/800x400/F1F5F9/1D4ED8?text=Cooperation+Process+Flowchart"
            alt="整体合作流程图"
            className="w-full h-auto rounded-lg border border-neutral-200 shadow-sm"
          />
          <figcaption className="text-center text-sm text-neutral-500 mt-3">图 1：河狸陪标准商务合作流程图</figcaption>
        </figure>
      </section>

      {/* 阶段 1：合作方初步筛选（准入评估） */}
      <section id="section-2" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 1：合作方初步筛选（准入评估）
        </h2>
        <p className="text-neutral-700 leading-relaxed">
          在正式建立合作前，我们将对潜在合作方进行多维度的准入评估，以确保双方在价值观、业务模式及目标受众上具备较高的契合度。
        </p>
        <ul className="list-disc pl-6 text-neutral-700 space-y-2 mt-4">
          <li><strong>企业资质审核：</strong> 营业执照、相关行业经营许可证等基础文件。</li>
          <li><strong>品牌信誉度：</strong> 市场口碑、历史合作案例及用户评价。</li>
          <li><strong>业务匹配度：</strong> 双方产品/服务是否能形成优势互补，受众是否重叠。</li>
        </ul>
        <div className="bg-neutral-50 rounded-lg p-4 mt-6 text-sm text-neutral-700">
          <span className="font-semibold text-neutral-900 block mb-1">💡 补充说明</span>
          对于初创型企业或创新型业务，可申请进入“白名单评估池”，我们将综合考量其业务潜力和创新价值。
        </div>
      </section>

      {/* 阶段 2：签署前——公司与产品服务尽调 → 合作协议 */}
      <section id="section-3" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 2：签署前——公司与产品服务尽调 → 合作协议
        </h2>
        <p className="text-neutral-700 leading-relaxed">
          通过初步筛选后，双方将进入深度的业务尽调和协议磋商阶段。
        </p>
        <ol className="list-decimal pl-6 text-neutral-700 space-y-3 mt-4">
          <li><strong>双向尽职调查：</strong> 深入了解产品细节、服务交付能力及售后保障体系。</li>
          <li><strong>合作模式确立：</strong> 明确合作模式（如：渠道代理、资源置换、联合开发等）。</li>
          <li><strong>商务条款磋商：</strong> 确认利益分配机制、结算周期及知识产权归属。</li>
          <li><strong>协议签署：</strong> 双方通过线上/线下方式正式签署《战略合作协议》及《保密协议》(NDA)。</li>
        </ol>
      </section>

      {/* 阶段 3：签署后——客户画像对齐 & 对接流程制定 */}
      <section id="section-4" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 3：签署后——客户画像对齐 & 对接流程制定
        </h2>
        <p className="text-neutral-700 leading-relaxed">
          协议签署完毕后，双方运营及交付团队将立刻介入，打通业务对接的“最后一公里”。
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <div className="border border-neutral-200 rounded-lg p-5 bg-white">
            <h4 className="text-lg font-semibold text-neutral-900 mb-2">🎯 客户画像对齐</h4>
            <p className="text-neutral-600 text-sm">联合梳理目标用户的核心痛点与需求特征，定制联合营销话术与转化策略。</p>
          </div>
          <div className="border border-neutral-200 rounded-lg p-5 bg-white">
            <h4 className="text-lg font-semibold text-neutral-900 mb-2">⚙️ 交付流程制定</h4>
            <p className="text-neutral-600 text-sm">明确线索流转SOP、客户跟进责任人及异常情况的升级处理机制(Escalation Path)。</p>
          </div>
        </div>
      </section>

      {/* 阶段 4：合作中——线索跟进与沟通节奏 */}
      <section id="section-5" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 4：合作中——线索跟进与沟通节奏
        </h2>
        <p className="text-neutral-700 leading-relaxed mb-4">
          在合作运营期间，保持高频、透明的沟通是确保线索转化率的关键。
        </p>
        <ul className="list-disc pl-6 text-neutral-700 space-y-2">
          <li><strong>实时线索同步：</strong> 通过专属企微群或CRM系统，实现线索的秒级分配与接盘。</li>
          <li><strong>进度定期反馈：</strong> 合作方需在规定时间内（通常为 24 小时）反馈首呼情况及意向评级。</li>
          <li><strong>例会制度：</strong> 建立双周或月度业务对接会，对齐转化数据，诊断流失原因。</li>
        </ul>
        <div className="bg-neutral-50 rounded-lg p-4 mt-6 text-sm text-neutral-700">
          <span className="font-semibold text-neutral-900 block mb-1">📌 小规模试点建议</span>
          对于全新的合作模式或陌生的客群，我们强烈建议先进行为期 1-2 个月的“小规模试点 (Pilot Test)”，通过跑通最小闭环（MVP）来验证转化模型，再进行全面铺开。
        </div>
      </section>

      {/* 阶段 5：成交确认与返佣结算 */}
      <section id="section-6" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 5：成交确认与返佣结算
        </h2>
        <p className="text-neutral-700 leading-relaxed">
          我们秉持公平、透明、高效的原则进行财务结算。
        </p>
        <ol className="list-decimal pl-6 text-neutral-700 space-y-3 mt-4">
          <li><strong>数据对账：</strong> 每月 5 日前，双方对上自然月产生的有效成交数据进行核对。</li>
          <li><strong>确认开票：</strong> 数据无误后，收款方开具符合国家规定的增值税发票。</li>
          <li><strong>资金拨付：</strong> 收到合规发票后的 15 个工作日内，完成返佣/分成款项的对公打款。</li>
        </ol>
      </section>

      {/* 阶段 6：合作复盘与续约决策 */}
      <section id="section-7" className="mb-12 scroll-mt-24">
        <h2 className="text-2xl font-bold text-blue-700 mb-4 pb-2 border-b border-neutral-100">
          阶段 6：合作复盘与续约决策
        </h2>
        <p className="text-neutral-700 leading-relaxed mb-6">
          在合作协议到期前 30 天，双方将启动年度/周期复盘，评估合作成效并探讨下一阶段的战略规划。
        </p>
        <div className="flex flex-col md:flex-row items-center bg-neutral-50 rounded-lg p-6 border border-neutral-200">
          <div className="flex-1 mb-4 md:mb-0 md:pr-6">
            <h4 className="text-lg font-semibold text-neutral-900 mb-2">续约评估维度</h4>
            <ul className="text-sm text-neutral-600 space-y-1">
              <li>• 业绩指标达成率 (KPI/OKR)</li>
              <li>• 客户满意度与客诉率</li>
              <li>• 沟通效率与协作顺畅度</li>
            </ul>
          </div>
          <div className="w-full md:w-1/3 flex justify-center">
            <img
              src="https://placehold.co/300x200/F1F5F9/1D4ED8?text=Review+Meeting"
              alt="复盘会议示意图"
              className="rounded shadow-sm"
            />
          </div>
        </div>
      </section>
    </div>
  );
};

export default ContentSections;