export type AssetType = 'image' | 'video' | 'audio' | 'reference'

export type Asset = {
  id: string
  project_id: string
  scene_id: string | null
  type: AssetType
  role: string
  relative_path: string
  thumbnail_path: string | null
  mime_type: string
  width: number | null
  height: number | null
  duration_seconds: number | null
  size_bytes: number
  hash: string | null
  created_at: string
}