export function TopBar() {
  return (
    <header className="border-b border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-4 py-3 sm:px-5 lg:px-6">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center border border-[color:var(--accent)] font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--accent)]"
          >
            AD
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold tracking-[0.01em] text-[color:var(--text-primary)]">
              AI Director
            </h1>
            <p className="truncate text-xs text-[color:var(--text-muted)]">本地 AI 视频导演台</p>
          </div>
          <span aria-hidden="true" className="hidden h-8 w-px bg-[var(--border-subtle)] sm:block" />
          <div className="min-w-0">
            <p className="font-mono text-[0.625rem] tracking-[0.14em] text-[color:var(--text-muted)]">
              当前项目
            </p>
            <p className="truncate text-sm text-[color:var(--text-primary)]">布布二故事</p>
          </div>
        </div>

        <div
          aria-label="ComfyUI 状态：未连接"
          role="status"
          className="flex items-center gap-2 border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2"
        >
          <span aria-hidden="true" className="size-2 rounded-full bg-[var(--status-offline)]" />
          <div className="leading-tight">
            <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">
              COMFYUI
            </p>
            <p className="text-xs text-[color:var(--text-primary)]">未连接</p>
          </div>
        </div>
      </div>
    </header>
  )
}
