const projects = [
  { name: '布布二故事', sceneCount: '0 个分镜', isCurrent: true },
  { name: '旅行短片', sceneCount: '0 个分镜', isCurrent: false },
  { name: '测试项目', sceneCount: '0 个分镜', isCurrent: false },
]

export function ProjectSidebar() {
  return (
    <aside
      aria-labelledby="projects-heading"
      className="border-b border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-4 lg:border-r lg:border-b-0 lg:p-5"
    >
      <div className="flex items-end justify-between gap-3 border-b border-[color:var(--border-subtle)] pb-4">
        <div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">PROJECTS</p>
          <h2 id="projects-heading" className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">
            项目
          </h2>
        </div>
        <span className="font-mono text-xs text-[color:var(--text-muted)]">03</span>
      </div>

      <ul className="mt-4 space-y-2" aria-label="静态项目列表">
        {projects.map((project, index) => (
          <li
            key={project.name}
            className={[
              'border px-3 py-3',
              project.isCurrent
                ? 'border-[color:var(--accent)] bg-[var(--accent-soft)]'
                : 'border-[color:var(--border-subtle)] bg-[var(--surface-raised)]',
            ].join(' ')}
          >
            <div className="flex items-center gap-3">
              <span
                aria-hidden="true"
                className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]"
              >
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-[color:var(--text-primary)]">{project.name}</p>
                <p className="mt-1 text-xs text-[color:var(--text-muted)]">{project.sceneCount}</p>
              </div>
              {project.isCurrent ? (
                <span className="font-mono text-[0.625rem] tracking-[0.1em] text-[color:var(--accent)]">当前</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>

      <button
        type="button"
        disabled
        className="mt-4 w-full border border-[color:var(--border-subtle)] px-3 py-2 text-left text-xs text-[color:var(--text-muted)] disabled:cursor-not-allowed disabled:opacity-70"
      >
        + 新建项目
      </button>
      <p className="mt-3 text-xs leading-5 text-[color:var(--text-muted)]">项目管理将在后续任务中启用。</p>
    </aside>
  )
}
