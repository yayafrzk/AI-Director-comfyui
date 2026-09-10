import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { apiErrorMessage } from '../../lib/apiErrors'
import { projectAssetsKey, uploadAsset } from '../../services/assets'
import type { Asset, AssetType } from '../../types/asset'

type AssetUploadControlProps = {
  projectId: string
  type?: AssetType
  role: string
  sceneId?: string
  accept: string
  label: string
}

export function AssetUploadControl({ projectId, type, role, sceneId, accept, label }: AssetUploadControlProps) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: () => uploadAsset({ projectId, file: file!, type: type ?? (file!.type.startsWith('video/') ? 'video' : 'image'), role, sceneId }),
    onSuccess: (asset) => {
      queryClient.setQueryData<Asset[]>(projectAssetsKey(projectId), (assets = []) =>
        [...assets, asset].sort((left, right) => left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id)),
      )
      setFile(null)
      setError(null)
      if (inputRef.current) inputRef.current.value = ''
    },
    onError: (requestError) => setError(apiErrorMessage(requestError, '素材上传失败')),
  })

  function handleUpload() {
    if (file === null) { setError('请选择文件'); return }
    if (!file.type.startsWith('image/') && !(accept.includes('video/*') && file.type.startsWith('video/'))) { setError('暂不支持该文件类型'); return }
    setError(null)
    mutation.mutate()
  }

  return <div className="mt-3 space-y-2">
    <label className={`inline-flex items-center border border-[color:var(--accent)] px-3 py-2 text-sm text-[color:var(--accent)] transition-colors focus-within:ring-2 focus-within:ring-[color:var(--accent)] focus-within:ring-offset-2 focus-within:ring-offset-[color:var(--surface-raised)] ${mutation.isPending ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-[var(--accent-soft)]'}`}>
      <span>{label}</span>
      <input ref={inputRef} type="file" accept={accept} disabled={mutation.isPending} onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null) }} className="sr-only" />
    </label>
    <p aria-live="polite" className="break-all text-xs text-[color:var(--text-muted)]">{file ? `已选择：${file.name}` : '未选择文件'}</p>
    {error ? <p role="alert" className="text-xs text-[color:var(--status-offline)]">{error}</p> : null}
    <button type="button" onClick={handleUpload} disabled={mutation.isPending} className="border border-[color:var(--accent)] px-3 py-1.5 text-sm text-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-50">{mutation.isPending ? '上传中...' : '上传'}</button>
  </div>
}