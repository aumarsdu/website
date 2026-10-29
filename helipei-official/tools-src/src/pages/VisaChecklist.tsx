import React, { useState, useEffect } from 'react';
import { Download, MessageCircle, FileText, CheckCircle2, AlertTriangle, AlertCircle, RefreshCw } from 'lucide-react';
import { visaData, MaterialItem } from '../data/visaData';

export const VisaChecklist: React.FC = () => {
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [selectedVisa, setSelectedVisa] = useState<string>('');
  const [selectedIdentity, setSelectedIdentity] = useState<string>('student');
  const [showChecklist, setShowChecklist] = useState<boolean>(false);
  
  // State for checklist items (stored in localStorage)
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});
  
  // Load saved state on mount
  useEffect(() => {
    const saved = localStorage.getItem('visa_checklist_saved');
    if (saved) {
      try {
        setCheckedItems(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse saved checklist state", e);
      }
    }
  }, []);

  // Save state when changed
  useEffect(() => {
    localStorage.setItem('visa_checklist_saved', JSON.stringify(checkedItems));
  }, [checkedItems]);

  const handleToggleItem = (id: string) => {
    setCheckedItems(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleGenerate = () => {
    if (selectedCountry && selectedVisa && selectedIdentity) {
      setShowChecklist(true);
    }
  };

  const currentCountry = visaData.find(c => c.id === selectedCountry);
  const currentVisa = currentCountry?.visa_types.find(v => v.id === selectedVisa);

  // Calculate progress
  let totalItems = 0;
  let completedItems = 0;

  if (currentVisa && showChecklist) {
    const filterByAuth = (items: MaterialItem[]) => items.filter(item => !item.for_identity || item.for_identity.includes(selectedIdentity));
    const allMaterials = [
      ...filterByAuth(currentVisa.materials.core),
      ...filterByAuth(currentVisa.materials.financial),
      ...filterByAuth(currentVisa.materials.academic),
      ...filterByAuth(currentVisa.materials.supporting)
    ];
    totalItems = allMaterials.length;
    completedItems = allMaterials.filter(m => checkedItems[m.id]).length;
  }

  const progressPercentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;

  const renderMaterialSection = (title: string, materials: MaterialItem[], icon: React.ReactNode) => {
    const filteredMaterials = materials?.filter(item => !item.for_identity || item.for_identity.includes(selectedIdentity)) || [];
    if (filteredMaterials.length === 0) return null;
    
    return (
      <div className="mb-8 bg-white rounded-xl border border-neutral-100 shadow-sm overflow-hidden">
        <div className="bg-neutral-50 px-6 py-4 border-b border-neutral-100 flex items-center gap-3">
          <div className="text-brand-blue">{icon}</div>
          <h3 className="text-lg font-bold text-neutral-800">{title}</h3>
        </div>
        <div className="divide-y divide-neutral-50">
          {filteredMaterials.map(item => (
            <div 
              key={item.id} 
              className={`p-6 transition-colors hover:bg-neutral-50 flex gap-4 cursor-pointer ${checkedItems[item.id] ? 'bg-brand-blue-light/30' : ''}`}
              onClick={() => handleToggleItem(item.id)}
            >
              <div className="flex-shrink-0 mt-1">
                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                  checkedItems[item.id] 
                    ? 'border-brand-blue-light0 bg-brand-blue-light0 text-white' 
                    : 'border-neutral-300 text-transparent'
                }`}>
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
                  <h4 className={`font-medium text-lg ${checkedItems[item.id] ? 'text-neutral-500 line-through' : 'text-neutral-800'}`}>
                    {item.name}
                  </h4>
                  <div className="flex gap-2">
                    {item.required && (
                      <span className="px-2 py-0.5 bg-red-50 text-red-600 text-xs font-medium rounded border border-red-100">必须</span>
                    )}
                    {item.needs_translation && (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-600 text-xs font-medium rounded border border-amber-100">需翻译/公证</span>
                    )}
                  </div>
                </div>
                <p className="text-neutral-600 text-sm mb-2">{item.notes}</p>
                <div className="flex items-center text-xs text-neutral-400 gap-1">
                  <RefreshCw className="w-3 h-3" />
                  <span>准备周期: {item.prep_time}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-black text-neutral-900 mb-4 tracking-tight">
          签证材料清单生成器
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          签证材料不踩坑，30 秒生成你的专属 Checklist。基于各国使馆最新要求，一次性准备齐全。
        </p>
      </div>

      <div className="max-w-4xl mx-auto">
        {/* Selector Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-neutral-200 p-6 md:p-8 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">1. 目标国家</label>
              <select 
                className="w-full bg-neutral-50 border border-neutral-200 text-neutral-800 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-blue-light0 focus:border-transparent transition-all"
                value={selectedCountry}
                onChange={(e) => {
                  setSelectedCountry(e.target.value);
                  setSelectedVisa('');
                  setShowChecklist(false);
                }}
              >
                <option value="">请选择国家</option>
                {visaData.map(c => (
                  <option key={c.id} value={c.id}>{c.country_name}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">2. 签证类型</label>
              <select 
                className="w-full bg-neutral-50 border border-neutral-200 text-neutral-800 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-blue-light0 focus:border-transparent transition-all disabled:opacity-50 disabled:bg-neutral-100"
                value={selectedVisa}
                onChange={(e) => {
                  setSelectedVisa(e.target.value);
                  setShowChecklist(false);
                }}
                disabled={!selectedCountry}
              >
                <option value="">请选择签证类型</option>
                {currentCountry?.visa_types.map(v => (
                  <option key={v.id} value={v.id}>{v.type_name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">3. 申请人身份</label>
              <select 
                className="w-full bg-neutral-50 border border-neutral-200 text-neutral-800 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-blue-light0 focus:border-transparent transition-all"
                value={selectedIdentity}
                onChange={(e) => {
                  setSelectedIdentity(e.target.value);
                  setShowChecklist(false);
                }}
              >
                <option value="student">留学生 (本科/硕博)</option>
                <option value="minor">未成年留学生 (中学)</option>
                <option value="scholar">访问学者/博士后</option>
              </select>
            </div>
          </div>

          <div className="mt-8 text-center">
            <button 
              onClick={handleGenerate}
              disabled={!selectedCountry || !selectedVisa}
              className="bg-brand-blue hover:bg-blue-800 disabled:bg-neutral-300 disabled:cursor-not-allowed text-white font-bold py-3.5 px-8 rounded-xl shadow-lg shadow-brand-blue/30 transition-all transform hover:-tranneutral-y-0.5 active:tranneutral-y-0 w-full md:w-auto min-w-[200px]"
            >
              生成专属材料清单
            </button>
          </div>
        </div>

        {/* Generated Checklist */}
        {showChecklist && currentVisa && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Summary Card */}
            <div className="bg-gradient-to-r from-neutral-800 to-neutral-900 rounded-2xl shadow-lg p-6 md:p-8 mb-8 text-white flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <h2 className="text-2xl font-bold mb-2 flex items-center gap-2">
                  {currentCountry?.country_name} {currentVisa.type_name} 材料清单
                </h2>
                <p className="text-neutral-300 text-sm">{currentVisa.description}</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <div className="bg-white/10 rounded-lg px-3 py-1.5 text-sm backdrop-blur-sm border border-white/5">
                    <span className="text-neutral-400 mr-1">签证费:</span>
                    <span className="font-medium">{currentVisa.fees.visa_fee.amount} {currentVisa.fees.visa_fee.currency} (约 ¥{currentVisa.fees.visa_fee.cny})</span>
                  </div>
                  <div className="bg-white/10 rounded-lg px-3 py-1.5 text-sm backdrop-blur-sm border border-white/5">
                    <span className="text-neutral-400 mr-1">审理周期:</span>
                    <span className="font-medium">{currentVisa.processing_time}</span>
                  </div>
                </div>
              </div>
              
              <div className="w-full md:w-64 bg-white/5 rounded-xl p-4 border border-white/10">
                <div className="flex justify-between items-end mb-2">
                  <span className="text-sm font-medium text-neutral-300">准备进度</span>
                  <span className="text-2xl font-bold text-blue-400">{progressPercentage}%</span>
                </div>
                <div className="w-full bg-neutral-700 rounded-full h-2.5 mb-2 overflow-hidden">
                  <div 
                    className="bg-brand-blue-light0 h-2.5 rounded-full transition-all duration-500 ease-out" 
                    style={{ width: `${progressPercentage}%` }}
                  ></div>
                </div>
                <div className="text-xs text-neutral-400 text-right">已准备 {completedItems}/{totalItems} 项</div>
              </div>
            </div>

            {/* Tips Section */}
            {currentVisa.materials.tips && currentVisa.materials.tips.length > 0 && (
              <div className="mb-8 bg-amber-50 border border-amber-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3 text-amber-800">
                  <AlertTriangle className="w-5 h-5" />
                  <h3 className="font-bold text-lg">避坑指南 & 注意事项</h3>
                </div>
                <ul className="space-y-2">
                  {currentVisa.materials.tips.map((tip, index) => (
                    <li key={index} className="flex items-start gap-2 text-amber-900 text-sm">
                      <span className="text-amber-500 font-bold mt-0.5">•</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Material Modules */}
            {renderMaterialSection("A. 必备核心材料", currentVisa.materials.core, <FileText className="w-5 h-5" />)}
            {renderMaterialSection("B. 财力证明材料", currentVisa.materials.financial, <AlertCircle className="w-5 h-5" />)}
            {renderMaterialSection("C. 学术/录取材料", currentVisa.materials.academic, <FileText className="w-5 h-5" />)}
            {renderMaterialSection("D. 辅助支持材料", currentVisa.materials.supporting, <FileText className="w-5 h-5" />)}

            {/* CTA Section */}
            <div className="mt-12 mb-8 bg-white rounded-2xl shadow-xl border border-brand-blue/20 overflow-hidden">
              <div className="bg-brand-blue-light px-6 py-4 border-b border-brand-blue/20">
                <h3 className="font-bold text-blue-800 flex items-center gap-2">
                  <span className="text-xl">🚀</span> 下一步行动
                </h3>
              </div>
              <div className="p-6 md:p-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-neutral-50 rounded-xl p-5 border border-neutral-100 flex flex-col items-center text-center transition-transform hover:-tranneutral-y-1">
                  <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mb-4">
                    <FileText className="w-6 h-6" />
                  </div>
                  <h4 className="font-bold text-neutral-800 mb-2">材料翻译/公证</h4>
                  <p className="text-sm text-neutral-600 mb-4 flex-grow">专业资质翻译机构，加盖专章，符合各国使馆要求，顺丰包邮。</p>
                  <button className="w-full py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors">
                    立即下单
                  </button>
                </div>
                
                <div className="bg-neutral-50 rounded-xl p-5 border border-neutral-100 flex flex-col items-center text-center transition-transform hover:-tranneutral-y-1">
                  <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center mb-4">
                    <MessageCircle className="w-6 h-6" />
                  </div>
                  <h4 className="font-bold text-neutral-800 mb-2">1v1 签证答疑</h4>
                  <p className="text-sm text-neutral-600 mb-4 flex-grow">前使馆签证官/资深顾问在线答疑，拒签史、敏感专业专项辅导。</p>
                  <button className="w-full py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors">
                    添加微信咨询
                  </button>
                </div>
                
                <div className="bg-neutral-50 rounded-xl p-5 border border-neutral-100 flex flex-col items-center text-center transition-transform hover:-tranneutral-y-1">
                  <div className="w-12 h-12 bg-brand-blue/20 text-brand-blue rounded-full flex items-center justify-center mb-4">
                    <Download className="w-6 h-6" />
                  </div>
                  <h4 className="font-bold text-neutral-800 mb-2">保存/分享清单</h4>
                  <p className="text-sm text-neutral-600 mb-4 flex-grow">生成 PDF 格式清单，方便打印随身携带，或分享给父母一起准备。</p>
                  <button 
                    className="w-full py-2.5 bg-white border-2 border-brand-blue text-brand-blue rounded-lg font-medium hover:bg-brand-blue-light transition-colors"
                    onClick={() => alert("PDF 下载功能开发中...")}
                  >
                    下载 PDF
                  </button>
                </div>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="text-center text-xs text-neutral-400 mt-8 mb-12 px-4">
              <p>本清单基于各国使馆官方公开信息整理，仅供参考。签证政策可能随时调整，请以使馆/签证中心最新要求为准。</p>
              <p className="mt-1">最后更新：2024年4月 | © 河狸陪高端留学</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
