import { useState, useEffect, useRef, useCallback } from 'react'

export function usePerformanceMonitor() {
  const [stats, setStats] = useState({
    fps: 0,
    frameTime: 0,
    memoryUsed: 0,
    memoryTotal: 0,
    dataLatency: 0,
    bufferPoints: 0,
    renderMode: 'canvas2d'
  })

  const lastCheckRef = useRef(Date.now())
  const intervalRef = useRef(null)

  const collectStats = useCallback(() => {
    const newStats = { ...stats }

    if (window.getChartStats) {
      const chartStats = window.getChartStats()
      newStats.fps = chartStats.fps || 0
      newStats.frameTime = chartStats.frameTime || 0
      newStats.bufferPoints = chartStats.bufferSize || 0
    }

    if (performance && performance.memory) {
      newStats.memoryUsed = Math.round(performance.memory.usedJSHeapSize / 1024 / 1024)
      newStats.memoryTotal = Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
    }

    if (window.performance && window.performance.getEntriesByType) {
      const entries = window.performance.getEntriesByType('resource')
      const wsEntries = entries.filter(e => e.name.includes('socket.io'))
      if (wsEntries.length > 0) {
        const last = wsEntries[wsEntries.length - 1]
        newStats.dataLatency = Math.round(last.duration || 0)
      }
    }

    setStats(newStats)
    lastCheckRef.current = Date.now()

    return newStats
  }, [stats])

  useEffect(() => {
    intervalRef.current = setInterval(collectStats, 1000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [collectStats])

  return stats
}
