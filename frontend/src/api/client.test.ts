import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, OFFLINE_MESSAGE, request } from './client'

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request', () => {
  it('returns parsed JSON on success and sends JSON bodies', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(request('POST', '/api/x', { a: 1 })).resolves.toEqual({ ok: 1 })
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(init.body).toBe('{"a":1}')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('turns backend error bodies into ApiError with the backend message', async () => {
    mockFetch(async () => new Response(JSON.stringify({ error: { code: 'not_ready', message: 'Resolve errors first.' } }), { status: 409 }))
    const err = await request('POST', '/api/x').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ code: 'not_ready', message: 'Resolve errors first.', status: 409 })
  })

  it('reports an unreachable backend clearly', async () => {
    mockFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    const err = await request('GET', '/api/health').catch((e) => e)
    expect(err).toMatchObject({ code: 'offline', message: OFFLINE_MESSAGE, status: 0 })
  })

  it('treats a proxy 502 without a JSON body as offline', async () => {
    mockFetch(async () => new Response('Bad gateway', { status: 502 }))
    const err = await request('GET', '/api/health').catch((e: unknown) => e)
    expect(err).toMatchObject({ code: 'offline', message: OFFLINE_MESSAGE })
  })

  it('gives a generic message for other non-JSON errors', async () => {
    mockFetch(async () => new Response('oops', { status: 500 }))
    const err = await request('GET', '/api/x').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 500, message: 'The server answered with an error (HTTP 500).' })
  })

  it('returns undefined for 204 responses', async () => {
    mockFetch(async () => new Response(null, { status: 204 }))
    await expect(request('DELETE', '/api/x')).resolves.toBeUndefined()
  })
})
