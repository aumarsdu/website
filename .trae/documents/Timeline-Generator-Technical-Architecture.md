# 申请时间线生成器 技术架构文档 (Technical Architecture)

## 一、技术栈与选型
*   **前端框架**：React 18 + Vite + TypeScript (复用现有架构)
*   **路由管理**：React Router DOM (`/timeline` 路径)
*   **状态管理**：Zustand (`timelineStore.ts`)
*   **样式方案**：Tailwind CSS + CSS Variables (复用全局主题与品牌色)
*   **图标库**：Lucide React
*   **分享图生成**：`html-to-image` (复用GPA计算器中成熟方案)

---

## 二、模块划分与组件结构

### 2.1 页面级组件 (Pages)
*   **`src/pages/TimelineGenerator.tsx`**：时间线生成器主页面，统筹表单与结果展示视图。根据全局路由结构，在 `App.tsx` 中增加对应路由配置。

### 2.2 业务组件 (Components)
位于 `src/components/timeline/` 目录下：
*   **`TimelineForm.tsx`**：表单输入组件，处理国家、层级、年级、专业等字段的级联逻辑（如：选择"本科"才显示申请轮次）。
*   **`TimelineResult.tsx`**：时间线结果展示容器，负责渲染生成后的时间线视图。
*   **`TimelineStageCard.tsx`**：单个时间线阶段卡片组件，展示核心任务、背景提升、截止日期、风险提示及CTA解锁按钮。
*   **`TimelineCta.tsx`**：转化组件，用于在时间线中间拦截、底部引导加微及PDF下载。

---

## 三、状态管理设计 (Zustand Store)

### 3.1 `src/store/timelineStore.ts`
管理时间线生成器的所有表单状态与结果状态。

```typescript
interface TimelineState {
  formData: {
    country: string;
    level: string;
    grade: string;
    major: string;
    tier?: string;
    round?: string;
  };
  timelineData: TimelineStage[] | null;
  isGenerated: boolean;
  setFormData: (data: Partial<TimelineState['formData']>) => void;
  generateTimeline: () => void;
  reset: () => void;
}
```

---

## 四、数据模型与 Mock 数据 (Data Model)

### 4.1 `src/utils/timeline/data.ts`
定义时间线阶段的数据结构，并提供MVP阶段的Mock数据及匹配逻辑。

```typescript
export interface TimelineStage {
  id: string;
  stageName: string;       // 例："高一上学期（9-12月）· 探索与定位"
  coreTasks: string[];     // 核心任务列表
  bgEnhancement: string;   // 背景提升建议
  deadline?: string;       // 关键截止日期
  riskWarning?: string;    // 风险提醒
  isLocked?: boolean;      // 是否为锁定阶段（需加微解锁）
}

// 核心匹配函数：根据 formData 返回对应的 timelineData 数组
export const getTimelineData = (formData: TimelineFormData): TimelineStage[] => {
  // 根据 country, level, grade 等字段进行动态匹配与拼装
}
```

---

## 五、核心逻辑实现细节

1.  **表单级联与动态渲染**：
    *   当申请层级为"本科"时，年级选项展示"初二"至"高三"及"已毕业"。
    *   当申请层级为"硕士"时，年级选项展示"大一"至"大四"及"已毕业"。
    *   "申请轮次"字段仅在申请层级为"本科"时显示。
2.  **内容锁定与 CTA 触发**：
    *   在渲染 `timelineData` 时，针对第3个及之后的阶段设置 `isLocked = true`（视具体剩余阶段数量而定，默认展示前60%）。
    *   渲染被锁定的 `TimelineStageCard` 时，使用模糊遮罩或渐变遮挡内容，并居中显示 "🔒 解锁完整规划 + 个性化背景提升方案" 按钮。
3.  **分享卡片生成**：
    *   使用 `html-to-image` 将整个结果容器 (`TimelineResult`) 转换为图片。
    *   在生成图片时，过滤掉互动按钮（如下载按钮），并注入底部的水印与二维码信息。
4.  **路由与入口集成**：
    *   在 `src/components/Header.tsx` 及 `src/pages/Home.tsx` 中增加时间线生成器的导航入口，引导用户访问 `/timeline`。