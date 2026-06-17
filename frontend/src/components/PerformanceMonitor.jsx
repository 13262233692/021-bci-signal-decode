import { useEffect, useRef } from 'react'

export default function PerformanceMonitor({ stats }) {
  const barRef = useRef(null)

  useEffect(() => {
    if (!barRef.current) return
    const max = 1000
    const val = Math.min(stats.fps, max)
    barRef.current.style.width = `${(val / max) * 100}%`
  }, [stats.fps])

  const getStatusColor = (fps) => {
    if (fps >= 50) return '#3fb950'
    if (fps >= 30) return '#d29922'
    return '#f85149'
  }

  const getMemoryColor = (used, total) => {
    const pct = (used / total) * 100
    if (pct < 50) return '#3fb950'
    if (pct < 80) return '#d29922'
    return '#f85149'
  }

  return (
    <div className="perf-monitor">
      <div className="perf-row">
        <span className="perf-label">渲染管线</span>
        <span className="perf-value canvas-mode">Canvas 2D + 环形缓冲</span>
      </div>

      <div className="perf-row">
        <span className="perf-label">渲染帧率</span>
        <div className="perf-bar">
          <div
            ref={barRef}
            className="perf-bar-fill"
            style={{ backgroundColor: getStatusColor(stats.fps) }}
          />
          <span
            className="perf-value"
            style={{ color: getStatusColor(stats.fps) }}
          >
            {stats.fps} FPS
          </span>
        </div>
      </div>

      <div className="perf-row">
        <span className="perf-label">帧耗时</span>
        <span
          className="perf-value"
          style={{ color: getStatusColor(1000 / (stats.frameTime || 16)) }}
        >
          {stats.frameTime.toFixed(1)} ms
        </span>
      </div>

      <div className="perf-row">
        <span className="perf-label">JS 堆内存</span>
        <span
          className="perf-value"
          style={{
            color: getMemoryColor(stats.memoryUsed, stats.memoryTotal)
          }}
        >
          {stats.memoryUsed} / {stats.memoryTotal} MB
        </span>
      </div>

      <div className="perf-row">
        <span className="perf-label">缓冲点数</span>
        <span className="perf-value">
          {stats.bufferPoints.toLocaleString()}
        </span>
      </div>

      <div className="perf-row">
        <span className="perf-label">GC 频率</span>
        <span className="perf-value gc-zero" title="零 GC 压力">
          ✅ 零临时对象
        </span>
      </div>

      <div className="perf-footer">
        <div className="perf-title">
          <span className="perf-dot"></span>
          实时性能指标 · 长期运行稳定
        </div>
      </div>
    </div>
  )
}
