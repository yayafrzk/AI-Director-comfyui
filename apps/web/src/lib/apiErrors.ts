import { ApiRequestError } from '../services/api'

const messages: Record<string, string> = {
  API_NETWORK_ERROR: '无法连接本地服务，请确认后端已启动。',
  API_INVALID_RESPONSE: '服务返回异常，请稍后重试。',

  COMFYUI_OFFLINE: 'ComfyUI 未连接，请确认服务已启动。',
  COMFYUI_TIMEOUT: 'ComfyUI 响应超时，请稍后重试。',
  COMFYUI_SUBMIT_FAILED: 'ComfyUI 提交失败，请重试。',
  COMFYUI_INVALID_RESPONSE: 'ComfyUI 返回了无效响应。',
  COMFYUI_REQUEST_INVALID: '生成请求无效。',
  COMFYUI_CANCEL_FAILED: '取消任务失败，请重试。',
  COMFYUI_CANCEL_NOT_APPLIED: 'ComfyUI 未能取消该任务。',
  COMFYUI_RUNNING_CANCEL_UNSUPPORTED: '当前 ComfyUI 不支持安全取消运行中的任务。',

  GENERATION_PARAMS_INVALID: '生成参数无效。',
  GENERATION_PERSISTENCE_FAILED: '生成任务保存失败，请重试。',
  GENERATION_JOB_NOT_FOUND: '生成任务不存在。',
  GENERATION_JOB_NOT_CANCELLABLE: '当前任务状态无法取消。',
  GENERATION_JOB_NOT_RETRYABLE: '只有失败的任务可以重试。',

  WORKFLOW_TEMPLATE_NOT_FOUND: '所选 Workflow 不存在，请重新选择。',
  WORKFLOW_TEMPLATE_DISABLED: '所选 Workflow 已禁用，请更换。',
  WORKFLOW_PATH_INVALID: 'Workflow 路径无效。',
  WORKFLOW_FILE_NOT_FOUND: 'Workflow 文件不存在。',
  WORKFLOW_JSON_INVALID: 'Workflow JSON 无效。',
  WORKFLOW_TEMPLATE_INVALID: 'Workflow 模板无效。',
  WORKFLOW_MANIFEST_INVALID: 'Workflow manifest 无效。',
  WORKFLOW_MANIFEST_MISMATCH: 'Workflow 配置与模板版本不匹配。',
  WORKFLOW_INPUT_UNKNOWN: 'Workflow 包含未知输入。',
  WORKFLOW_INPUT_REQUIRED: 'Workflow 缺少必填输入。',

  ASSET_UPLOAD_FAILED: '素材上传失败，请重试。',
  ASSET_MEDIA_INVALID: '无法读取该视频文件。',
  ASSET_THUMBNAIL_FAILED: '视频缩略图生成失败。',
  ASSET_FILE_NOT_FOUND: '所选素材文件不存在，无法继续操作。',
  ASSET_FILE_INVALID: '所选素材文件无效。',
  ASSET_PATH_INVALID: '所选素材文件路径无效。',
  ASSET_NOT_FOUND: '素材不存在。',
  ASSET_NOT_IN_SCENE: '素材不属于当前分镜。',
  ASSET_NOT_GENERATION_OUTPUT: '素材不是生成输出。',
  ASSET_SCENE_PROJECT_MISMATCH: '素材与分镜项目不匹配。',
  FFPROBE_NOT_FOUND: '未检测到 ffprobe，无法读取视频信息。',
  FFMPEG_NOT_FOUND: '未检测到 FFmpeg，无法处理视频。',

  SCENE_SELECTED_ASSET_MISSING: '有分镜尚未选择最终版本，无法导出。',
  SCENE_SELECTED_ASSET_INVALID: '有分镜的最终版本无效，请重新选择。',
  PROJECT_NOT_FOUND: '当前项目不存在。',
  SCENE_NOT_FOUND: '分镜不存在。',
  SCENE_REORDER_INVALID: '分镜排序无效。',

  EXPORT_FAILED: '导出失败，请重试。',
  EXPORT_ID_INVALID: '导出记录无效，无法下载。',
  EXPORT_NOT_FOUND: '导出文件不存在，请重新导出。',
  EXPORT_CONTENT_INVALID: '导出内容异常，请重新导出。',
  EXPORT_DOWNLOAD_FAILED: '下载失败，请重试。',
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    return messages[error.code] ?? (error.message || fallback)
  }

  if (error instanceof Error) {
    return error.message || fallback
  }

  return fallback
}
