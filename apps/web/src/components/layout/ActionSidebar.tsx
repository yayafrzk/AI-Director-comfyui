import { useMutation } from '@tanstack/react-query'

import { downloadProjectExport, exportProject, ProjectRequestError } from '../../services/projects'

type ActionSidebarProps = {
  projectId: string | null
}

const unavailableActions = [
  { name: '导入素材', detail: '管理首帧与参考素材' },
  { name: '批量生成', detail: '提交多个分镜任务' },
]

const exportErrorMessages: Record<string, string> = {
  SCENE_SELECTED_ASSET_MISSING: '有分镜尚未选择最终版本，无法导出。',
  SCENE_SELECTED_ASSET_INVALID: '有分镜的最终版本无效，请重新选择。',
  ASSET_FILE_NOT_FOUND: '所选素材文件不存在，无法导出。',
  ASSET_PATH_INVALID: '所选素材文件路径无效，无法导出。',
  PROJECT_NOT_FOUND: '当前项目不存在。',
  EXPORT_FAILED: '导出失败，请重试。',
}

const downloadErrorMessages: Record<string, string> = {
  PROJECT_NOT_FOUND: '当前项目不存在。',
  EXPORT_ID_INVALID: '导出记录无效，无法下载。',
  EXPORT_NOT_FOUND: '导出文件不存在，请重新导出。',
  EXPORT_CONTENT_INVALID: '导出内容异常，请重新导出。',
  EXPORT_DOWNLOAD_FAILED: '下载失败，请重试。',
}

function exportErrorMessage(error: unknown): string {
  if (error instanceof ProjectRequestError) {
    return exportErrorMessages[error.code] ?? error.message
  }
  return error instanceof Error ? error.message : '导出失败，请重试。'
}

function downloadErrorMessage(error: unknown): string {
  if (error instanceof ProjectRequestError) {
    return downloadErrorMessages[error.code] ?? error.message
  }
  return error instanceof Error ? error.message : '下载失败，请重试。'
}

export function ActionSidebar({ projectId }: ActionSidebarProps) {
  const exportMutation = useMutation({
    mutationFn: () => exportProject(projectId!),
  })
  const downloadMutation = useMutation({
    mutationFn: ({ projectId: downloadProjectId, exportId }: { projectId: string; exportId: string }) =>
      downloadProjectExport(downloadProjectId, exportId),
  })
  const exportDisabled = projectId === null || exportMutation.isPending
  const exportStatus = projectId === null ? '未选择项目' : exportMutation.isPending ? '处理中' : '可导出'

  function handleExport() {
    if (projectId === null) {
      return
    }
    downloadMutation.reset()
    exportMutation.mutate()
  }

  function handleDownload() {
    const exportResult = exportMutation.data
    if (!exportResult) {
      return
    }
    downloadMutation.mutate({
      projectId: exportResult.project_id,
      exportId: exportResult.export_id,
    })
  }

  return (
    <aside
      aria-labelledby="actions-heading"
      className="border-t border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-4 lg:border-t-0 lg:border-l lg:p-5"
    >
      <div className="border-b border-[color:var(--border-subtle)] pb-4">
        <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">ACTIONS</p>
        <h2 id="actions-heading" className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">
          操作
        </h2>
      </div>

      <div className="mt-4 space-y-2">
        {unavailableActions.map((action, index) => (
          <button
            key={action.name}
            type="button"
            disabled
            className="flex w-full items-start gap-3 border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-3 text-left disabled:cursor-not-allowed disabled:opacity-70"
          >
            <span className="pt-0.5 font-mono text-[0.625rem] tracking-[0.1em] text-[color:var(--text-muted)]">
              {String(index + 1).padStart(2, '0')}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm text-[color:var(--text-primary)]">{action.name}</span>
              <span className="mt-1 block text-xs leading-5 text-[color:var(--text-muted)]">{action.detail}</span>
            </span>
            <span className="font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--text-muted)]">待接入</span>
          </button>
        ))}

        <button
          type="button"
          disabled={exportDisabled}
          onClick={handleExport}
          className="flex w-full items-start gap-3 border border-[color:var(--accent)] bg-[var(--accent-soft)] p-3 text-left transition-colors hover:bg-[color:var(--surface-raised)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="pt-0.5 font-mono text-[0.625rem] tracking-[0.1em] text-[color:var(--accent)]">03</span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm text-[color:var(--text-primary)]">{exportMutation.isPending ? '导出中...' : '导出素材'}</span>
            <span className="mt-1 block text-xs leading-5 text-[color:var(--text-muted)]">整理最终选择版本</span>
          </span>
          <span className="font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--accent)]">{exportStatus}</span>
        </button>
      </div>

      {exportMutation.isSuccess ? (
        <section aria-live="polite" className="mt-5 border-l-2 border-[color:var(--accent)] bg-[var(--surface-raised)] px-3 py-3">
          <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--accent)]">EXPORT COMPLETE</p>
          <p className="mt-1 text-sm text-[color:var(--text-primary)]">导出完成</p>
          <dl className="mt-3 space-y-2 text-xs leading-5 text-[color:var(--text-muted)]">
            <div className="flex items-center justify-between gap-3">
              <dt>文件数量</dt>
              <dd className="font-mono text-[color:var(--text-primary)]">{exportMutation.data.files.length} 个文件</dd>
            </div>
            <div>
              <dt className="font-mono text-[0.625rem] tracking-[0.1em]">EXPORT ID</dt>
              <dd className="mt-1 break-all font-mono text-[color:var(--text-primary)]">{exportMutation.data.export_id}</dd>
            </div>
            <div>
              <dt>目录</dt>
              <dd className="mt-1 break-all font-mono text-[color:var(--text-primary)]">{exportMutation.data.export_dir}</dd>
            </div>
            <div>
              <dt>Manifest</dt>
              <dd className="mt-1 font-mono text-[color:var(--text-primary)]">{exportMutation.data.manifest_filename}</dd>
            </div>
          </dl>
          <button
            type="button"
            disabled={downloadMutation.isPending}
            onClick={handleDownload}
            className="mt-4 w-full border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[color:var(--text-primary)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {downloadMutation.isPending ? '下载中...' : '下载 ZIP'}
          </button>
          {downloadMutation.isSuccess ? (
            <p aria-live="polite" className="mt-2 text-xs leading-5 text-[color:var(--text-muted)]">
              下载已开始
            </p>
          ) : null}
          {downloadMutation.isError ? (
            <p role="alert" className="mt-2 text-xs leading-5 text-[color:var(--status-offline)]">
              {downloadErrorMessage(downloadMutation.error)}
            </p>
          ) : null}
        </section>
      ) : null}

      {exportMutation.isError ? (
        <section role="alert" aria-live="polite" className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-raised)] px-3 py-3">
          <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--status-offline)]">EXPORT ERROR</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--text-primary)]">{exportErrorMessage(exportMutation.error)}</p>
        </section>
      ) : null}

      <div className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-raised)] px-3 py-3">
        <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">SYSTEM NOTE</p>
        <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">连接状态仅为静态占位，不会访问 ComfyUI。</p>
      </div>
    </aside>
  )
}
