import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { apiErrorMessage } from '../../lib/apiErrors'
import {
  getWorkflowTemplates,
  importWorkflowTemplate,
  workflowTemplatesKey,
  type WorkflowTemplateImportPayload,
} from '../../services/workflows'

type WorkflowForm = Omit<WorkflowTemplateImportPayload, 'is_enabled'>

const emptyForm: WorkflowForm = {
  name: '',
  slug: '',
  version: '',
  template_path: '',
  manifest_path: '',
}

export function WorkflowTemplateManager() {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState(true)
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [form, setForm] = useState<WorkflowForm>(emptyForm)
  const [formError, setFormError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const workflowQuery = useQuery({
    queryKey: workflowTemplatesKey(),
    queryFn: getWorkflowTemplates,
  })
  const templates = workflowQuery.data ?? []

  const registerMutation = useMutation({
    mutationFn: importWorkflowTemplate,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: workflowTemplatesKey() })
      setForm(emptyForm)
      setFormError(null)
      setSuccessMessage('Workflow 已注册，可以在分镜配置中选择。')
      setIsRegisterOpen(false)
    },
  })

  function updateField(field: keyof WorkflowForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
    setFormError(null)
    setSuccessMessage(null)
    registerMutation.reset()
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload = {
      name: form.name.trim(),
      slug: form.slug.trim(),
      version: form.version.trim(),
      template_path: form.template_path.trim(),
      manifest_path: form.manifest_path.trim(),
    }

    if (Object.values(payload).some((value) => value.length === 0)) {
      setFormError('请完整填写 Workflow 注册信息。')
      return
    }

    setFormError(null)
    setSuccessMessage(null)
    registerMutation.mutate({ ...payload, is_enabled: true })
  }

  function toggleRegisterForm() {
    setIsRegisterOpen((current) => !current)
    setFormError(null)
    setSuccessMessage(null)
    registerMutation.reset()
  }

  const countLabel = workflowQuery.isLoading ? '加载中' : `${templates.length} 个`

  return (
    <section className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)]">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-start gap-3 p-3 text-left transition-colors hover:bg-[color:var(--surface-base)]"
      >
        <span className="pt-0.5 font-mono text-[0.625rem] tracking-[0.1em] text-[color:var(--accent)]">WF</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm text-[color:var(--text-primary)]">Workflow 模板</span>
          <span className="mt-1 block text-xs leading-5 text-[color:var(--text-muted)]">注册已有 Workflow 文件并用于分镜生成</span>
        </span>
        <span className="font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--accent)]">
          {countLabel} · {isOpen ? '收起' : '展开'}
        </span>
      </button>

      {isOpen ? (
        <div className="border-t border-[color:var(--border-subtle)] p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">已注册 {countLabel}</p>
            <button
              type="button"
              onClick={toggleRegisterForm}
              disabled={registerMutation.isPending}
              className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-2 py-1.5 text-xs text-[color:var(--text-primary)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRegisterOpen ? '收起注册表单' : '+ 注册 Workflow'}
            </button>
          </div>

          {successMessage ? (
            <p aria-live="polite" className="mt-3 border-l-2 border-[color:var(--accent)] px-2 text-xs leading-5 text-[color:var(--text-primary)]">
              {successMessage}
            </p>
          ) : null}

          {workflowQuery.isError ? (
            <p role="alert" className="mt-3 text-xs leading-5 text-[color:var(--status-offline)]">
              {apiErrorMessage(workflowQuery.error, 'Workflow 加载失败，请重试。')}
            </p>
          ) : null}

          {!workflowQuery.isLoading && !workflowQuery.isError && templates.length === 0 ? (
            <div className="mt-3 border-l-2 border-[color:var(--accent)] px-3 py-1 text-xs leading-5 text-[color:var(--text-muted)]">
              <p className="text-sm text-[color:var(--text-primary)]">暂无 Workflow</p>
              <ol className="mt-2 list-decimal space-y-1 pl-4">
                <li>将 Workflow JSON 和 manifest JSON 放入 workflows 目录</li>
                <li>点击“注册 Workflow”</li>
                <li>注册后即可在分镜配置中选择</li>
              </ol>
              <p className="mt-2 font-mono text-[0.625rem] text-[color:var(--text-muted)]">例如：h3/template.json、h3/manifest.json</p>
            </div>
          ) : null}

          {templates.length > 0 ? (
            <ul className="mt-3 space-y-2" aria-label="已注册 Workflow 模板">
              {templates.map((template) => (
                <li key={template.id} className="border border-[color:var(--border-subtle)] p-2 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 break-words text-sm text-[color:var(--text-primary)]">{template.name}</p>
                    <span className={template.is_enabled ? 'shrink-0 text-[color:var(--accent)]' : 'shrink-0 text-[color:var(--status-offline)]'}>
                      {template.is_enabled ? '已启用' : '已禁用'}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-[0.625rem] text-[color:var(--text-muted)]">v{template.version} · {template.slug}</p>
                </li>
              ))}
            </ul>
          ) : null}

          {isRegisterOpen ? (
            <form noValidate onSubmit={handleSubmit} className="mt-4 border-t border-[color:var(--border-subtle)] pt-4">
              <p className="text-sm text-[color:var(--text-primary)]">注册 Workflow</p>
              <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">
                填写 workflows 目录内的相对路径，不要填写 C:\ 或 D:\ 开头的绝对路径。例如：minimax-h3/template.json
              </p>
              <div className="mt-3 space-y-3">
                <label className="block text-xs text-[color:var(--text-primary)]">
                  名称
                  <input
                    value={form.name}
                    onChange={(event) => updateField('name', event.target.value)}
                    disabled={registerMutation.isPending}
                    placeholder="Minimax H3"
                    className="mt-1 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="block text-xs text-[color:var(--text-primary)]">
                  标识 Slug
                  <input
                    value={form.slug}
                    onChange={(event) => updateField('slug', event.target.value)}
                    disabled={registerMutation.isPending}
                    placeholder="minimax-h3"
                    className="mt-1 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="block text-xs text-[color:var(--text-primary)]">
                  版本
                  <input
                    value={form.version}
                    onChange={(event) => updateField('version', event.target.value)}
                    disabled={registerMutation.isPending}
                    placeholder="1"
                    className="mt-1 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="block text-xs text-[color:var(--text-primary)]">
                  Workflow JSON 相对路径
                  <input
                    value={form.template_path}
                    onChange={(event) => updateField('template_path', event.target.value)}
                    disabled={registerMutation.isPending}
                    placeholder="minimax-h3/template.json"
                    className="mt-1 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
                <label className="block text-xs text-[color:var(--text-primary)]">
                  Manifest JSON 相对路径
                  <input
                    value={form.manifest_path}
                    onChange={(event) => updateField('manifest_path', event.target.value)}
                    disabled={registerMutation.isPending}
                    placeholder="minimax-h3/manifest.json"
                    className="mt-1 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-60"
                  />
                </label>
              </div>

              {formError ? <p role="alert" className="mt-3 text-xs text-[color:var(--status-offline)]">{formError}</p> : null}
              {registerMutation.isError ? (
                <p role="alert" className="mt-3 text-xs leading-5 text-[color:var(--status-offline)]">
                  {apiErrorMessage(registerMutation.error, 'Workflow 注册失败，请重试。')}
                </p>
              ) : null}

              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={toggleRegisterForm}
                  disabled={registerMutation.isPending}
                  className="border border-[color:var(--border-subtle)] px-3 py-2 text-sm text-[color:var(--text-muted)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={registerMutation.isPending}
                  className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[color:var(--text-primary)] transition-colors hover:bg-[color:var(--surface-base)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {registerMutation.isPending ? '注册中...' : '注册 Workflow'}
                </button>
              </div>
            </form>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
