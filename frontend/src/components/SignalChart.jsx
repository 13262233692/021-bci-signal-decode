import { useEffect, useRef, useMemo, useState, useCallback } from 'react'
import * as echarts from 'echarts'

const CHANNEL_GAP = 100
const VISIBLE_POINTS = 3000

function generateChannelColors(count) {
  const palette = [
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
  const result = []
  for (let i = 0; i < count; i++) {
    result.push(palette[i % palette.length])
  }
  return result
}

export default function SignalChart({ subscribe, numChannels = 64, config }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const dataRef = useRef({ timestamps: [], channels: Array.from({ length: numChannels }, () => []) })
  const rafRef = useRef(null)
  const pendingRef = useRef(false)
  const [, setChartKey] = useState(0)

  const colors = useMemo(() => generateChannelColors(numChannels), [numChannels])

  const channelOffsets = useMemo(() => {
    const offsets = []
    for (let i = 0; i < numChannels; i++) {
      offsets.push(i * CHANNEL_GAP)
    }
    return offsets
  }, [numChannels])

  const buildOption = useCallback(() => {
    const yAxisLabels = []
    for (let i = 0; i < numChannels; i++) {
      yAxisLabels.push({
        value: channelOffsets[i],
        label: {
          show: true,
          formatter: `Ch${String(i + 1).padStart(2, '0')}`,
          color: colors[i],
          fontSize: 10,
          fontFamily: 'monospace',
          fontWeight: 'bold'
        }
      })
    }

    return {
      backgroundColor: '#0d1117',
      animation: false,
      textStyle: { color: '#8b949e' },
      grid: { left: 70, right: 30, top: 20, bottom: 50, containLabel: false },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: 0,
          filterMode: 'none',
          zoomOnMouseWheel: true,
          moveOnMouseMove: false
        },
        {
          type: 'slider',
          xAxisIndex: 0,
          height: 20,
          bottom: 10,
          borderColor: '#30363d',
          backgroundColor: '#161b22',
          fillerColor: 'rgba(88, 166, 255, 0.15)',
          handleStyle: { color: '#58a6ff' },
          textStyle: { color: '#8b949e' },
          moveHandleSize: 8,
          showDataShadow: false,
          showDetail: false
        }
      ],
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: '#30363d' } },
        axisTick: { lineStyle: { color: '#30363d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 11,
          formatter: (value) => {
            const d = new Date(value)
            const ms = String(d.getMilliseconds()).padStart(3, '0')
            return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}.${ms}`
          }
        },
        splitLine: { show: true, lineStyle: { color: '#21262d', type: 'dashed' } }
      },
      yAxis: {
        type: 'value',
        min: -CHANNEL_GAP * 0.5,
        max: (numChannels - 1) * CHANNEL_GAP + CHANNEL_GAP * 0.5,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: true, lineStyle: { color: '#161b22', type: 'solid', width: 1 } },
        splitArea: { show: false },
        data: yAxisLabels
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(22, 27, 34, 0.95)',
        borderColor: '#30363d',
        borderWidth: 1,
        textStyle: { color: '#c9d1d9', fontSize: 12 },
        axisPointer: {
          type: 'line',
          lineStyle: { color: '#58a6ff', width: 1, type: 'dashed' }
        },
        formatter: (params) => {
          if (!params || params.length === 0) return ''
          const time = new Date(params[0].value[0])
          const timeStr = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}:${time.getSeconds().toString().padStart(2, '0')}.${String(time.getMilliseconds()).padStart(3, '0')}`
          let html = `<div style="font-weight:600;margin-bottom:8px;color:#f0f6fc">⏱ ${timeStr}</div>`
          const showCount = Math.min(params.length, 8)
          for (let i = 0; i < showCount; i++) {
            const p = params[i]
            const chIdx = p.seriesIndex
            if (chIdx >= channelOffsets.length) continue
            const rawValue = (p.value[1] - channelOffsets[chIdx]).toFixed(2)
            html += `<div style="display:flex;align-items:center;gap:8px;margin:2px 0;">
              <span style="width:10px;height:10px;border-radius:2px;background:${colors[chIdx]}"></span>
              <span style="color:#8b949e;width:40px;">Ch${String(chIdx + 1).padStart(2, '0')}</span>
              <span style="color:#f0f6fc;font-family:monospace;">${rawValue} μV</span>
            </div>`
          }
          if (params.length > showCount) {
            html += `<div style="color:#6e7681;font-size:11px;margin-top:4px;">+${params.length - showCount} more channels...</div>`
          }
          return html
        }
      },
      series: Array.from({ length: numChannels }, (_, i) => ({
        name: `Channel ${i + 1}`,
        type: 'line',
        showSymbol: false,
        sampling: 'lttb',
        data: [],
        lineStyle: { color: colors[i], width: 1, opacity: 0.9 },
        itemStyle: { color: colors[i] },
        emphasis: { disabled: true },
        animation: false,
        progressive: 5000,
        progressiveThreshold: 10000
      }))
    }
  }, [numChannels, colors, channelOffsets])

  const updateChart = useCallback(() => {
    pendingRef.current = false
    const chart = chartRef.current
    if (!chart) return

    const { timestamps, channels } = dataRef.current
    if (!timestamps || timestamps.length === 0 || !channels || channels.length === 0) return

    const dataLen = timestamps.length
    const startIdx = Math.max(0, dataLen - VISIBLE_POINTS)
    const xData = timestamps.slice(startIdx)

    const series = new Array(numChannels)
    for (let ch = 0; ch < numChannels; ch++) {
      const chData = channels[ch]
      const offset = channelOffsets[ch]
      if (!chData || chData.length === 0) {
        series[ch] = { data: [] }
        continue
      }
      const sliced = chData.slice(startIdx)
      const points = new Array(sliced.length)
      for (let i = 0; i < sliced.length; i++) {
        points[i] = [xData[i], sliced[i] + offset]
      }
      series[ch] = { data: points }
    }

    try {
      chart.setOption({ series }, { lazyUpdate: true, silent: true })
    } catch (e) {
      // ignore setOption errors during render
    }
  }, [numChannels, channelOffsets])

  const scheduleUpdate = useCallback(() => {
    if (pendingRef.current) return
    pendingRef.current = true
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null
      updateChart()
    })
  }, [updateChart])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = echarts.init(container, 'dark', { renderer: 'canvas' })
    chartRef.current = chart
    chart.setOption(buildOption())

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    const unsubscribe = subscribe((data) => {
      dataRef.current = data
      scheduleUpdate()
    })

    return () => {
      window.removeEventListener('resize', handleResize)
      unsubscribe()
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      chart.dispose()
      chartRef.current = null
    }
  }, [subscribe, buildOption, scheduleUpdate, numChannels])

  const handleReset = useCallback(() => {
    setChartKey(prev => {
      const next = prev + 1
      const chart = chartRef.current
      if (chart) {
        dataRef.current = { timestamps: [], channels: Array.from({ length: numChannels }, () => []) }
        chart.setOption(buildOption(), { notMerge: true })
      }
      return next
    })
  }, [buildOption, numChannels])

  useEffect(() => {
    window.handleChartReset = handleReset
    return () => { delete window.handleChartReset }
  }, [handleReset])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
