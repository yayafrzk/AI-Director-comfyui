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

export type ProjectExportFile = {
  scene_id: string
  scene_number: number
  asset_id: string
  filename: string
}

export type ProjectExportResult = {
  project_id: string
  export_id: string
  export_dir: string
  manifest_filename: string
  files: ProjectExportFile[]
}
