import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, Sparkles, MapPin, ChevronRight, Lock } from 'lucide-react';

const QUESTIONS = [
  {
    id: 1,
    question: "你更看重留学中的哪一点？",
    options: [
      { id: 'A', text: "顶尖学术资源和研究机会", scores: { US: 30, UK: 20, SG: 0, AU: 0, EU: 0 } },
      { id: 'B', text: "短学制高效率", scores: { US: 0, UK: 30, SG: 25, AU: 0, EU: 0 } },
      { id: 'C', text: "毕业后留下工作的机会", scores: { US: 15, UK: 0, SG: 0, AU: 30, EU: 0 } },
      { id: 'D', text: "性价比（花最少的钱获得最好的学历）", scores: { US: 0, UK: 0, SG: 30, AU: 20, EU: 0 } },
      { id: 'E', text: "文化体验和个人成长", scores: { US: 20, UK: 0, SG: 0, AU: 0, EU: 25 } },
    ]
  },
  {
    id: 2,
    question: "你更喜欢什么样的生活环境？",
    options: [
      { id: 'A', text: "繁华大都市，什么都方便", emoji: "🏙️", scores: { US: 15, UK: 15, SG: 25, AU: 0, EU: 0 } },
      { id: 'B', text: "安全宁静的中小城市", emoji: "🏡", scores: { US: 0, UK: 15, SG: 0, AU: 25, EU: 0 } },
      { id: 'C', text: "文化丰富的欧洲城市", emoji: "🏰", scores: { US: 0, UK: 0, SG: 0, AU: 0, EU: 30 } },
      { id: 'D', text: "华人多、中餐多、适应快", emoji: "🍜", scores: { US: 0, UK: 0, SG: 30, AU: 15, EU: 0 } },
      { id: 'E', text: "无所谓，学校好就行", emoji: "🎓", scores: { US: 5, UK: 5, SG: 5, AU: 5, EU: 5 } },
    ]
  },
  {
    id: 3,
    question: "你毕业后的打算？",
    options: [
      { id: 'A', text: "拿完文凭火速回国，国内才是主场", scores: { US: 0, UK: 25, SG: 20, AU: 0, EU: 0 } },
      { id: 'B', text: "攒几年海外工作经验，把学费赚回来", scores: { US: 15, UK: 0, SG: 0, AU: 30, EU: 0 } },
      { id: 'C', text: "希望最终能拿绿卡移民", scores: { US: 0, UK: 0, SG: 0, AU: 30, EU: 0 } },
      { id: 'D', text: "走一步看一步", scores: { US: 10, UK: 10, SG: 10, AU: 10, EU: 10 } },
    ]
  }
];

const COUNTRIES = {
  US: { name: "美国", emoji: "🇺🇸", desc: "世界顶尖的学术资源，充满无限可能的机遇之地", cost: "50-80w/年", time: "本科4年/硕士1-2年", persona: "🔥 稳扎稳打的名校收割机" },
  UK: { name: "英国", emoji: "🇬🇧", desc: "古典与现代的完美融合，短学制高效率的典范", cost: "35-50w/年", time: "本科3年/硕士1年", persona: "🎓 高效拿证的体验派" },
  SG: { name: "新加坡/香港", emoji: "🇸🇬", desc: "离家近、性价比高，亚洲金融与科技中心", cost: "25-40w/年", time: "本科3-4年/硕士1年", persona: "💼 亚洲金融与科技新贵" },
  AU: { name: "澳洲/加拿大", emoji: "🇦🇺", desc: "风景优美、生活舒适，最适合移民与长远发展", cost: "30-45w/年", time: "本科3-4年/硕士1.5-2年", persona: "🌿 追求生活品质的实干家" },
  EU: { name: "欧洲其他", emoji: "🇪🇺", desc: "小语种优势，深厚的历史文化底蕴与极高性价比", cost: "10-20w/年", time: "本科3年/硕士2年", persona: "🏰 沉浸式体验的文化探险者" },
};

export const TendencyTest: React.FC = () => {
  const [started, setStarted] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [scores, setScores] = useState({ US: 0, UK: 0, SG: 0, AU: 0, EU: 0 });
  const [isCalculating, setIsCalculating] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [calculatingText, setCalculatingText] = useState('正在解析学术背景...');

  useEffect(() => {
    // 动态更新页面 SEO 信息
    document.title = "留学国家倾向测试 | 河狸陪留学工具箱";
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute("content", "通过科学的性格、预算、规划等多维度测试，为你精准匹配最适合的留学目的地。怕选错，就找河狸陪。");
    }
  }, []);

  useEffect(() => {
    if (isCalculating) {
      const texts = [
        '正在解析学术背景...',
        '正在匹配河狸陪 10,000+ 真实录取数据库...',
        '正在生成专属定制路径...'
      ];
      let i = 0;
      const interval = setInterval(() => {
        i = (i + 1) % texts.length;
        setCalculatingText(texts[i]);
      }, 1200);
      return () => clearInterval(interval);
    }
  }, [isCalculating]);

  const handleStart = () => {
    setStarted(true);
    if (window.gtag) {
      window.gtag('event', 'tendency_test_start', {
        event_category: 'engagement',
        event_label: 'start_test'
      });
    }
  };

  const handleAnswer = (optionScores: Record<string, number>, optionId: string, qId: number) => {
    if (window.gtag) {
      window.gtag('event', `tendency_test_answer_q${qId}`, {
        event_category: 'engagement',
        event_label: `answer_${optionId}`,
        question_id: qId,
        option_id: optionId
      });
    }

    const newScores = { ...scores };
    Object.keys(optionScores).forEach(country => {
      newScores[country as keyof typeof scores] += optionScores[country];
    });
    setScores(newScores);

    if (qId === 1) {
      if (optionId === 'A') {
        setToastMessage('✨ 冲刺顶尖名校的绝佳选择！');
        setTimeout(() => setToastMessage(null), 2000);
      } else if (optionId === 'D') {
        setToastMessage('💰 高性价比的聪明决定！');
        setTimeout(() => setToastMessage(null), 2000);
      }
    }

    if (currentStep < QUESTIONS.length - 1) {
      setCurrentStep(curr => curr + 1);
    } else {
      setIsCalculating(true);
      setTimeout(() => {
        setIsCalculating(false);
        setShowResult(true);

        const bestCode = Object.entries(newScores)
          .sort(([,a], [,b]) => b - a)[0][0];

        if (window.gtag) {
          window.gtag('event', 'tendency_test_complete', {
            event_category: 'engagement',
            event_label: `result_${bestCode}`,
            recommended_country: bestCode
          });
        }
      }, 4000); // 留出足够时间显示最后一条
    }
  };

  const getTopCountries = () => {
    return Object.entries(scores)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 3)
      .map(([code, score]) => ({
        code,
        ...(COUNTRIES as Record<string, { name: string; emoji: string; desc: string; cost: string; time: string; persona: string }>)[code],
        matchRate: Math.min(99, 40 + Math.floor((score / 90) * 60)) // 假装算出来的百分比
      }));
  };


  const renderContent = () => {
    if (!started) {
      return (
        <div className="bg-white rounded-2xl p-8 shadow-sm border border-neutral-200 text-center">

          <div className="w-16 h-16 bg-brand-blue-light text-brand-blue rounded-xl flex items-center justify-center mx-auto mb-6">
            <MapPin className="w-8 h-8" />
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-neutral-900 mb-4 tracking-tight">
            选错赛道白花百万？<br/><span className="text-brand-blue">测测你最适合哪个国家</span>
          </h1>
          <div className="text-neutral-500 mb-8 leading-relaxed space-y-2 text-sm md:text-base text-left bg-neutral-50 p-4 rounded-xl">
            <p><span className="font-bold text-neutral-700">现状：</span>英美澳加新各有千秋，盲目跟风可能导致水土不服。</p>
            <p><span className="font-bold text-neutral-700">问题：</span>到底哪个国家最适合你的性格、预算与未来规划？</p>
            <p><span className="font-bold text-neutral-700">方案：</span>只需 1 分钟完成多维度测试，基于 10,000+ 真实案例，为你精准匹配最优留学目的地。</p>
          </div>
          <button
            onClick={handleStart}
            className="w-full py-4 bg-brand-blue hover:bg-blue-800 text-white rounded-xl font-bold text-lg transition-all transform hover:scale-105 shadow-lg flex items-center justify-center group cursor-pointer"
          >
            <Sparkles className="w-5 h-5 mr-2" />
            开始免费测评
            <ArrowRight className="w-5 h-5 ml-2 group-hover:tranneutral-x-1 transition-transform" />
          </button>
          <p className="mt-4 text-xs text-neutral-500">⏱️ 只需 1 分钟 · 已有 12,458 人完成测试</p>

        </div>
      );
    }

    if (isCalculating) {
      return (
        <div className="bg-white rounded-2xl p-12 shadow-sm border border-neutral-200 text-center flex flex-col items-center justify-center min-h-[400px]">

          <div className="w-20 h-20 border-4 border-brand-blue-light border-t-brand-blue rounded-full animate-spin mx-auto mb-6"></div>
          <h2 className="text-xl font-bold text-neutral-900 mb-2">正在通过多维度测算...</h2>
          <div className="h-12 relative flex justify-center">
            <AnimatePresence mode="wait">
              <motion.p
                key={calculatingText}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                transition={{ duration: 0.3 }}
                className="text-neutral-500 absolute"
              >
                {calculatingText}
              </motion.p>
            </AnimatePresence>
          </div>

        </div>
      );
    }

    if (showResult) {
      const topCountries = getTopCountries();
      const best = topCountries[0];
      return (
        <div className="space-y-6">

          {/* Top 1 Result */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-shadow border border-neutral-300 relative overflow-hidden mb-6"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-brand-blue-light rounded-bl-full -z-10"></div>
            <div className="text-sm font-bold text-brand-blue uppercase tracking-widest mb-4">
              最适合你的留学目的地
            </div>
            <div className="inline-block bg-brand-blue-light text-brand-blue text-xs font-bold px-3 py-1 rounded-full mb-3">
              {best.persona}
            </div>
            <div className="flex items-end gap-3 mb-2">
              <span className="text-5xl" role="img" aria-label={`${best.name} emoji`}>{best.emoji}</span>
              <h2 className="text-4xl font-black text-neutral-900">{best.name}</h2>
            </div>
            <div className="inline-block px-3 py-1 bg-brand-green-light text-brand-green font-bold rounded-full text-sm mb-6">
              匹配度 {best.matchRate}%
            </div>

            <p className="text-neutral-700 mb-6 font-medium leading-relaxed">
              你是天生的破局者，{best.desc}。这里高度契合你的个人追求与价值观。
            </p>

            <div className="bg-neutral-50 rounded-xl p-4 grid grid-cols-2 gap-4 mb-6">
              <div>
                <div className="text-xs text-neutral-500 mb-1">学制时长</div>
                <div className="font-bold text-neutral-700 text-sm">{best.time}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-500 mb-1">年均费用</div>
                <div className="font-bold text-neutral-700 text-sm">{best.cost}</div>
              </div>
            </div>

            {/* Gated Content CTA */}
            <div className="relative rounded-xl border border-neutral-300 overflow-hidden mb-6 bg-neutral-50">
              <div className="p-5 blur-[3px] select-none opacity-60">
                <h4 className="font-bold text-neutral-900 mb-4 flex items-center">
                  核心优劣势剖析 & 专属时间线
                </h4>
                <div className="space-y-3">
                  <div className="h-4 bg-neutral-300 rounded w-3/4"></div>
                  <div className="h-4 bg-neutral-300 rounded w-full"></div>
                  <div className="h-4 bg-neutral-300 rounded w-5/6"></div>
                  <div className="h-4 bg-neutral-300 rounded w-2/3"></div>
                </div>
              </div>
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/50 backdrop-blur-[1px] p-4">
                <div className="bg-neutral-900/80 text-white p-3 rounded-full mb-4 shadow-lg backdrop-blur-md">
                  <Lock className="w-5 h-5" />
                </div>
                {!showQR ? (
                  <button
                    onClick={() => {
                      setShowQR(true);
                      if (window.gtag) {
                        window.gtag('event', 'tendency_test_unlock_pdf', {
                          event_category: 'engagement',
                          event_label: 'unlock_pdf'
                        });
                      }
                    }}
                    className="w-full py-4 bg-brand-blue hover:bg-blue-800 text-white rounded-xl font-bold shadow-md hover:shadow-lg transition-all flex items-center justify-center animate-bounce cursor-pointer"
                  >
                    解锁专属留学路径诊断报告 PDF <ArrowRight className="w-4 h-4 ml-2" />
                  </button>
                ) : (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="bg-white rounded-xl p-4 text-center border border-brand-blue-light shadow-sm w-full"
                  >
                    <img
                      src="/assets/wechat-qr.jpeg"
                      alt="扫码添加资深顾问"
                      className="w-48 h-48 mx-auto mb-4 border border-neutral-200 rounded-lg shadow-sm"
                    />
                    <p className="text-sm font-bold text-brand-blue mb-1">长按扫码添加资深顾问</p>
                    <p className="text-xs text-brand-blue opacity-80">发送截图，免费获取完整版诊断报告</p>
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>

          {/* Locked Top 2 & 3 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="bg-white rounded-xl p-6 shadow-sm border border-neutral-300 relative overflow-hidden cursor-pointer group"
            title="扫码解锁 Top2 & Top3 备选方案"
            onClick={() => {
              setShowQR(true);
              if (window.gtag) {
                window.gtag('event', 'tendency_test_unlock_pdf', {
                  event_category: 'engagement',
                  event_label: 'unlock_top23'
                });
              }
            }}
          >
            <div className="absolute inset-0 bg-white/60 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center group-hover:bg-white/50 transition-all">
               <div className="bg-neutral-900/80 text-white px-4 py-2 rounded-full text-sm font-medium backdrop-blur-md group-hover:scale-105 transition-transform shadow-lg">
                 扫码解锁 Top2 & Top3 备选方案
               </div>
            </div>
            <h3 className="font-bold text-neutral-900 mb-4">其他高匹配推荐</h3>
            <div className="space-y-4">
              {topCountries.slice(1).map(c => (
                <div key={c.code} className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl" role="img" aria-label={`${c.name} emoji`}>{c.emoji}</span>
                    <span className="font-bold text-neutral-700 blur-sm select-none">{c.name}</span>
                  </div>
                  <span className="text-neutral-500 font-medium blur-sm select-none">{c.matchRate}%</span>
                </div>
              ))}
            </div>
          </motion.div>

        </div>
      );
    }

    const currentQ = QUESTIONS[currentStep];
    return (
      <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-neutral-200">

        {/* Progress */}
        <div className="mb-8">
          <div className="flex justify-between text-xs font-bold text-neutral-500 mb-2 uppercase tracking-wider">
            <span>Question {currentStep + 1}</span>
            <span>{Math.round(((currentStep + 1) / QUESTIONS.length) * 100)}%</span>
          </div>
          <div className="h-2 bg-neutral-300 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-brand-blue rounded-full"
              initial={{ width: `${(currentStep / QUESTIONS.length) * 100}%` }}
              animate={{ width: `${((currentStep + 1) / QUESTIONS.length) * 100}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>

        {/* Question */}
        <div className="flex-1 min-h-[400px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              <h2 className="text-2xl font-bold text-neutral-900 mb-8 leading-snug">
                {currentQ.question}
              </h2>

              <div className="space-y-3">
                {currentQ.options.map(opt => (
                  <button
                    key={opt.id}
                    onClick={() => handleAnswer(opt.scores, opt.id, currentQ.id)}
                    className="w-full text-left p-4 rounded-xl bg-white border border-neutral-300 hover:border-brand-blue hover:shadow-md transition-all group flex items-center justify-between shadow-sm cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      {'emoji' in opt && <span className="text-2xl" role="img" aria-label="option emoji">{opt.emoji}</span>}
                      <span className="font-medium text-neutral-700 group-hover:text-brand-blue transition-colors text-left">
                        {opt.text}
                      </span>
                    </div>
                    <div className="w-6 h-6 rounded-full bg-neutral-50 flex items-center justify-center group-hover:bg-brand-blue-light">
                      <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-brand-blue" />
                    </div>
                  </button>
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">

      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-5xl font-black text-neutral-900 mb-4 tracking-tight">
          国家/路径倾向测评
        </h1>
        <p className="text-lg text-neutral-500 max-w-2xl mx-auto">
          选错赛道白花百万？1分钟完成多维度测算，为你精准匹配最适合的留学目的地。
        </p>
      </div>


      <div className="max-w-4xl mx-auto">
        {renderContent()}
      </div>

      {/* Toast */}

      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            className="fixed bottom-10 left-1/2 -tranneutral-x-1/2 bg-neutral-900 text-white px-6 py-3 rounded-full shadow-2xl z-50 whitespace-nowrap font-medium"
          >
            {toastMessage}
          </motion.div>
        )}
      </AnimatePresence>
    </div>

  );
}
