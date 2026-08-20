import { ActionSidebar } from './components/layout/ActionSidebar'
import { ProjectSidebar } from './components/layout/ProjectSidebar'
import { SceneWorkspace } from './components/layout/SceneWorkspace'
import { TopBar } from './components/layout/TopBar'

function App() {
  return (
    <div className="grid min-h-dvh min-w-[20rem] grid-rows-[auto_1fr] bg-[var(--canvas)] text-[color:var(--text-primary)]">
      <TopBar />
      <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[15rem_minmax(0,1fr)_17rem]">
        <ProjectSidebar />
        <SceneWorkspace />
        <ActionSidebar />
      </div>
    </div>
  )
}

export default App
