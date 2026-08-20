# 03_API — API 设计

统一前缀：

`/api/v1`

---

## Health

### GET /health

返回服务状态。

### GET /comfyui/health

检测 ComfyUI。

---

## Projects

### GET /projects
项目列表

### POST /projects
创建项目

### GET /projects/{id}
项目详情

### PATCH /projects/{id}
修改项目

### DELETE /projects/{id}
删除项目

---

## Scenes

### GET /projects/{project_id}/scenes
获取分镜

### POST /projects/{project_id}/scenes
创建分镜

### GET /scenes/{id}
详情

### PATCH /scenes/{id}
更新

### DELETE /scenes/{id}
删除

### POST /projects/{project_id}/scenes/reorder
重新排序

Body：

```json
{
  "scene_ids": ["uuid1", "uuid2", "uuid3"]
}
```

---

## Assets

### POST /projects/{project_id}/assets/upload
上传素材

### GET /assets/{id}
素材信息

### GET /assets/{id}/content
查看文件

### DELETE /assets/{id}
删除素材

### POST /scenes/{scene_id}/assets/{asset_id}/select
设为选中版本

---

## Workflows

### GET /workflow-templates
模板列表

### GET /workflow-templates/{id}
模板信息

### POST /workflow-templates/import
导入 workflow 模板

### POST /workflow-templates/{id}/validate
验证参数映射

---

## Generation

### POST /scenes/{scene_id}/generate
创建生成任务

建议 Body：

```json
{
  "workflow_template_id": "uuid",
  "seed": 123456,
  "params": {
    "frames": 81,
    "cfg": 5
  }
}
```

### GET /generation-jobs/{id}
任务详情

### GET /scenes/{scene_id}/generation-jobs
生成历史

### POST /generation-jobs/{id}/cancel
取消

### POST /generation-jobs/{id}/retry
重试

---

## WebSocket

### /ws/generation

事件示例：

```json
{
  "type": "generation.progress",
  "job_id": "uuid",
  "scene_id": "uuid",
  "progress": 0.42,
  "node_id": "38"
}
```

完成：

```json
{
  "type": "generation.completed",
  "job_id": "uuid",
  "outputs": ["asset_uuid"]
}
```

失败：

```json
{
  "type": "generation.failed",
  "job_id": "uuid",
  "error_code": "COMFYUI_EXECUTION_ERROR",
  "message": "CUDA out of memory"
}
```

---

## Export

### POST /projects/{project_id}/exports

Body：

```json
{
  "mode": "selected_versions",
  "include_manifest": true,
  "include_subtitles": true
}
```

返回导出任务/路径。
