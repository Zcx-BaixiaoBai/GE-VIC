/**
 * ??????? (Canvas) - ?????????????
 *
 * ??:
 *   - ?? <= 1920px (4K ?????, ??/???????)
 *   - JPEG ?? 0.85 (??????, ??? 70-80%)
 *   - 5MB iPhone ?? -> ~500KB
 *
 * ??:
 *   - ?? (mime ?? video/) - ???
 *   - GIF  - ????
 *   - ? < 800KB ??? - ?????
 *   - HEIC - ??? canvas ???, ????? (worker ????)
 */
export interface CompressOptions {
  /** ??????, ?? 1920 */
  maxLongEdge?: number
  /** JPEG ?? 0-1, ?? 0.85 */
  quality?: number
  /** ?????????? (??), ?? 800KB */
  skipUnderBytes?: number
  /** ???? (???????) */
  onProgress?: (info: { stage: 'loading' | 'compressing' | 'done' | 'skipped' }) => void
}

export interface CompressResult {
  file: File
  /** ???? */
  originalSize: number
  /** ????? */
  compressedSize: number
  /** ??????? (false=??) */
  compressed: boolean
  /** ????? */
  skipReason?: string
}

const DEFAULTS = {
  maxLongEdge: 1920,
  quality: 0.85,
  skipUnderBytes: 800 * 1024,
}

/** ????????? (???? HEIC: Safari OK, Chrome/Firefox ??) */
function canDecode(mime: string): boolean {
  // ?? Chrome/Firefox ??? canvas ?? HEIC
  if (/heic|heif/i.test(mime)) return false
  // ico / svg ????
  if (mime === 'image/svg+xml' || mime === 'image/x-icon') return false
  return mime.startsWith('image/')
}

async function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = (e) => {
      URL.revokeObjectURL(url)
      reject(new Error(`image load failed: ${file.type}`))
    }
    img.src = url
  })
}

function calcTargetSize(w: number, h: number, maxEdge: number): { w: number; h: number } {
  if (w <= maxEdge && h <= maxEdge) return { w, h }
  if (w >= h) {
    return { w: maxEdge, h: Math.round((h * maxEdge) / w) }
  }
  return { w: Math.round((w * maxEdge) / h), h: maxEdge }
}

function canvasToFile(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error('toBlob returned null'))),
      type,
      quality,
    )
  })
}

export async function compressImage(
  file: File,
  opts: CompressOptions = {},
): Promise<CompressResult> {
  const o = { ...DEFAULTS, ...opts }
  const originalSize = file.size

  // 1) ????
  if (file.type.startsWith('video/')) {
    return { file, originalSize, compressedSize: file.size, compressed: false, skipReason: 'video' }
  }
  // 2) ??? (? HEIC/SVG/ICO) ??
  if (!canDecode(file.type)) {
    return { file, originalSize, compressedSize: file.size, compressed: false, skipReason: 'non-decodable' }
  }
  // 3) ????
  if (file.size < o.skipUnderBytes) {
    opts.onProgress?.({ stage: 'skipped' })
    return { file, originalSize, compressedSize: file.size, compressed: false, skipReason: 'already-small' }
  }

  try {
    opts.onProgress?.({ stage: 'loading' })
    const img = await loadImage(file)
    const { w: tw, h: th } = calcTargetSize(img.naturalWidth, img.naturalHeight, o.maxLongEdge)

    opts.onProgress?.({ stage: 'compressing' })
    const canvas = document.createElement('canvas')
    canvas.width = tw
    canvas.height = th
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas 2d not available')
    // ???? PNG ?????
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, tw, th)
    ctx.drawImage(img, 0, 0, tw, th)

    // ??: jpeg ??; ??? png ????????? png
    const isPng = file.type === 'image/png'
    const outType = isPng ? 'image/png' : 'image/jpeg'
    const quality = isPng ? undefined : o.quality
    const blob = await canvasToFile(canvas, outType, quality ?? 0.92)
    const newName = isPng
      ? file.name.replace(/\.png$/i, '.png')
      : file.name.replace(/\.(png|webp|bmp|gif)$/i, '.jpg')
    const compressed = new File([blob], newName, { type: outType, lastModified: Date.now() })
    opts.onProgress?.({ stage: 'done' })
    return {
      file: compressed,
      originalSize,
      compressedSize: compressed.size,
      compressed: true,
    }
  } catch (e) {
    // ?????? (HEIC ? Chrome/Firefox ???)
    return {
      file,
      originalSize,
      compressedSize: file.size,
      compressed: false,
      skipReason: `compress-failed: ${(e as Error).message}`,
    }
  }
}

export function useImageCompress() {
  return { compressImage }
}
