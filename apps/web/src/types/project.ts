export type Project = {
  id: string
  name: string
  description: string | null
  aspect_ratio: string
  width: number
  height: number
  fps: number
  created_at: string
  updated_at: string
}

export type ProjectCreate = {
  name: string
  description: string
  aspect_ratio: string
  width: number
  height: number
  fps: number
}
