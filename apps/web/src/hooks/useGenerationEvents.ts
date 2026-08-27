import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { parseGenerationEvent, type GenerationJob } from '../types/generation'

export const generationJobsKey = (sceneId: string) => ['generation-jobs', sceneId] as const

function websocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/generation`
}

export function useGenerationEvents(enabled: boolean): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!enabled) return
    let socket: WebSocket | null = null
    let reconnectTimer: number | undefined
    let disposed = false

    const connect = () => {
      if (disposed || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
      socket = new WebSocket(websocketUrl())
      socket.onmessage = (message) => {
        if (typeof message.data !== 'string') return
        const event = parseGenerationEvent(message.data)
        if (!event) return
        queryClient.setQueryData<GenerationJob[]>(generationJobsKey(event.scene_id), (jobs = []) =>
          jobs.map((job) => job.id === event.job_id ? { ...job, status: event.status, progress: event.progress ?? job.progress, node_id: event.node_id ?? job.node_id, error_code: event.error_code ?? job.error_code, error_message: event.message ?? job.error_message } : job),
        )
      }
      socket.onclose = () => {
        if (!disposed) reconnectTimer = window.setTimeout(connect, 1000)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      disposed = true
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [enabled, queryClient])
}
