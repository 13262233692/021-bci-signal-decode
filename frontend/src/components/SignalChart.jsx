import { useEffect, useRef, useCallback, useState } from 'react'

const CHANNEL_GAP = 60
const LABEL_PADDING_LEFT = 70
const LABEL_PADDING_RIGHT = 30
const PADDING_TOP = 20
const PADDING_BOTTOM = 50
const SLIDER_HEIGHT = 20

const COLOR_PALETTE = [
  '#58a6ff', '#3fb950', '#f85149', '#d29922', '#bc8cff',
  '#f778ba', '#39d0d8', '#ffa657', '#8b949e', '#79c0ff',
  '#56d364', '#ff7b72', '#e3b341', '#a371f7', '#db61a2',
  '#56d4dd', '#ffa14f', '#6e7681', '#1f6feb', '#238636',
  '#da3633', '#9e6a03', '#8957e5', '#bf3989', '#0e7490',
  '#9a6700', '#30363d', '#0969da', '#2ea043', '#ff6b6b',
  '#b08800', '#9860e0', '#c2410c', '#0891b2', '#854d0e',
  '#484f58', '#2563eb', '#16a34a', '#dc2626', '#ca8a04',
  '#7c3aed', '#be185d', '#0891b2', '#ea580c', '#3f3f46',
  '#3b82f6', '#22c55e', '#ef4444', '#eab308', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#52525b', '#6366f1',
  '#4ade80', '#f87171', '#facc15', '#a78bfa', '#f472b6',
  '#22d3ee', '#fb923c', '#71717a'
]

export default function SignalChart({ subscribe, numChannels = 64 }) {
  const containerRef = useRef(null)
  const canvasRef = useRef(null)
  const bgCanvasRef = useRef(null)
  const bufferRef = useRef(null)
  const stateRef = useRef({
    width: 1200,
    height: 700,
    chartX: LABEL_PADDING_LEFT,
    chartY: PADDING_TOP,
    chartWidth: 1200 - LABEL_PADDING_LEFT - LABEL_PADDING_RIGHT,
    chartHeight: 700 - PADDING_TOP - PADDING_BOTTOM - SLIDER_HEIGHT,
    viewStart: 0,
    viewEnd: 1,
    rafId: null,
    lastCount: -1,
    bgDirty: true,
    waveDirty: true,
    currentFps: 0
  })
  const [fps, setFps] = useState(0)

  const colors = COLOR_PALETTE.slice(0, numChannels)

  const drawBackground = useCallback(() => {
    const state = stateRef.current
    const bgCanvas = bgCanvasRef.current
    if (!bgCanvas) return

    const ctx = bgCanvas.getContext('2d')
    const { chartX, chartY, chartWidth, chartHeight } = state

    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, state.width, state.height)

    ctx.strokeStyle = '#161b22'
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let ch = 0; ch <= numChannels; ch++) {
      const y = chartY + (ch / numChannels) * chartHeight
      ctx.moveTo(chartX, y + 0.5)
      ctx.lineTo(chartX + chartWidth, y + 0.5)
    }
    ctx.stroke()

    ctx.font = 'bold 10px monospace'
    ctx.textBaseline = 'middle'
    ctx.textAlign = 'right'
    for (let ch = 0; ch < numChannels; ch++) {
      const y = chartY + ((ch + 0.5) / numChannels) * chartHeight
      ctx.fillStyle = colors[ch]
      ctx.fillText(`Ch${String(ch + 1).padStart(2, '0')}`, chartX - 8, y)
    }

    const canvasCtx = canvasRef.current?.getContext('2d')
    if (canvasCtx) {
      canvasCtx.drawImage(bgCanvas, 0, 0)
    }

    state.bgDirty = false
  }, [numChannels, colors])

  const drawWaves = useCallback(() => {
    const state = stateRef.current
    const buffer = bufferRef.current
    if (!buffer || buffer.length === 0) return

    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return

    const { chartX, chartY, chartWidth, chartHeight } = state

    if (state.bgDirty) {
      drawBackground()
    }

    ctx.clearRect(chartX - 1, chartY - 1, chartWidth + 2, chartHeight + 2)

    const viewStartIdx = Math.floor(state.viewStart * (buffer.length - 1))
    const viewEndIdx = Math.floor(state.viewEnd * (buffer.length - 1))
    const viewCount = viewEndIdx - viewStartIdx

    if (viewCount < 2) return

    const sampleStep = Math.max(1, Math.floor(viewCount / (chartWidth * 2)))
    const drawCount = Math.floor(viewCount / sampleStep)

    const channelHeight = chartHeight / numChannels
    const yScale = channelHeight * 0.7

    for (let ch = 0; ch < numChannels; ch++) {
      const baseY = chartY + ((ch + 0.5) / numChannels) * chartHeight
      const scale = yScale / 80

      ctx.strokeStyle = colors[ch]
      ctx.lineWidth = 1
      ctx.beginPath()

      let first = true
      let lastX = -1

      for (let i = 0; i < drawCount; i++) {
        const bufferIdx = viewStartIdx + i * sampleStep
        const value = buffer.getSample(ch, bufferIdx)
        const x = chartX + (i / (drawCount - 1)) * chartWidth
        const y = baseY - value * scale

        if (x === lastX) continue

        if (first) {
          ctx.moveTo(x, y)
          first = false
        } else {
          ctx.lineTo(x, y)
        }
        lastX = x
      }

      ctx.stroke()
    }

    state.waveDirty = false
    state.lastCount = buffer.length
  }, [numChannels, colors, drawBackground])

  const renderLoop = useCallback(() => {
    const state = stateRef.current
    const buffer = bufferRef.current
    const now = performance.now()

    if (buffer && buffer.length !== state.lastCount) {
      state.waveDirty = true
    }

    if (state.bgDirty) drawBackground()
    if (state.waveDirty) drawWaves()

    if (!state._frameCount) state._frameCount = 0
    if (!state._lastFpsTime) state._lastFpsTime = now
    state._frameCount++

    if (now - state._lastFpsTime >= 1000) {
      state.currentFps = state._frameCount
      setFps(state._frameCount)
      state._frameCount = 0
      state._lastFpsTime = now
    }

    state.rafId = requestAnimationFrame(renderLoop)
  }, [drawBackground, drawWaves])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const dpr = window.devicePixelRatio || 1
    const rect = container.getBoundingClientRect()
    const width = rect.width || 1200
    const height = rect.height || 700

    stateRef.current.width = width
    stateRef.current.height = height
    stateRef.current.chartWidth = width - LABEL_PADDING_LEFT - LABEL_PADDING_RIGHT
    stateRef.current.chartHeight = height - PADDING_TOP - PADDING_BOTTOM - SLIDER_HEIGHT

    const canvas = document.createElement('canvas')
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = width + 'px'
    canvas.style.height = height + 'px'
    canvas.style.position = 'absolute'
    canvas.style.left = '0'
    canvas.style.top = '0'
    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    canvasRef.current = canvas

    const bgCanvas = document.createElement('canvas')
    bgCanvas.width = width * dpr
    bgCanvas.height = height * dpr
    const bgCtx = bgCanvas.getContext('2d')
    bgCtx.setTransform(dpr, 0, 0, dpr, 0, 0)
    bgCanvasRef.current = bgCanvas

    container.innerHTML = ''
    container.appendChild(canvas)

    stateRef.current.rafId = requestAnimationFrame(renderLoop)

    const unsubscribe = subscribe((buffer) => {
      bufferRef.current = buffer
      stateRef.current.waveDirty = true
      if (stateRef.current.viewEnd === 1 && buffer.length > 3000) {
        stateRef.current.viewStart = 1 - 3000 / buffer.length
      }
    })

    window.getChartStats = () => ({
      fps: stateRef.current.currentFps,
      frameTime: 0,
      bufferSize: bufferRef.current?.length || 0
    })

    return () => {
      unsubscribe()
      if (window.getChartStats) {
        delete window.getChartStats
      }
      if (stateRef.current.rafId) {
        cancelAnimationFrame(stateRef.current.rafId)
      }
    }
  }, [subscribe, renderLoop])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div style={{
        position: 'absolute',
        top: 10,
        right: 24,
        fontSize: 11,
        fontFamily: 'monospace',
        color: '#3fb950',
        zIndex: 10
      }}>
        ● {fps} FPS · Canvas 2D · 零 GC
      </div>
    </div>
  )
}
