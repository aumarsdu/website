export interface School {
  id: string;
  name: string;
  en_name: string;
  country: 'US' | 'UK' | 'HK';
  ranking: number;
  logo?: string;
  req_gpa: number; 
  req_toefl?: number;
  req_ielts?: number;
  tags: string[];
}

export const mockSchools: School[] = [
  { id: 'us-1', name: '普林斯顿大学', en_name: 'Princeton University', country: 'US', ranking: 1, req_gpa: 3.9, req_toefl: 110, tags: ['常春藤', '学术顶尖'] },
  { id: 'us-2', name: '麻省理工学院', en_name: 'MIT', country: 'US', ranking: 2, req_gpa: 3.9, req_toefl: 110, tags: ['理工科强校', '科研'] },
  { id: 'us-3', name: '哈佛大学', en_name: 'Harvard University', country: 'US', ranking: 3, req_gpa: 3.9, req_toefl: 110, tags: ['常春藤', '综合顶尖'] },
  { id: 'us-4', name: '斯坦福大学', en_name: 'Stanford University', country: 'US', ranking: 3, req_gpa: 3.9, req_toefl: 110, tags: ['硅谷核心', '创业氛围'] },
  { id: 'us-10', name: '西北大学', en_name: 'Northwestern University', country: 'US', ranking: 10, req_gpa: 3.8, req_toefl: 105, tags: ['新闻传媒', '商科'] },
  { id: 'us-15', name: '康奈尔大学', en_name: 'Cornell University', country: 'US', ranking: 15, req_gpa: 3.8, req_toefl: 105, tags: ['常春藤', '工科'] },
  { id: 'us-20', name: '加州大学伯克利分校', en_name: 'UC Berkeley', country: 'US', ranking: 20, req_gpa: 3.8, req_toefl: 100, tags: ['公立常春藤', '理工科'] },
  { id: 'us-28', name: '南加州大学', en_name: 'USC', country: 'US', ranking: 28, req_gpa: 3.7, req_toefl: 100, tags: ['传媒强', '洛杉矶'] },
  { id: 'us-35', name: '纽约大学', en_name: 'NYU', country: 'US', ranking: 35, req_gpa: 3.6, req_toefl: 100, tags: ['曼哈顿', '商科艺术'] },
  { id: 'us-40', name: '波士顿大学', en_name: 'Boston University', country: 'US', ranking: 40, req_gpa: 3.5, req_toefl: 90, tags: ['波士顿', '综合'] },
  { id: 'us-50', name: '俄亥俄州立大学', en_name: 'Ohio State University', country: 'US', ranking: 50, req_gpa: 3.3, req_toefl: 80, tags: ['公立大校', '体育强'] },

  { id: 'uk-1', name: '牛津大学', en_name: 'University of Oxford', country: 'UK', ranking: 1, req_gpa: 3.8, req_ielts: 7.5, tags: ['G5', '书院制'] },
  { id: 'uk-2', name: '剑桥大学', en_name: 'University of Cambridge', country: 'UK', ranking: 2, req_gpa: 3.8, req_ielts: 7.5, tags: ['G5', '书院制'] },
  { id: 'uk-3', name: '帝国理工学院', en_name: 'Imperial College London', country: 'UK', ranking: 3, req_gpa: 3.7, req_ielts: 7.0, tags: ['G5', '理工科强校'] },
  { id: 'uk-4', name: '伦敦大学学院', en_name: 'UCL', country: 'UK', ranking: 4, req_gpa: 3.6, req_ielts: 7.0, tags: ['G5', '综合强校'] },
  { id: 'uk-5', name: '伦敦政治经济学院', en_name: 'LSE', country: 'UK', ranking: 5, req_gpa: 3.7, req_ielts: 7.0, tags: ['G5', '社科商科强校'] },
  { id: 'uk-8', name: '爱丁堡大学', en_name: 'University of Edinburgh', country: 'UK', ranking: 8, req_gpa: 3.5, req_ielts: 6.5, tags: ['罗素集团', '苏格兰'] },
  { id: 'uk-10', name: '曼彻斯特大学', en_name: 'University of Manchester', country: 'UK', ranking: 10, req_gpa: 3.4, req_ielts: 6.5, tags: ['红砖大学', '商科强'] },
  { id: 'uk-15', name: '布里斯托大学', en_name: 'University of Bristol', country: 'UK', ranking: 15, req_gpa: 3.3, req_ielts: 6.5, tags: ['红砖大学', '工科强'] },
  { id: 'uk-20', name: '格拉斯哥大学', en_name: 'University of Glasgow', country: 'UK', ranking: 20, req_gpa: 3.2, req_ielts: 6.5, tags: ['罗素集团', '历史悠久'] },

  { id: 'hk-1', name: '香港大学', en_name: 'HKU', country: 'HK', ranking: 1, req_gpa: 3.6, req_ielts: 6.5, tags: ['港三所', '综合顶尖'] },
  { id: 'hk-2', name: '香港中文大学', en_name: 'CUHK', country: 'HK', ranking: 2, req_gpa: 3.5, req_ielts: 6.5, tags: ['港三所', '文社科强'] },
  { id: 'hk-3', name: '香港科技大学', en_name: 'HKUST', country: 'HK', ranking: 3, req_gpa: 3.5, req_ielts: 6.5, tags: ['港三所', '商科理工强'] },
  { id: 'hk-4', name: '香港城市大学', en_name: 'CityU', country: 'HK', ranking: 4, req_gpa: 3.3, req_ielts: 6.5, tags: ['港五所', '发展迅速'] },
  { id: 'hk-5', name: '香港理工大学', en_name: 'PolyU', country: 'HK', ranking: 5, req_gpa: 3.3, req_ielts: 6.5, tags: ['港五所', '实用型'] },
  { id: 'hk-6', name: '香港浸会大学', en_name: 'HKBU', country: 'HK', ranking: 6, req_gpa: 3.0, req_ielts: 6.0, tags: ['传媒强', '博雅教育'] }
];

export type MatchLevel = 'reach' | 'match' | 'safety';

export interface MatchedSchool extends School {
  matchLevel: MatchLevel;
  matchScore: number;
}

export const matchSchools = (
  userGpa: number, 
  targetCountries: string[],
  schoolBg: string,
  highlights: string[]
): { reach: MatchedSchool[], match: MatchedSchool[], safety: MatchedSchool[] } => {
  const results: MatchedSchool[] = [];

  // 1. Apply GPA compensation based on undergraduate/high school background
  let adjustedGpa = userGpa;
  switch (schoolBg) {
    // Bachelor (High School)
    case 'overseas_hs':
    case 'top_international':
      adjustedGpa += 0.1;
      break;
    case 'top_public':
      adjustedGpa += 0.05;
      break;
    case 'normal_international':
    case 'key_public':
      // Baseline
      break;
    case 'normal_public':
      adjustedGpa -= 0.1;
      break;

    // Master (Undergrad)
    case 'c9':
    case 'overseas':
      adjustedGpa += 0.15;
      break;
    case '985':
      adjustedGpa += 0.1;
      break;
    case '211':
    case 'coop':
      adjustedGpa += 0.05;
      break;
    case 'double_first':
    case 'normal':
      // Baseline, no adjustment
      break;
    case 'other':
      adjustedGpa -= 0.1;
      break;

    // PhD (Highest Degree)
    case 'top_overseas':
    case 'c9_985':
    case 'research_inst':
      adjustedGpa += 0.15;
      break;
    case 'normal_overseas':
    case '211_double_first':
      adjustedGpa += 0.05;
      break;
    case 'normal_cn':
      adjustedGpa -= 0.15;
      break;
      
    default:
      break;
  }

  // 2. Expand reach tolerance based on highlights (max 3 highlights counted = +0.15 tolerance)
  const highlightBonus = Math.min(highlights.length * 0.05, 0.15);
  const reachLowerBound = -0.4 - highlightBonus;

  mockSchools.forEach(school => {
    if (targetCountries.length > 0 && !targetCountries.includes(school.country)) return;

    let level: MatchLevel | null = null;
    const diff = adjustedGpa - school.req_gpa;

    if (diff >= 0.2) {
      level = 'safety';
    } else if (diff >= -0.15 && diff < 0.2) {
      level = 'match';
    } else if (diff >= reachLowerBound && diff < -0.15) {
      level = 'reach';
    }

    if (level) {
      results.push({
        ...school,
        matchLevel: level,
        matchScore: diff
      });
    }
  });

  const reach = results.filter(s => s.matchLevel === 'reach').sort((a, b) => b.req_gpa - a.req_gpa);
  const match = results.filter(s => s.matchLevel === 'match').sort((a, b) => Math.abs(a.matchScore) - Math.abs(b.matchScore));
  const safety = results.filter(s => s.matchLevel === 'safety').sort((a, b) => b.req_gpa - a.req_gpa);

  return { reach, match, safety };
};