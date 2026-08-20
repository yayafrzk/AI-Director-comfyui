# AGENTS.md — AI Director 项目开发宪法

本文件对所有 AI Coding Agent 生效。

---

## 1. 项目定位

AI Director 是一个面向本地 AI 视频生产的导演台。

目标链路：

创意 → 项目 → 分镜 → Prompt/参考图 → ComfyUI → 生成任务 → 多版本 → 选择结果 → 导出剪映素材。

项目 **不是剪映替代品**。

---

## 2. 固定技术栈

未经明确批准，禁止更换：

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Zustand
- TanStack Query

### Backend
- Python 3.11
- FastAPI
- SQLAlchemy
- Pydantic
- SQLite
- WebSocket

### Media
- FFmpeg

---

## 3. 开发原则

### 3.1 最小修改原则
只修改完成当前任务所必需的文件。

### 3.2 禁止顺便优化
如果任务未要求，不得：
- 大范围重构
- 更换状态管理
- 更换 UI 框架
- 修改目录结构
- 修改数据库结构
- 升级依赖
- 删除接口
- 修改已有正常功能
- 修改 ComfyUI workflow
- 改变 API 返回格式

### 3.3 先理解再编码
开始任务前必须：
1. 阅读相关文档
2. 阅读现有实现
3. 确认影响范围
4. 给出简短实现计划
5. 再开始修改

---

## 4. 目录约束

```text
ai-director/
├─ apps/
│  ├─ web/
│  └─ api/
├─ data/
├─ projects/
├─ workflows/
├─ docs/
├─ prompts/
├─ tests/
├─ AGENTS.md
└─ README.md
```

禁止随意新建根目录。

---

## 5. Backend 分层

```text
apps/api/app/
├─ api/         # 路由
├─ models/      # SQLAlchemy ORM
├─ schemas/     # Pydantic
├─ services/    # 业务逻辑
├─ repositories/# 数据访问，可在需要时引入
├─ core/        # 配置、日志、异常
└─ main.py
```

规则：
- Route 不写复杂业务逻辑
- ComfyUI 调用放 `services/comfyui_*`
- 文件系统逻辑放 `services/storage_*`
- 数据库模型不要在任务外修改

---

## 6. Frontend 分层

```text
apps/web/src/
├─ components/
├─ features/
├─ pages/
├─ services/
├─ stores/
├─ hooks/
├─ types/
└─ utils/
```

规则：
- 页面组件不得直接写 fetch
- API 调用统一在 services
- 共享状态仅在确有必要时进入 Zustand
- 服务端状态优先 TanStack Query

---

## 7. API 规范

统一前缀：

`/api/v1`

成功：

```json
{
  "data": {},
  "error": null
}
```

失败：

```json
{
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project not found"
  }
}
```

禁止：
- 同一类接口返回不同结构
- 将 Python traceback 直接返回前端

---

## 8. 数据库规范

- 主键：UUID 字符串
- 所有时间存 UTC
- 创建时间：`created_at`
- 更新时间：`updated_at`
- 删除优先软删除仅在业务确有必要时使用
- 不随意增加 JSON 大字段
- 文件本体不进数据库，只保存路径和元数据

数据库结构变更必须单独任务处理。

---

## 9. 文件路径规范

数据库保存“项目相对路径”，不要保存写死的 Windows 盘符。

推荐：

```text
projects/<project_id>/
├─ source/
├─ images/
├─ videos/
├─ audio/
├─ thumbnails/
├─ exports/
└─ metadata/
```

必须测试：
- 中文路径
- 空格路径
- 文件不存在
- 无权限
- 磁盘空间不足时的错误处理

---

## 10. ComfyUI 规范

禁止把某个模型写死进业务代码。

使用：

**WorkflowTemplate + 参数映射 + Prompt JSON**

所有模板必须可配置。

ComfyUI 连接信息通过配置：

```text
COMFYUI_BASE_URL=http://127.0.0.1:8188
```

生成流程必须支持：
- 健康检查
- 提交
- 队列
- 状态
- history
- WebSocket 进度
- 取消
- 失败
- 结果文件归档

---

## 11. Workflow 规范

`workflows/` 存放模板和参数描述。

每个模板至少包含：

```text
template.json
manifest.json
```

manifest 示例：

```json
{
  "id": "minimax-h3-i2v",
  "name": "MiniMax H3 I2V",
  "version": "1.0.0",
  "inputs": {
    "prompt": {"node_id": "12", "field": "text"},
    "seed": {"node_id": "41", "field": "noise_seed"},
    "image": {"node_id": "7", "field": "image"}
  }
}
```

禁止在服务代码中通过猜节点名修改 workflow。

---

## 12. 生成任务规范

状态固定：

```text
pending
queued
running
completed
failed
cancelled
```

任何生成任务必须记录：
- scene_id
- workflow_template_id
- workflow_version
- prompt
- negative_prompt
- seed
- 参数快照
- ComfyUI prompt_id
- 状态
- 开始时间
- 完成时间
- 错误信息

---

## 13. 日志规范

至少：
- `logs/app.log`
- `logs/comfyui.log`
- `logs/generation.log`

禁止打印敏感信息。

错误日志必须包含：
- job_id
- project_id（如有）
- scene_id（如有）
- comfyui prompt_id（如有）

---

## 14. 测试规范

每个核心模块至少覆盖：

### Project
- create
- list
- get
- update
- delete

### Scene
- create
- reorder
- update
- delete
- 自动 scene_number

### Generation
- ComfyUI 离线
- 提交成功
- 提交失败
- 任务完成
- 任务失败
- 取消
- 重试

### Storage
- 中文路径
- 文件不存在
- 重名
- 不支持格式

---

## 15. Git 规范

分支：

```text
main
dev
feature/<task-name>
fix/<bug-name>
```

Commit 建议：

```text
feat(scene): add scene create api
fix(comfyui): handle websocket disconnect
test(project): add project api tests
docs: update api spec
```

每个 Task 尽量一个独立 commit。

---

## 16. 每个任务的执行模板

开始时输出：

```text
理解：
影响文件：
实现计划：
风险：
```

完成时输出：

```text
已完成：
修改文件：
测试：
git diff 摘要：
仍存在的问题：
```

---

## 17. 禁止事项

除非用户明确要求：

- 不做剪辑时间线引擎
- 不训练模型
- 不接支付
- 不接会员
- 不做多租户
- 不上 Kubernetes
- 不上微服务
- 不引入 Redis
- 不引入 PostgreSQL
- 不做云 GPU 调度
- 不写自动更新器
- 不做模型下载器
