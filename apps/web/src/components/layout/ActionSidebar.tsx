const actions = [
  { name: '导入素材', detail: '管理首帧与参考素材' },
  { name: '批量生成', detail: '提交多个分镜任务' },
  { name: '导出素材', detail: '整理最终选择版本' },
]

export function ActionSidebar() {
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
        {actions.map((action, index) => (
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
      </div>

      <div className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-raised)] px-3 py-3">
        <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">SYSTEM NOTE</p>
        <p className="mt-1 text-xs leading-5 text-[color:var(--text-muted)]">连接状态仅为静态占位，不会访问 ComfyUI。</p>
      </div>
    </aside>
  )
}
