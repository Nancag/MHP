<script setup>
import { computed } from 'vue'
import { assetPreviewUrl } from '../../api/client'

const props = defineProps({
  t: { type: Object, required: true },
  product: { type: Object, default: null },
  generation: { type: Object, default: null },
  activeTab: { type: String, default: 'original' },
  generationUrl: { type: String, default: '' },
  generating: { type: Boolean, default: false },
})

const emit = defineEmits(['update:activeTab'])
const errorMessage = computed(() => {
  if (!props.generation?.error) return props.t.ptmd.products.pendingNote
  if (props.generation.status === 'cancelled') return props.t.ptmd.prompt.cancelled
  return props.t.ptmd.params.options.language[0] === 'Chinese' ? props.t.ptmd.prompt.generateFailed : props.generation.error
})

const info = computed(() => props.activeTab === 'generated' ? props.generation : props.product)

const tabs = [
  { key: 'original', labelKey: 'original' },
  { key: 'generated', labelKey: 'generated' },
]

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}
</script>

<template>
  <section class="wb-canvas">
    <div class="wb-canvas__tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="wb-tab"
        :class="{ 'wb-tab--active': activeTab === tab.key }"
        type="button"

        @click="emit('update:activeTab', tab.key)"
      >
        {{ t.ptmd.canvas[tab.labelKey] }}
      </button>
    </div>

    <div class="wb-canvas__stage">
      <div class="wb-canvas__checker wb-checkerboard" aria-hidden="true"></div>

      <div v-if="!product && activeTab !== 'generated'" class="wb-canvas__empty">
        <svg
          class="icon wb-canvas__empty-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 6 h18 v12 H3 Z" />
          <path d="M9 6 v12" />
          <path d="M3 15 l5 -4 l4 3 l3 -2 l6 5" />
        </svg>
        <p class="wb-canvas__empty-title">{{ t.ptmd.canvas.empty }}</p>
        <p class="wb-canvas__empty-note">{{ t.ptmd.canvas.emptyNote }}</p>
      </div>

      <template v-else>
        <Transition name="wb-fade" mode="out-in">
          <div v-if="activeTab === 'original' && product" key="original" class="wb-canvas__img-wrap">
            <img
              class="wb-canvas__img"
              :src="assetPreviewUrl(product.asset_id)"
              :alt="product.filename"
            />
          </div>
          <div v-else key="generated" class="wb-canvas__img-wrap">
            <div v-if="generating" class="wb-canvas__generating">
              <span class="wb-canvas__spin"></span>
              <p>{{ t.ptmd.canvas.generating }}</p>
            </div>
            <template v-else-if="generationUrl">
              <img
                class="wb-canvas__img"
                :src="generationUrl"
                :alt="t.ptmd.canvas.generated"
              />
              <p v-if="!generation?.design && !generation?.workflow" class="wb-canvas__mock-note">{{ t.ptmd.canvas.compositeNote }}</p>
            </template>
            <div v-else class="wb-canvas__placeholder">
              <p>{{ errorMessage }}</p>
            </div>
          </div>
        </Transition>
      </template>
    </div>

    <div v-if="info?.width" class="wb-canvas__info">
      <span class="wb-canvas__info-item">
        <span class="wb-canvas__info-label">{{ t.ptmd.canvas.imgInfo }}</span>
        {{ info.width }} × {{ info.height }} px
      </span>
      <span class="wb-canvas__info-item">
        <span class="wb-canvas__info-label">{{ t.ptmd.canvas.type }}</span>
        {{ info.format || 'PNG' }}
      </span>
      <span class="wb-canvas__info-item">
        <span class="wb-canvas__info-label">{{ t.ptmd.canvas.size }}</span>
        {{ formatBytes(info.size_bytes) }}
      </span>
      <span class="wb-canvas__info-item wb-canvas__info-ratio">
        ← {{ t.ptmd.canvas.preview }}
      </span>
    </div>
  </section>
</template>

<style scoped>
.wb-canvas__controls { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; color: var(--text-secondary); font-size: 12px; }
.wb-canvas__controls .wb-tab { padding: 5px 9px; font-size: 12px; }
.wb-canvas__controls label { display: flex; align-items: center; gap: 4px; }
.wb-canvas__compare { display: grid !important; grid-template-columns: 1fr 1fr; gap: 12px; }
.wb-canvas__compare figure { position: relative; margin: 0; height: 100%; min-height: 0; min-width: 0; display: flex; align-items: center; justify-content: center; }
.wb-canvas__compare figcaption { position: absolute; top: 0; left: 0; z-index: 1; color: white; background: #333b; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
.wb-canvas {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  padding: 14px;
  gap: 12px;
}

.wb-canvas__tabs {
  display: flex;
  gap: 8px;
  flex: none;
}

.wb-tab {
  padding: 8px 18px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-smooth), box-shadow var(--transition-smooth);
}

.wb-tab:hover {
  color: var(--text-primary);
  border-color: var(--neon-blue);
}

.wb-tab--active {
  background: var(--grad-active);
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 0 12px var(--glow-purple);
}

.wb-canvas__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-glow);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.wb-canvas__checker {
  position: absolute;
  inset: 0;
}

.wb-canvas__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
}

.wb-canvas__empty-icon {
  width: 56px;
  height: 56px;
  opacity: 0.55;
}

.wb-canvas__empty-title {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.wb-canvas__empty-note {
  margin: 0;
  font-size: 12px;
  opacity: 0.75;
}

.wb-canvas__img-wrap {
  position: absolute;
  inset: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wb-canvas__img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.wb-canvas__placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.wb-canvas__info {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
}

.wb-canvas__info-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
}

.wb-canvas__info-label {
  color: var(--text-secondary);
}

.wb-canvas__info-ratio {
  margin-left: auto;
  color: var(--neon-blue);
  font-weight: 600;
  text-shadow: 0 0 8px var(--glow-blue);
}

.wb-fade-enter-active,
.wb-fade-leave-active {
  transition: opacity var(--transition-smooth), transform var(--transition-smooth);
}

.wb-fade-enter-from,
.wb-fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

.wb-canvas__mock-note {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: rgba(0, 0, 0, 0.5);
  color: var(--text-secondary);
  font-size: 11px;
  white-space: nowrap;
  z-index: 2;
}

.wb-canvas__generating {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: 13px;
}

.wb-canvas__spin {
  width: 32px;
  height: 32px;
  border: 3px solid var(--neon-blue);
  border-top-color: transparent;
  border-radius: 50%;
  animation: wbCanvasSpin 0.8s linear infinite;
  box-shadow: 0 0 12px var(--glow-blue);
}

@keyframes wbCanvasSpin {
  to {
    transform: rotate(360deg);
  }
}
</style>
