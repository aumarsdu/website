import React from 'react';
import { Link } from 'react-router-dom';
import { Calculator, DollarSign, Calendar, Target, ArrowRight, FileText, Trophy, MapPin, GraduationCap, Compass, Search } from 'lucide-react';

export const Home: React.FC = () => {
  return (
    <div className="max-w-6xl mx-auto pb-20">
      {/* Hero Section */}
      <div className="text-center mb-16 pt-8">
        <h1 className="text-4xl md:text-5xl font-bold text-neutral-900 mb-6 tracking-tight">
          全网最全的<span className="text-brand-blue">留学申请工具箱</span>
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          告别信息差与机构忽悠。用数据与工具，为你的留学申请保驾护航。免费、客观、专业。
        </p>
      </div>

      {/* Tools Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

        {/* Tool 1 */}
        <Link
          to="/gpa"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Calculator className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Calculator className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">GPA 换算器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              支持标准 4.0、北大算法、WES 算法等多种标准，一键将百分制转换为准确的 GPA。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始换算 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 2 */}
        <Link
          to="/cost"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <DollarSign className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <DollarSign className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">留学费用评估</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              全网最细致的留学成本计算。涵盖美英澳加港等主流国家，学费、住宿费、生活费一网打尽。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              免费评估 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 3 */}
        <Link
          to="/timeline"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Calendar className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Calendar className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">申请时间线规划</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              输入当前就读年级与目标国家，自动生成到入学前的每一个关键时间节点规划表。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              生成规划 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 4 */}
        <Link
          to="/visa-checklist"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <FileText className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <FileText className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">签证材料清单</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              告别繁杂的官网说明。动态生成匹配你个人情况的定制版留学签证准备清单。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              获取清单 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 5 */}
        <Link
          to="/school-matcher"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Target className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Target className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">智能选校匹配</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              输入你的 GPA、标化成绩与意向专业，基于百万真实案例库，智能推荐冲刺与保底名校。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始匹配 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 6 */}
        <Link
          to="/mock-exam"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Trophy className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Trophy className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">国际竞赛模考</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              全真在线模拟考试，免费评估你在各大国际顶尖学术竞赛中的真实水平。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始模考 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 7 */}
        <Link
          to="/tendency"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <MapPin className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <MapPin className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">国家倾向测评</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              不知道去哪个国家留学？5分钟心理测评，帮你找到最契合你性格与发展的留学地。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始测评 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 8 */}
        <Link
          to="/university-tiering"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <GraduationCap className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <GraduationCap className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">美国大学分级库</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              打破 U.S.News 排名滤镜，带你还原最真实的美国大学录取难度与含金量分级。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              查看分级 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 9 */}
        <Link
          to="/extracurricular-activity-planner"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Compass className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Compass className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">课外活动规划器</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              背景提升项目「排雷」体检器，真实评估项目的藤校认可度与避坑风险。
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              开始排雷 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>

        {/* Tool 10 */}
        <Link
          to="/case-matcher"
          className="group bg-white p-8 rounded-xl shadow-sm border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Search className="w-32 h-32 text-brand-blue" />
          </div>
          <div className="relative z-10">
            <div className="w-12 h-12 bg-brand-blue-light rounded-lg flex items-center justify-center mb-6 text-brand-blue group-hover:scale-110 transition-transform">
              <Search className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-neutral-900 mb-3">录取案例去水罗盘</h2>
            <p className="text-neutral-500 mb-6 min-h-[48px]">
              拒绝“保录”忽悠与幸存者偏差。看看与你背景最相似的学长，真实去向是哪里？
            </p>
            <span className="inline-flex items-center text-brand-blue font-medium group-hover:underline">
              匹配学长 <ArrowRight className="w-4 h-4 ml-1" />
            </span>
          </div>
        </Link>
      </div>
    </div>
  );
};
