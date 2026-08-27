export type Scene = {
  id: string
  project_id: string
  scene_number: number
  title: string
  description: string | null
  prompt: string | null
  negative_prompt: string | null
  seed: number | null
  duration_seconds: number
  workflow_template_id: string | null
  selected_asset_id: string | null
  status: string
  created_at: string
  updated_at: string
}

export type SceneUpdate = {
  title?: string
  description?: string | null
  prompt?: string | null
  negative_prompt?: string | null
  seed?: number | null
  duration_seconds?: number
}
