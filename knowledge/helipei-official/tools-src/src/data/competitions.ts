
export interface Competition {
  id: string;
  name: string;
  enName: string;
  category: string;
  isAvailable?: boolean;
}

export const COMPETITIONS: Competition[] = [
  {
    "id": "amc8",
    "name": "AMC 8（美国数学竞赛·初中）",
    "enName": "AMC 8",
    "category": "数学",
    "isAvailable": true
  },
  {
    "id": "amc10",
    "name": "AMC 10（美国数学竞赛）",
    "enName": "AMC 10",
    "category": "数学",
    "isAvailable": true
  },
  {
    "id": "amc12",
    "name": "AMC 12（美国数学竞赛）",
    "enName": "AMC 12",
    "category": "数学",
    "isAvailable": true
  },
  {
    "id": "ukmtjmcimcsmc",
    "name": "UKMT 数学挑战（JMC/IMC/SMC）",
    "enName": "UKMT (JMC/IMC/SMC)",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "bmo1bmo2",
    "name": "UKMT 英国数学奥林匹克（BMO Round 1/2）",
    "enName": "BMO1/BMO2",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "cemceuclid",
    "name": "滑铁卢欧几里得数学竞赛",
    "enName": "CEMC Euclid",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "cemcfermat",
    "name": "滑铁卢费马数学竞赛",
    "enName": "CEMC Fermat",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "mathkangaroo",
    "name": "袋鼠数学竞赛（国际/中国大陆常见）",
    "enName": "Math Kangaroo",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "himcm",
    "name": "美国数学建模（HiMCM）",
    "enName": "HiMCM",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "immc",
    "name": "国际数学建模挑战（IMMC）",
    "enName": "IMMC",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "physicsbowl",
    "name": "PhysicsBowl 物理碗",
    "enName": "PhysicsBowl",
    "category": "物理",
    "isAvailable": true
  },
  {
    "id": "bpho",
    "name": "BPhO 英国物理奥赛（Round 1/2）",
    "enName": "BPhO",
    "category": "物理",
    "isAvailable": false
  },
  {
    "id": "usapho",
    "name": "USAPhO（美国物理奥赛·选拔体系）",
    "enName": "USAPhO",
    "category": "物理",
    "isAvailable": false
  },
  {
    "id": "ukchoround1",
    "name": "UKChO 英国化学奥赛（Round 1）",
    "enName": "UKChO Round 1",
    "category": "化学",
    "isAvailable": false
  },
  {
    "id": "ccc",
    "name": "CCC 加拿大化学竞赛",
    "enName": "CCC",
    "category": "化学",
    "isAvailable": false
  },
  {
    "id": "britishbiologyolympiadbbo",
    "name": "BBO 英国生物奥赛",
    "enName": "British Biology Olympiad (BBO)",
    "category": "生物/医学",
    "isAvailable": false
  },
  {
    "id": "usaboopenexam",
    "name": "USABO 美国生物奥赛（公开赛段）",
    "enName": "USABO (Open Exam)",
    "category": "生物/医学",
    "isAvailable": false
  },
  {
    "id": "brainbee",
    "name": "Brain Bee 脑科学大赛",
    "enName": "Brain Bee",
    "category": "生物/医学",
    "isAvailable": false
  },
  {
    "id": "hosa",
    "name": "HOSA 未来健康领袖挑战",
    "enName": "HOSA",
    "category": "生物/医学",
    "isAvailable": false
  },
  {
    "id": "usaco",
    "name": "USACO 美国信息学奥赛（分级）",
    "enName": "USACO",
    "category": "计算机/信息学",
    "isAvailable": false
  },
  {
    "id": "bebraschallenge",
    "name": "Bebras 信息学挑战（海狸竞赛）",
    "enName": "Bebras Challenge",
    "category": "计算机/信息学",
    "isAvailable": false
  },
  {
    "id": "nationaleconomicschallengenec",
    "name": "NEC 全美经济学挑战",
    "enName": "National Economics Challenge (NEC)",
    "category": "商科/经济",
    "isAvailable": false
  },
  {
    "id": "whartoninvestmentcompetition",
    "name": "Wharton Global High School Investment Competition",
    "enName": "Wharton Investment Competition",
    "category": "商科/经济",
    "isAvailable": false
  },
  {
    "id": "diamondchallenge",
    "name": "Diamond Challenge 创业挑战赛",
    "enName": "Diamond Challenge",
    "category": "商科/经济",
    "isAvailable": false
  },
  {
    "id": "johnlockeglobalessayprize",
    "name": "John Locke Essay（约翰·洛克写作）",
    "enName": "John Locke Global Essay Prize",
    "category": "人文/写作",
    "isAvailable": false
  },
  {
    "id": "hirawritingcontest",
    "name": "Harvard International Review 写作竞赛（HIRA）",
    "enName": "HIRA Writing Contest",
    "category": "人文/写作",
    "isAvailable": false
  },
  {
    "id": "worldscholarscupwsc",
    "name": "World Scholar’s Cup 世界学者杯",
    "enName": "World Scholar’s Cup (WSC)",
    "category": "辩论",
    "isAvailable": false
  },
  {
    "id": "modelunitednationsmun",
    "name": "模拟联合国（各类大会：校际/城市/国际）",
    "enName": "Model United Nations (MUN)",
    "category": "MUN",
    "isAvailable": false
  },
  {
    "id": "vex",
    "name": "VEX Robotics Competition",
    "enName": "VEX",
    "category": "机器人/工程",
    "isAvailable": false
  },
  {
    "id": "ftc",
    "name": "FIRST Tech Challenge",
    "enName": "FTC",
    "category": "机器人/工程",
    "isAvailable": false
  },
  {
    "id": "wro",
    "name": "World Robot Olympiad 世界机器人奥林匹克",
    "enName": "WRO",
    "category": "机器人/工程",
    "isAvailable": false
  },
  {
    "id": "amcaustralia",
    "name": "澳大利亚数学竞赛",
    "enName": "AMC (Australia)",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "cemccontests",
    "name": "加拿大数学竞赛（Cayley/Fryer/Galois/Hypatia）",
    "enName": "CEMC Contests",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "cap",
    "name": "CAP 加拿大物理竞赛",
    "enName": "CAP",
    "category": "物理",
    "isAvailable": false
  },
  {
    "id": "sin",
    "name": "SIN 加拿大滑铁卢牛顿物理竞赛",
    "enName": "SIN",
    "category": "物理",
    "isAvailable": false
  },
  {
    "id": "ccccambridge",
    "name": "Cambridge Chemistry Challenge",
    "enName": "CCC (Cambridge)",
    "category": "化学",
    "isAvailable": false
  },
  {
    "id": "ibointermediatevar",
    "name": "IBO 中级/区域类生物竞赛（按赛区）",
    "enName": "IBO Intermediate (var.)",
    "category": "生物/医学",
    "isAvailable": false
  },
  {
    "id": "bio",
    "name": "British Informatics Olympiad",
    "enName": "BIO",
    "category": "计算机/信息学",
    "isAvailable": false
  },
  {
    "id": "fbla",
    "name": "FBLA 商赛（北美高中商业学术）",
    "enName": "FBLA",
    "category": "商科/经济",
    "isAvailable": false
  },
  {
    "id": "ieo",
    "name": "IEO 国际经济学奥赛（赛区选拔）",
    "enName": "IEO",
    "category": "商科/经济",
    "isAvailable": false
  },
  {
    "id": "nytstudentcontests",
    "name": "NYT Student Contests（写作/观点等）",
    "enName": "NYT Student Contests",
    "category": "人文/写作",
    "isAvailable": false
  },
  {
    "id": "scholasticawards",
    "name": "Scholastic Art & Writing Awards（部分国际学生可参）",
    "enName": "Scholastic Awards",
    "category": "人文/写作",
    "isAvailable": false
  },
  {
    "id": "debateleagues",
    "name": "英文辩论（World Schools/各联赛）",
    "enName": "Debate Leagues",
    "category": "辩论",
    "isAvailable": false
  },
  {
    "id": "usad",
    "name": "USAD 学术十项全能（赛区）",
    "enName": "USAD",
    "category": "综合",
    "isAvailable": false
  },
  {
    "id": "tcr",
    "name": "The Concord Review 历史论文",
    "enName": "TCR",
    "category": "综合",
    "isAvailable": false
  },
  {
    "id": "isef",
    "name": "ISEF 科研展（地区→国家→国际）",
    "enName": "ISEF",
    "category": "工程/科研",
    "isAvailable": false
  },
  {
    "id": "sts",
    "name": "Regeneron Science Talent Search（美国为主）",
    "enName": "STS",
    "category": "工程/科研",
    "isAvailable": false
  },
  {
    "id": "purplecomet",
    "name": "Purple Comet! Math Meet",
    "enName": "Purple Comet",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "mathcounts",
    "name": "MathCounts（美国为主）",
    "enName": "MATHCOUNTS",
    "category": "数学",
    "isAvailable": false
  },
  {
    "id": "codejam",
    "name": "Google Code Jam（已停办，历史记录）",
    "enName": "Code Jam",
    "category": "计算机/信息学",
    "isAvailable": false
  }
];

export const COMPETITION_CATEGORIES = [
  "数学",
  "物理",
  "化学",
  "生物/医学",
  "计算机/信息学",
  "商科/经济",
  "人文/写作",
  "辩论",
  "MUN",
  "机器人/工程",
  "综合",
  "工程/科研"
];
