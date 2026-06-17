export class CircularFrameBuffer {
  constructor(numChannels, maxFrames) {
    this.numChannels = numChannels
    this.maxFrames = maxFrames

    this.timestamps = new Float64Array(maxFrames)
    this.channels = new Array(numChannels)
    for (let i = 0; i < numChannels; i++) {
      this.channels[i] = new Float32Array(maxFrames)
    }

    this.writePos = 0
    this.length = 0
    this._readCursor = 0
    this._minValues = new Float32Array(numChannels)
    this._maxValues = new Float32Array(numChannels)
    this._channelOffsets = new Float32Array(numChannels)
    this._channelScales = new Float32Array(numChannels)

    for (let i = 0; i < numChannels; i++) {
      this._minValues[i] = Infinity
      this._maxValues[i] = -Infinity
      this._channelOffsets[i] = 0
      this._channelScales[i] = 1
    }

    this._dirtyFrom = 0
    this._dirtyTo = 0
    this._hasDirty = false
  }

  clear() {
    this.writePos = 0
    this.length = 0
    this._readCursor = 0
    this._hasDirty = false
    for (let i = 0; i < this.numChannels; i++) {
      this._minValues[i] = Infinity
      this._maxValues[i] = -Infinity
    }
  }

  pushBatch(timestamps, samples) {
    const batchSize = timestamps.length
    if (batchSize === 0) return

    const startWritePos = this.writePos
    const wrapPoint = this.maxFrames - startWritePos

    if (batchSize <= wrapPoint) {
      this.timestamps.set(timestamps, startWritePos)
      for (let ch = 0; ch < this.numChannels; ch++) {
        this.channels[ch].set(samples[ch], startWritePos)
      }
      this.writePos += batchSize
      if (this.writePos >= this.maxFrames) {
        this.writePos = this.writePos % this.maxFrames
      }
    } else {
      this.timestamps.set(timestamps.subarray(0, wrapPoint), startWritePos)
      this.timestamps.set(timestamps.subarray(wrapPoint), 0)
      for (let ch = 0; ch < this.numChannels; ch++) {
        this.channels[ch].set(samples[ch].subarray(0, wrapPoint), startWritePos)
        this.channels[ch].set(samples[ch].subarray(wrapPoint), 0)
      }
      this.writePos = batchSize - wrapPoint
    }

    const prevLength = this.length
    this.length = Math.min(this.length + batchSize, this.maxFrames)

    if (this.length === this.maxFrames) {
      this._readCursor = this.writePos
    }

    this._updateMinMax(timestamps, samples, batchSize)
    this._markDirty(startWritePos, batchSize)
  }

  _updateMinMax(timestamps, samples, batchSize) {
    for (let ch = 0; ch < this.numChannels; ch++) {
      const chData = samples[ch]
      let min = this._minValues[ch]
      let max = this._maxValues[ch]
      if (min === Infinity) {
        min = chData[0]
        max = chData[0]
      }
      for (let i = 0; i < batchSize; i++) {
        const v = chData[i]
        if (v < min) min = v
        if (v > max) max = v
      }
      this._minValues[ch] = min
      this._maxValues[ch] = max
    }
  }

  _markDirty(start, count) {
    if (!this._hasDirty) {
      this._dirtyFrom = start
      this._dirtyTo = start + count
      this._hasDirty = true
    } else {
      this._dirtyFrom = Math.min(this._dirtyFrom, start)
      this._dirtyTo = Math.max(this._dirtyTo, start + count)
    }
    if (this._dirtyTo > this.maxFrames) {
      this._dirtyTo = this._dirtyTo % this.maxFrames
    }
  }

  consumeDirty() {
    if (!this._hasDirty) return null
    const result = { from: this._dirtyFrom, to: this._dirtyTo }
    this._hasDirty = false
    return result
  }

  getReadRange() {
    if (this.length === 0) return { start: 0, count: 0 }
    if (this.length < this.maxFrames) {
      return { start: 0, count: this.length }
    }
    return { start: this.writePos, count: this.maxFrames }
  }

  getTimestamp(index) {
    const pos = (this.writePos - this.length + index + this.maxFrames) % this.maxFrames
    return this.timestamps[pos]
  }

  getSample(channel, index) {
    const pos = (this.writePos - this.length + index + this.maxFrames) % this.maxFrames
    return this.channels[channel][pos]
  }

  forEachInRange(rangeStart, rangeCount, callback) {
    if (rangeCount === 0) return
    const actualStart = (this.writePos - this.length + rangeStart + this.maxFrames) % this.maxFrames
    const firstPart = Math.min(rangeCount, this.maxFrames - actualStart)

    for (let i = 0; i < firstPart; i++) {
      callback(i, actualStart + i, this.timestamps[actualStart + i])
    }
    if (firstPart < rangeCount) {
      const secondPart = rangeCount - firstPart
      for (let i = 0; i < secondPart; i++) {
        callback(firstPart + i, i, this.timestamps[i])
      }
    }
  }

  getChannelMinMax(channel) {
    return { min: this._minValues[channel], max: this._maxValues[channel] }
  }

  setChannelScale(channel, offset, scale) {
    this._channelOffsets[channel] = offset
    this._channelScales[channel] = scale
  }

  getChannelOffset(channel) { return this._channelOffsets[channel] }
  getChannelScale(channel) { return this._channelScales[channel] }
}
