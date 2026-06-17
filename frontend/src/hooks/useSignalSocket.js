import { useState, useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'

const MAX_TIMESTAMPS = 10000
const DEFAULT_CHANNELS = 64

export function useSignalSocket() {
  const [connected, setConnected] = useState(false)
  const [config, setConfig] = useState(null)
  const [totalSamples, setTotalSamples] = useState(0)
  const [packetRate, setPacketRate] = useState(0)

  const socketRef = useRef(null)
  const bufferRef = useRef({
    timestamps: [],
    channels: Array.from({ length: DEFAULT_CHANNELS }, () => [])
  })
  const listenersRef = useRef([])
  const packetCountRef = useRef(0)
  const lastRateUpdateRef = useRef(Date.now())
  const configRef = useRef(null)

  const initBuffer = useCallback((numChannels) => {
    bufferRef.current = {
      timestamps: [],
      channels: Array.from({ length: numChannels }, () => [])
    }
  }, [])

  const ensureBuffer = useCallback((numChannels) => {
    const buf = bufferRef.current
    if (!buf.channels || buf.channels.length !== numChannels) {
      initBuffer(numChannels)
    }
  }, [initBuffer])

  const processPackets = useCallback((packets) => {
    for (const packet of packets) {
      const { timestamps, samples } = packet
      if (!timestamps || !samples || !samples.length) continue

      const numChannels = samples.length
      ensureBuffer(numChannels)

      const buf = bufferRef.current
      buf.timestamps.push(...timestamps)

      for (let ch = 0; ch < numChannels; ch++) {
        if (buf.channels[ch]) {
          buf.channels[ch].push(...samples[ch])
        }
      }

      setTotalSamples(prev => prev + timestamps.length)
      packetCountRef.current++
    }

    const buf = bufferRef.current
    while (buf.timestamps.length > MAX_TIMESTAMPS) {
      const overflow = buf.timestamps.length - MAX_TIMESTAMPS
      buf.timestamps.splice(0, overflow)
      for (let ch = 0; ch < buf.channels.length; ch++) {
        if (buf.channels[ch]) {
          buf.channels[ch].splice(0, overflow)
        }
      }
    }

    const now = Date.now()
    if (now - lastRateUpdateRef.current >= 1000) {
      setPacketRate(packetCountRef.current)
      packetCountRef.current = 0
      lastRateUpdateRef.current = now
    }

    for (const listener of listenersRef.current) {
      listener({
        timestamps: buf.timestamps,
        channels: buf.channels
      })
    }
  }, [ensureBuffer])

  useEffect(() => {
    const socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000
    })

    socketRef.current = socket

    socket.on('connect', () => {
      setConnected(true)
    })

    socket.on('disconnect', () => {
      setConnected(false)
    })

    socket.on('config', (cfg) => {
      configRef.current = cfg
      setConfig(cfg)
      initBuffer(cfg.channels)
    })

    socket.on('signal_data', (data) => {
      if (data && data.packets && data.packets.length > 0) {
        processPackets(data.packets)
      }
    })

    socket.on('reset_done', () => {
      const numChannels = configRef.current?.channels || DEFAULT_CHANNELS
      initBuffer(numChannels)
      setTotalSamples(0)
    })

    return () => {
      socket.disconnect()
      socketRef.current = null
    }
  }, [processPackets, initBuffer])

  const subscribe = useCallback((listener) => {
    listenersRef.current.push(listener)

    const buf = bufferRef.current
    if (buf.timestamps.length > 0) {
      listener({
        timestamps: buf.timestamps,
        channels: buf.channels
      })
    }

    return () => {
      const idx = listenersRef.current.indexOf(listener)
      if (idx !== -1) {
        listenersRef.current.splice(idx, 1)
      }
    }
  }, [])

  const reset = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.emit('reset')
    }
  }, [])

  return {
    connected,
    config,
    totalSamples,
    packetRate,
    subscribe,
    reset
  }
}
