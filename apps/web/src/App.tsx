import { useState } from 'react'

import { ActionSidebar } from './components/layout/ActionSidebar'
import { ProjectSidebar } from './components/layout/ProjectSidebar'
import { SceneWorkspace } from './components/layout/SceneWorkspace'
import { TopBar } from './components/layout/TopBar'

function App() {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)

  return (
    <div className="grid min-h-dvh min-w-[20rem] grid-rows-[auto_1fr] bg-[var(--canvas)] text-[color:var(--text-primary)]">
      <TopBar />
      <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[15rem_minmax(0,1fr)_17rem]">
        <ProjectSidebar selectedProjectId={selectedProjectId} onSelectProject={setSelectedProjectId} />
        <SceneWorkspace key={selectedProjectId ?? 'no-project'} projectId={selectedProjectId} />
        <ActionSidebar key={selectedProjectId ?? 'no-project'} projectId={selectedProjectId} />
      </div>
    </div>
  )
}

export default App
