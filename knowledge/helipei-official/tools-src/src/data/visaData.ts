export interface MaterialItem {
  id: string;
  name: string;
  required: boolean;
  prep_time: string;
  notes: string;
  needs_translation: boolean;
}

export interface VisaType {
  id: string;
  type: string;
  type_name: string;
  description: string;
  fees: {
    visa_fee: { amount: number; currency: string; cny: number };
    sevis_fee?: { amount: number; currency: string; cny: number };
    ihs_fee?: { amount: number; currency: string; cny: number };
  };
  processing_time: string;
  materials: {
    core: MaterialItem[];
    financial: MaterialItem[];
    academic: MaterialItem[];
    supporting: MaterialItem[];
    tips: string[];
  };
}

export interface CountryVisa {
  id: string;
  country: string;
  country_name: string;
  visa_types: VisaType[];
}

export const visaData: CountryVisa[] = [
  {
    id: "us",
    country: "US",
    country_name: "美国",
    visa_types: [
      {
        id: "us-f1",
        type: "F1",
        type_name: "F-1 学生签证",
        description: "全日制学术课程（本科/硕士/博士/语言课程）",
        fees: {
          visa_fee: { amount: 185, currency: "USD", cny: 1340 },
          sevis_fee: { amount: 350, currency: "USD", cny: 2540 }
        },
        processing_time: "面签当天出结果，护照返回 3-7 个工作日",
        materials: {
          core: [
            {
              id: "us-f1-core-1",
              name: "有效护照",
              required: true,
              prep_time: "首次 7-15 工作日",
              notes: "有效期超出留学期间至少 6 个月，至少 2 页空白签证页",
              needs_translation: false
            },
            {
              id: "us-f1-core-2",
              name: "DS-160 确认页",
              required: true,
              prep_time: "1-2 小时",
              notes: "在线填写后打印确认页，记住申请编号",
              needs_translation: false
            },
            {
              id: "us-f1-core-3",
              name: "I-20 表格",
              required: true,
              prep_time: "学校签发 1-4 周",
              notes: "由录取学校签发，须本人签字；转学需新 I-20",
              needs_translation: false
            },
            {
              id: "us-f1-core-4",
              name: "面签预约单",
              required: true,
              prep_time: "预约后立等可取",
              notes: "缴费后预约面签时间的确认凭证",
              needs_translation: false
            },
            {
              id: "us-f1-core-5",
              name: "SEVIS 缴费收据 (I-901)",
              required: true,
              prep_time: "缴费后立等可取",
              notes: "在线缴纳SEVIS费后打印的凭证",
              needs_translation: false
            },
            {
              id: "us-f1-core-6",
              name: "签证照片 (51mm x 51mm)",
              required: true,
              prep_time: "1-2 天",
              notes: "近6个月内白底彩照，露出双耳，不可戴眼镜",
              needs_translation: false
            }
          ],
          financial: [
            {
              id: "us-f1-fin-1",
              name: "银行存款证明",
              required: true,
              prep_time: "1-3 工作日",
              notes: "金额 ≥ I-20 上标注的第一年费用；冻结至少到签证面试后",
              needs_translation: true
            },
            {
              id: "us-f1-fin-2",
              name: "父母收入证明",
              required: false,
              prep_time: "3-5 工作日",
              notes: "如资金由父母提供，需提供父母在职及收入证明",
              needs_translation: true
            },
            {
              id: "us-f1-fin-3",
              name: "房产/车产证明",
              required: false,
              prep_time: "1-3 工作日",
              notes: "非必需，作为辅助财力证明增加过签率",
              needs_translation: true
            }
          ],
          academic: [
            {
              id: "us-f1-acad-1",
              name: "学校录取通知书 (Offer/Admission Letter)",
              required: true,
              prep_time: "已获得",
              notes: "原件或高清晰打印件",
              needs_translation: false
            },
            {
              id: "us-f1-acad-2",
              name: "官方成绩单",
              required: true,
              prep_time: "1-2 周",
              notes: "中英文对照，加盖学校公章并密封",
              needs_translation: true
            },
            {
              id: "us-f1-acad-3",
              name: "学位证/毕业证/在读证明",
              required: true,
              prep_time: "1-2 周",
              notes: "中英文对照原件，加盖学校公章",
              needs_translation: true
            },
            {
              id: "us-f1-acad-4",
              name: "语言成绩单 (TOEFL/IELTS等)",
              required: false,
              prep_time: "已获得",
              notes: "提供复印件即可，证明语言能力符合要求",
              needs_translation: false
            },
            {
              id: "us-f1-acad-5",
              name: "学习计划 (Study Plan)",
              required: false,
              prep_time: "3-5 天",
              notes: "特别是敏感专业/硕博申请者，强烈建议准备",
              needs_translation: true
            },
            {
              id: "us-f1-acad-6",
              name: "导师简历/个人简历",
              required: false,
              prep_time: "1-3 天",
              notes: "硕博申请者必需，包含研究方向说明",
              needs_translation: true
            }
          ],
          supporting: [
            {
              id: "us-f1-sup-1",
              name: "户口本原件",
              required: false,
              prep_time: "已获得",
              notes: "证明亲属关系（如资助人为父母）",
              needs_translation: true
            },
            {
              id: "us-f1-sup-2",
              name: "旧护照",
              required: false,
              prep_time: "已获得",
              notes: "如有旧护照必须提供，以展示过往出入境记录",
              needs_translation: false
            }
          ],
          tips: [
            "面签回答简洁明了，不要背诵答案，只回答签证官问到的问题",
            "SEVIS 费需在面签前至少 3 天缴纳",
            "必须证明自己没有移民倾向，毕业后有明确回国计划",
            "如有拒签史，准备好合理解释，不要试图隐瞒"
          ]
        }
      },
      {
        id: "us-j1",
        type: "J1",
        type_name: "J-1 访问学者签证",
        description: "交流访问学者、交换生等",
        fees: {
          visa_fee: { amount: 185, currency: "USD", cny: 1340 },
          sevis_fee: { amount: 220, currency: "USD", cny: 1595 }
        },
        processing_time: "面签当天出结果，护照返回 3-7 个工作日",
        materials: {
          core: [
            {
              id: "us-j1-core-1",
              name: "有效护照",
              required: true,
              prep_time: "首次 7-15 工作日",
              notes: "有效期超出计划停留期至少 6 个月",
              needs_translation: false
            },
            {
              id: "us-j1-core-2",
              name: "DS-2019 表格",
              required: true,
              prep_time: "机构签发 2-4 周",
              notes: "由美国赞助机构签发，须本人签字",
              needs_translation: false
            },
            {
              id: "us-j1-core-3",
              name: "DS-160 确认页",
              required: true,
              prep_time: "1-2 小时",
              notes: "在线填写后打印确认页",
              needs_translation: false
            },
            {
              id: "us-j1-core-4",
              name: "SEVIS 缴费收据 (I-901)",
              required: true,
              prep_time: "缴费后立等可取",
              notes: "某些政府资助项目可能免除",
              needs_translation: false
            }
          ],
          financial: [
            {
              id: "us-j1-fin-1",
              name: "资金证明",
              required: true,
              prep_time: "1-3 工作日",
              notes: "需覆盖在美期间生活费用，如由赞助方提供需出具证明",
              needs_translation: true
            }
          ],
          academic: [
            {
              id: "us-j1-acad-1",
              name: "邀请信",
              required: true,
              prep_time: "已获得",
              notes: "美国接收机构或导师出具的正式邀请函",
              needs_translation: false
            },
            {
              id: "us-j1-acad-2",
              name: "个人简历",
              required: true,
              prep_time: "1-3 天",
              notes: "详细的教育和工作经历，英文",
              needs_translation: true
            }
          ],
          supporting: [],
          tips: [
            "注意 J-1 签证可能带有「两年回国服务限制」(212(e))",
            "建议提前了解保险要求，J-1 持有者必须购买符合规定的健康保险"
          ]
        }
      }
    ]
  },
  {
    id: "uk",
    country: "UK",
    country_name: "英国",
    visa_types: [
      {
        id: "uk-student",
        type: "Student",
        type_name: "Student Visa (原Tier 4)",
        description: "16岁以上赴英攻读学位或长期课程",
        fees: {
          visa_fee: { amount: 490, currency: "GBP", cny: 4500 },
          ihs_fee: { amount: 776, currency: "GBP", cny: 7100 }
        },
        processing_time: "标准服务 3 周内（可加急）",
        materials: {
          core: [
            {
              id: "uk-stu-core-1",
              name: "有效护照",
              required: true,
              prep_time: "首次 7-15 工作日",
              notes: "至少留有一页正反两面都是空白的签证页",
              needs_translation: false
            },
            {
              id: "uk-stu-core-2",
              name: "CAS (Confirmation of Acceptance for Studies)",
              required: true,
              prep_time: "学校发放 1-2 周",
              notes: "学校提供的一个电子参考号码，无需纸质文件",
              needs_translation: false
            },
            {
              id: "uk-stu-core-3",
              name: "签证申请表打印件",
              required: true,
              prep_time: "1-2 小时",
              notes: "在线提交后打印，签字",
              needs_translation: false
            },
            {
              id: "uk-stu-core-4",
              name: "肺结核检测证明",
              required: true,
              prep_time: "检查后 1-3 天",
              notes: "计划在英停留超过 6 个月必须提供（指定医院）",
              needs_translation: false
            },
            {
              id: "uk-stu-core-5",
              name: "ATAS 证书",
              required: false,
              prep_time: "20-30 工作日",
              notes: "仅限特定敏感专业的本硕博申请者",
              needs_translation: false
            }
          ],
          financial: [
            {
              id: "uk-stu-fin-1",
              name: "银行存款证明",
              required: true,
              prep_time: "存满28天",
              notes: "金额=第一年学费+9个月生活费；必须连续存满28天",
              needs_translation: true
            },
            {
              id: "uk-stu-fin-2",
              name: "银行流水单",
              required: true,
              prep_time: "存满28天",
              notes: "证明资金存满28天的历史记录，最后交易日期在签证申请前31天内",
              needs_translation: true
            },
            {
              id: "uk-stu-fin-3",
              name: "父母同意信及出生证明",
              required: false,
              prep_time: "1-3 工作日",
              notes: "如资金在父母名下，需提供户口本/出生证及父母同意资助信",
              needs_translation: true
            }
          ],
          academic: [
            {
              id: "uk-stu-acad-1",
              name: "CAS 提到的学术材料",
              required: true,
              prep_time: "已获得",
              notes: "通常包括成绩单、毕业证、学位证原件及翻译件",
              needs_translation: true
            },
            {
              id: "uk-stu-acad-2",
              name: "语言成绩单",
              required: true,
              prep_time: "已获得",
              notes: "如 CAS 中明确要求，如 UKVI 雅思成绩单",
              needs_translation: false
            }
          ],
          supporting: [
            {
              id: "uk-stu-sup-1",
              name: "旧护照",
              required: false,
              prep_time: "已获得",
              notes: "如有必须提供",
              needs_translation: false
            }
          ],
          tips: [
            "存款证明是英国签证最容易出错的环节，务必确保连续存满 28 天",
            "目前中国大陆申请人属于低风险国家，签证中心实行简化材料政策，但可能被抽查，建议全部备齐",
            "签证费和 IHS (医疗附加费) 均需在线缴纳"
          ]
        }
      }
    ]
  },
  {
    id: "au",
    country: "AU",
    country_name: "澳大利亚",
    visa_types: [
      {
        id: "au-500",
        type: "Subclass 500",
        type_name: "学生签证 (500类别)",
        description: "赴澳攻读各类全日制课程",
        fees: {
          visa_fee: { amount: 710, currency: "AUD", cny: 3400 }
        },
        processing_time: "通常 2-4 周（大学高等教育类）",
        materials: {
          core: [
            {
              id: "au-500-core-1",
              name: "有效护照",
              required: true,
              prep_time: "首次 7-15 工作日",
              notes: "彩色扫描件（首页及所有包含签证/印章的页面）",
              needs_translation: false
            },
            {
              id: "au-500-core-2",
              name: "COE (Confirmation of Enrolment)",
              required: true,
              prep_time: "缴费后 1-2 周",
              notes: "接受 Offer 并缴费后学校出具的入学确认信",
              needs_translation: false
            },
            {
              id: "au-500-core-3",
              name: "OSHC (海外学生健康保险)",
              required: true,
              prep_time: "1-2 天",
              notes: "必须覆盖整个签证有效期的保险凭证",
              needs_translation: false
            },
            {
              id: "au-500-core-4",
              name: "体检证明",
              required: true,
              prep_time: "检查后 3-5 天",
              notes: "建议在提交申请前通过 eMedical 系统提前体检",
              needs_translation: false
            },
            {
              id: "au-500-core-5",
              name: "GTE (真实临时入境者) 声明",
              required: true,
              prep_time: "3-5 天",
              notes: "撰写详细的 Personal Statement 证明留学目的真实性",
              needs_translation: true
            }
          ],
          financial: [
            {
              id: "au-500-fin-1",
              name: "资金证明",
              required: true,
              prep_time: "1-3 工作日",
              notes: "需覆盖第一年的学费、生活费和差旅费；中国属较低风险等级通常不强制要求，但可能抽查",
              needs_translation: true
            }
          ],
          academic: [
            {
              id: "au-500-acad-1",
              name: "最高学历证明",
              required: true,
              prep_time: "1-2 周",
              notes: "毕业证、学位证公证件或学校出具的中英文证明",
              needs_translation: true
            },
            {
              id: "au-500-acad-2",
              name: "成绩单",
              required: true,
              prep_time: "1-2 周",
              notes: "中英文对照，加盖学校公章",
              needs_translation: true
            },
            {
              id: "au-500-acad-3",
              name: "语言成绩单",
              required: false,
              prep_time: "已获得",
              notes: "雅思/托福等成绩单扫描件",
              needs_translation: false
            }
          ],
          supporting: [
            {
              id: "au-500-sup-1",
              name: "出生公证",
              required: false,
              prep_time: "1-2 周",
              notes: "强烈建议提供（尤其是18岁以下申请人必须提供）",
              needs_translation: true
            },
            {
              id: "au-500-sup-2",
              name: "曾用名公证",
              required: false,
              prep_time: "1-2 周",
              notes: "如有曾用名必须提供",
              needs_translation: true
            }
          ],
          tips: [
            "澳洲学生签证为纯电子签证，在线提交彩色扫描件，无需寄送原件",
            "GTE 声明是澳洲签证审核的核心，务必认真撰写回国动机",
            "请勿在签证下发前购买不可退改的机票"
          ]
        }
      }
    ]
  }
];
