export class ApiRequestError extends Error {
  readonly code: string
  readonly status: number | null

  constructor(code: string, message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.status = status
  }
}

export type ApiErrorPayload = {
  code: string
  message: string
}

export type ApiEnvelope<T> = {
  data: T | null
  error: ApiErrorPayload | null
}

const networkErrorMessage = '无法连接本地服务，请确认后端已启动。'
const invalidResponseMessage = '服务返回异常，请稍后重试。'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  return (
    isRecord(value) &&
    typeof value.code === 'string' &&
    typeof value.message === 'string'
  )
}

function isApiEnvelope<T>(value: unknown): value is ApiEnvelope<T> {
  return (
    isRecord(value) &&
    'data' in value &&
    'error' in value &&
    (value.error === null || isApiErrorPayload(value.error))
  )
}

export async function fetchApi(input: RequestInfo, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw new ApiRequestError('API_NETWORK_ERROR', networkErrorMessage, null)
  }
}

export async function readApiError(
  response: Response,
  fallbackCode: string,
  fallbackMessage: string,
): Promise<ApiRequestError> {
  try {
    const payload: unknown = await response.json()
    if (isApiEnvelope(payload) && payload.error !== null) {
      return new ApiRequestError(payload.error.code, payload.error.message, response.status)
    }
  } catch {
    // The endpoint may return a non-JSON error response.
  }

  return new ApiRequestError(fallbackCode, fallbackMessage, response.status)
}

export async function requestJson<T>(
  input: RequestInfo,
  init: RequestInit | undefined,
  fallbackCode: string,
  fallbackMessage: string,
): Promise<T> {
  const response = await fetchApi(input, init)

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ApiRequestError(
      response.ok ? 'API_INVALID_RESPONSE' : fallbackCode,
      response.ok ? invalidResponseMessage : fallbackMessage,
      response.status,
    )
  }

  if (!isApiEnvelope<T>(payload)) {
    throw new ApiRequestError(
      response.ok ? 'API_INVALID_RESPONSE' : fallbackCode,
      response.ok ? invalidResponseMessage : fallbackMessage,
      response.status,
    )
  }

  if (!response.ok) {
    if (payload.error !== null) {
      throw new ApiRequestError(payload.error.code, payload.error.message, response.status)
    }
    throw new ApiRequestError(fallbackCode, fallbackMessage, response.status)
  }

  if (payload.error !== null) {
    throw new ApiRequestError(payload.error.code, payload.error.message, response.status)
  }

  return payload.data as T
}
