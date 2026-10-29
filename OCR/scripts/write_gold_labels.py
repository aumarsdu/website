#!/usr/bin/env python3
"""把人工视觉核对结论写入金标准清单。

背景：金标准清单由 `make golden-manifest` 生成（分层抽样 20 张），
`人工确认文本 / 人工确认关键字段 / 判定` 三列由人工读图核对后写入。
本脚本把已核对结论一次性写入清单，保证清单可复现、可审计、可 diff。

用法：
  .venv_paddleocr/bin/python scripts/write_gold_labels.py

关键字段用 | 分隔；留空表示该图「无文字 / 不可辨认」，不计入命中率分母。
判定取值：通过 / 已知难例 / 人工不可辨 / 无文字
"""
import csv
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "data" / "golden" / "manifest.csv"

GOLD = {
"G01": ("University of California, Santa Barbara；UC SANTA BARBARA；Office of Admissions；March 17, 2026；"
        "offer you admission to the Pre-Sociology major in the College of Letters and Science for the Fall 2026 quarter；"
        "A world of opportunity awaits you at UC Santa Barbara",
        "UC Santa Barbara|Pre-Sociology|March 17, 2026|Fall 2026", "通过", "录取信截图+彩带遮挡，英文页"),
"G02": ("（低分辨率模糊英文文书截图，正文无法可靠辨认；机器零中文属预期结果，不算识别失败）",
        "", "人工不可辨", "图像质量不足，任何引擎都无法可靠识别；该图应从失败池剔除"),
"G03": ("英语老师推荐信摘要，教AP英语语言：L不是班上最快的学生，有些同学一眼能看出的问题，他要花更多时间消化…"
        "他的B+不是天赋型选手的B+，是一个努力型选手在一个自己不占优势的领域里拿到的真实成绩…"
        "十一年级他写了一篇关于数据如何讲述人权故事的论文，用了联合国难民署的公开数据做文本分析",
        "英语老师推荐信|他的B+|AP英语|联合国难民署", "通过", "现役引擎此图中文产出极低，PP-OCRv6 完整还原"),
"G04": ("NEW YORK UNIVERSITY；On behalf of the admissions committee…admitted to the Steinhardt School of Culture, "
        "Education, and Human Development at New York University, and the NYU Class of 2030；"
        "spring semester, starting in January 2027；graduate in May 2030",
        "NEW YORK UNIVERSITY|Steinhardt School of Culture, Education, and Human Development|Class of 2030|January 2027|May 2030",
        "通过", "NYU 录取信，斜向水印干扰"),
"G05": ("（纯校园风景照片，画面无任何文字；机器零中文属预期结果，不算识别失败）",
        "", "无文字", "本就不含文字，不应进入失败池；机器输出 111111 属建筑纹理误识"),
"G06": ("选校的注意事项；第二种方案偏向于保守型，就是加大保底院校…变成3+4+4…"
        "我见过一个同济大学的学生，USNEWS排名前50的都申了…所以10一15个申请院校真的足够了，不要贪多，要求精",
        "3+4+4|USNEWS排名前50|同济大学|10一15个申请院校", "通过", ""),
"G07": ("三、寻找实习的渠道和注意事项；招聘网站 App: 实习僧、Boss 直聘、应届生、LinkedIn etc；"
        "准备格式规范的中英文简历…使用STAR法则来讲述每段经历…"
        "可以通过牛客网、LeetCode、Codeforces等平台进行题目训练",
        "实习僧|Boss 直聘|STAR法则|LeetCode|Codeforces|LinkedIn", "通过",
        "LinkedIn 被识成 Linkedln（I/l 混淆），属已知错字，记入基线作回归哨兵"),
"G08": ("英港新截止日期汇总；帝国理工IC商学院 第一轮：2025年9月28日；牛津大学商科 首轮：2025年10月24日；"
        "剑桥大学授课型硕士 能在2025年11月15日；伦敦大学学院(UCL) 2025年10月13日；曼彻斯特大学商学院 第二轮：2026年3月1日；"
        "爱丁堡大学 2025年9月上旬；香港大学 第一轮：2025年10月3日；香港中文大学 第四轮：2026年1月12日；"
        "香港科技大学 第一轮：2025年10月12日；新加坡国立(NUS) 第一轮：2025年10月15日；南洋理工(NTU) 第二轮：2026年2月28日",
        "帝国理工IC|2025年9月28日|牛津大学|剑桥大学|伦敦大学学院|曼彻斯特大学|爱丁堡大学|香港大学|香港中文大学|香港科技大学|新加坡国立|南洋理工",
        "通过", "密集表格，全字段命中"),
"G09": ("留学申请工具表2：院校信息整理表；院校的排名（可以是综排、专排、QS排名）；学校名称、地理位置、专业名称、"
        "专业页面链接…申请要求、学费等信息整理备用；哥大 Master of Professional Studies, 3 terms or degree or international，"
        "$2,266 per point；西北大学 Master of Science in Analytics，麦考密克工程学院，$19,344 per quarter",
        "院校信息整理表|哥大|$2.266|西北大学|$19,344", "通过", ""),
"G10": ("备忘录；芝大MSFM: 119人、数学系、15个月、$9.8万学费。期权定价和衍生品方向极强，Roger Lee和Lawler是王牌师资…"
        "CMUMSCF: 约100人、Tepper商学院、16个月、学费約$11万…另外CornellMFE的课程设置更加全面，比芝大更灵活",
        "芝大MSFM|119人|15个月|$9.8万|CMUMSCF|约100人|16个月|$11万", "通过", ""),
"G11": ("1. 普林斯顿大学 人物画像:学术精英，尤其擅长数学和科学…2. 哈佛大学 人物画像:学术顶尖，GPA和标准化考试分数极高…"
        "3. 耶鲁大学 人物画像：富有创造力，特别注重人文学科的深度理解，写作能力强",
        "普林斯顿大学|哈佛大学|耶鲁大学|人物画像", "通过", "长图切片后完整还原"),
"G12": ("备忘录；12%、咨询占10%、医疗制药占7%。起薪在生物统计领域正常；平均起薪约$75,000-$85,000，制药行业中位数$12万-$14万；"
        "两年总预算约$16万（约114万人民币）；学费每年$50,900，纽黑文的生活成本比纽约和波士顿便宜很多",
        "$75,000-$85,000|$12万-$14万|$16万|114万|$50,900", "通过", "金额字段全命中"),
"G13": ("L的写作风格是有温度的精确…十一年级他写了一篇关于数据如何讲述人权故事的论文，用了联合国难民署的公开数据做文本分析；"
        "Phase 3活动列表；第一项，校学生会数据管理员，十年级到十二年级，每周五小时",
        "联合国难民署|AP英语|Phase 3活动列表|校学生会数据管理员", "通过", ""),
"G14": ("耶鲁的生物统计，估计是头部最好录的DS/统计类项目了；萌萌姐－美国留学选校系列；常春藤里相对够得着的项目；"
        "MS和MPH怎么选；26年秋新课程结构，取消了固定的3个分支方向；全美第4｜GPA建议3.7+；"
        "耶鲁生物统计MS，全美综排第4的常春藤，录取率约20%，GPA建议3.7+；MS生统项目2024届招了44人，MPH生统近两年分别招了16人和18人",
        "全美第4|GPA建议3.7+|20%|44人|16人和18人", "通过", ""),
"G15": ("备忘录；强制暑期实习；两年制项目中间的暑假必须完成实习（0学分但必修）；实习单位包括Moderna、Roche、"
        "Yale New Haven Hospital等；平均起薪约$75,000-$85,000，制药行业中位数$12万-$14万；"
        "两年总预算约$17万（约120万人民币）；MS学费每年$52,400（2026-2027GSAS标准），两年学费约$11万美金，年生活费约$3.5万",
        "强制暑期实习|Moderna|Roche|Yale New Haven Hospital|$17万|120万|$52,400|$3.5万", "通过",
        "注意与 G12 同项目不同年份：此图为 $17万/120万，G12 为 $16万/114万，金额不可混用"),
"G16": ("GRADUATE STUDIES；UNIVERSITY of ROCHESTER；MELIORA；我有学上啦！；I am pleased to inform you that you have been "
        "admitted to graduate studies in Arts, Sciences and Engineering；Program: Computer Science；Degree: Master's；"
        "Time Status: Full Time；Matriculation Term: Fall 2023；Response Deadline: April 15, 2023",
        "我有学上啦！|Computer Science|Master's|Fall 2023|April 15, 2023|ROCHESTER", "通过",
        "中文贴纸（艺术字+描边）成功识别，是同类难例的正向对照"),
"G17": ("connect.nyu.edu；Download PDF；February 12, 2026；Congratulations；admitted to New York University and the Class of 2030；"
        "offer you admission to the Gallatin School of Individualized Study；your deadline is March 1, 2026",
        "New York University|Class of 2030|Gallatin School of Individualized Study|February 12, 2026|March 1, 2026",
        "通过", ""),
"G18": ("宾大：IMPA- International Master of Public Administration；Master of And Behavioral decision science；"
        "MSOD Master of science in Organizational Dynamics；哥大：MS in Applied Statistics；GSAS；MS in Social work；"
        "Master of Science in Applied Analytics；Master of Science in Enterprise Risk Management (ERM)",
        "宾大|IMPA|MSOD|GSAS|MS in Applied Statistics|Master of Science in Enterprise Risk Management",
        "通过", "水印为「萌萌留学说」，非正文"),
"G19": ("低分逆袭的秘密；Imperial College London；Admissions；18 April 2023；Congratulations! We are delighted to inform you "
        "that your application to Imperial College London has been successful；找对核心特色；COS code: 100079；"
        "低GPA 巧妙翻身；First year tuition fee: £34400；GPA3.47 收获帝国理工；Status: Not Received",
        "Imperial College London|18 April 2023|找对核心特色|低GPA|巧妙翻身|GPA3.47|收获帝国理工|£34400|100079",
        "通过", "大号白字贴纸压在信正文上，仍全部命中"),
"G20": ("y table has two sides only. Don't get me wrong, the other two sides still exist. It's just that they have to face "
        "the wall otherwise there will be no room for me and mum to get by.",
        "y table has two sides only|Don't get me wrong|face the wall", "已知难例",
        "图片本身左端被裁切（原文首字 M 已被裁掉），参考文本按图内实际可见内容记录；"
        "机器把 wall 识成 vall（w→v），记入基线作回归哨兵"),
}


def main():
    rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8-sig")))
    fields = list(rows[0].keys())
    missing = []
    for row in rows:
        g = GOLD.get(row["样本ID"])
        if not g:
            missing.append(row["样本ID"])
            continue
        row["人工确认文本"], row["人工确认关键字段"], row["判定"], row["备注"] = g
    if missing:
        raise SystemExit(f"清单中存在未标注样本：{missing}")
    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"已写入 {len(rows)} 条金标准标注（含机器初标列，供人工比对）")
    for row in rows:
        print(f"  {row['样本ID']} {row['判定']:<8} 关键字段 {row['人工确认关键字段'][:64]}")


if __name__ == "__main__":
    main()
