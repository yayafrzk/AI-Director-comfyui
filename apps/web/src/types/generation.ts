export type GenerationStatus = 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export type GenerationJob = {
  id: string
  scene_id: string
  status: GenerationStatus
  error_code?: string | null
  error_message?: string | null
  progress?: number
  node_id?: string
  created_at?: string
  prompt_snapshot?: string
  seed?: number | null
  workflow_version?: string
  outputs?: GenerationOutput[]
}

export type GenerationOutput = { id: string; output_index: number; asset: { id: string; type: string; role: string; thumbnail_path: string | null; mime_type: string; relative_path: string; width: number | null; height: number | null; duration_seconds: number | null; created_at: string } }

export type GenerationEvent = {
  type: 'generation.progress' | 'generation.running' | 'generation.completed' | 'generation.failed' | 'generation.cancelled'
  job_id: string
  scene_id: string
  status: GenerationStatus
  progress?: number
  node_id?: string
  error_code?: string | null
  message?: string | null
}

export function parseGenerationEvent(raw: string): GenerationEvent | null {
  try {
    const value: unknown = JSON.parse(raw)
    if (typeof value !== 'object' || value === null) return null
    const event = value as Record<string, unknown>
    const types = new Set(['generation.progress', 'generation.running', 'generation.completed', 'generation.failed', 'generation.cancelled'])
    if (!types.has(String(event.type)) || typeof event.job_id !== 'string' || typeof event.scene_id !== 'string' || typeof event.status !== 'string') return null
    return event as GenerationEvent
  } catch {
    return null
  }
}

export function formatGenerationStatus(job: GenerationJob | undefined): string {
  if (!job) return '待处理'
  const labels: Record<GenerationStatus, string> = { pending: '待处理', queued: '排队中', running: '生成中', completed: '已完成', failed: '失败', cancelled: '已取消' }
  if (job.status !== 'running') return labels[job.status]
  const progress = typeof job.progress === 'number' ? ` ${Math.round(Math.max(0, Math.min(1, job.progress)) * 100)}%` : ''
  const node = job.node_id ? ` · Node ${job.node_id}` : ''
  return `${labels.running}${progress}${node}`
}
