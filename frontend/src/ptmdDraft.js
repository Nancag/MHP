// Old saved templates may contain only part of an editable storyboard.
export function createSetDraft(input = {}, assetId = null, defaultResolution = '2000') {
  const value = input && typeof input === 'object' ? input : {}
  const sourcePages = Array.isArray(value.pages) ? value.pages : []
  const count = Number.isInteger(value.count) && value.count >= 1 && value.count <= 9
    ? value.count : Math.max(1, Math.min(9, sourcePages.length))
  const text = value => typeof value === 'string' ? value : ''
  return {
    preset_id: typeof value.preset_id === 'string' ? value.preset_id : null,
    engine: value.engine === 'reference' ? 'reference' : 'local',
    image_quality: ['low', 'medium', 'high'].includes(value.image_quality) ? value.image_quality : null,
    text_rendering: ['local', 'model'].includes(value.text_rendering) ? value.text_rendering : (sourcePages.length && !Object.hasOwn(value, 'text_rendering') ? 'local' : null),
    palette: ['cool', 'warm', 'mono'].includes(value.palette) ? value.palette : 'cool',
    product_name: text(value.product_name),
    requirements: text(value.requirements),
    reference_ids: Array.isArray(value.reference_ids) ? [...value.reference_ids] : [],
    language: value.language === 'en' ? 'en' : 'ru',
    resolution: ['1200', '2000'].includes(String(value.resolution)) ? String(value.resolution) : defaultResolution,
    count,
    pages: Array.from({ length: count }, (_, index) => {
      const page = sourcePages[index] || {}
      return {
        asset_id: assetId ?? text(page.asset_id),
        kind: index === 0 ? 'main' : ['feature', 'detail', 'scene'].includes(page.kind) ? page.kind : 'detail',
        title: text(page.title),
        title_zh: text(page.title_zh),
        copy_lines: Array.isArray(page.copy_lines) ? page.copy_lines.filter(line => typeof line === 'string') : [],
        copy_lines_zh: Array.isArray(page.copy_lines_zh) ? page.copy_lines_zh.filter(line => typeof line === 'string') : [],
        direction: text(page.direction),
        crop: page.crop || null,
        source_is_scene: page.source_is_scene === true,
        no_overlay: page.no_overlay === true,
      }
    }),
  }
}
