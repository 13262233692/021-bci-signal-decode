import { useState, useMemo } from 'react'
import { useSignalSocket } from './hooks/useSignalSocket'
import { usePerformanceMonitor } from './hooks/usePerformanceMonitor'
import SignalChart from './components/SignalChart'
import PerformanceMonitor from './components/PerformanceMonitor'

export default function App() {
  const {
    connected,
    config,
    totalSamples,
    packetRate,
    subscribe,
    reset
  } = useSignalSocket()

  const perfStats = usePerformanceMonitor()
  const [showPerf, setShowPerf] = useState(true)

  const numChannels = config?.channels || 64
  const sampleRate = config?.sampleRate || 1000

  const formatDuration = useMemo(() => {
    const totalSeconds = totalSamples / sampleRate
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = Math.floor(totalSeconds % 60)
    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`
    }
    return `${seconds}s`
  }, [totalSamples, sampleRate])

  const handleReset = () => {
    reset()
    if (window.handleChartReset) {
      window.handleChartReset()
    }
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-left">
          <span className="logo">🧠</span>
          <div>
            <div className="title">BCI 脑电信号实时监控平台</div>
            <div className="subtitle">运动皮层 · 微电极阵列 · 64通道</div>
          </div>
        </div>
        <div className="header-right">
          <div className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            <span>{connected ? '数据连接正常' : '等待数据连接...'}</span>
          </div>
        </div>
      </header>

      <div className="stats-panel">
        <div className="stat-item">
          <span className="stat-label">通道数</span>
          <span className="stat-value">{numChannels}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">采样率</span>
          <span className="stat-value">{sampleRate} Hz</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">陷波滤波</span>
          <span className="stat-value">{config?.notchFreq || 50} Hz</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">带通范围</span>
          <span className="stat-value">
            {config?.bandpass ? `${config.bandpass[0]}-${config.bandpass[1]} Hz` : '0.5-300 Hz'}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">累计采样</span>
          <span className="stat-value">{totalSamples.toLocaleString()}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">数据包/秒</span>
          <span className="stat-value">{packetRate}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">记录时长</span>
          <span className="stat-value">{formatDuration}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">渲染帧率</span>
          <span
            className="stat-value"
            style={{
              color: perfStats.fps >= 50 ? '#3fb950' : perfStats.fps >= 30 ? '#d29922' : '#f85149'
            }}
          >
            {perfStats.fps} FPS
          </span>
        </div>
      </div>

      <div className="chart-container">
        <div className="chart-controls">
          <button className="control-btn" onClick={handleReset}>
            🔄 重置视图
          </button>
          <button
            className="control-btn primary"
            onClick={handleReset}
          >
            ⏹ 清空缓冲区
          </button>
          <button
            className="control-btn"
            onClick={() => setShowPerf(!showPerf)}
          >
            {showPerf ? '📊 隐藏性能' : '📊 显示性能'}
          </button>
        </div>
        <div className="channel-chart">
          <SignalChart
            subscribe={subscribe}
            numChannels={numChannels}
            config={config}
          />
        </div>
        {showPerf && (
          <PerformanceMonitor stats={perfStats} />
        )}
      </div>

      <footer className="app-footer">
        <div className="footer-left">
          <div className="footer-item">
            <span>📡</span>
            <span>ZeroMQ SUB → {connected ? '已连接' : '未连接'}</span>
          </div>
          <div className="footer-item">
            <span>⚡</span>
            <span>WebSocket Stream → {connected ? '活跃' : '待机'}</span>
          </div>
          <div className="footer-item">
            <span>🗃️</span>
            <span>Redis Queue → Ready</span>
          </div>
          <div className="footer-item">
            <span>🎨</span>
            <span>渲染 → Canvas 2D + 环形缓冲</span>
          </div>
        </div>
        <div>
          神经科学研究所 · 运动皮层信号解码实验室
        </div>
      </footer>
    </div>
  )
}
