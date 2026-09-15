import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { apiErrorMessage } from '../../lib/apiErrors'
import { AssetUploadControl } from '../assets/AssetUploadControl'
import { WorkflowTemplateManager } from '../workflows/WorkflowTemplateManager'
import { assetContentUrl, getProjectAssets, projectAssetsKey } from '../../services/assets'
import { downloadProjectExport, exportProject } from '../../services/projects'

type ActionSidebarProps = {
  projectId: string | null
}

export function ActionSidebar({ projectId }: ActionSidebarProps) {
  const [importOpen, setImportOpen] = useState(false)
  const assetsQuery = useQuery({
    queryKey: projectAssetsKey(projectId ?? 'no-project'),
    queryFn: () => getProjectAssets(projectId!),
    enabled: projectId !== null,
  })
  const sourceAssets = (assetsQuery.data ?? []).filter(
    (asset) => asset.scene_id === null && asset.role === 'source',
  )
  const exportMutation = useMutation({
    mutationFn: () => exportProject(projectId!),
  })
  const downloadMutation = useMutation({
    mutationFn: ({ projectId: downloadProjectId, exportId }: { projectId: string; exportId: string }) =>
      downloadProjectExport(downloadProjectId, exportId),
  })
  const exportDisabled = projectId === null || exportMutation.isPending

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
      aria-labelledby="project-tools-heading"
      className="border-t border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-4 lg:border-t-0 lg:border-l lg:p-5"
    >
      <div className="border-b border-[color:var(--border-subtle)] pb-4">
        <h2 id="project-tools-heading" className="text-sm font-semibold text-[color:var(--text-primary)]">
          项目工具
        </h2>
        <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">
          管理 Workflow、项目素材与最终导出
        </p>
      </div>

      <div className="mt-4">
        <WorkflowTemplateManager />
      </div>

      <div className="mt-4 space-y-3">
        <section className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)]">
          <button
            type="button"
            disabled={projectId === null}
            onClick={() => setImportOpen((open) => !open)}
            className="w-full p-3 text-left transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-[color:var(--text-primary)]">项目素材</span>
                <span className="mt-1 block text-xs leading-5 text-[color:var(--text-muted)]">
                  导入和查看项目参考图片、视频
                </span>
              </span>
              {importOpen && projectId !== null ? (
                <span className="font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--accent)]">收起</span>
              ) : null}
            </span>
          </button>

          {projectId === null ? (
            <p className="border-t border-[color:var(--border-subtle)] px-3 py-2 text-xs text-[color:var(--text-muted)]">
              请先选择项目
            </p>
          ) : null}

          {projectId !== null && importOpen ? (
            <div className="border-t border-[color:var(--border-subtle)] p-3">
              <AssetUploadControl
                projectId={projectId}
                role="source"
                accept="image/*,video/*"
                label="选择图片或视频"
              />
              {assetsQuery.isError ? (
                <p role="alert" className="mt-2 text-xs text-[color:var(--status-offline)]">
                  素材加载失败：{apiErrorMessage(assetsQuery.error, '素材加载失败')}
                </p>
              ) : null}
              <div className="mt-4 space-y-3">
                {sourceAssets.map((asset) => (
                  <div key={asset.id} className="border border-[color:var(--border-subtle)] p-2">
                    <p className="text-xs text-[color:var(--text-muted)]">
                      {asset.type} · {asset.mime_type}
                    </p>
                    {asset.type === 'video' ? (
                      <video controls preload="metadata" className="mt-2 w-full" src={assetContentUrl(asset.id)} />
                    ) : (
                      <img
                        className="mt-2 max-h-32 w-full object-contain"
                        src={assetContentUrl(asset.id)}
                        alt="项目素材"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-3">
          <p className="text-sm text-[color:var(--text-primary)]">导出最终成果</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">
            将各分镜已选中的最终版本整理并打包
          </p>
          {projectId === null ? (
            <p className="mt-2 text-xs text-[color:var(--text-muted)]">请先选择项目</p>
          ) : null}
          <button
            type="button"
            disabled={exportDisabled}
            onClick={handleExport}
            className="mt-3 w-full border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[color:var(--text-primary)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exportMutation.isPending ? '正在导出...' : '开始导出'}
          </button>

          {exportMutation.isSuccess ? (
            <div aria-live="polite" className="mt-4 border-t border-[color:var(--border-subtle)] pt-3">
              <p className="text-sm text-[color:var(--text-primary)]">导出完成</p>
              <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">
                已整理 {exportMutation.data.files.length} 个文件。
              </p>
              <button
                type="button"
                disabled={downloadMutation.isPending}
                onClick={handleDownload}
                className="mt-3 w-full border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[color:var(--text-primary)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
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
                  {apiErrorMessage(downloadMutation.error, '下载失败，请重试。')}
                </p>
              ) : null}
            </div>
          ) : null}

          {exportMutation.isError ? (
            <div role="alert" aria-live="polite" className="mt-4 border-t border-[color:var(--border-subtle)] pt-3">
              <p className="text-sm text-[color:var(--text-primary)]">导出失败</p>
              <p className="mt-1 text-xs leading-5 text-[color:var(--status-offline)]">
                {apiErrorMessage(exportMutation.error, '导出失败，请重试。')}
              </p>
            </div>
          ) : null}
        </section>
      </div>
    </aside>
  )
}
