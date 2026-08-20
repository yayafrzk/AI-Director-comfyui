export function SceneWorkspace() {
  return (
    <main className="min-w-0 bg-[var(--canvas)] p-4 sm:p-5 lg:p-6" aria-labelledby="scene-workspace-heading">
      <div className="flex items-end justify-between gap-4 border-b border-[color:var(--border-subtle)] pb-4">
        <div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENES / EDITING BAY</p>
          <h2 id="scene-workspace-heading" className="mt-1 text-base font-semibold text-[color:var(--text-primary)]">
            分镜工作区
          </h2>
        </div>
        <span className="font-mono text-xs text-[color:var(--text-muted)]">0 个镜头</span>
      </div>

      <section
        aria-labelledby="empty-scenes-heading"
        className="mt-5 grid min-h-[22rem] place-items-center border border-dashed border-[color:var(--border-strong)] bg-[var(--surface-base)] p-6 sm:min-h-[28rem]"
      >
        <div className="max-w-sm text-center">
          <div className="mb-5 flex items-center justify-center gap-3" aria-hidden="true">
            <span className="h-px w-8 bg-[var(--accent)]" />
            <span className="font-mono text-xs tracking-[0.2em] text-[color:var(--accent)]">00</span>
            <span className="h-px w-8 bg-[var(--accent)]" />
          </div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENE QUEUE</p>
          <h3 id="empty-scenes-heading" className="mt-3 text-lg font-medium text-[color:var(--text-primary)]">
            暂无分镜
          </h3>
          <p className="mt-2 text-sm leading-6 text-[color:var(--text-muted)]">后续将在这里管理 Scene。</p>
        </div>
      </section>
    </main>
  )
}
