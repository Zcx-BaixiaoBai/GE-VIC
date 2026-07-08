/**
 * TUS 1.0.0 ??? - ??????????
 *
 * ??:
 *   - ???? (onProgress)
 *   - ?????? + ?? (HEAD ? offset ??????)
 *   - ?????: localStorage ??? session ??
 *   - ????: ???? (? size+name ??) ??? session
 *
 * ???? (tus.io 1.0.0):
 *   - POST /uploads  -> 201 + Location: /uploads/{id}
 *   - HEAD /uploads/{id} -> Upload-Offset
 *   - PATCH /uploads/{id} (Upload-Offset + body) -> 204 + Upload-Offset
 *   - DELETE /uploads/{id} -> 204
 */
const TUS_VERSION = '1.0.0'
const DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024 // 8MB (larger chunks = fewer requests, better for high-latency links like cpolar)
const STORAGE_PREFIX = 'gevic-tus-'
const MAX_RETRIES = 5

export interface TusUploadOptions {
  /** ????, ?? 5MB */
  chunkSize?: number
  /** TUS ???? URL, ???? origin + /api/v1/uploads */
  endpoint?: string
  /** TUS ?????, ?? algorithm_code / file_hash */
  metadata?: Record<string, string>
  /** ???? (0-1) */
  onProgress?: (frac: number) => void
  /** ???? */
  onStatus?: (status: 'starting' | 'uploading' | 'paused' | 'resuming' | 'done' | 'error') => void
  /** ????, ?? true ????? */
  onRetry?: (err: Error, attempt: number) => boolean | Promise<boolean>
}

export interface TusUploadResult {
  /** session id (URL ??) */
  sessionId: string
  /** ????? */
  totalSize: number
}

interface StoredSession {
  id: string
  endpoint: string
  totalSize: number
  filename: string
  createdAt: number
}

/** ?????? (????????) - ?? hash ??, ??????? */
function quickFingerprint(file: File): string {
  return `${file.size}-${file.name}-${(file as any).lastModified ?? 0}`
}

function loadStored(fingerprint: string): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + fingerprint)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredSession
    // 24h ??
    if (Date.now() - parsed.createdAt > 24 * 3600 * 1000) {
      localStorage.removeItem(STORAGE_PREFIX + fingerprint)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

function saveStored(fingerprint: string, sess: StoredSession) {
  try {
    localStorage.setItem(STORAGE_PREFIX + fingerprint, JSON.stringify(sess))
  } catch {
    /* quota ?, ?? */
  }
}

function clearStored(fingerprint: string) {
  try {
    localStorage.removeItem(STORAGE_PREFIX + fingerprint)
  } catch { /* ignore */ }
}

function metaB64(md: Record<string, string>): string {
  return Object.entries(md)
    .map(([k, v]) => `${k} ${btoa(unescape(encodeURIComponent(v)))}`)
    .join(',')
}

/** ? XHR ? PATCH, ????? upload.onprogress */
function patchChunk(
  url: string,
  offset: number,
  blob: Blob,
  onProgress: (loaded: number, total: number) => void,
): Promise<number> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PATCH', url, true)
    xhr.setRequestHeader('Tus-Resumable', TUS_VERSION)
    xhr.setRequestHeader('Upload-Offset', String(offset))
    xhr.setRequestHeader('Content-Type', 'application/offset+octet-stream')
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded, e.total)
    }
    xhr.onload = () => {
      if (xhr.status === 204) {
        const newOffset = Number(xhr.getResponseHeader('Upload-Offset') ?? offset + blob.size)
        resolve(newOffset)
      } else {
        reject(new Error(`PATCH ${xhr.status}: ${xhr.responseText?.slice(0, 200) ?? ''}`))
      }
    }
    xhr.onerror = () => reject(new Error('network error during PATCH'))
    xhr.onabort = () => reject(new Error('aborted'))
    xhr.send(blob)
  })
}

async function headOffset(url: string): Promise<number | null> {
  const r = await fetch(url, { method: 'HEAD' })
  if (r.status === 404) return null
  if (!r.ok) throw new Error(`HEAD ${r.status}`)
  return Number(r.headers.get('Upload-Offset') ?? 0)
}

async function createSession(
  endpoint: string,
  file: File,
  metadata: Record<string, string>,
): Promise<string> {
  const r = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Tus-Resumable': TUS_VERSION,
      'Upload-Length': String(file.size),
      'Upload-Metadata': metaB64(metadata),
    },
  })
  if (r.status !== 201) {
    throw new Error(`create session failed: ${r.status} ${await r.text()}`)
  }
  const loc = r.headers.get('Location')
  if (!loc) throw new Error('create session: no Location header')
  // Location ????? URL, ?? session id
  return loc.split('/').pop()!
}

export async function tusUpload(
  file: File,
  opts: TusUploadOptions = {},
): Promise<TusUploadResult> {
  const endpoint = opts.endpoint ?? `${window.location.origin}/api/v1/uploads`
  const chunkSize = opts.chunkSize ?? DEFAULT_CHUNK_SIZE
  const fingerprint = quickFingerprint(file)
  const metadata: Record<string, string> = {
    filename: file.name,
    filetype: file.type || 'application/octet-stream',
    file_type: file.type.startsWith('video/') ? 'video' : (file.type.startsWith('image/') ? 'image' : 'other'),
    ...opts.metadata,
  }

  // 1) ??? session (????) ???
  const stored = loadStored(fingerprint)
  let sessionId = ''
  let sessionUrl = ''
  let startOffset = 0

  if (stored && stored.endpoint === endpoint && stored.totalSize === file.size) {
    sessionId = stored.id
    sessionUrl = `${endpoint}/${sessionId}`
    opts.onStatus?.('resuming')
    const head = await headOffset(sessionUrl)
    if (head === null) {
      // ? session ????? GC - ?????????
      clearStored(fingerprint)
      sessionId = ''
      sessionUrl = ''
    } else {
      startOffset = head
      if (startOffset === file.size) {
        // ??? - ????
        opts.onProgress?.(1)
        opts.onStatus?.('done')
        return { sessionId, totalSize: file.size }
      }
    }
  }

  if (!sessionId) {
    opts.onStatus?.('starting')
    sessionId = await createSession(endpoint, file, metadata)
    sessionUrl = `${endpoint}/${sessionId}`
    saveStored(fingerprint, {
      id: sessionId,
      endpoint,
      totalSize: file.size,
      filename: file.name,
      createdAt: Date.now(),
    })
  }

  opts.onStatus?.('uploading')

  // 2) ????
  let offset = startOffset
  while (offset < file.size) {
    const end = Math.min(offset + chunkSize, file.size)
    const blob = file.slice(offset, end)
    let attempt = 0
    let success = false
    while (!success && attempt < MAX_RETRIES) {
      try {
        const newOffset = await patchChunk(
          sessionUrl,
          offset,
          blob,
          (loaded) => {
            const frac = (offset + loaded) / file.size
            opts.onProgress?.(frac)
          },
        )
        offset = newOffset
        success = true
      } catch (e) {
        attempt++
        const err = e as Error
        const shouldRetry = opts.onRetry ? await opts.onRetry(err, attempt) : attempt < MAX_RETRIES
        if (!shouldRetry) {
          clearStored(fingerprint)
          opts.onStatus?.('error')
          throw err
        }
        // ????? - ? HEAD ??? offset
        await new Promise((r) => setTimeout(r, Math.min(1000 * 2 ** attempt, 15000)))
        const head = await headOffset(sessionUrl)
        if (head !== null) offset = head
      }
    }
  }

  // 3) ??
  clearStored(fingerprint)
  opts.onProgress?.(1)
  opts.onStatus?.('done')
  return { sessionId, totalSize: file.size }
}

export function useTusUpload() {
  return { tusUpload }
}
