const fs = require('fs');
const path = require('path');

const routeMeta = {
  'gpa': { title: 'GPA 换算器 | 河狸陪', desc: '河狸陪提供权威专业的留学生GPA换算器，支持多种算法和分数制。' },
  'cost': { title: '留学费用评估 | 河狸陪', desc: '免费计算各个国家的留学费用，涵盖学费、生活费等各项开支。' },
  'timeline': { title: '留学时间线规划 | 河狸陪', desc: '根据你的申请阶段，自动生成详细的留学申请时间线和重要节点提醒。' },
  'visa-checklist': { title: '签证材料清单 | 河狸陪', desc: '为你定制专属的留学签证材料准备清单，涵盖各国F1/T4等学生签证。' },
  'school-matcher': { title: '院校匹配器 | 河狸陪', desc: '根据你的GPA、专业和软背景，智能匹配冲刺、匹配和保底的海外名校。' },
  'mock-exam': { title: '模拟考试 | 河狸陪', desc: '留学相关的模拟考试测评，帮你评估自身水平。' },
  'mock-exam/play': { title: '模拟考试中 | 河狸陪', desc: '留学相关的模拟考试测评，帮你评估自身水平。' },
  'mock-exam/result': { title: '模拟考试结果 | 河狸陪', desc: '留学相关的模拟考试测评，帮你评估自身水平。' },
  'university-tiering': { title: '院校分级指南 | 河狸陪', desc: '了解海外高校的梯队和分级情况，助你更精准地定位目标。' },
  'tendency': { title: '留学倾向测试 | 河狸陪', desc: '通过测试了解自己最适合的留学国家和专业方向。' },
  'extracurricular-activity-planner': { title: '课外活动规划 | 河狸陪', desc: '为您量身定制的课外活动规划，全面提升留学申请竞争力。' },
  'case-matcher': { title: '录取案例去水罗盘 | 河狸陪', desc: '匹配相似背景的学长真实录取去向。' }
};

const routes = Object.keys(routeMeta);
const dist = path.join(__dirname, '../tools');
const indexHtml = fs.readFileSync(path.join(dist, 'index.html'), 'utf-8');

routes.forEach(route => {
  const dir = path.join(dist, route);
  fs.mkdirSync(dir, { recursive: true });

  const meta = routeMeta[route];
  let customizedHtml = indexHtml
    .replace(/<title>.*?<\/title>/g, `<title>${meta.title}</title>`)
    .replace(/<meta name="description" content=".*?"/g, `<meta name="description" content="${meta.desc}"`)
    .replace(/<meta property="og:title" content=".*?"/g, `<meta property="og:title" content="${meta.title}"`)
    .replace(/<meta property="og:description" content=".*?"/g, `<meta property="og:description" content="${meta.desc}"`);

  fs.writeFileSync(path.join(dir, 'index.html'), customizedHtml);
});
console.log('Static routes with SEO meta generated successfully.');
