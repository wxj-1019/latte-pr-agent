  分析报告：后端驱动的 Latte PR Agent 前端优化方案                                                                                
  一、后端数据结构梳理                                                                                                            
  通过分析后端模型 (src/models/)，我识别出以下核心数据实体：

  实体: Review
  关键字段: id, platform, repo_id, pr_number, pr_title, status,  
    risk_level, ai_model, created_at, completed_at
  前端用途: Reviews 列表页、详情页头部
  ────────────────────────────────────────
  实体: ReviewFinding
  关键字段: id, file_path, line_number, severity, description,   
    suggestion, confidence, ai_model
  前端用途: Finding 详情面板、Diff 标注
  ────────────────────────────────────────
  实体: PRFile
  关键字段: file_path, change_type, additions, deletions,        
    diff_content
  前端用途: 文件树、Diff 视图
  ────────────────────────────────────────
  实体: DeveloperFeedback
  关键字段: is_false_positive, comment
  前端用途: 反馈按钮、误报标记
  ────────────────────────────────────────
  实体: BugKnowledge
  关键字段: bug_pattern, severity, fix_description
  前端用途: RAG 知识库展示
  ────────────────────────────────────────
  实体: ProjectConfig
  关键字段: config_json
  前端用途: 项目配置页

  Workflow 流程: Webhook → Review (pending) → Celery Worker →    
  Finding 生成 → Publisher 发布评论 → Review (completed/failed)  

  ---
  二、现有前端设计评估

  优势：
  - "Latte" 品牌概念完整，配色系统独特
  - Apple-style 玻璃拟态 + 拿铁色调的视觉方向明确
  - 组件大纲结构清晰

  需要完善的地方：

  1. 数据与视图的映射不够清晰 - 需要明确每个页面展示哪些后端字段 
  2. 缺少 API 接口设计 - 前端需要知道如何获取数据
  3. Dashboard 交互状态流缺失 - 例如 Review 从 pending →
  completed 的实时更新
  4. 缺少错误状态和空状态设计

  ---
  三、优化后的完整方案

  3.1 API 接口设计（新增）

  // lib/api.ts
  export const api = {
    // Reviews
    getReviews: (params?: { status?: string; repo?: string;      
  page?: number }) =>
      fetch(`/api/reviews?${new URLSearchParams(params)}`),      

    getReviewDetail: (id: number) =>
      fetch(`/api/reviews/${id}`),

    // Findings
    getReviewFindings: (reviewId: number) =>
      fetch(`/api/reviews/${reviewId}/findings`),

    submitFeedback: (findingId: number, data: {
  is_false_positive: boolean; comment?: string }) =>
      fetch(`/api/findings/${findingId}/feedback`, { method:     
  'POST', body: JSON.stringify(data) }),

    // Metrics
    getMetrics: (range: '7d' | '30d' | '90d') =>
      fetch(`/api/metrics?range=${range}`),

    // Config
    getProjectConfig: (repoId: string) =>
      fetch(`/api/config/${repoId}`),
    updateProjectConfig: (repoId: string, config: object) =>     
      fetch(`/api/config/${repoId}`, { method: 'PUT', body:      
  JSON.stringify(config) }),

    // SSE 实时更新
    subscribeReviewUpdates: (callback: (update: ReviewUpdate) => 
  void) => {
      const es = new EventSource('/api/sse/reviews');
      es.onmessage = (e) => callback(JSON.parse(e.data));        
      return () => es.close();
    }
  };

  3.2 Dashboard 页面增强设计

  Reviews 列表页 (/dashboard/reviews)

  ┌──────────────────────────────────────────────────────────────
  ───────┐
  │  [Filter: Status ▼]  [Filter: Repo ▼]  [Filter: Risk ▼]      
  [Search]  │
  ├──────────────────────────────────────────────────────────────
  ───────┤
  │
         │
  │
  ┌─────────────────────────────────────────────────────────────┐
     │
  │  │ ● pending   #42  feat: add user auth    org/repo    2m ago
    │   │
  │  │            "Add OAuth2 integration"      DeepSeek
    │   │
  │
  └─────────────────────────────────────────────────────────────┘
     │
  │
         │
  │
  ┌─────────────────────────────────────────────────────────────┐
     │
  │  │ ● completed #41  fix: memory leak       org/repo    1h ago
    │   │
  │  │            "Fix connection pool exhaustion"  [critical]   
    │   │
  │  │             Claude-3.5  3 findings
    │   │
  │
  └─────────────────────────────────────────────────────────────┘
     │
  │
         │
  └──────────────────────────────────────────────────────────────
  ───────┘

  关键设计决策：
  1. 卡片列表替代表格 - 更符合玻璃拟态风格，信息密度适中
  2. 状态圆点颜色：
    - pending → 琥珀脉冲动画（表示处理中）
    - running → 蓝色旋转指示器
    - completed → 抹茶绿
    - failed → 深红
    - skipped → 灰色
  3. 风险等级徽章 - 仅在 completed 且非 low 时显示

  Review 详情页 (/dashboard/reviews/[id])

  三栏布局调整为：

  ┌──────────┬──────────────────────────────┬────────────────────
  ──┐
  │  文件树   │         Diff 视图             │    Finding       
  列表面板   │
  │          │                              │
    │
  │ ▼ src/   │  @@ -45,7 +45,7 @@          │ ┌─────────────────┐ 
   │
  │   auth/  │  - const timeout = 5000;     │ │ ⚠️ Warning       
  │  │
  │   ▶ api.ts│  + const timeout = 30000;   │ │ Line 47         │
    │
  │     [3]  │                              │ │ High confidence │
    │
  │ ▼ utils/ │  [高亮显示变更]               │
  └─────────────────┘  │
  │   db.ts  │                              │ ┌─────────────────┐
    │
  │     [1]  │  点击行号可关联 finding      │ │ 🔴 Critical      
  │  │
  │          │                              │ │ Line 52         │
    │
  │          │                              │ │ [展开详情...]   │
    │
  │          │                              │ └─────────────────┘
    │
  └──────────┴──────────────────────────────┴────────────────────
  ──┘

  新增交互：
  - 文件树显示每个文件的 finding 数量徽章
  - Diff 行号与 Finding 关联（点击行号高亮对应 finding）
  - Finding 卡片展开后显示：
    - AI 生成的描述和建议
    - Confidence 进度条（金色渐变）
    - "Mark as False Positive" 按钮
    - 应用的 AI Model 标签

  3.3 新增页面：Prompt Management

  根据后端 PromptRegistry 和 PromptExperiment 模型：

  /dashboard/prompts

  ┌──────────────────────────────────────────────────────────────
  ───┐
  │  Prompt Registry                                    [+ New]  
     │
  ├──────────────────────────────────────────────────────────────
  ───┤
  │
     │
  │  ┌─────────────────────────────────────────────────────────┐ 
    │
  │  │ v1.2.0-system  (active)                    [Edit] [Test] │
     │
  │  │ 使用于: 3 个仓库  |  准确率: 94.2%
  │   │
  │  │ A/B 测试: 50% / 50% (vs v1.1.9)                          │
     │
  │  └─────────────────────────────────────────────────────────┘ 
    │
  │
     │
  │  ┌─────────────────────────────────────────────────────────┐ 
    │
  │  │ v1.1.9-system  (baseline)                  [Edit] [Test] │
     │
  │  │ 使用于: 5 个仓库  |  准确率: 91.8%
  │   │
  │  └─────────────────────────────────────────────────────────┘ 
    │
  │
     │
  └──────────────────────────────────────────────────────────────
  ───┘

  3.4 组件增强

  GlassCard 新增变体：

  // components/ui/glass-card.tsx
  interface GlassCardProps {
    variant?: "default" | "interactive" | "elevated" | "status"; 
    status?: "pending" | "running" | "completed" | "failed";     
    // ... existing props
  }

  // 状态卡片带有左侧彩色边条
  // pending = 琥珀色脉冲
  // running = 蓝色渐变流动
  // completed = 抹茶绿
  // failed = 深红

  新增 DiffViewer 组件：

  // components/dashboard/diff-viewer.tsx
  interface DiffViewerProps {
    files: PRFile[];
    findings: ReviewFinding[];
    onLineClick?: (lineNum: number, filePath: string) => void;   
  }

  // 使用 Shiki 语法高亮，配色适配 Latte 主题
  // 新增行：深绿背景 (#7D8471/10%)
  // 删除行：深红背景 (#8B3A3A/10%)
  // Finding 标注：右侧金色竖线 + 悬浮提示

  新增 RealtimeIndicator 组件：

  // components/dashboard/realtime-indicator.tsx
  // SSE 连接状态指示器，显示在 Header
  // 连接中 → 琥珀点脉冲
  // 已连接 → 抹茶绿点
  // 断开 → 深红点

  3.5 主题配色微调建议

  根据后端 severity 等级，优化功能色：

  /* latte-theme.css 补充 */
  --latte-severity-info: #9A8B7A;      /* 信息 - 拿铁褐 */       
  --latte-severity-warning: #B85C38;    /* 警告 - 肉桂橙 */      
  --latte-severity-critical: #8B3A3A;   /* 严重 - 深红砖 */      

  /* 新增 GitHub/GitLab 品牌色（用于平台标识） */
  --latte-github: #F5E6D3;
  --latte-gitlab: #E8C4A0;

  /* 新增 Confidence 渐变色 */
  --latte-confidence-low: #8B7D6D;      /* < 70% */
  --latte-confidence-med: #C4A77D;      /* 70-90% */
  --latte-confidence-high: #7D8471;     /* > 90% */

  3.6 动效与微交互增强

  Review 状态流转动画：
    - pending → running: 卡片左侧出现蓝色流动光效
    - running → completed: 绿色光效从左侧扫过，数字计数器动画    
    - 任何 → failed: 红色抖动 + 错误图标浮现
  Finding Confidence 可视化：
  // 金色圆弧进度条，类似 Apple Watch 圆环
  <ConfidenceRing value={0.92} size={40} />
  代码审查热图：
    - 在文件树中，有 finding 的文件名右侧显示小圆点
    - 颜色表示最高 severity

  ---
  四、文件结构补充

  frontend/
  ├── app/
  │   ├── dashboard/
  │   │   ├── reviews/
  │   │   │   └── [id]/
  │   │   │       ├── page.tsx           # Review 详情
  │   │   │       └── components/
  │   │   │           ├── diff-viewer.tsx
  │   │   │           ├── finding-panel.tsx
  │   │   │           └── file-tree.tsx
  │   │   ├── metrics/
  │   │   │   └── page.tsx               # 指标统计
  │   │   ├── config/
  │   │   │   └── page.tsx               # 项目配置
  │   │   └── prompts/
  │   │       └── page.tsx               # Prompt 管理（新增）   
  │   └── api/                           # Next.js API Routes    
  │       ├── reviews/
  │       ├── findings/
  │       └── sse/
  ├── components/
  │   ├── ui/
  │   │   ├── confidence-ring.tsx        # 置信度圆环（新增）    
  │   │   ├── status-badge.tsx           # 状态徽章（新增）      
  │   │   └── realtime-indicator.tsx     # 实时连接指示（新增）  
  │   └── dashboard/
  │       └── diff-viewer.tsx            # Diff 查看器（新增）   
  ├── hooks/
  │   ├── use-review.ts                  # SWR 获取 review       
  │   ├── use-sse.ts                     # SSE 订阅 hook（新增） 
  │   └── use-metrics.ts                 # 指标数据 hook（新增） 
  └── lib/
      ├── api.ts                         # API 客户端（新增）    
      └── theme.ts                       # 主题工具

  ---
  五、实施优先级建议

  ┌────────┬───────────────────────────┬────────────────────┐    
  │ 优先级 │           任务            │        原因        │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P0     │ Reviews 列表页 + API 连接 │ 核心功能，数据驱动 │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P0     │ Review 详情页（三栏布局） │ 核心价值展示       │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P1     │ SSE 实时更新              │ 提升用户体验       │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P1     │ Metrics 图表页            │ 数据可视化需求     │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P2     │ Prompt Management         │ 高级功能           │    
  ├────────┼───────────────────────────┼────────────────────┤    
  │ P2     │ 动画/微交互完善           │ 体验优化           │    
  └────────┴───────────────────────────┴────────────────────┘    

  ---