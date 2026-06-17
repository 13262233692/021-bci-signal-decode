import { useState, useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'
import { CircularFrameBuffer } from '../utils/CircularFrameBuffer'

const MAX_FRAMES = 30000
const DEFAULT_CHANNELS = 64

export function useSignalSocket() {
  const [connected, setConnected] = useState(false)
  const [config, setConfig] = useState(null)
  const [totalSamples, setTotalSamples] = useState(0)
  const [packetRate, setPacketRate] = useState(0)
  const [buffer, setBuffer] = useState(null)

  const socketRef = useRef(null)
  const bufferRef = useRef(null)
  const listenersRef = useRef([])
  const packetCountRef = useRef(0)
  const lastRateUpdateRef = useRef(Date.now())
  const configRef = useRef(null)
  const notifyTimerRef = useRef(null)
  const pendingNotifyRef = useRef(false)

  const initBuffer = useCallback((numChannels) => {
    const buf = new CircularFrameBuffer(numChannels, MAX_FRAMES)
    bufferRef.current = buf
    setBuffer(buf)
    return buf
  }, [])

  const ensureBuffer = useCallback((numChannels) => {
    if (!bufferRef.current || bufferRef.current.numChannels !== numChannels) {
      return initBuffer(numChannels)
    }
    return bufferRef.current
  }, [initBuffer])

  const processPackets = useCallback((packets) => {
    const numChannels = configRef.current?.channels || DEFAULT_CHANNELS
    const buf = ensureBuffer(numChannels)

    let totalNewSamples = 0

    for (const packet of packets) {
      const { timestamps, samples } = packet
      if (!timestamps || !samples || !samples.length) continue

      const packetSize = timestamps.length
      if (packetSize === 0) continue

      const tsArr = new Float64Array(timestamps)
      const chArr = new Array(samples.length)
      for (let ch = 0; ch < samples.length; ch++) {
        chArr[ch] = new Float32Array(samples[ch])
      }

      buf.pushBatch(tsArr, chArr)
      totalNewSamples += packetSize
    }

    if (totalNewSamples > 0) {
      setTotalSamples(prev => prev + totalNewSamples)
      packetCountRef.current += packets.length

      if (!pendingNotifyRef.current) {
        pendingNotifyRef.current = true
        notifyTimerRef.current = requestAnimationFrame(() => {
          pendingNotifyRef.current = false
          for (const listener of listenersRef.current) {
            listener(bufferRef.current)
          }
        })
      }
    }

    const now = Date.now()
    if (now - lastRateUpdateRef.current >= 1000) {
      setPacketRate(packetCountRef.current)
      packetCountRef.current = 0
      lastRateUpdateRef.current = now
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
      if (notifyTimerRef.current) {
        cancelAnimationFrame(notifyTimerRef.current)
      }
    }
  }, [processPackets, initBuffer])

  const subscribe = useCallback((listener) => {
    listenersRef.current.push(listener)

    if (bufferRef.current && bufferRef.current.length > 0) {
      listener(bufferRef.current)
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
    buffer,
    subscribe,
    reset
  }
}
