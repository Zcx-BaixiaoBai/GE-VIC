import { test, expect } from '@playwright/test'

// ? TUS ?? + ???? + ?????
// ????????? UI, ??? API, ????

test.describe('TUS resumable upload protocol', () => {
  test('OPTIONS /api/v1/uploads ?? TUS ???', async ({ request }) => {
    const r = await request.fetch('http://127.0.0.1:8000/api/v1/uploads', { method: 'OPTIONS' })
    expect(r.status()).toBe(204)
    expect(r.headers()['tus-resumable']).toBe('1.0.0')
    expect(r.headers()['tus-version']).toBe('1.0.0')
    expect(r.headers()['tus-extension']).toContain('creation')
    expect(r.headers()['tus-extension']).toContain('termination')
    expect(Number(r.headers()['tus-max-size'])).toBeGreaterThan(0)
  })

  test('POST /api/v1/uploads ???? (Creation-With-Upload)', async ({ request }) => {
    const body = Buffer.alloc(100, 0x41) // 100 bytes of 'A'
    const r = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: {
        'Tus-Resumable': '1.0.0',
        'Upload-Length': '100',
        'Content-Type': 'application/offset+octet-stream',
      },
      data: body,
    })
    expect(r.status()).toBe(201)
    expect(r.headers()['location']).toMatch(/\/api\/v1\/uploads\/[a-f0-9]{32}$/)
    expect(r.headers()['upload-offset']).toBe('100')
  })

  test('?? TUS ??: ?? -> ?? -> HEAD ?? -> ??', async ({ request }) => {
    const total = 1024 * 100 // 100KB
    // 1) ??
    const create = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: { 'Tus-Resumable': '1.0.0', 'Upload-Length': String(total) },
    })
    expect(create.status()).toBe(201)
    const loc = create.headers()['location']!
    expect(create.headers()['upload-offset']).toBe('0')

    // 2) ?? 1: 50KB
    const chunk1 = Buffer.alloc(50 * 1024, 0x01)
    const p1 = await request.fetch(loc, {
      method: 'PATCH',
      headers: { 'Upload-Offset': '0', 'Content-Type': 'application/offset+octet-stream', 'Tus-Resumable': '1.0.0' },
      data: chunk1,
    })
    expect(p1.status()).toBe(204)
    expect(p1.headers()['upload-offset']).toBe(String(50 * 1024))

    // 3) ???? -> HEAD ?? offset (??????)
    const head = await request.fetch(loc, { method: 'HEAD' })
    expect(head.status()).toBe(200)
    expect(head.headers()['upload-offset']).toBe(String(50 * 1024))
    expect(head.headers()['upload-length']).toBe(String(total))

    // 4) ???????? 50KB
    const chunk2 = Buffer.alloc(50 * 1024, 0x02)
    const p2 = await request.fetch(loc, {
      method: 'PATCH',
      headers: { 'Upload-Offset': String(50 * 1024), 'Content-Type': 'application/offset+octet-stream', 'Tus-Resumable': '1.0.0' },
      data: chunk2,
    })
    expect(p2.status()).toBe(204)
    expect(p2.headers()['upload-offset']).toBe(String(total))

    // 5) ???? status JSON
    const sid = loc.split('/').pop()!
    const status = await request.get(`http://127.0.0.1:8000/api/v1/uploads/${sid}/status`)
    expect(status.status()).toBe(200)
    const s = await status.json()
    expect(s.status).toBe('completed')
    expect(s.progress).toBe(1)
  })

  test('PATCH ?? offset -> 409', async ({ request }) => {
    const create = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: { 'Tus-Resumable': '1.0.0', 'Upload-Length': '1000' },
    })
    const loc = create.headers()['location']!
    // ??? PATCH: offset=0, 200 bytes -> ??? offset=200
    await request.fetch(loc, {
      method: 'PATCH',
      headers: { 'Upload-Offset': '0', 'Content-Type': 'application/offset+octet-stream' },
      data: Buffer.alloc(200, 0x01),
    })
    // ??? PATCH: ?? offset=999 -> 409
    const bad = await request.fetch(loc, {
      method: 'PATCH',
      headers: { 'Upload-Offset': '999', 'Content-Type': 'application/offset+octet-stream' },
      data: Buffer.alloc(10, 0x02),
    })
    expect(bad.status()).toBe(409)
  })

  test('DELETE ????', async ({ request }) => {
    const create = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: { 'Tus-Resumable': '1.0.0', 'Upload-Length': '500' },
    })
    const loc = create.headers()['location']!
    const sid = loc.split('/').pop()!
    const del = await request.fetch(loc, { method: 'DELETE' })
    expect(del.status()).toBe(204)
    // ? HEAD ????
    const head = await request.fetch(loc, { method: 'HEAD' })
    expect(head.status()).toBe(404)
  })

  test('?? Tus-Resumable ?? -> 412', async ({ request }) => {
    const r = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: { 'Tus-Resumable': '0.0.1', 'Upload-Length': '100' },
    })
    expect(r.status()).toBe(412)
  })

  test('?? Upload-Length (?? TUS_MAX_SIZE) -> 422', async ({ request }) => {
    const r = await request.post('http://127.0.0.1:8000/api/v1/uploads', {
      headers: { 'Tus-Resumable': '1.0.0', 'Upload-Length': '999999999999' },
    })
    // ????
    expect(r.status()).toBeGreaterThanOrEqual(400)
  })
})

test.describe('Inspect endpoint - size limits by file type', () => {
  // ?? inspect.py ? max_size ? file_type ????
  test('?? < 20MB ??? 413 ?? (??? bug)', async ({ request }) => {
    // 1KB ??, ??? max_size ??
    const r = await request.post('http://127.0.0.1:8000/api/v1/inspect/insulator-damage', {
      headers: { 'X-Inspector-Id': 'E2E-TUS-1' },
      multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.alloc(1024, 0xff) }, meta: '{}' },
    })
    // ???? 200/202/400/500, ????? 413 (1KB ??? 20MB ??)
    expect(r.status()).not.toBe(413)
  })

  test('??? 20MB ??? 413 ?? (??? bug)', async ({ request }) => {
    // 30MB ??, ????? 20MB ??????; ?????? 500MB
    const r = await request.post('http://127.0.0.1:8000/api/v1/inspect/insulator-damage', {
      headers: { 'X-Inspector-Id': 'E2E-TUS-1' },
      multipart: { file: { name: 'big.mp4', mimeType: 'video/mp4', buffer: Buffer.alloc(30 * 1024 * 1024, 0x01) }, meta: '{}' },
      timeout: 60000,
    })
    expect(r.status()).not.toBe(413)
  })
})
