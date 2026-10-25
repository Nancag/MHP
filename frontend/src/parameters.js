export const values = {
  ratio: ['1:1', '4:3', '3:4', '16:9', '9:16'],
  resolution: ['1200', '2000'],
  language: ['zh', 'ru', 'en', 'other'],
  platform: ['ozon', 'wildberries', 'amazon', 'other'],
  scene: ['livingroom', 'bedroom', 'kitchen', 'office', 'outdoor', 'car', 'warehouse', 'industrial'],
  style: ['premium', 'minimalist', 'tech', 'business', 'natural', 'lifestyle'],
}
export const defaults = () => ({ ratio: '1:1', resolution: '2000', language: 'zh', platform: 'ozon', scene: 'livingroom', style: 'premium' })
export function parameterLabel(t, field, value) {
  const index = values[field]?.indexOf(value)
  return index >= 0 ? t.ptmd.params.options[field][index] : value
}
