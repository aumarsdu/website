export interface TimelineStage {
  id: string;
  stageName: string;
  timeRange: string;
  coreTasks: string[];
  bgEnhancement?: string;
  deadline?: string;
  riskWarning?: string;
  isLocked?: boolean;
  icon?: string;
}

export interface TimelineFormData {
  country: string;
  level: string;
  grade: string;
  major: string;
  tier?: string;
  round?: string;
}

// Mock Data
export const mockUSUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '探索与定位期',
    timeRange: '高一上学期（9-12月）',
    icon: '🔍',
    coreTasks: [
      '确定课程体系（AP/IB/A-Level）',
      '初步选校方向调研',
      '启动英语能力提升'
    ],
    bgEnhancement: '校内活动探索、兴趣领域调研。可开始探索科研方向，推荐参加入门级科研项目。',
    riskWarning: '⚠️ 不要盲目跟风选课，需结合自身优势和学校资源。'
  },
  {
    id: 'stage-2',
    stageName: '基础构建期',
    timeRange: '高一下学期（1-6月）',
    icon: '📚',
    coreTasks: [
      'GPA 严格管理，保持上升趋势',
      '标化首轮备考（托福/雅思）',
      '课外活动深入参与'
    ],
    bgEnhancement: '参加入门级竞赛或学术项目，积累学术背景。',
    deadline: 'AP 考试（5月）',
  },
  {
    id: 'stage-3',
    stageName: '加速提升期',
    timeRange: '高一暑假（7-8月）',
    icon: '🚀',
    coreTasks: [
      '参加暑期科研/夏校',
      'SAT/ACT 强化备考',
      '课外活动列表初建'
    ],
    bgEnhancement: '🔑 暑期科研项目（核心提升窗口），深入特定学术领域。',
    deadline: 'SAT 首考建议时间：高一暑假',
    riskWarning: '⚠️ 不要同时启动 3 门 AP + SAT 备考，容易 GPA 翻车。'
  },
  {
    id: 'stage-4',
    stageName: '深度打磨期',
    timeRange: '高二上学期（9-12月）',
    icon: '🎯',
    coreTasks: [
      '标化成绩冲刺',
      '核心竞赛参与并争取奖项',
      '推荐人关系建立与维护'
    ],
    bgEnhancement: '学科竞赛 + 深度科研，产出核心学术成果。',
    deadline: 'SAT/ACT 目标出分（11-12月）'
  },
  {
    id: 'stage-5',
    stageName: '申请准备期',
    timeRange: '高二下学期至暑假（1-8月）',
    icon: '✍️',
    coreTasks: [
      '选校定校策略确认',
      '主文书构思与初稿撰写',
      '活动清单定稿与完善'
    ],
    bgEnhancement: '🔒 科研论文/竞赛成果收尾，准备作为申请附加材料。',
    deadline: 'Common App 开放（8月1日）'
  },
  {
    id: 'stage-6',
    stageName: '申请冲刺期',
    timeRange: '高三上学期（9-12月）',
    icon: '📮',
    coreTasks: [
      '所有文书定稿',
      '网申系统填报与提交',
      '面试准备与模拟'
    ],
    bgEnhancement: '专注于申请材料打磨，确保每一部分都完美呈现。',
    deadline: 'ED 截止（11/1）、EA 截止（11/1-15）、RD 截止（1/1）',
    riskWarning: '⚠️ 密切关注各校具体截止时间，预留系统拥堵的缓冲时间。'
  },
  {
    id: 'stage-7',
    stageName: '收尾决策期',
    timeRange: '高三下学期（1-5月）',
    icon: '🏁',
    coreTasks: [
      '等待录取结果',
      '对比 Offer，做出最终决定',
      '签证材料准备与申请'
    ],
    bgEnhancement: '保持良好学术状态，避免最后一年 GPA 严重下滑。',
    deadline: 'RD 放榜（3-4月）、确认入学（5/1）'
  }
];

export const mockUKUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '学术探索期',
    timeRange: '高一/AS上学期',
    icon: '🔍',
    coreTasks: ['明确专业方向', '重视校内成绩', '雅思基础学习'],
    bgEnhancement: '广泛阅读专业相关书籍，建立学术兴趣基础。'
  },
  {
    id: 'stage-2',
    stageName: '学术积累期',
    timeRange: '高一/AS下学期',
    icon: '📚',
    coreTasks: ['雅思首考出分', '报名专业竞赛（如BPhO/UKMT）', '参加夏校申请'],
    bgEnhancement: '参加高含金量学科竞赛，开始进行深度课题研究。'
  },
  {
    id: 'stage-3',
    stageName: '核心提升期',
    timeRange: '暑假（7-8月）',
    icon: '🚀',
    coreTasks: ['参加学术夏校/科研项目', '准备附加考试（MAT/STEP/PAT等）', '开始构思个人陈述(PS)'],
    bgEnhancement: '🔑 参加顶尖大学夏校或高强度科研项目，产出能写入PS的素材。'
  },
  {
    id: 'stage-4',
    stageName: '申请递交期',
    timeRange: '高二/A2上学期（9-10月）',
    icon: '📮',
    coreTasks: ['确定最终5所选校', 'PS定稿', '提交UCAS申请'],
    bgEnhancement: '🔒 停止新增大型活动，将已有成果完美呈现在文书中。',
    deadline: '牛剑及医学专业：10月15日；常规专业：次年1月底'
  },
  {
    id: 'stage-5',
    stageName: '面试与冲刺期',
    timeRange: '高二/A2上学期（11-12月）',
    icon: '🎯',
    coreTasks: ['参加笔试（牛剑/帝国理工等）', '准备面试（如获邀）', '收到预录取(Conditional Offer)'],
    bgEnhancement: '专注于面试训练，强化专业领域的口头表达和逻辑推导能力。'
  },
  {
    id: 'stage-6',
    stageName: '换取无条件录取',
    timeRange: '高二/A2下学期',
    icon: '🏁',
    coreTasks: ['全力备战A-Level/IB大考', '考取满足条件的雅思成绩', '申请语言班（如需）'],
    deadline: '通常8月中旬A-Level放榜后确认是否过线',
    riskWarning: '⚠️ 英国发的是预录取，最终成绩不达标将被取消录取！务必保住大考成绩。'
  }
];

export const mockCanadaUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '基础规划期',
    timeRange: '高一阶段',
    icon: '🔍',
    coreTasks: ['保持优秀在校成绩', '确定选科方向', '语言能力提升'],
    bgEnhancement: '参加志愿者活动或社团，加拿大注重学生的全面发展。'
  },
  {
    id: 'stage-2',
    stageName: '成绩提升期',
    timeRange: '高二阶段',
    icon: '📚',
    coreTasks: ['攻克雅思/托福', '准备会考', '参与省级/国家级竞赛'],
    bgEnhancement: '🔑 争取在滑铁卢数学竞赛（Euclid）等加系赛事中获奖。'
  },
  {
    id: 'stage-3',
    stageName: '申请准备期',
    timeRange: '高二暑假（7-8月）',
    icon: '✍️',
    coreTasks: ['确定申请院校及专业', '准备申请文书素材', '开具成绩单'],
    bgEnhancement: '参加与目标专业紧密相关的夏令营或社会实践。'
  },
  {
    id: 'stage-4',
    stageName: '网申递交期',
    timeRange: '高三上学期（9-12月）',
    icon: '📮',
    coreTasks: ['提交 OUAC 申请（安省院校）', '完成文书撰写与视频面试（Kira）', '提交语言成绩'],
    bgEnhancement: '🔒 准备商科/工程专业的 Kira 面试，梳理活动经历。',
    deadline: '多数顶尖院校（多大/UBC）早申或热门专业截止于 11-12 月'
  },
  {
    id: 'stage-5',
    stageName: '录取追踪期',
    timeRange: '高三下学期（1-5月）',
    icon: '🏁',
    coreTasks: ['补充提交高三上学期成绩', '跟进录取状态', '办理学习签证'],
    deadline: '多伦多大学等通常在 2-5 月分批放榜',
    riskWarning: '⚠️ 高三下学期成绩必须达标，否则可能被撤销录取。'
  }
];

export const mockSingaporeUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '准备与规划期',
    timeRange: '高一至高二',
    icon: '🔍',
    coreTasks: ['保持顶尖的在校成绩', '冲刺雅思/托福', '准备高考（走高考途径）或准备A-Level/IB'],
    bgEnhancement: '参加高级别竞赛（如数理化奥赛），新加坡公立大学非常看重硬核学术奖项。'
  },
  {
    id: 'stage-2',
    stageName: '申请递交期',
    timeRange: '高三上学期（10-12月）',
    icon: '📮',
    coreTasks: ['完成网申并提交文书', '提交已有标化成绩', '联系推荐人'],
    bgEnhancement: '梳理高中阶段的所有获奖证书并进行公证/翻译。',
    deadline: 'NUS/NTU 通常在 10 月开放申请，次年 2-3 月截止'
  },
  {
    id: 'stage-3',
    stageName: '笔试与面试期',
    timeRange: '高三下学期（3-5月）',
    icon: '🎯',
    coreTasks: ['部分专业参加入学笔试', '参加线上面试', '高考冲刺（高考途径）'],
    bgEnhancement: '练习全英文面试，展示出色的逻辑思维和沟通能力。'
  },
  {
    id: 'stage-4',
    stageName: '录取与行前',
    timeRange: '高考后（6-7月）',
    icon: '🏁',
    coreTasks: ['补充提交高考成绩（出分后 3 天内）', '获取录取通知', '申请学生准证(IPA)及宿舍'],
    deadline: '通常在 6 月底至 7 月初出最终录取结果'
  }
];

export const mockAustraliaUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '方案制定期',
    timeRange: '高二下学期',
    icon: '🔍',
    coreTasks: ['评估现有成绩（平时成绩/高考预估）', '选择申请路径（直申/预科/国际大一）', '备考雅思'],
    bgEnhancement: '澳洲本科主要看重学术成绩，背景提升主要用于申请高额奖学金。'
  },
  {
    id: 'stage-2',
    stageName: '申请递交期',
    timeRange: '高三上学期（7-9月）',
    icon: '📮',
    coreTasks: ['开具 5 学期成绩单', '递交有条件录取申请（Conditional Offer）', '雅思冲刺'],
    deadline: '澳洲 2 月开学为主，建议尽早占位',
    riskWarning: '⚠️ 八大名校部分热门专业（如医学、精算）满位极快。'
  },
  {
    id: 'stage-3',
    stageName: '补充材料期',
    timeRange: '高三下学期（1-5月）',
    icon: '📚',
    coreTasks: ['补交雅思成绩', '准备高考（如走高考直申途径）', '申请语言班（如雅思未达标）'],
    bgEnhancement: '🔑 若雅思难以达标，需尽早申请配套语言班（通常提前 3-6 个月）。'
  },
  {
    id: 'stage-4',
    stageName: '换取无条件录取',
    timeRange: '高考后（6-7月）',
    icon: '🏁',
    coreTasks: ['提交完整成绩单/毕业证/高考成绩', '换取 Unconditional Offer', '缴纳学费换取 COE', '递交签证'],
    deadline: '获取 COE 后需立即办理签证，确保赶上 7 月或次年 2 月开学'
  }
];

export const mockUSMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '规划与准备期',
    timeRange: '大三上学期',
    icon: '🔍',
    coreTasks: ['确定申请专业方向', '制定语言和GRE/GMAT备考计划', '维持并提升GPA'],
    bgEnhancement: '寻找专业相关的实习机会或进入实验室跟进项目。',
  },
  {
    id: 'stage-2',
    stageName: '背景提升期',
    timeRange: '大三下学期',
    icon: '🚀',
    coreTasks: ['参加语言和GRE/GMAT考试', '深入参与核心科研或实习', '初步筛选目标院校'],
    bgEnhancement: '🔑 争取获得一段高质量的专业对口实习或科研成果。',
    deadline: '争取在暑假前出一次可用的标化成绩'
  },
  {
    id: 'stage-3',
    stageName: '申请材料准备期',
    timeRange: '大三暑假',
    icon: '✍️',
    coreTasks: ['敲定最终选校名单', '联系推荐人', '开始撰写PS和CV初稿'],
    bgEnhancement: '🔒 利用暑假进行高强度的核心实习或科研项目冲刺。',
  },
  {
    id: 'stage-4',
    stageName: '冲刺与提交期',
    timeRange: '大四上学期',
    icon: '📮',
    coreTasks: ['网申系统填报', '文书精修与定稿', '提交成绩单与语言成绩'],
    bgEnhancement: '确保所有申请材料准确无误。',
    deadline: '大多数项目截止日期集中在12月至次年1月',
    riskWarning: '⚠️ 注意各项目是否需要提交WES认证，预留充足时间。'
  }
];

export const mockHKMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '探索定位期',
    timeRange: '大三下学期',
    icon: '🔍',
    coreTasks: ['了解港校申请要求', '准备雅思/托福', '提升在校GPA'],
    bgEnhancement: '寻找对口的实习机会，港校非常看重实践经验。'
  },
  {
    id: 'stage-2',
    stageName: '材料准备期',
    timeRange: '大三暑假',
    icon: '✍️',
    coreTasks: ['准备申请文书(PS, CV)', '联系推荐人获取推荐信', '准备成绩单及在读证明'],
    bgEnhancement: '🔑 积累一段有含金量的专业实习。'
  },
  {
    id: 'stage-3',
    stageName: '申请提交期',
    timeRange: '大四上学期（9-12月）',
    icon: '📮',
    coreTasks: ['港校网申开放，第一时间递交', '补充提交最新语言成绩', '准备可能出现的面试'],
    bgEnhancement: '🔒 准备好应对部分商科或社科项目的面试环节。',
    deadline: '港校多为滚动录取（Rolling），建议尽早申请！',
    riskWarning: '⚠️ 港校遵循先到先得原则，切勿拖延至最后期限。'
  }
];

export const mockUKMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '准备与定校期',
    timeRange: '大三下学期',
    icon: '🔍',
    coreTasks: ['保持高GPA', '确定申请专业和学校梯队', '开始准备雅思'],
    bgEnhancement: '寻找相关的实习或科研项目，英国看重学术和实践的匹配度。'
  },
  {
    id: 'stage-2',
    stageName: '材料准备期',
    timeRange: '大三暑假',
    icon: '✍️',
    coreTasks: ['联系教授写推荐信', '撰写个人陈述(PS)和CV', '开具在读证明及成绩单'],
    bgEnhancement: '🔑 深入完善专业实习或科研经历。'
  },
  {
    id: 'stage-3',
    stageName: '申请递交期',
    timeRange: '大四上学期（9-11月）',
    icon: '📮',
    coreTasks: ['网申开放后第一时间递交', '跟进推荐信提交状态', '继续刷雅思分数'],
    deadline: '英国实行先到先得（Rolling），热门专业11月可能就满位。'
  },
  {
    id: 'stage-4',
    stageName: '录取与语言班',
    timeRange: '大四下学期（1-5月）',
    icon: '🏁',
    coreTasks: ['收到 Conditional Offer', '若雅思未达标，申请语言班', '准备毕业设计'],
    riskWarning: '⚠️ 务必注意换取 Unconditional Offer 的截止日期。'
  }
];

export const mockCanadaMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '前期准备期',
    timeRange: '大三阶段',
    icon: '🔍',
    coreTasks: ['极力提升GPA', '准备雅思/托福', '准备GRE/GMAT（如申请商科/工科）'],
    bgEnhancement: '参与教授科研项目或高含金量专业实习。'
  },
  {
    id: 'stage-2',
    stageName: '文书与套磁',
    timeRange: '大三暑假（7-8月）',
    icon: '✍️',
    coreTasks: ['筛选目标项目（授课型 vs 研究型）', '准备文书材料', '研究型硕士开始套磁教授'],
    bgEnhancement: '🔑 梳理科研经历，撰写 Research Proposal（如需）。'
  },
  {
    id: 'stage-3',
    stageName: '网申递交期',
    timeRange: '大四上学期（9-12月）',
    icon: '📮',
    coreTasks: ['完成网申并提交申请费', '进行 Kira 视频面试（如商科）', '邮寄纸质成绩单（如学校要求）'],
    deadline: '多数顶尖大学硕士项目于 12 月或 1 月截止。'
  },
  {
    id: 'stage-4',
    stageName: '等待与签证',
    timeRange: '大四下学期（1-6月）',
    icon: '🏁',
    coreTasks: ['等待录取结果', '办理加拿大签证（SDS/普签）', '体检及行前准备'],
    riskWarning: '⚠️ 加拿大学签审核严格且周期长，拿到 Offer 后应立刻准备资金证明并递签。'
  }
];

export const mockAustraliaMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '选校与备考',
    timeRange: '大三下学期',
    icon: '🔍',
    coreTasks: ['根据当前GPA匹配澳洲八大', '开始准备雅思', '确定专业方向'],
    bgEnhancement: '澳洲授课型硕士基本只看硬件（GPA+语言），背景提升为辅。'
  },
  {
    id: 'stage-2',
    stageName: '5学期成绩单申请',
    timeRange: '大四上学期（7-10月）',
    icon: '📮',
    coreTasks: ['开具前5或6学期成绩单', '递交免雅思的有条件录取申请', '获取 Conditional Offer'],
    deadline: '澳洲名校商科/计算机满位快，建议大四上学期即用 5 学期成绩单占位。'
  },
  {
    id: 'stage-3',
    stageName: '雅思冲刺与补件',
    timeRange: '大四下学期（1-5月）',
    icon: '📚',
    coreTasks: ['全力考出达标雅思成绩', '若未达标尽早配语言班', '准备毕业事宜'],
    bgEnhancement: '🔑 提前准备好资金证明。'
  },
  {
    id: 'stage-4',
    stageName: '换取 COE 与签证',
    timeRange: '毕业后（7月）',
    icon: '🏁',
    coreTasks: ['补交完整成绩单和毕业证学位证', '换取 Unconditional Offer', '缴纳学费换取 COE', '递交签证'],
    deadline: '赶 7 月开学的同学时间非常紧凑，需提前与学校沟通加急处理。'
  }
];

export const mockSingaporeMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '规划与备考期',
    timeRange: '大三下学期',
    icon: '🔍',
    coreTasks: ['保持高GPA（非常重要）', '备考雅思/托福', '准备GMAT/GRE（部分商科必备）'],
    bgEnhancement: '新加坡公立三所非常看重本科学校背景和高GPA，需针对性提升实习/科研经历。'
  },
  {
    id: 'stage-2',
    stageName: '材料打磨期',
    timeRange: '大三暑假',
    icon: '✍️',
    coreTasks: ['撰写 PS 和 CV', '联系学术/职业推荐人', '开具成绩单等官方文件'],
    bgEnhancement: '🔑 补充高质量的大厂实习或核心科研。'
  },
  {
    id: 'stage-3',
    stageName: '申请递交与面试',
    timeRange: '大四上学期（9-12月）',
    icon: '📮',
    coreTasks: ['项目开放后尽早递交网申', '准备并参加笔试/面试', '持续跟进申请状态'],
    deadline: '新加坡多数项目分轮次审理，第一轮通常在 10-11 月，建议赶早。'
  },
  {
    id: 'stage-4',
    stageName: '录取与行前',
    timeRange: '大四下学期（1-5月）',
    icon: '🏁',
    coreTasks: ['确认录取并缴纳留位费', '办理学生准证（IPA）', '寻找租房（大部分授课型硕士不提供宿舍）'],
    riskWarning: '⚠️ 新加坡留位费较高且通常不退，多校混申时需把握好接受 Offer 的节奏。'
  }
];

export const generateTimeline = (formData: TimelineFormData): TimelineStage[] => {
  let timeline: TimelineStage[] = [];

  // MVP 匹配逻辑
  if (formData.country === '美国') {
    if (formData.level === '本科') {
      timeline = [...mockUSUndergradTimeline];
    } else {
      timeline = [...mockUSMasterTimeline];
    }
  } else if (formData.country === '英国') {
    if (formData.level === '本科') {
      timeline = [...mockUKUndergradTimeline];
    } else {
      timeline = [...mockUKMasterTimeline];
    }
  } else if (formData.country === '加拿大') {
    if (formData.level === '本科') {
      timeline = [...mockCanadaUndergradTimeline];
    } else {
      timeline = [...mockCanadaMasterTimeline];
    }
  } else if (formData.country === '澳大利亚') {
    if (formData.level === '本科') {
      timeline = [...mockAustraliaUndergradTimeline];
    } else {
      timeline = [...mockAustraliaMasterTimeline];
    }
  } else if (formData.country === '新加坡') {
    if (formData.level === '本科') {
      timeline = [...mockSingaporeUndergradTimeline];
    } else {
      timeline = [...mockSingaporeMasterTimeline];
    }
  } else if (formData.country === '中国香港') {
    timeline = [...mockHKMasterTimeline];
  } else {
    // 默认回退
    timeline = [...mockUSUndergradTimeline];
  }

  // 动态截断与锁定逻辑
  // 假设根据年级截断部分过去的阶段（这里简化处理，只做锁定演示）
  // 对阶段数组，从第3个阶段开始设置锁定标记
  const lockIndex = Math.floor(timeline.length * 0.6); // 60% 处锁定
  
  return timeline.map((stage, index) => ({
    ...stage,
    isLocked: index >= lockIndex,
  }));
};
