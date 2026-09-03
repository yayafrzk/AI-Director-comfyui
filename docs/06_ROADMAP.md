# 06_ROADMAP — 版本路线

## V0.1 — 可用导演台

目标：真正开始日常使用。

- 项目
- 分镜
- 素材
- Prompt
- Seed
- Workflow
- ComfyUI Bridge
- 单任务生成
- 队列状态
- WebSocket 进度
- 历史
- 多版本
- 选择最终版本
- 导出
- 日志

完成标准：
能完整制作一个 6 镜头短片并导出给剪映。

---

## V0.1 Closure Phase

V0.1 核心 backend、生成、归档、历史、多版本、Selected Version、导出、manifest 与 ZIP download 已完成。V0.1 尚未完成；以下 Closure tasks 完成并通过集成验收后才可标记为 complete：

- TASK-041 — V0.1 Baseline / Docs Sync
- TASK-042 — Frontend Scene Create + Delete
- TASK-043 — Frontend Asset Import / Reference Management
- TASK-044 — WorkflowTemplate API: List + Register/Import
- TASK-045 — Frontend Workflow Selection + Scene Binding
- TASK-046 — TopBar Real Project + ComfyUI Health
- TASK-047 — Unified Frontend API Error UX
- TASK-048 — Core V0.1 Integration Test

### V0.1 最终验收

用户必须能够从浏览器 UI 完整完成以下链路：

1. 创建 Project。
2. 创建至少 6 个 Scene。
3. 编辑 Scene title / prompt / seed / duration。
4. 导入首帧或参考素材。
5. 选择 Workflow。
6. 提交 ComfyUI 生成。
7. 查看 queued / running / completed / failed。
8. 查看生成历史与多个版本。
9. cancel / retry。
10. 选择最终版本。
11. 导出 Project。
12. 下载 ZIP。
13. 在 ZIP 中获得按 `scene_number` 排序的 selected assets 与 `manifest.json`。

只有以上链路可从 UI 完整走通，才可标记 **V0.1 Complete**。

---

## V0.2 — AI 视频生产增强

- Character Library
- 固定角色 Prompt
- 参考图集合
- Workflow 参数面板
- 批量生成
- 批量重试
- Workflow 版本管理
- 生成收藏/评分
- 项目模板

---

## V0.3 — AI Director

- 故事拆分
- 自动分镜
- 首帧 Prompt
- 视频 Prompt
- 镜头语言
- 场景连续性检查
- 角色一致性提示
- Prompt 补全
- 批量写入 Scene

---

## V0.4 — 音频与预览

- TTS
- 音频导入
- BGM
- SRT
- 简易顺序播放
- 总时长预览

仍不做：
剪映级时间线。

---

## V0.5 — 剪映工作流增强

- 导出视频序列
- SRT
- 音频
- 项目 manifest
- 剪辑清单
- 素材重命名
- 可选代理文件

---

## V1.0 — 远程导演台

可选：
- Cloud metadata
- 远程控制 Local Worker
- 多设备项目查看
- 本地 Worker 安全连接

此阶段再评估云服务。
