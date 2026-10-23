export interface TimelineStage {
  id: string;
  stageName: string;
  timeRange: string;
  coreTasks: string[];
  bgEnhancement: string;
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

export const mockUKUndergradTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '探索与定位期',
    timeRange: '高一上学期（9-12月）',
    icon: '🔍',
    coreTasks: [
      '确定课程体系（A-Level/IB）与科目组合',
      '了解 UCAS 申请机制与五个志愿规则',
      '初步调研英国大学与专业方向（G5/罗素集团）'
    ],
    bgEnhancement: '校内活动探索、兴趣领域调研。可开始探索学科相关的入门背景项目。',
    riskWarning: '⚠️ A-Level 选科需对标目标专业的申请要求，避免组合受限。'
  },
  {
    id: 'stage-2',
    stageName: '基础构建期',
    timeRange: '高一下学期（1-6月）',
    icon: '📚',
    coreTasks: [
      'GPA 与 A-Level 阶段成绩严格管理，保持上升趋势',
      '雅思（IELTS）首考，摸清听说读写短板',
      '课外活动与学科延伸阅读深入参与'
    ],
    bgEnhancement: '参加入门级学科竞赛或学术项目，积累学术背景。',
    deadline: '雅思首考建议时间：高一下学期（5-6月）',
  },
  {
    id: 'stage-3',
    stageName: '加速提升期',
    timeRange: '高一暑假（7-8月）',
    icon: '🚀',
    coreTasks: [
      '参加英国方向夏校/学术营',
      '雅思强化备考',
      '围绕目标专业开展深度阅读或小型研究'
    ],
    bgEnhancement: '🔑 暑期学术项目（核心提升窗口），深入特定学科领域。',
    deadline: '雅思建议在申请前达到 6.5（单项不低于 6.0）',
    riskWarning: '⚠️ 雅思备考与 A-Level 课程学习需平衡，避免顾此失彼。'
  },
  {
    id: 'stage-4',
    stageName: '深度打磨期',
    timeRange: '高二上学期（9-12月）',
    icon: '🎯',
    coreTasks: [
      'A-Level/IB 学习冲刺，为预估成绩打好基础',
      '核心学科竞赛参与并争取奖项',
      '文书素材与学术经历持续积累'
    ],
    bgEnhancement: '学科竞赛 + 深度学术项目，产出可写进 Personal Statement 的核心成果。',
    deadline: 'A-Level/IB 预估成绩通常于高二下学期出具，直接影响申请',
  },
  {
    id: 'stage-5',
    stageName: '申请准备期',
    timeRange: '高二下学期至暑假（1-8月）',
    icon: '✍️',
    coreTasks: [
      '确定 UCAS 五个志愿的选校组合（冲刺/匹配/保底）',
      'Personal Statement 构思与初稿撰写（一篇覆盖全部志愿）',
      '联系推荐老师，准备成绩单与在读证明'
    ],
    bgEnhancement: '🔒 文书与学术成果收尾，牛剑/医学方向需同步准备入学笔试。',
    deadline: 'UCAS 通道通常于 9 月初开放提交',
  },
  {
    id: 'stage-6',
    stageName: '申请冲刺期',
    timeRange: '高三上学期（9-12月）',
    icon: '📮',
    coreTasks: [
      'UCAS 网申填报与提交',
      '牛剑及医学方向：参加笔试与面试',
      '雅思成绩达标或规划重考'
    ],
    bgEnhancement: '专注于文书与面试打磨，牛剑面试需系统模拟练习。',
    deadline: '牛剑/医学截止（10/15）、其余批次截止（1月底）',
    riskWarning: '⚠️ UCAS 志愿提交后不可更换，提交前务必反复核对。'
  },
  {
    id: 'stage-7',
    stageName: '收尾决策期',
    timeRange: '高三下学期至入学前（1-8月）',
    icon: '🏁',
    coreTasks: [
      '跟进 offer/conditional offer，确定第一与保险志愿',
      'A-Level/IB 大考冲刺，达标换取无条件 offer',
      '换取 CAS、办理学生签证（eVisa）、申请宿舍并完成行前准备'
    ],
    bgEnhancement: '保持良好学术状态，大考成绩不达标将导致 offer 失效。',
    deadline: 'A-Level/IB 大考（5-6月）、放榜与 Clearing 补录（8月）',
    riskWarning: '⚠️ 注意押金缴纳与宿舍申请截止时间，有条件 offer 出分后尽快确认。'
  }
];

export const mockUKMasterTimeline: TimelineStage[] = [
  {
    id: 'stage-1',
    stageName: '规划与准备期',
    timeRange: '大三上学期',
    icon: '🔍',
    coreTasks: ['确定申请方向与院校梯度（G5/罗素集团）', '了解目标院校的均分与雅思要求', '维持并提升GPA'],
    bgEnhancement: '寻找专业相关的实习机会或进入实验室跟进项目。',
  },
  {
    id: 'stage-2',
    stageName: '背景提升期',
    timeRange: '大三下学期',
    icon: '🚀',
    coreTasks: ['雅思（IELTS）首考，明确与目标分的差距', '深入参与核心科研或专业实习', '初步筛选目标院校名单'],
    bgEnhancement: '🔑 争取一段高质量的对口实习或科研成果，弥补均分短板。',
    deadline: '争取在暑假前拿到一次合格的雅思成绩'
  },
  {
    id: 'stage-3',
    stageName: '材料准备期',
    timeRange: '大三暑假',
    icon: '✍️',
    coreTasks: ['撰写 Personal Statement（突出学术动机与规划）', '联系 2 位学术推荐人出具推荐信', '准备中英文成绩单、均分证明与在读证明'],
    bgEnhancement: '🔒 利用暑假完成文书精修与背景材料定稿。',
  },
  {
    id: 'stage-4',
    stageName: '申请提交期',
    timeRange: '大四上学期（9-12月）',
    icon: '📮',
    coreTasks: ['英校网申开放，第一时间递交申请', '补交最新的雅思成绩', '跟进部分院校的视频面试或补件要求'],
    bgEnhancement: '确保所有申请材料准确无误，均分证明需与成绩单一致。',
    deadline: '英国硕士多为滚动录取（Rolling），热门项目 11-12 月即满位',
    riskWarning: '⚠️ 先到先得，切勿拖延至截止日期。'
  },
  {
    id: 'stage-5',
    stageName: '录取收尾期',
    timeRange: '大四下学期至入学前（1-8月）',
    icon: '🏁',
    coreTasks: ['对比 offer，缴纳押金锁定名额', '雅思未达标者申请语言班并规划签证时间', '换取 CAS、办理学生签证（eVisa）、申请宿舍并完成行前准备'],
    bgEnhancement: '保持大四成绩达标，毕业证与学位证需按院校要求补交。',
    deadline: '语言班申请（春季截止）、押金与 CAS 办理（4-6月）',
    riskWarning: '⚠️ 语言班名额有限，未达标需尽早申请并预留签证时间。'
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
    timeline = formData.level === '本科'
      ? [...mockUKUndergradTimeline]
      : [...mockUKMasterTimeline];
  } else if (formData.country === '中国香港') {
    timeline = [...mockHKMasterTimeline];
  } else {
    // 默认回退（仅限未收录的国家/层级组合）
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
