import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type DragEvent, type FormEvent } from 'react'

import { apiErrorMessage } from '../../lib/apiErrors'
import { cancelGenerationJob, createScene, generateScene, getProjectScenes, getSceneGenerationJobs, reorderScenes, retryGenerationJob } from '../../services/scenes'
import { generationJobsKey, useGenerationEvents } from '../../hooks/useGenerationEvents'
import type { GenerationJob } from '../../types/generation'
import type { Scene, SceneCreate } from '../../types/scene'
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

type CreateVariables = {
  projectId: string
  scene: SceneCreate
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
  const [createOpen, setCreateOpen] = useState(false)
  const [createTitle, setCreateTitle] = useState('')
  const [createDuration, setCreateDuration] = useState('5')
  const [createValidationError, setCreateValidationError] = useState<string | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)

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
  const createMutation = useMutation({
    mutationFn: ({ projectId: createProjectId, scene }: CreateVariables) => createScene(createProjectId, scene),
    onSuccess: (createdScene, variables) => {
      queryClient.setQueryData<Scene[]>(sceneQueryKey(variables.projectId), (currentScenes = []) =>
        [...currentScenes, createdScene].sort((left, right) => left.scene_number - right.scene_number),
      )
      setCreateOpen(false)
      setCreateTitle('')
      setCreateDuration('5')
      setCreateValidationError(null)
      setCreateError(null)
    },
    onError: (error) => {
      setCreateError(apiErrorMessage(error, '创建分镜失败'))
    },
  })
  const reorderMutation = useMutation({
    mutationFn: ({ projectId: reorderProjectId, sceneIds }: ReorderVariables) => reorderScenes(reorderProjectId, sceneIds),
    onSuccess: (reorderedScenes, variables) => {
      queryClient.setQueryData(sceneQueryKey(variables.projectId), reorderedScenes)
    },
    onError: (error, variables) => {
      queryClient.setQueryData(sceneQueryKey(variables.projectId), variables.previousScenes)

      setReorderError({
        projectId: variables.projectId,
        message: apiErrorMessage(error, '分镜排序保存失败'),
      })
    },
    onSettled: () => {
      reorderLockRef.current = false
    },
  })
  const generateMutation = useMutation({ mutationFn: (scene: Scene) => generateScene(scene.id, scene.workflow_template_id!), onSuccess: (submitted, scene) => queryClient.setQueryData<GenerationJob[]>(generationJobsKey(scene.id), (jobs = []) => [{ id: submitted.job_id, scene_id: scene.id, status: submitted.status }, ...jobs]) })
  const cancelMutation = useMutation({
    mutationFn: (job: GenerationJob) => cancelGenerationJob(job.id),
    onSuccess: (cancelledJob) => {
      queryClient.setQueryData<GenerationJob[]>(generationJobsKey(cancelledJob.scene_id), (jobs = []) =>
        jobs.map((job) => (job.id === cancelledJob.id ? { ...job, ...cancelledJob } : job)),
      )
    },
  })
  const retryMutation = useMutation({
    mutationFn: (job: GenerationJob) => retryGenerationJob(job.id),
    onSuccess: (_submitted, job) => {
      void queryClient.invalidateQueries({ queryKey: generationJobsKey(job.scene_id) })
    },
  })
  const isSorting = draggingSceneId !== null || reorderMutation.isPending
  const dragDisabled = scenes.length < 2 || reorderMutation.isPending

  function handleOpenCreate() {
    if (projectId === null || createMutation.isPending) {
      return
    }
    setCreateTitle('')
    setCreateDuration('5')
    setCreateValidationError(null)
    setCreateError(null)
    setCreateOpen(true)
  }

  function handleCancelCreate() {
    if (createMutation.isPending) {
      return
    }
    setCreateOpen(false)
    setCreateTitle('')
    setCreateDuration('5')
    setCreateValidationError(null)
    setCreateError(null)
  }

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (projectId === null) {
      return
    }

    const title = createTitle.trim()
    const durationSeconds = Number(createDuration)
    if (title === '') {
      setCreateValidationError('标题不能为空')
      return
    }
    if (createDuration.trim() === '' || !Number.isFinite(durationSeconds) || durationSeconds <= 0) {
      setCreateValidationError('时长必须是大于 0 的有效数字')
      return
    }

    setCreateValidationError(null)
    setCreateError(null)
    createMutation.mutate({
      projectId,
      scene: {
        title,
        duration_seconds: durationSeconds,
      },
    })
  }

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
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-[color:var(--text-muted)]">{scenes.length} 个镜头</span>
          <button
            type="button"
            disabled={projectId === null || createOpen || createMutation.isPending}
            onClick={handleOpenCreate}
            className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-sm text-[color:var(--accent)] transition-colors hover:bg-[color:var(--surface-raised)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {createMutation.isPending ? '创建中...' : '+ 新建分镜'}
          </button>
        </div>
      </div>

      {projectId !== null && createOpen ? (
        <form noValidate onSubmit={handleCreate} className="mt-5 border border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-4 sm:p-5">
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--accent)]">NEW SCENE</p>
          <h3 className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">新建分镜</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="create-scene-title" className="text-xs text-[color:var(--text-primary)]">标题</label>
              <input
                id="create-scene-title"
                value={createTitle}
                onChange={(event) => {
                  setCreateTitle(event.target.value)
                  setCreateValidationError(null)
                  setCreateError(null)
                }}
                aria-invalid={createValidationError !== null}
                aria-describedby={createValidationError ? 'create-scene-error' : undefined}
                disabled={createMutation.isPending}
                className={inputClassName}
              />
            </div>
            <div>
              <label htmlFor="create-scene-duration" className="text-xs text-[color:var(--text-primary)]">时长（秒）</label>
              <input
                id="create-scene-duration"
                type="number"
                min="0"
                step="any"
                value={createDuration}
                onChange={(event) => {
                  setCreateDuration(event.target.value)
                  setCreateValidationError(null)
                  setCreateError(null)
                }}
                aria-invalid={createValidationError !== null}
                aria-describedby={createValidationError ? 'create-scene-error' : undefined}
                disabled={createMutation.isPending}
                className={inputClassName}
              />
            </div>
          </div>
          {createValidationError ? <p id="create-scene-error" role="alert" className="mt-3 text-xs text-[color:var(--status-offline)]">{createValidationError}</p> : null}
          {createError ? <p role="alert" className="mt-3 text-xs text-[color:var(--status-offline)]">{createError}</p> : null}
          <div className="mt-4 flex justify-end gap-3">
            <button type="button" onClick={handleCancelCreate} disabled={createMutation.isPending} className="border border-[color:var(--border-subtle)] px-4 py-2 text-sm text-[color:var(--text-muted)] hover:border-[color:var(--accent)] hover:text-[color:var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50">取消</button>
            <button type="submit" disabled={createMutation.isPending} className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-sm text-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-50">{createMutation.isPending ? '创建中...' : '创建'}</button>
          </div>
        </form>
      ) : null}

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
            {apiErrorMessage(scenesQuery.error, '分镜加载失败')}
          </p>
        </section>
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length === 0 ? (
        <EmptySceneState
          title="暂无分镜"
          description="创建第一个分镜开始制作。"
          onCreate={handleOpenCreate}
          createDisabled={createOpen || createMutation.isPending}
        />
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length > 0 ? (
        <section className="mt-5 space-y-3" aria-label="分镜列表">
          {scenes.map((scene, index) => (
            <SceneCard
              key={scene.id}
              scene={scene}
              generationJob={jobsByScene.get(scene.id)}
              generating={generateMutation.isPending && generateMutation.variables?.id === scene.id}
              cancelling={cancelMutation.isPending && cancelMutation.variables?.id === jobsByScene.get(scene.id)?.id}
              retrying={retryMutation.isPending && retryMutation.variables?.id === jobsByScene.get(scene.id)?.id}
              generationError={
                generateMutation.isError && generateMutation.variables?.id === scene.id
                  ? apiErrorMessage(generateMutation.error, '生成提交失败')
                  : null
              }
              cancelError={
                cancelMutation.isError && cancelMutation.variables?.id === jobsByScene.get(scene.id)?.id
                  ? apiErrorMessage(cancelMutation.error, '取消任务失败，请重试。')
                  : null
              }
              retryError={
                retryMutation.isError && retryMutation.variables?.id === jobsByScene.get(scene.id)?.id
                  ? apiErrorMessage(retryMutation.error, '重试任务失败，请重试。')
                  : null
              }
              onGenerate={(target) => generateMutation.mutate(target)}
              onCancel={(job) => cancelMutation.mutate(job)}
              onRetry={(job) => retryMutation.mutate(job)}
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
  onCreate?: () => void
  createDisabled?: boolean
}

function EmptySceneState({ title, description, onCreate, createDisabled = false }: EmptySceneStateProps) {
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
        {onCreate ? (
          <button
            type="button"
            onClick={onCreate}
            disabled={createDisabled}
            className="mt-5 border border-[color:var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-sm text-[color:var(--accent)] transition-colors hover:bg-[color:var(--canvas)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            + 新建分镜
          </button>
        ) : null}
      </div>
    </section>
  )
}

const inputClassName =
  'mt-2 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[color:var(--text-primary)] outline-none focus:border-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-60'
