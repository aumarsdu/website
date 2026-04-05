import React, { useState } from 'react';
import { Search, GraduationCap, Globe, Filter, AlertCircle, ArrowRight, Download, Lock } from 'lucide-react';
import { matchSchools, MatchedSchool } from '../data/schoolData';

export const SchoolMatcher: React.FC = () => {
  const [step, setStep] = useState<number>(1);
  
  // Form State
  const [degree, setDegree] = useState<string>('master');
  const [major, setMajor] = useState<string>('cs');
  const [gpaStr, setGpaStr] = useState<string>('');
  const [gpaError, setGpaError] = useState<string>('');
  const [schoolBg, setSchoolBg] = useState<string>('985');
  const [countries, setCountries] = useState<string[]>([]);
  const [highlights, setHighlights] = useState<string[]>([]);
  
  // Results State
  const [results, setResults] = useState<{ reach: MatchedSchool[], match: MatchedSchool[], safety: MatchedSchool[] } | null>(null);

  const handleCountryToggle = (code: string) => {
    setCountries(prev => 
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    );
  };

  const handleHighlightToggle = (tag: string) => {
    setHighlights(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const validateGpa = () => {
    if (!gpaStr) {
      setGpaError("请输入当前 GPA");
      return false;
    }
    const gpa = parseFloat(gpaStr);
    if (isNaN(gpa) || gpa < 0 || gpa > 4.0) {
      setGpaError("请输入有效的 GPA (0.0 - 4.0)");
      return false;
    }
    setGpaError("");
    return true;
  };

  const handleMatch = () => {
    if (!validateGpa()) return;
    
    const gpa = parseFloat(gpaStr);
    const matched = matchSchools(gpa, countries, schoolBg, highlights);
    setResults(matched);
    setStep(3);
  };

  const renderSchoolCard = (school: MatchedSchool, index: number, isLocked: boolean = false) => {
    return (
      <div key={school.id} className={`p-5 rounded-xl border relative transition-all ${isLocked ? 'bg-slate-50 border-slate-200 opacity-90' : 'bg-white border-slate-100 shadow-sm hover:shadow-md'}`}>
        {isLocked && (
          <div className="absolute inset-0 bg-slate-50/60 backdrop-blur-[2px] rounded-xl flex flex-col items-center justify-center z-10">
            <div className="bg-white p-3 rounded-full shadow-sm mb-2">
              <Lock className="w-5 h-5 text-slate-400" />
            </div>
            <span className="text-sm font-medium text-slate-500">解锁查看</span>
          </div>
        )}
        
        <div className="flex justify-between items-start mb-3">
          <div>
            <h4 className="font-bold text-lg text-slate-800">{school.name}</h4>
            <p className="text-xs text-slate-500 font-medium">{school.en_name}</p>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-xs font-bold px-2 py-1 bg-slate-100 text-slate-600 rounded-md">
              {school.country === 'US' ? 'US News' : school.country === 'UK' ? 'QS' : 'QS'} #{school.ranking}
            </span>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-2 mb-4">
          {school.tags.map(tag => (
            <span key={tag} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded border border-blue-100">
              {tag}
            </span>
          ))}
        </div>
        
        <div className="pt-3 border-t border-slate-100 flex justify-between items-center text-sm">
          <span className="text-slate-500">建议 GPA</span>
          <span className="font-medium text-slate-700">{school.req_gpa.toFixed(1)}+</span>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-20">
      <div className="bg-gradient-to-br from-blue-900 to-indigo-900 text-white py-12 px-4 sm:px-6 lg:px-8 text-center relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
        <div className="max-w-3xl mx-auto relative z-10">
          <div className="inline-flex items-center justify-center p-2 bg-white/10 rounded-xl mb-4 backdrop-blur-sm border border-white/20">
            <Search className="w-5 h-5 mr-2 text-blue-200" />
            <span className="font-medium text-blue-50 tracking-wide text-sm">河狸陪智能选校</span>
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold mb-4 leading-tight">
            院校匹配器
          </h1>
          <p className="text-lg md:text-xl text-blue-100 max-w-2xl mx-auto">
            输入你的背景条件，10秒智能生成 冲刺 / 匹配 / 保底 选校方案。
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-20">
        
        {step < 3 && (
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-8 border-b border-slate-100 pb-4">
              <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                {step === 1 ? <><GraduationCap className="w-6 h-6 text-blue-600" /> 1. 学术背景</> : <><Globe className="w-6 h-6 text-blue-600" /> 2. 目标偏好</>}
              </h2>
              <div className="text-sm font-medium text-slate-400">
                Step {step} of 2
              </div>
            </div>

            {step === 1 && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">申请层级</label>
                    <div className="flex gap-3">
                      {['bachelor', 'master', 'phd'].map(deg => (
                        <button
                          key={deg}
                          onClick={() => {
                            setDegree(deg);
                            // Reset schoolBg to default based on degree
                            if (deg === 'bachelor') setSchoolBg('key_public');
                            else if (deg === 'master') setSchoolBg('985');
                            else if (deg === 'phd') setSchoolBg('c9_985');
                          }}
                          className={`flex-1 py-3 px-4 rounded-xl border font-medium text-sm transition-all ${
                            degree === deg 
                              ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm' 
                              : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          {deg === 'bachelor' ? '本科' : deg === 'master' ? '硕士' : '博士'}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">当前 GPA (4.0制)</label>
                    <input 
                      type="number" 
                      step="0.1" 
                      min="0" 
                      max="4.0"
                      placeholder="例如: 3.5"
                      value={gpaStr}
                      onChange={(e) => {
                        setGpaStr(e.target.value);
                        if (gpaError) setGpaError("");
                      }}
                      className={`w-full bg-slate-50 border ${gpaError ? 'border-red-500 focus:ring-red-500' : 'border-slate-200 focus:ring-blue-500'} text-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:border-transparent transition-all`}
                    />
                    {gpaError && <p className="text-xs text-red-500 mt-2 flex items-center gap-1"><AlertCircle className="w-3 h-3" /> {gpaError}</p>}
                    <p className="text-xs text-slate-400 mt-2">不知道 4.0 GPA？可以使用 <a href="/gpa" className="text-blue-500 hover:underline">GPA 换算器</a></p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      {degree === 'bachelor' ? '高中学校背景' : 
                       degree === 'master' ? '本科院校背景' : '最高学历院校背景'}
                    </label>
                    <select 
                      value={schoolBg}
                      onChange={(e) => setSchoolBg(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 text-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    >
                      {degree === 'bachelor' && (
                        <>
                          <option value="top_international">顶尖国际学校/公立国际部</option>
                          <option value="normal_international">普通国际学校/双语学校</option>
                          <option value="top_public">国内顶尖重点高中</option>
                          <option value="key_public">国内省级/市级重点高中</option>
                          <option value="normal_public">国内普通高中</option>
                          <option value="overseas_hs">海外高中</option>
                        </>
                      )}
                      {degree === 'master' && (
                        <>
                          <option value="c9">C9 联盟</option>
                          <option value="985">985 高校</option>
                          <option value="211">211 高校</option>
                          <option value="double_first">双一流</option>
                          <option value="normal">双非一本</option>
                          <option value="other">二本及其他</option>
                          <option value="overseas">海外本</option>
                          <option value="coop">中外合作办学</option>
                        </>
                      )}
                      {degree === 'phd' && (
                        <>
                          <option value="top_overseas">海外顶尖名校 (QS Top 50)</option>
                          <option value="normal_overseas">海外普通院校</option>
                          <option value="c9_985">国内 C9 / 985 高校</option>
                          <option value="211_double_first">国内 211 / 双一流</option>
                          <option value="normal_cn">国内双非院校</option>
                          <option value="research_inst">中科院等顶尖科研院所</option>
                        </>
                      )}
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">意向专业大类</label>
                    <select 
                      value={major}
                      onChange={(e) => setMajor(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 text-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    >
                      <option value="cs">计算机/EE/数据科学</option>
                      <option value="business">商科/泛商科</option>
                      <option value="engineering">传统工科</option>
                      <option value="science">理科/基础学科</option>
                      <option value="arts">人文社科</option>
                      <option value="design">艺术设计</option>
                      <option value="law">法学</option>
                      <option value="med">医学/公共卫生</option>
                    </select>
                  </div>
                </div>

                <div className="mt-8 flex justify-end">
                  <button 
                    onClick={() => {
                      if (validateGpa()) {
                        setStep(2);
                      }
                    }}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3.5 px-8 rounded-xl shadow-lg shadow-blue-600/30 transition-all flex items-center gap-2"
                  >
                    下一步 <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-3">目标留学国家/地区 (可多选)</label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { code: 'US', label: '美国', icon: '🇺🇸' },
                      { code: 'UK', label: '英国', icon: '🇬🇧' },
                      { code: 'HK', label: '中国香港', icon: '🇭🇰' },
                      { code: 'SG', label: '新加坡', icon: '🇸🇬' },
                      { code: 'AU', label: '澳洲', icon: '🇦🇺' },
                      { code: 'CA', label: '加拿大', icon: '🇨🇦' }
                    ].map(country => (
                      <button
                        key={country.code}
                        onClick={() => handleCountryToggle(country.code)}
                        className={`py-3 px-4 rounded-xl border flex items-center justify-center gap-2 transition-all ${
                          countries.includes(country.code) 
                            ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm' 
                            : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        <span className="text-xl">{country.icon}</span>
                        <span className="font-medium text-sm">{country.label}</span>
                      </button>
                    ))}
                  </div>
                  {countries.length === 0 && <p className="text-xs text-amber-500 mt-2">如不选则默认推荐所有国家</p>}
                </div>

                <div className="bg-slate-50 rounded-xl p-5 border border-slate-100 mt-6">
                  <div className="flex items-start gap-3">
                    <Filter className="w-5 h-5 text-slate-400 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-slate-700 text-sm mb-1">选填项：背景亮点加成</h4>
                      <p className="text-xs text-slate-500 mb-3">勾选以下亮点，将略微提升冲刺名校的成功率预测。</p>
                      <div className="flex flex-wrap gap-2">
                        {['高分标化 (GRE/GMAT)', '顶级科研/一作论文', '大厂核心实习', '国际竞赛大奖', '海外交换经历'].map(tag => (
                          <label key={tag} className={`flex items-center gap-2 bg-white border px-3 py-1.5 rounded-lg cursor-pointer transition-colors ${highlights.includes(tag) ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                            <input 
                              type="checkbox" 
                              className="rounded text-blue-600 focus:ring-blue-500" 
                              checked={highlights.includes(tag)}
                              onChange={() => handleHighlightToggle(tag)}
                            />
                            <span className={`text-xs font-medium ${highlights.includes(tag) ? 'text-blue-700' : 'text-slate-600'}`}>{tag}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-8 flex justify-between">
                  <button 
                    onClick={() => setStep(1)}
                    className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 font-medium py-3.5 px-6 rounded-xl transition-all"
                  >
                    返回修改
                  </button>
                  <button 
                    onClick={handleMatch}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3.5 px-8 rounded-xl shadow-lg shadow-blue-600/30 transition-all flex items-center gap-2"
                  >
                    开始智能匹配 <Search className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Results */}
        {step === 3 && results && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 md:p-8 mb-8 flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <h2 className="text-2xl font-bold text-slate-800 mb-2">您的专属选校方案</h2>
                <div className="flex flex-wrap gap-2 text-sm text-slate-500">
                  <span className="px-2 py-1 bg-slate-100 rounded-md">GPA: {gpaStr}</span>
                  <span className="px-2 py-1 bg-slate-100 rounded-md">
                    {schoolBg === 'top_international' ? '顶尖国际学校' : 
                     schoolBg === 'normal_international' ? '普通国际学校' : 
                     schoolBg === 'top_public' ? '顶尖重点高中' : 
                     schoolBg === 'key_public' ? '省级/市级重点' : 
                     schoolBg === 'normal_public' ? '普通高中' : 
                     schoolBg === 'overseas_hs' ? '海外高中' : 
                     schoolBg === 'c9' ? 'C9联盟' : 
                     schoolBg === '985' ? '985高校' : 
                     schoolBg === '211' ? '211高校' : 
                     schoolBg === 'double_first' ? '双一流' : 
                     schoolBg === 'overseas' ? '海外本' : 
                     schoolBg === 'coop' ? '中外合作' : 
                     schoolBg === 'normal' ? '双非一本' : 
                     schoolBg === 'top_overseas' ? '海外顶尖名校' : 
                     schoolBg === 'normal_overseas' ? '海外普通院校' : 
                     schoolBg === 'c9_985' ? 'C9/985高校' : 
                     schoolBg === '211_double_first' ? '211/双一流' : 
                     schoolBg === 'normal_cn' ? '国内双非' : 
                     schoolBg === 'research_inst' ? '顶尖科研院所' : '其他'}
                  </span>
                  <span className="px-2 py-1 bg-slate-100 rounded-md">
                    {major === 'cs' ? 'CS/数据' : 
                     major === 'business' ? '商科' : 
                     major === 'engineering' ? '工科' : 
                     major === 'science' ? '理科' : 
                     major === 'arts' ? '人文社科' : 
                     major === 'design' ? '艺术设计' : 
                     major === 'law' ? '法学' : '医学'}
                  </span>
                  {highlights.length > 0 && (
                    <span className="px-2 py-1 bg-blue-50 text-blue-600 rounded-md font-medium border border-blue-100">
                      有高光背景加成
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-3 w-full md:w-auto">
                <button 
                  onClick={() => setStep(1)}
                  className="flex-1 md:flex-none px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-50"
                >
                  重新测算
                </button>
                <button 
                  className="flex-1 md:flex-none px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center justify-center gap-2 shadow-sm"
                  onClick={() => alert("PDF 下载功能开发中...")}
                >
                  <Download className="w-4 h-4" /> 保存报告
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              {/* Reach Schools */}
              <div className="flex flex-col gap-4">
                <div className="bg-red-50 border border-red-100 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">🔴</span>
                    <h3 className="font-bold text-red-800">冲刺校 (Reach)</h3>
                  </div>
                  <p className="text-xs text-red-600">录取率较低，需要极强软背景支持</p>
                </div>
                
                {results.reach.slice(0, 1).map((school, i) => renderSchoolCard(school, i, false))}
                {results.reach.length > 1 && results.reach.slice(1, 3).map((school, i) => renderSchoolCard(school, i + 1, true))}
                {results.reach.length === 0 && (
                  <div className="p-5 text-center text-slate-500 text-sm border border-dashed border-slate-300 rounded-xl bg-white">
                    <p className="font-medium mb-1">未匹配到冲刺名校</p>
                    <p className="text-xs text-slate-400">您的背景较为特殊，建议直接获取 1v1 人工深度评估。</p>
                  </div>
                )}
              </div>

              {/* Match Schools */}
              <div className="flex flex-col gap-4">
                <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">🟡</span>
                    <h3 className="font-bold text-amber-800">匹配校 (Match)</h3>
                  </div>
                  <p className="text-xs text-amber-600">硬件达标，主申院校，需文书发力</p>
                </div>

                {results.match.slice(0, 2).map((school, i) => renderSchoolCard(school, i, false))}
                {results.match.length > 2 && results.match.slice(2, 4).map((school, i) => renderSchoolCard(school, i + 2, true))}
                {results.match.length === 0 && (
                  <div className="p-5 text-center text-slate-500 text-sm border border-dashed border-slate-300 rounded-xl bg-white">
                    <p className="font-medium mb-1">无完全匹配的院校</p>
                    <p className="text-xs text-slate-400">建议调整选校范围，或联系顾问定制方案。</p>
                  </div>
                )}
              </div>

              {/* Safety Schools */}
              <div className="flex flex-col gap-4">
                <div className="bg-green-50 border border-green-100 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">🟢</span>
                    <h3 className="font-bold text-green-800">保底校 (Safety)</h3>
                  </div>
                  <p className="text-xs text-green-600">硬件稳录区间，兜底选择</p>
                </div>

                {results.safety.slice(0, 1).map((school, i) => renderSchoolCard(school, i, false))}
                {results.safety.length > 1 && results.safety.slice(1, 2).map((school, i) => renderSchoolCard(school, i + 1, true))}
                {results.safety.length === 0 && (
                  <div className="p-5 text-center text-slate-500 text-sm border border-dashed border-slate-300 rounded-xl bg-white">
                    <p className="font-medium mb-1">未匹配到保底院校</p>
                    <p className="text-xs text-slate-400">可能是 GPA 过低或数据库未覆盖您的保底选项。</p>
                  </div>
                )}
              </div>
            </div>

            {/* CTA Section */}
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl shadow-xl overflow-hidden relative">
              <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 -translate-y-1/2 translate-x-1/2"></div>
              
              <div className="p-8 md:p-10 flex flex-col md:flex-row items-center justify-between relative z-10 gap-8">
                <div className="text-white max-w-xl text-center md:text-left">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 border border-white/20 text-blue-300 text-xs font-medium mb-4">
                    <AlertCircle className="w-3.5 h-3.5" /> 仅展示部分简略结果
                  </div>
                  <h3 className="text-2xl md:text-3xl font-bold mb-3">解锁完整 15 所校单 & 差距诊断</h3>
                  <p className="text-slate-300 text-sm md:text-base leading-relaxed mb-6">
                    获取完整匹配院校库，并由前招生官领衔团队进行 1v1 履历评估。我们将指出你与梦校的真实差距，提供科研/竞赛/实习的专属补强方案。
                  </p>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-slate-200 mb-0">
                    <li className="flex items-center gap-2"><CheckCircleIcon /> 完整版选校组合推荐</li>
                    <li className="flex items-center gap-2"><CheckCircleIcon /> 个性化背景提升规划</li>
                    <li className="flex items-center gap-2"><CheckCircleIcon /> 核心软实力缺失诊断</li>
                    <li className="flex items-center gap-2"><CheckCircleIcon /> 申请时间线排期建议</li>
                  </ul>
                </div>
                
                <div className="w-full md:w-auto flex-shrink-0 bg-white p-6 rounded-xl shadow-lg text-center min-w-[280px]">
                  <div className="w-40 h-40 bg-slate-100 mx-auto mb-4 rounded-lg flex items-center justify-center border border-slate-200 overflow-hidden">
                    <div className="text-center">
                      <div className="w-24 h-24 bg-white border-2 border-slate-800 rounded-md mx-auto flex items-center justify-center p-1 mb-2">
                        <div className="w-full h-full border-4 border-slate-800 border-dashed opacity-50"></div>
                      </div>
                      <span className="text-xs text-slate-400 font-medium">微信扫码添加</span>
                    </div>
                  </div>
                  <p className="text-slate-800 font-bold text-sm mb-1">长按或扫码添加顾问</p>
                  <p className="text-blue-600 text-xs font-medium">免费获取你的完整报告</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const CheckCircleIcon = () => (
  <svg className="w-4 h-4 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22 4 12 14.01 9 11.01"></polyline>
  </svg>
);