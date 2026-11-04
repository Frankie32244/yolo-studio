import test from 'node:test'
import assert from 'node:assert/strict'
import { decode, overlap, names } from '../src/browser/postprocess.js'
test('class-aware NMS keeps overlapping different classes and suppresses duplicates', () => {
  const n = 3, data = new Float32Array(84 * n)
  for (let i = 0; i < n; i++) {
    data[i] = 208; data[n + i] = 208; data[2 * n + i] = 100; data[3 * n + i] = 100
  }
  data[4 * n] = .9; data[4 * n + 1] = .8; data[5 * n + 2] = .85
  const results = decode(data, n, { scale: .5, left: 0, top: 104, width: 832, height: 416 }, .25, .45)
  assert.equal(results.length, 2)
  assert.deepEqual(results.map(i => i.class_id), [0, 1])
  assert.deepEqual(results[0].bbox, [316, 108, 516, 308])
})
test('threshold, clipping and empty output', () => {
  const data = new Float32Array(84)
  data[0] = 10; data[1] = 10; data[2] = data[3] = 40; data[4] = .8
  const transform = { scale: 1, left: 0, top: 0, width: 416, height: 416 }
  assert.deepEqual(decode(data, 1, transform, .9, .45), [])
  assert.deepEqual(decode(data, 1, transform, .5, .45)[0].bbox, [0, 0, 30, 30])
  assert.equal(overlap([0, 0, 10, 10], [20, 20, 30, 30]), 0)
  assert.equal(names.length, 80)
})
