export const names = 'person,bicycle,car,motorcycle,airplane,bus,train,truck,boat,traffic light,fire hydrant,stop sign,parking meter,bench,bird,cat,dog,horse,sheep,cow,elephant,bear,zebra,giraffe,backpack,umbrella,handbag,tie,suitcase,frisbee,skis,snowboard,sports ball,kite,baseball bat,baseball glove,skateboard,surfboard,tennis racket,bottle,wine glass,cup,fork,knife,spoon,bowl,banana,apple,sandwich,orange,broccoli,carrot,hot dog,pizza,donut,cake,chair,couch,potted plant,bed,dining table,toilet,tv,laptop,mouse,remote,keyboard,cell phone,microwave,oven,toaster,sink,refrigerator,book,clock,vase,scissors,teddy bear,hair drier,toothbrush'.split(',')
export function overlap(a, b) {
  const intersection = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]))
  const area = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
  return area > 0 ? intersection / area : 0
}
export function decode(data, count, transform, confidence, iou) {
  const { scale, left, top, width, height } = transform
  const candidates = []
  for (let n = 0; n < count; n++) {
    let score = 0, category = 0
    for (let c = 0; c < 80; c++) {
      const value = data[(c + 4) * count + n]
      if (value > score) { score = value; category = c }
    }
    if (score < confidence) continue
    const x = data[n], y = data[count + n], w = data[2 * count + n], h = data[3 * count + n]
    const bbox = [(x - w / 2 - left) / scale, (y - h / 2 - top) / scale,
      (x + w / 2 - left) / scale, (y + h / 2 - top) / scale]
      .map((v, index) => Math.max(0, Math.min(index % 2 ? height : width, v)))
    if (bbox[2] <= bbox[0] || bbox[3] <= bbox[1]) continue
    candidates.push({ class_id: category, label: names[category], confidence: Number(score.toFixed(5)), bbox })
  }
  candidates.sort((a, b) => b.confidence - a.confidence)
  const kept = []
  for (const candidate of candidates.slice(0, 3000)) {
    if (!kept.some(other => other.class_id === candidate.class_id && overlap(other.bbox, candidate.bbox) > iou)) {
      kept.push(candidate)
      if (kept.length === 300) break
    }
  }
  return kept.map(item => ({ ...item, bbox: item.bbox.map(v => Number(v.toFixed(2))) }))
}
