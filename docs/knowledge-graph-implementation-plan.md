# Latte PR Agent — 代码实体级知识图谱 + GraphRAG + 语义搜索 实现方案

## 概述

本方案详细说明如何在 Latte PR Agent 中实现三个高级功能：
1. **代码实体级知识图谱** — 函数/类/变量级别的调用、继承、依赖关系图谱
2. **GraphRAG** — 基于知识图谱的检索增强生成，替代纯向量 RAG
3. **语义代码搜索** — 自然语言查询代码功能

---

## 一、代码实体级知识图谱

### 1.1 目标

将当前"文件级依赖图"升级为"实体级知识图谱"：
- 节点：模块、类、函数、变量
- 边：contains（包含）、calls（调用）、inherits（继承）、imports（导入）、decorates（装饰）
- 可视化：支持按类型过滤、按模块分组、路径高亮

### 1.2 数据库设计

```sql
-- 代码实体表
CREATE TABLE code_entities (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES project_repos(id) ON DELETE CASCADE,
    entity_type VARCHAR(20) NOT NULL CHECK (entity_type IN ('module', 'class', 'function', 'variable', 'interface', 'enum')),
    name VARCHAR(200) NOT NULL,
    qualified_name VARCHAR(500),  -- 如 "src.services.user_service.UserService.create_user"
    file_path VARCHAR(500) NOT NULL,
    start_line INT,
    end_line INT,
    signature TEXT,  -- 函数签名或类定义
    docstring TEXT,  -- 文档字符串（用于语义搜索）
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, qualified_name)
);
CREATE INDEX idx_code_entities_project ON code_entities(project_id);
CREATE INDEX idx_code_entities_type ON code_entities(entity_type);
CREATE INDEX idx_code_entities_file ON code_entities(file_path);

-- 代码关系表
CREATE TABLE code_relationships (
    id SERIAL PRIMARY KEY,
    project_id INT NOT NULL REFERENCES project_repos(id) ON DELETE CASCADE,
    source_id INT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
    target_id INT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
    rel_type VARCHAR(20) NOT NULL CHECK (rel_type IN ('contains', 'calls', 'inherits', 'implements', 'imports', 'decorates', 'references')),
    line_number INT,  -- 关系发生的代码行
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, source_id, target_id, rel_type)
);
CREATE INDEX idx_code_rels_project ON code_relationships(project_id);
CREATE INDEX idx_code_rels_source ON code_relationships(source_id);
CREATE INDEX idx_code_rels_target ON code_relationships(target_id);
CREATE INDEX idx_code_rels_type ON code_relationships(rel_type);

-- 代码实体向量表（用于语义搜索）
CREATE TABLE code_entity_embeddings (
    id SERIAL PRIMARY KEY,
    entity_id INT NOT NULL REFERENCES code_entities(id) ON DELETE CASCADE,
    embedding VECTOR(1536),  -- DeepSeek text-embedding-v3 维度
    content_hash VARCHAR(64),  -- 用于检测变更
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_id)
);
CREATE INDEX idx_code_entity_embeddings_vector ON code_entity_embeddings USING ivfflat (embedding vector_cosine_ops);
```

### 1.3 AST 提取增强

基于现有 `code_ast/extractors.py` 扩展：

#### 新增 `CallExtractor`（函数调用提取）

**Python 示例**：
```python
def _extract_python_calls(node: Node, current_func: str | None) -> List[CallInfo]:
    """提取函数调用关系。"""
    calls = []
    for call_node in _walk(node, "call"):
        func_node = _find_child(call_node, "identifier") or _find_child(call_node, "attribute")
        if func_node:
            callee = _node_text(func_node)
            calls.append(CallInfo(
                caller=current_func,
                callee=callee,
                line_number=call_node.start_point[0] + 1,
            ))
    return calls
```

**TypeScript/JavaScript 示例**：
```python
def _extract_ts_calls(node: Node, current_func: str | None) -> List[CallInfo]:
    """提取 JS/TS 函数调用。"""
    calls = []
    for call_expr in _walk(node, "call_expression"):
        func_node = call_expr.children[0] if call_expr.children else None
        if func_node:
            callee = _node_text(func_node)
            calls.append(CallInfo(
                caller=current_func,
                callee=callee,
                line_number=call_expr.start_point[0] + 1,
            ))
    return calls
```

#### 新增 `InheritanceExtractor`（继承关系提取）

**Python**：
```python
def _extract_python_inheritance(node: Node) -> List[InheritanceInfo]:
    """提取类继承关系。"""
    inheritances = []
    for class_node in _walk(node, "class_definition"):
        class_name = _node_text(_find_child(class_node, "identifier"))
        arg_list = _find_child(class_node, "argument_list")
        if arg_list:
            for base in _find_children(arg_list, "identifier"):
                inheritances.append(InheritanceInfo(
                    child_class=class_name,
                    parent_class=_node_text(base),
                    line_number=class_node.start_point[0] + 1,
                ))
    return inheritances
```

#### 新增 `DecoratorExtractor`（装饰器/注解提取）

用于识别 API 路由、中间件、测试标记等：
```python
@dataclass
class DecoratorInfo:
    target_name: str
    decorator_name: str
    args: List[str]
    line_number: int

def _extract_python_decorators(node: Node) -> List[DecoratorInfo]:
    """提取装饰器信息。"""
    decorators = []
    for decorated in _walk(node, "decorated_definition"):
        def_node = decorated.children[-1] if decorated.children else None
        target_name = ""
        if def_node and def_node.type in ("function_definition", "class_definition"):
            target_name = _node_text(_find_child(def_node, "identifier"))
        
        for child in decorated.children:
            if child.type == "decorator":
                decorator_name = _node_text(child).lstrip("@").split("(")[0]
                decorators.append(DecoratorInfo(
                    target_name=target_name,
                    decorator_name=decorator_name,
                    args=[],
                    line_number=child.start_point[0] + 1,
                ))
    return decorators
```

### 1.4 知识图谱构建服务

新建 `src/knowledge_graph/builder.py`：

```python
class KnowledgeGraphBuilder:
    """基于 AST 构建代码实体级知识图谱。"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.entity_cache: Dict[str, int] = {}  # qualified_name -> entity_id
    
    async def build(self, project_id: int, repo_path: str, force: bool = False) -> None:
        """扫描项目代码，构建完整知识图谱。"""
        if not force:
            existing = await self._check_existing(project_id)
            if existing:
                return
        
        await self._clear_existing(project_id)
        
        for file_path in self._iter_code_files(repo_path):
            await self._process_file(project_id, repo_path, file_path)
        
        await self._resolve_calls(project_id)  # 将函数名解析为 entity_id
    
    async def _process_file(self, project_id: int, repo_path: str, file_path: Path) -> None:
        """处理单个文件，提取所有实体和关系。"""
        lang = EXTENSION_TO_LANG.get(file_path.suffix)
        if not lang:
            return
        
        source = file_path.read_bytes()
        tree = TreeSitterParser(lang).parse(source)
        if not tree:
            return
        
        rel_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
        
        # 1. 提取模块实体（文件本身）
        module_id = await self._create_entity(
            project_id, "module", rel_path, rel_path, rel_path, 0, 0
        )
        
        # 2. 提取类实体
        classes = ClassExtractor(lang).extract(tree.root_node)
        for cls in classes:
            entity_id = await self._create_entity(
                project_id, "class", cls.name, f"{rel_path}::{cls.name}",
                rel_path, cls.start_line, cls.end_line,
                signature=f"class {cls.name}({', '.join(cls.bases)})" if cls.bases else f"class {cls.name}"
            )
            await self._create_rel(project_id, module_id, entity_id, "contains")
        
        # 3. 提取函数实体
        functions = FunctionExtractor(lang).extract(tree.root_node)
        for func in functions:
            parent_id = module_id
            # 判断函数所属类
            for cls in classes:
                if cls.start_line <= func.start_line <= cls.end_line:
                    parent_id = self.entity_cache.get(f"{rel_path}::{cls.name}")
                    break
            
            entity_id = await self._create_entity(
                project_id, "function", func.name, f"{rel_path}::{func.name}",
                rel_path, func.start_line, func.end_line,
                signature=func.signature
            )
            await self._create_rel(project_id, parent_id, entity_id, "contains")
            
            # 4. 提取函数内的调用关系
            calls = CallExtractor(lang).extract(tree.root_node, func.name)
            for call in calls:
                await self._create_call_rel(project_id, entity_id, call.callee, call.line_number)
        
        # 5. 提取继承关系
        inheritances = InheritanceExtractor(lang).extract(tree.root_node)
        for inh in inheritances:
            child_id = self.entity_cache.get(f"{rel_path}::{inh.child_class}")
            parent_id = self.entity_cache.get(f"{rel_path}::{inh.parent_class}")
            if child_id and parent_id:
                await self._create_rel(project_id, child_id, parent_id, "inherits")
```

### 1.5 前端可视化增强

基于已有的 `KnowledgeGraphPanel`，增强实体级可视化：

```typescript
interface EntityNode {
  id: string;
  name: string;
  type: "module" | "class" | "function" | "variable";
  filePath: string;
  signature?: string;
  group: string;  // 所属模块
}

interface EntityEdge {
  source: string;
  target: string;
  type: "contains" | "calls" | "inherits" | "imports";
}
```

**新增交互**：
- 节点类型过滤：只显示 class / function / 全部
- 关系类型过滤：只显示 calls / inherits / 全部
- 点击节点：显示代码签名、文档字符串、跳转到文件
- 双击节点：展开/折叠子节点（模块 → 类 → 函数）
- 搜索框：按名称搜索实体并高亮
- 路径高亮：选中两个节点，高亮它们之间的最短路径

---

## 二、GraphRAG（图检索增强生成）

### 2.1 核心思想

传统 RAG 的问题是：
- 向量相似度检索可能返回语义相关但逻辑无关的代码
- 无法理解"调用链"、"继承链"等多跳关系

GraphRAG 的优势：
- 检索时沿着图的边遍历，找到真正相关的代码
- 可以回答"修改函数 A 会影响哪些下游调用方"
- 可以理解"类 B 的所有子类实现"

### 2.2 GraphRAG 检索器

新建 `src/knowledge_graph/graph_rag.py`：

```python
class GraphRAGRetriever:
    """基于知识图谱的检索增强生成器。"""
    
    def __init__(self, session: AsyncSession, embedder: EmbeddingClient):
        self.session = session
        self.embedder = embedder
    
    async def retrieve(
        self,
        project_id: int,
        query: str,
        changed_files: List[str],
        depth: int = 2,
        top_k: int = 10,
    ) -> List[Dict]:
        """检索与查询和变更文件相关的代码上下文。
        
        策略：
        1. 向量检索：找到语义相关的代码实体
        2. 图扩展：从相关实体出发，沿边遍历 depth 层
        3. 变更感知：优先返回变更文件直接影响的路径
        """
        # Step 1: 向量检索获取种子实体
        query_embedding = await self.embedder.embed(query)
        seed_entities = await self._vector_search(project_id, query_embedding, top_k=5)
        
        # Step 2: 从变更文件获取种子实体
        changed_entities = await self._get_changed_entities(project_id, changed_files)
        
        # Step 3: 图遍历扩展
        all_seeds = seed_entities + changed_entities
        expanded = await self._graph_expand(project_id, all_seeds, depth=depth)
        
        # Step 4: 去重和排序（按与查询的相似度 + 与变更的距离）
        results = self._rank_results(expanded, query_embedding, changed_entities)
        return results[:top_k]
    
    async def _graph_expand(
        self,
        project_id: int,
        seed_ids: List[int],
        depth: int = 2,
    ) -> List[Dict]:
        """从种子实体出发，沿图边遍历。"""
        sql = text("""
            WITH RECURSIVE graph_search AS (
                -- 初始种子
                SELECT 
                    ce.id as entity_id,
                    ce.qualified_name,
                    ce.entity_type,
                    ce.signature,
                    ce.file_path,
                    0 as depth,
                    ARRAY[ce.id] as path
                FROM code_entities ce
                WHERE ce.id = ANY(:seed_ids)
                  AND ce.project_id = :project_id
                
                UNION
                
                -- 递归扩展：沿关系边遍历
                SELECT 
                    ce.id as entity_id,
                    ce.qualified_name,
                    ce.entity_type,
                    ce.signature,
                    ce.file_path,
                    gs.depth + 1,
                    gs.path || ce.id
                FROM graph_search gs
                JOIN code_relationships cr ON 
                    (cr.source_id = gs.entity_id OR cr.target_id = gs.entity_id)
                JOIN code_entities ce ON 
                    (ce.id = cr.target_id AND cr.source_id = gs.entity_id)
                    OR (ce.id = cr.source_id AND cr.target_id = gs.entity_id)
                WHERE gs.depth < :max_depth
                  AND ce.project_id = :project_id
                  AND NOT ce.id = ANY(gs.path)  -- 避免环路
            )
            SELECT DISTINCT ON (entity_id)
                entity_id, qualified_name, entity_type, signature, file_path, depth
            FROM graph_search
            ORDER BY entity_id, depth
        """)
        result = await self.session.execute(sql, {
            "seed_ids": seed_ids,
            "project_id": project_id,
            "max_depth": depth,
        })
        return [dict(row) for row in result.mappings()]
```

### 2.3 与审查流程的集成

在 `ReviewEngine` 和 `_do_analyze_commit` 中使用 GraphRAG：

```python
# 在 _do_analyze_commit 中
graph_rag = GraphRAGRetriever(session, embedder)
context = await graph_rag.retrieve(
    project_id=project_id,
    query=f"分析 commit {commit_hash} 的代码变更",
    changed_files=changed_files,  # 本次变更的文件列表
    depth=2,
    top_k=8,
)

# 将上下文融入 Prompt
context_str = "\n".join(
    f"- [{c['entity_type']}] {c['qualified_name']}: {c['signature']}"
    for c in context
)

system_prompt += f"\n\n【相关代码上下文（GraphRAG 检索）】\n{context_str}"
```

---

## 三、语义代码搜索

### 3.1 核心思想

用户输入自然语言查询（如"用户认证的代码在哪里"），系统返回最相关的代码实体。

结合两种技术：
1. **向量相似度**：代码实体文档字符串/签名的嵌入向量
2. **图结构**：返回的实体在知识图谱中的连接关系

### 3.2 实现

新建 `src/knowledge_graph/semantic_search.py`：

```python
class SemanticCodeSearch:
    """自然语言语义代码搜索。"""
    
    def __init__(self, session: AsyncSession, embedder: EmbeddingClient):
        self.session = session
        self.embedder = embedder
    
    async def search(
        self,
        project_id: int,
        query: str,
        entity_type: Optional[str] = None,  # "function" | "class" | None
        top_k: int = 10,
    ) -> List[SearchResult]:
        """语义搜索代码实体。"""
        query_embedding = await self.embedder.embed(query)
        
        # 向量检索
        sql = text("""
            SELECT 
                ce.id,
                ce.qualified_name,
                ce.entity_type,
                ce.name,
                ce.file_path,
                ce.start_line,
                ce.signature,
                ce.docstring,
                1 - (cee.embedding <=> :query_embedding) as similarity
            FROM code_entities ce
            JOIN code_entity_embeddings cee ON ce.id = cee.entity_id
            WHERE ce.project_id = :project_id
              AND (:entity_type IS NULL OR ce.entity_type = :entity_type)
            ORDER BY cee.embedding <=> :query_embedding
            LIMIT :top_k
        """)
        result = await self.session.execute(sql, {
            "query_embedding": str(query_embedding),  # pgvector 格式
            "project_id": project_id,
            "entity_type": entity_type,
            "top_k": top_k,
        })
        
        rows = [dict(r) for r in result.mappings()]
        
        # 增强：对每个结果补充图邻居信息
        for row in rows:
            row["neighbors"] = await self._get_neighbors(project_id, row["id"], limit=3)
        
        return rows
    
    async def _get_neighbors(self, project_id: int, entity_id: int, limit: int = 3) -> List[Dict]:
        """获取实体的直接邻居（用于展示关联代码）。"""
        sql = text("""
            SELECT 
                ce.qualified_name,
                ce.entity_type,
                ce.name,
                cr.rel_type
            FROM code_relationships cr
            JOIN code_entities ce ON 
                (ce.id = cr.target_id AND cr.source_id = :entity_id)
                OR (ce.id = cr.source_id AND cr.target_id = :entity_id)
            WHERE cr.project_id = :project_id
            LIMIT :limit
        """)
        result = await self.session.execute(sql, {
            "entity_id": entity_id,
            "project_id": project_id,
            "limit": limit,
        })
        return [dict(r) for r in result.mappings()]
```

### 3.3 前端搜索界面

在项目详情页新增「代码搜索」Tab：

```tsx
function CodeSearchPanel({ projectId }: { projectId: number }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    setLoading(true);
    const res = await api.semanticCodeSearch(projectId, query);
    setResults(res.results);
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索代码，如：用户认证、数据库连接、API 路由..."
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Button onClick={handleSearch} loading={loading}>搜索</Button>
      </div>
      {results.map((r) => (
        <SearchResultCard key={r.id} result={r} />
      ))}
    </div>
  );
}
```

### 3.4 搜索示例

| 查询 | 返回结果 |
|------|----------|
| "用户登录验证" | `auth_service.authenticate()`、`login_handler()`、`JWTValidator` |
| "数据库事务处理" | `db_session.begin()`、`TransactionManager.commit()` |
| "发送邮件" | `EmailService.send()`、`notify_user()` |
| "Redis 缓存" | `cache.get()`、`CacheMiddleware` |

---

## 四、增量更新策略

知识图谱构建成本较高，需要支持增量更新：

```python
async def incremental_update(self, project_id: int, changed_files: List[str]) -> None:
    """仅更新变更文件相关的实体和关系。"""
    for file_path in changed_files:
        # 1. 删除该文件的旧实体和关系
        await self._delete_file_entities(project_id, file_path)
        # 2. 重新解析该文件
        await self._process_file(project_id, repo_path, Path(file_path))
    # 3. 重新解析全局调用关系（因为函数名可能跨文件引用）
    await self._resolve_calls(project_id)
```

**触发时机**：
- 项目同步（Sync）完成后
- Commit Analysis 发现新 commit 时
- 用户手动点击"重建知识图谱"按钮

---

## 五、前端架构

### 5.1 新增页面/组件

```
frontend/src/components/dashboard/
├── knowledge-graph-panel.tsx      # 已有，需增强实体级渲染
├── architecture-diagram-panel.tsx # 已有
├── code-search-panel.tsx          # 新增：语义搜索
└── entity-detail-card.tsx         # 新增：实体详情卡片

frontend/src/app/dashboard/projects/[id]/
└── page.tsx  # 新增 tabs: knowledge-graph, architecture, code-search
```

### 5.2 API 端点

```
GET  /projects/{id}/knowledge-graph      # 已有（文件级），扩展为实体级
GET  /projects/{id}/architecture         # 已有
POST /projects/{id}/knowledge-graph/build # 新增：触发知识图谱构建
GET  /projects/{id}/code-search?q=...    # 新增：语义搜索
GET  /projects/{id}/entities/{entity_id}  # 新增：实体详情
GET  /projects/{id}/entities/{id}/neighbors # 新增：邻居查询
```

---

## 六、实施路线图

### Phase 1：代码实体级知识图谱（5-6 天）

| 天数 | 任务 |
|------|------|
| Day 1 | 数据库迁移：`code_entities`, `code_relationships`, `code_entity_embeddings` |
| Day 2 | AST 提取器增强：`CallExtractor`, `InheritanceExtractor`, `DecoratorExtractor` |
| Day 3 | `KnowledgeGraphBuilder` 核心构建逻辑 |
| Day 4 | 后端 API：`build`, `entities`, `neighbors` |
| Day 5 | 前端：`KnowledgeGraphPanel` 实体级渲染增强 |
| Day 6 | 联调测试 |

### Phase 2：GraphRAG（3-4 天）

| 天数 | 任务 |
|------|------|
| Day 1 | `GraphRAGRetriever` 核心检索逻辑 |
| Day 2 | 与 `ReviewEngine` / `_do_analyze_commit` 集成 |
| Day 3 | 测试：验证 GraphRAG 比纯向量 RAG 更准确 |
| Day 4 | 优化：调整 depth 和 top_k 参数 |

### Phase 3：语义代码搜索（2-3 天）

| 天数 | 任务 |
|------|------|
| Day 1 | `SemanticCodeSearch` + 向量嵌入生成 |
| Day 2 | 前端 `CodeSearchPanel` |
| Day 3 | 联调测试 |

**总计：约 10-13 天**

---

## 七、技术风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Tree-sitter 解析大文件慢 | 构建时间长 | 跳过 >500KB 文件；异步批处理 |
| 函数名解析歧义 | 调用关系错误 | 使用 qualified_name；未解析的调用标记为 unresolved |
| 向量嵌入成本高 | API 费用 | 增量更新；缓存嵌入结果 |
| 图数据量大 | 查询慢 | PostgreSQL 索引优化；必要时限制 depth |
| 多语言 AST 差异 | 提取器复杂 | 优先支持 Python/TS；其他语言逐步扩展 |

---

## 八、与现有功能的协同

| 现有功能 | 协同方式 |
|----------|----------|
| **Commit Analysis** | 分析时注入 GraphRAG 上下文（"该函数影响 12 个调用方"） |
| **PR Review** | ReviewEngine 使用 GraphRAG 评估变更影响范围 |
| **Prompt 进化** | Prompt 生成时参考知识图谱中的 API 模式 |
| **Dashboard 统计** | 新增"代码复杂度指标"（上帝类数量、循环依赖数） |
| **Bug RAG** | Bug 知识库与代码实体关联，实现"这个 Bug 涉及哪些函数" |

---

*文档生成时间：2026-04-24*  
*基于 Latte PR Agent 当前架构设计*
