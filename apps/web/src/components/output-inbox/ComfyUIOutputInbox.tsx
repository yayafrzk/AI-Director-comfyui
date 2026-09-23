import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { generationJobsKey } from '../../hooks/useGenerationEvents'
import { apiErrorMessage } from '../../lib/apiErrors'
import { ApiRequestError } from '../../services/api'
import { projectAssetsKey } from '../../services/assets'
import {
  getOutputInboxItems,
  getOutputInboxSettings,
  importOutputInboxItem,
  outputInboxContentUrl,
  outputInboxItemsKey,
  outputInboxSettingsKey,
  updateOutputInboxSettings,
  type OutputInboxItem,
  type OutputInboxSettings,
} from '../../services/outputInbox'
import type { GenerationJob } from '../../types/generation'
import type { Scene } from '../../types/scene'


type ComfyUIOutputInboxProps = { projectId: string; scene: Scene }
type InboxFilter = 'all' | 'unarchived' | 'archived'

const filters: { id: InboxFilter; label: string }[] = [
  { id: 'all', label: '全部' },
  { id: 'unarchived', label: '未归档' },
  { id: 'archived', label: '已归档' },
]

function inboxErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const messages: Record<string, string> = {
      OUTPUT_INBOX_DIRECTORY_INVALID: '路径必须是本机已存在的文件夹，请检查后重试。',
      OUTPUT_INBOX_NOT_CONFIGURED: '请先设置 ComfyUI Output 路径。',
      OUTPUT_INBOX_PATH_INVALID: '文件路径无效或超出了设置的目录。',
      OUTPUT_INBOX_ITEM_NOT_FOUND: '文件已不存在，请刷新列表。',
      OUTPUT_INBOX_TYPE_UNSUPPORTED: '目前只能归档图片和视频。',
      OUTPUT_INBOX_ITEM_ALREADY_ARCHIVED: '这个结果已归档，请刷新列表。',
      OUTPUT_INBOX_ITEM_BUSY: '文件可能仍在写入，请稍后刷新再试。',
      OUTPUT_INBOX_IMPORT_FAILED: '复制文件失败，请检查磁盘空间和目录权限。',
      OUTPUT_INBOX_SETTINGS_FAILED: '保存路径失败，请检查目录权限。',
      OUTPUT_INBOX_SETTINGS_INVALID: '路径设置无法读取，请重新保存。',
      ASSET_MEDIA_INVALID: '无法读取视频信息，请检查文件后重试。',
      FFPROBE_NOT_FOUND: '未找到 ffprobe，无法读取视频信息。',
      FFMPEG_NOT_FOUND: '未找到 FFmpeg，无法生成视频缩略图。',
      ASSET_THUMBNAIL_FAILED: '视频缩略图生成失败，请重试。',
    }
    return messages[error.code] ?? apiErrorMessage(error, fallback)
  }
  return apiErrorMessage(error, fallback)
}

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function modifiedLabel(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '时间未知'
    : new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

export function ComfyUIOutputInbox({ projectId, scene }: ComfyUIOutputInboxProps) {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<InboxFilter>('unarchived')
  const [editingPath, setEditingPath] = useState(false)
  const [pathDraft, setPathDraft] = useState('')
  const [pathError, setPathError] = useState<string | null>(null)
  const [failedItemId, setFailedItemId] = useState<string | null>(null)
  const [itemError, setItemError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const settingsQuery = useQuery({ queryKey: outputInboxSettingsKey(), queryFn: getOutputInboxSettings })
  const configured = settingsQuery.data?.configured === true
  const itemsQuery = useQuery({
    queryKey: outputInboxItemsKey(),
    queryFn: getOutputInboxItems,
    enabled: configured,
  })

  const settingsMutation = useMutation<OutputInboxSettings, Error, string>({
    mutationFn: updateOutputInboxSettings,
    onSuccess: (settings) => {
      queryClient.setQueryData(outputInboxSettingsKey(), settings)
      queryClient.setQueryData<OutputInboxItem[]>(outputInboxItemsKey(), [])
      queryClient.invalidateQueries({ queryKey: outputInboxItemsKey() })
      setEditingPath(false)
      setPathError(null)
    },
    onError: (error) => setPathError(inboxErrorMessage(error, '保存输出目录失败')),
  })
  const importMutation = useMutation<GenerationJob, Error, OutputInboxItem>({
    mutationFn: (item) => importOutputInboxItem(scene.id, {
      relative_path: item.relative_path,
      prompt_snapshot: scene.prompt ?? '',
      negative_prompt_snapshot: scene.negative_prompt ?? '',
      seed: null,
      select_as_final: false,
    }),
    onSuccess: (job, item) => {
      queryClient.setQueryData<OutputInboxItem[]>(outputInboxItemsKey(), (items = []) =>
        items.map((current) => current.id === item.id
          ? { ...current, archived: true, archived_scene_id: scene.id }
          : current),
      )
      queryClient.setQueryData<GenerationJob[]>(generationJobsKey(scene.id), (jobs = []) => [job, ...jobs])
      queryClient.invalidateQueries({ queryKey: outputInboxItemsKey() })
      queryClient.invalidateQueries({ queryKey: generationJobsKey(scene.id) })
      queryClient.invalidateQueries({ queryKey: projectAssetsKey(projectId) })
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'scenes'] })
      setFailedItemId(null)
      setItemError(null)
      setSuccessMessage("已归档「" + item.filename + "」，可在“已归档”查看。")
    },
    onError: (error, item) => {
      setFailedItemId(item.id)
      setItemError(inboxErrorMessage(error, '归入当前分镜失败'))
    },
  })

  const items = itemsQuery.data ?? []
  const counts = {
    all: items.length,
    unarchived: items.filter((item) => !item.archived).length,
    archived: items.filter((item) => item.archived).length,
  }
  const visibleItems = items.filter((item) =>
    filter === 'all' || (filter === 'archived' ? item.archived : !item.archived),
  )
  const showPathForm = !configured || editingPath

  function savePath() {
    if (!pathDraft.trim()) {
      setPathError('请输入 ComfyUI Output 文件夹的完整路径。')
      return
    }
    setPathError(null)
    settingsMutation.mutate(pathDraft.trim())
  }

  return (
    <section aria-label="ComfyUI 最新结果" className="border border-slate-300 bg-slate-50 p-4 text-slate-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">ComfyUI 最新结果</h3>
          {configured && !showPathForm ? (
            <p className="mt-1 break-all text-xs text-slate-600">{settingsQuery.data?.output_dir}</p>
          ) : null}
        </div>
        {configured && !showPathForm ? (
          <div className="flex gap-2">
            <button type="button" onClick={() => {
              setPathDraft(settingsQuery.data?.output_dir ?? '')
              setPathError(null)
              setEditingPath(true)
            }} className="cursor-pointer border border-slate-400 px-2.5 py-1.5 text-xs hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-blue-600">
              设置路径
            </button>
            <button type="button" onClick={() => queryClient.invalidateQueries({ queryKey: outputInboxItemsKey() })}
              disabled={itemsQuery.isFetching} className="cursor-pointer border border-slate-400 px-2.5 py-1.5 text-xs hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50">
              {itemsQuery.isFetching ? '刷新中…' : '刷新'}
            </button>
          </div>
        ) : null}
      </div>

      {settingsQuery.isPending ? <p className="mt-3 text-sm text-slate-600">读取路径设置中…</p> : null}
      {settingsQuery.isError ? (
        <div role="alert" className="mt-3 text-sm text-red-700">
          {inboxErrorMessage(settingsQuery.error, '读取路径设置失败')}
          <button type="button" onClick={() => settingsQuery.refetch()} className="ml-2 cursor-pointer underline focus-visible:outline-2 focus-visible:outline-blue-600">重试</button>
        </div>
      ) : null}

      {!settingsQuery.isPending && !settingsQuery.isError && showPathForm ? (
        <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
          {!configured ? <p className="text-sm text-slate-700">尚未设置 ComfyUI Output 路径。</p> : null}
          <label htmlFor="output-inbox-path" className="block text-xs font-medium">本机 Output 文件夹</label>
          <input id="output-inbox-path" type="text" value={pathDraft}
            onChange={(event) => { setPathDraft(event.target.value); setPathError(null) }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                if (!event.nativeEvent.isComposing) savePath()
              }
            }}
            disabled={settingsMutation.isPending} aria-invalid={pathError !== null}
            aria-describedby={pathError ? 'output-inbox-path-error' : 'output-inbox-path-hint'}
            placeholder="例如：D:\ComfyUI\output"
            className="w-full border border-slate-400 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-600 disabled:opacity-60" />
          <p id="output-inbox-path-hint" className="text-xs text-slate-600">填写 ComfyUI 实际保存图片和视频的本机目录。</p>
          {pathError ? <p id="output-inbox-path-error" role="alert" className="text-xs text-red-700">{pathError}</p> : null}
          <div className="flex gap-2">
            <button type="button" onClick={savePath} disabled={settingsMutation.isPending}
              className="cursor-pointer bg-blue-700 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50">
              {settingsMutation.isPending ? '保存中…' : '保存路径'}
            </button>
            {configured ? <button type="button" onClick={() => { setEditingPath(false); setPathError(null) }} disabled={settingsMutation.isPending}
              className="cursor-pointer border border-slate-400 px-3 py-2 text-xs hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50">取消</button> : null}
          </div>
        </div>
      ) : null}

      {configured && !showPathForm ? (
        <div className="mt-4">
          <div aria-label="结果筛选" className="flex flex-wrap gap-1 border-b border-slate-300 pb-2">
            {filters.map(({ id, label }) => (
              <button key={id} type="button" aria-pressed={filter === id} onClick={() => setFilter(id)}
                className={`cursor-pointer px-3 py-1.5 text-xs focus-visible:outline-2 focus-visible:outline-blue-600 ${filter === id ? 'bg-slate-800 font-semibold text-white' : 'text-slate-700 hover:bg-slate-200'}`}>
                {label} ({counts[id]})
              </button>
            ))}
          </div>
          {successMessage ? <p role="status" className="mt-3 text-xs font-medium text-emerald-800">{successMessage}</p> : null}
          {itemsQuery.isPending ? <p className="py-5 text-sm text-slate-600">正在查找最新结果…</p> : null}
          {itemsQuery.isError ? <div role="alert" className="py-4 text-sm text-red-700">{inboxErrorMessage(itemsQuery.error, '读取最新结果失败')}<button type="button" onClick={() => itemsQuery.refetch()} className="ml-2 cursor-pointer underline focus-visible:outline-2 focus-visible:outline-blue-600">重试</button></div> : null}
          {!itemsQuery.isPending && !itemsQuery.isError && visibleItems.length === 0 ? (
            <p className="py-5 text-sm text-slate-600">{filter === 'archived' ? '还没有已归档的结果。' : filter === 'unarchived' ? '暂无待归档结果。生成完成后点击“刷新”。' : '目录里还没有图片或视频。'}</p>
          ) : null}
          <div className="mt-3 space-y-3">
            {visibleItems.map((item) => (
              <article key={item.id} className="border border-slate-300 bg-white p-2.5">
                <div className="flex gap-3">
                  <div className="h-28 w-28 shrink-0 overflow-hidden bg-slate-200 sm:h-32 sm:w-36">
                    {item.type === 'image' ? (
                      <img src={outputInboxContentUrl(item.relative_path)} alt={item.filename} loading="lazy" className="h-full w-full object-cover" />
                    ) : (
                      <video src={outputInboxContentUrl(item.relative_path)} aria-label={item.filename} preload="metadata" muted playsInline className="h-full w-full object-cover" />
                    )}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
                    <p className="w-full break-all text-sm font-medium leading-5">{item.filename}</p>
                    <p className="text-xs text-slate-600">{sizeLabel(item.size_bytes)} · {modifiedLabel(item.modified_at)}</p>
                    {item.archived ? (
                      <p className="mt-auto text-xs font-medium text-emerald-800">✓ 已归档 · {item.archived_scene_id === scene.id ? '已归入当前 Scene' : '已归档至其他 Scene'}</p>
                    ) : (
                      <button type="button" onClick={() => { setFailedItemId(null); setItemError(null); setSuccessMessage(null); importMutation.mutate(item) }}
                        disabled={importMutation.isPending}
                        className="mt-auto cursor-pointer bg-blue-700 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-50">
                        {importMutation.isPending && importMutation.variables?.id === item.id ? '归档中…' : '归入当前 Scene'}
                      </button>
                    )}
                    {failedItemId === item.id && itemError ? <p role="alert" className="text-xs text-red-700">{itemError}</p> : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}
