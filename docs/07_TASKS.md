# 07_TASKS — V0.1 任务清单

规则：一次只执行一个 Task；每个 Task 建议单独分支/commit。

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
| TASK-037 | 导出 manifest.json | 包含场景、Prompt、Seed、workflow、文件名。 | JSON 可读且信息完整。 |
| TASK-038 | 前端导出面板 | 右侧操作区增加导出。 | 可触发并显示导出路径。 |
| TASK-039 | 错误统一与 Toast | 统一 API error 结构。 | ComfyUI 离线/OOM 能显示清楚。 |
| TASK-040 | 核心集成测试 | 覆盖 Project→Scene→Generate→Output→Export。 | 核心链路测试通过。 |

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
