import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, configureApi, REQUEST_TIMEOUT_MS } from '../lib/api'
import { json } from './utils'

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('sends the bearer token and unwraps the data envelope', async () => {
    const fetchMock = vi.fn(() => json({ data: { status: 'ok' } }))
    vi.stubGlobal('fetch', fetchMock)
    configureApi({ getToken: () => 'abc', onUnauthorized: () => {} })

    await expect(api.appointmentStats()).resolves.toEqual({ status: 'ok' })
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer abc')
  })

  it('keeps pagination meta for list endpoints and drops empty params', async () => {
    const fetchMock = vi.fn(() => json({ data: [], meta: { page: 1, total: 0 } }))
    vi.stubGlobal('fetch', fetchMock)
    configureApi({ getToken: () => 'abc', onUnauthorized: () => {} })

    const result = await api.listAppointments({ q: '', status: 'pending', page: 2 })
    expect(result).toEqual({ data: [], meta: { page: 1, total: 0 } })
    const url = new URL(fetchMock.mock.calls[0][0])
    expect(url.searchParams.get('status')).toBe('pending')
    expect(url.searchParams.has('q')).toBe(false)
  })

  it('turns error bodies into ApiError with code and field details', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ error: { code: 'INVALID_INPUT', message: 'Bad', details: { symptoms: 'Required' } } }, 400)))
    configureApi({ getToken: () => 'abc', onUnauthorized: () => {} })

    const error = await api.createAppointment({}).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 400, code: 'INVALID_INPUT', details: { symptoms: 'Required' } })
  })

  it('notifies the auth layer when an authenticated request gets 401', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ error: { code: 'TOKEN_EXPIRED', message: 'Expired' } }, 401)))
    const onUnauthorized = vi.fn()
    configureApi({ getToken: () => 'abc', onUnauthorized })

    await expect(api.me()).rejects.toMatchObject({ code: 'TOKEN_EXPIRED' })
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('reports network failures clearly', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
    configureApi({ getToken: () => null, onUnauthorized: () => {} })
    await expect(api.health()).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })

  it('gives up on a hung request instead of spinning forever', async () => {
    vi.useFakeTimers()
    try {
      // A server that never answers: the promise only settles when the request is aborted.
      vi.stubGlobal('fetch', vi.fn((url, { signal }) => new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })))
      configureApi({ getToken: () => null, onUnauthorized: () => {} })

      const pending = api.login('frontdesk1', 'pw').catch((e) => e)
      await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS)
      await expect(pending).resolves.toMatchObject({ code: 'TIMEOUT' })
    } finally {
      vi.useRealTimers()
    }
  })
})
