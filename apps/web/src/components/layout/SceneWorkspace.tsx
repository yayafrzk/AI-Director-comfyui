import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type DragEvent } from 'react'

import { generateScene, getProjectScenes, getSceneGenerationJobs, reorderScenes } from '../../services/scenes'
import { generationJobsKey, useGenerationEvents } from '../../hooks/useGenerationEvents'
import type { GenerationJob } from '../../types/generation'
import type { Scene } from '../../types/scene'
import { SceneCard } from './SceneCard'
import { SceneDetailDrawer } from './SceneDetailDrawer'

type SceneWorkspaceProps = {
  projectId: string | null
}

type ReorderVariables = {
  projectId: string
  sceneIds: string[]
  previousScenes: Scene[]
}

function sceneQueryKey(projectId: string | null) {
  return ['projects', projectId, 'scenes'] as const
}

function moveScene(scenes: Scene[], sceneId: string, targetSceneId: string): Scene[] {
  const sourceIndex = scenes.findIndex((scene) => scene.id === sceneId)
  const targetIndex = scenes.findIndex((scene) => scene.id === targetSceneId)

  if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) {
    return scenes
  }

  const reorderedScenes = [...scenes]
  const [movedScene] = reorderedScenes.splice(sourceIndex, 1)
  reorderedScenes.splice(targetIndex, 0, movedScene)
  return reorderedScenes
}

function hasSameSceneOrder(first: Scene[], second: Scene[]): boolean {
  return first.length === second.length && first.every((scene, index) => scene.id === second[index]?.id)
}

export function SceneWorkspace({ projectId }: SceneWorkspaceProps) {
  const queryClient = useQueryClient()
  const previousScenesRef = useRef<Scene[] | null>(null)
  const draggedSceneIdRef = useRef<string | null>(null)
  const draggedProjectIdRef = useRef<string | null>(null)
  const reorderLockRef = useRef(false)
  const [draggingSceneId, setDraggingSceneId] = useState<string | null>(null)
  const [reorderError, setReorderError] = useState<{ projectId: string; message: string } | null>(null)
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)

  const scenesQuery = useQuery({
    queryKey: sceneQueryKey(projectId),
    queryFn: () => getProjectScenes(projectId!),
    enabled: projectId !== null,
  })
  const scenes = scenesQuery.data ?? []
  useGenerationEvents(projectId !== null)
  const generationQueries = useQueries({ queries: scenes.map((scene) => ({ queryKey: generationJobsKey(scene.id), queryFn: () => getSceneGenerationJobs(scene.id) })) })
  const jobsByScene = new Map(scenes.map((scene, index) => [scene.id, generationQueries[index]?.data?.[0]]))
  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId) ?? null
  const reorderMutation = useMutation({
    mutationFn: ({ projectId: reorderProjectId, sceneIds }: ReorderVariables) => reorderScenes(reorderProjectId, sceneIds),
    onSuccess: (reorderedScenes, variables) => {
      queryClient.setQueryData(sceneQueryKey(variables.projectId), reorderedScenes)
    },
    onError: (error, variables) => {
      queryClient.setQueryData(sceneQueryKey(variables.projectId), variables.previousScenes)

      setReorderError({
        projectId: variables.projectId,
        message: error instanceof Error ? error.message : '分镜排序保存失败',
      })
    },
    onSettled: () => {
      reorderLockRef.current = false
    },
  })
  const generateMutation = useMutation({ mutationFn: (scene: Scene) => generateScene(scene.id, scene.workflow_template_id!), onSuccess: (submitted, scene) => queryClient.setQueryData<GenerationJob[]>(generationJobsKey(scene.id), (jobs = []) => [{ id: submitted.job_id, scene_id: scene.id, status: submitted.status }, ...jobs]) })
  const isSorting = draggingSceneId !== null || reorderMutation.isPending
  const dragDisabled = scenes.length < 2 || reorderMutation.isPending

  function handleDragStart(event: DragEvent<HTMLButtonElement>, sceneId: string) {
    if (projectId === null || reorderLockRef.current || scenes.length < 2) {
      event.preventDefault()
      return
    }

    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', sceneId)
    previousScenesRef.current = scenes
    draggedSceneIdRef.current = sceneId
    draggedProjectIdRef.current = projectId
    setDraggingSceneId(sceneId)
    setReorderError(null)
  }

  function handleDragEnter(targetSceneId: string) {
    const draggedSceneId = draggedSceneIdRef.current
    const draggedProjectId = draggedProjectIdRef.current

    if (
      draggedSceneId === null ||
      draggedProjectId === null ||
      draggedSceneId === targetSceneId ||
      reorderLockRef.current ||
      draggedProjectId !== projectId
    ) {
      return
    }

    queryClient.setQueryData<Scene[]>(sceneQueryKey(draggedProjectId), (currentScenes = []) =>
      moveScene(currentScenes, draggedSceneId, targetSceneId),
    )
  }

  function handleDragEnd() {
    const draggedProjectId = draggedProjectIdRef.current
    const previousScenes = previousScenesRef.current

    draggedSceneIdRef.current = null
    draggedProjectIdRef.current = null
    previousScenesRef.current = null

    if (draggedProjectId === null || previousScenes === null) {
      setDraggingSceneId(null)
      return
    }

    if (draggedProjectId !== projectId) {
      queryClient.setQueryData(sceneQueryKey(draggedProjectId), previousScenes)
      setDraggingSceneId(null)
      return
    }

    const reorderedScenes = queryClient.getQueryData<Scene[]>(sceneQueryKey(draggedProjectId)) ?? previousScenes

    if (hasSameSceneOrder(previousScenes, reorderedScenes)) {
      setDraggingSceneId(null)
      return
    }

    reorderLockRef.current = true
    reorderMutation.mutate({
      projectId: draggedProjectId,
      sceneIds: reorderedScenes.map((scene) => scene.id),
      previousScenes,
    })
    setDraggingSceneId(null)
  }

  return (
    <main className="min-w-0 bg-[var(--canvas)] p-4 sm:p-5 lg:p-6" aria-labelledby="scene-workspace-heading">
      <div className="flex items-end justify-between gap-4 border-b border-[color:var(--border-subtle)] pb-4">
        <div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENES / EDITING BAY</p>
          <h2 id="scene-workspace-heading" className="mt-1 text-base font-semibold text-[color:var(--text-primary)]">
            分镜工作区
          </h2>
        </div>
        <span className="font-mono text-xs text-[color:var(--text-muted)]">{scenes.length} 个镜头</span>
      </div>

      {reorderError?.projectId === projectId ? (
        <section className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-base)] px-4 py-4">
          <p className="text-sm text-[color:var(--text-primary)]">分镜排序保存失败</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">{reorderError.message}</p>
        </section>
      ) : null}

      {projectId === null ? (
        <EmptySceneState title="请选择项目" description="从左侧选择一个项目后，即可查看其分镜。" />
      ) : null}

      {projectId !== null && scenesQuery.isLoading ? (
        <section className="mt-5 grid min-h-[22rem] place-items-center border border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-6 sm:min-h-[28rem]">
          <p className="text-sm text-[color:var(--text-muted)]">加载分镜...</p>
        </section>
      ) : null}

      {projectId !== null && scenesQuery.isError ? (
        <section className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-base)] px-4 py-4">
          <p className="text-sm text-[color:var(--text-primary)]">分镜加载失败</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">
            {scenesQuery.error instanceof Error ? scenesQuery.error.message : '请稍后重试'}
          </p>
        </section>
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length === 0 ? (
        <EmptySceneState title="暂无分镜" description="后续将在这里管理 Scene。" />
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length > 0 ? (
        <section className="mt-5 space-y-3" aria-label="分镜列表">
          {scenes.map((scene, index) => (
            <SceneCard
              key={scene.id}
              scene={scene}
              generationJob={jobsByScene.get(scene.id)}
              generating={generateMutation.isPending && generateMutation.variables?.id === scene.id}
              onGenerate={(target) => generateMutation.mutate(target)}
              position={index}
              isSorting={isSorting}
              dragDisabled={dragDisabled}
              onDragStart={handleDragStart}
              onDragEnter={handleDragEnter}
              onDragEnd={handleDragEnd}
              onOpen={setSelectedSceneId}
            />
          ))}
        </section>
      ) : null}

      {projectId !== null && selectedScene !== null ? (
        <SceneDetailDrawer key={selectedScene.id} projectId={projectId} scene={selectedScene} onClose={() => setSelectedSceneId(null)} />
      ) : null}
    </main>
  )
}

type EmptySceneStateProps = {
  title: string
  description: string
}

function EmptySceneState({ title, description }: EmptySceneStateProps) {
  return (
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
          {title}
        </h3>
        <p className="mt-2 text-sm leading-6 text-[color:var(--text-muted)]">{description}</p>
      </div>
    </section>
  )
}
