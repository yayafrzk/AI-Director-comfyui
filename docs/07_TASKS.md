# 07_TASKS — V0.1 任务清单

规则：一次只执行一个 Task；每个 Task 建议单独分支/commit。

## 当前状态

`TASK-001 ~ TASK-040` 已完成。以下历史任务表保留其真实实现范围；TASK-039 与 TASK-040 已按实际交付修正。

| ID | 任务 | 范围 | 验收 |
|---|---|---|---|
| TASK-001 | 初始化 Git 仓库与目录结构 | 创建固定项目目录；不实现业务。 | 目录符合 AGENTS.md；Git 可正常工作。 |
| TASK-002 | 初始化 React + TypeScript + Vite | 建立 apps/web 并可启动。 | npm run dev 成功；无控制台致命错误。 |
| TASK-003 | 建立三栏主布局 | 左项目栏、中分镜区、右操作栏，仅静态。 | 布局在 1440p 下正常；可响应窗口缩放。 |
| TASK-004 | 初始化 FastAPI | 建立 apps/api 与 GET /api/v1/health。 | uvicorn 可启动；/docs 可访问。 |
| TASK-005 | 建立配置系统 | 支持 APP_DATA_DIR、COMFYUI_BASE_URL 等配置。 | 默认值可运行；环境变量可覆盖。 |
| TASK-006 | 建立日志系统 | app/comfyui/generation 三类 logger。 | 日志文件可写；错误含 timestamp。 |
| TASK-007 | 初始化 SQLite + SQLAlchemy | 建立 DB session/base。 | 启动可创建数据库。 |
| TASK-008 | 实现 Project 模型与 schema | 实现 Project ORM + Pydantic。 | 字段符合数据库文档。 |
| TASK-009 | 实现 Project CRUD API | list/create/get/update/delete。 | API 测试通过。 |
| TASK-010 | 实现 Project Sidebar | 前端接 Project API。 | 新建项目后左侧立即出现。 |
| TASK-011 | 实现 Scene 模型与 schema | 实现 Scene ORM。 | project_id + scene_number 约束正确。 |
| TASK-012 | 实现 Scene 创建 API | 自动 scene_number。 | 连续创建返回 1/2/3。 |
| TASK-013 | 实现 Scene CRUD API | list/get/update/delete。 | CRUD 测试通过。 |
| TASK-014 | 实现 Scene reorder API | 批量更新 scene_number。 | 拖拽序列能可靠保存。 |
| TASK-015 | 实现 Scene Card | 显示编号、标题、Prompt 摘要、状态。 | 列表正常渲染。 |
| TASK-016 | 实现分镜拖拽排序 | 前端拖拽并调用 reorder。 | 刷新后顺序保持。 |
| TASK-017 | 实现 Scene Detail Drawer | 编辑标题、描述、Prompt、Seed、时长。 | 保存后立即同步。 |
| TASK-018 | 实现 Asset 模型 | 建立素材 metadata。 | 字段符合文档。 |
| TASK-019 | 实现素材上传 API | 支持 image/video/audio/reference。 | 中文文件名可上传。 |
| TASK-020 | 实现素材文件访问 | content 与 thumbnail 接口。 | 前端可以预览。 |
| TASK-021 | 接入 FFmpeg metadata | 读取视频时长、分辨率。 | 视频上传后 metadata 正确。 |
| TASK-022 | 生成视频缩略图 | FFmpeg 抽帧。 | 视频卡片有缩略图。 |
| TASK-023 | 实现 WorkflowTemplate 模型 | 保存模板 metadata。 | 可导入模板记录。 |
| TASK-024 | 实现 Workflow manifest 加载器 | 读取 template.json + manifest.json。 | 错误映射可被识别。 |
| TASK-025 | 实现 Workflow 参数替换 | 按 node_id/field 修改 JSON。 | 单元测试验证不改其他节点。 |
| TASK-026 | 实现 ComfyUI health | GET /comfyui/health。 | 离线/在线状态正确。 |
| TASK-027 | 实现 ComfyUI submit | 提交 Prompt JSON 并获取 prompt_id。 | 测试使用 mock 或可控环境。 |
| TASK-028 | 实现 GenerationJob 模型 | 记录任务完整快照。 | 状态机字段正确。 |
| TASK-029 | 实现 Scene Generate API | 创建 Job + 提交 ComfyUI。 | 返回 job_id；DB 保存 prompt_id。 |
| TASK-030 | 实现 ComfyUI WebSocket 监听 | 接收执行进度/完成/错误。 | 断线不会导致 API 崩溃。 |
| TASK-031 | 实现前端生成状态 | 显示 queued/running/completed/failed。 | 状态可实时更新。 |
| TASK-032 | 实现生成结果归档 | 从 ComfyUI history 获取并归档 Asset。 | 结果进入项目目录而非只留在 ComfyUI/output。 |
| TASK-033 | 实现生成历史与多版本 | Scene 显示历史输出。 | 可查看至少 3 个版本。 |
| TASK-034 | 实现 Selected Version | 可把一个 Asset 设为最终版本。 | 刷新后 selected 状态保持。 |
| TASK-035 | 实现取消/失败重试 | cancel + retry。 | 重试产生新 Job，不覆盖旧记录。 |
| TASK-036 | 实现导出服务 | 按 scene_number 导出 selected 版本。 | 输出 01_xxx.mp4、02_xxx.mp4。 |
| TASK-037 | 导出 manifest.json | 为每次 project export 写入 schema_version、project/export metadata、Scene selected asset 与导出文件信息。 | manifest 与导出文件使用同一 scene 顺序和 filename；UTF-8 JSON；失败回滚当前 export。 |
| TASK-038 | 前端导出面板 | 右侧操作区增加导出。 | 可触发并显示导出路径。 |
| TASK-039 | Export Bundle Download API | 将既有 export directory 安全打包为临时 ZIP，并提供下载 API。 | ZIP 仅含顶层安全文件与 manifest；失败不影响历史 export。 |
| TASK-040 | Frontend Export ZIP Download | 在当前 export success UI 下载该次 export 的 ZIP。 | 使用 GET download endpoint；pending 防重复；错误保留 backend code。 |

## V0.1 Closure Phase

| ID | 任务 | 范围 | 验收 |
|---|---|---|---|
| TASK-041 | V0.1 Baseline / Docs Sync | 修正文档历史、记录当前基线并建立 Closure Plan。 | 文档反映 TASK-001 ~ TASK-040 的真实实现与 V0.1 验收链路。 |
| TASK-042 | Frontend Scene Create + Delete | 在 Project 内复用现有 Scene API 创建与删除 Scene。 | 空 Project 可新建 Scene；多个创建正常；删除后列表同步；刷新后状态保持。 |
| TASK-043 | Frontend Asset Import / Reference Management | 接入既有 Asset upload/content backend，覆盖 image、video、reference。 | 可选择并上传首帧、参考图、普通素材；图片/视频可预览；中文文件名正常。 |
| TASK-044 | WorkflowTemplate API: List + Register/Import | 为既有 WorkflowTemplate model、loader 与 builder 提供最小可用 API。 | 可 list templates、register/import local template、读取 template metadata。 |
| TASK-045 | Frontend Workflow Selection + Scene Binding | 在 Scene UI 选择 WorkflowTemplate 并保存 `workflow_template_id`。 | 选择并保存后刷新保持；从 Scene Card 点击生成使用所选 workflow。 |
| TASK-046 | TopBar Real Project + ComfyUI Health | TopBar 使用真实 Project name 与 `GET /api/v1/comfyui/health`。 | 显示在线、离线、检查中；删除静态 ComfyUI 占位文案。 |
| TASK-047 | Unified Frontend API Error UX | 统一前端 error type、常见 code mapping 与现有 inline error UI。 | 保留 backend `error.code`；覆盖 ComfyUI、workflow、generation、asset、export 与 cancel errors。 |
| TASK-048 | Core V0.1 Integration Test | 为 Project→Scene→GenerationJob→Archive→Selected Version→Export→Manifest→ZIP Download 建立稳定 backend 核心链路测试。 | 使用 mock / controllable ComfyUI transport；不依赖真实 GPU、公网或人工启动 ComfyUI。 |

## 推荐阶段

### Milestone A — Skeleton
TASK-001 ~ TASK-007

### Milestone B — Project & Scene
TASK-008 ~ TASK-017

### Milestone C — Assets
TASK-018 ~ TASK-022

### Milestone D — Workflow & ComfyUI
TASK-023 ~ TASK-032

### Milestone E — Version & Export
TASK-033 ~ TASK-040

## 第一阶段完成条件

只有当 TASK-001 ~ TASK-017 全部稳定后，才建议正式接 ComfyUI。

这样可以避免 UI、数据库和 ComfyUI 三条线同时出错。
