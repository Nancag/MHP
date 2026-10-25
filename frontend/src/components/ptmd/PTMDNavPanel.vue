<script setup>
import { values, parameterLabel } from '../../parameters'
import { ref } from 'vue'
import ReferenceLibrary from './ReferenceLibrary.vue'
import { assetPreviewUrl, generationPreviewUrl } from '../../api/client'

defineProps({
  t: { type: Object, required: true },
  products: { type: Array, default: () => [] },
  productsLoading: { type: Boolean, default: false },
  productsTotal: { type: Number, default: 0 },
  activeSection: { type: String, default: 'products' },
  selectedId: { type: String, default: '' },
  selectedProduct: { type: Object, default: null },
  uploadLoading: { type: Boolean, default: false },
  generations: { type: Array, default: () => [] },
  generationsLoading: { type: Boolean, default: false },
  generationsTotal: { type: Number, default: 0 },
  generationsError: { type: String, default: '' },
  references: {type:Array,default:()=>[]},
  referenceFolderId: {type:String,default:''},
  selectedReferences: {type:Array,default:()=>[]},
  referenceUploading:Boolean,
  setWorkflow:Boolean,
  localLayout:Boolean,
  busy:Boolean,
})

const emit = defineEmits(['select-section', 'select-product', 'upload-file', 'upload-references', 'toggle-reference', 'select-generation', 'filter-change','delete-asset','reference-deleted','load-more-products','load-more-history','retry-history'])

const fileInput = ref(null)
const referenceInput = ref(null)

const filterScene = ref('')
const filterPlatform = ref('')
const filterStyle = ref('')

function emitFilterChange() {
  emit('filter-change', {
    scene: filterScene.value || null,
    platform: filterPlatform.value || null,
    style: filterStyle.value || null,
  })
}

function onFilterScene(event) {
  filterScene.value = event.target.value
  emitFilterChange()
}

function onFilterPlatform(event) {
  filterPlatform.value = event.target.value
  emitFilterChange()
}

function onFilterStyle(event) {
  filterStyle.value = event.target.value
  emitFilterChange()
}

function triggerUpload() {
  fileInput.value?.click()
}

function onFileChange(event) {
  const files = Array.from(event.target.files || [])
  if (files.length) emit('upload-file', files)
  event.target.value = ''
}

const isDragging = ref(false)

function handleDragOver() {
  isDragging.value = true
}

function handleDragLeave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragging.value = false
  }
}

function handleDrop(event) {
  isDragging.value = false
  const files=Array.from(event.dataTransfer.files||[]).filter(file=>file.type.startsWith('image/'))
  if(files.length)emit('upload-file',files)
}
function referenceFiles(event){emit('upload-references',Array.from(event.target.files||[]));event.target.value=''}
function referenceDrop(event){emit('upload-references',Array.from(event.dataTransfer.files||[]).filter(file=>file.type.startsWith('image/')))}
</script>

<template>
  <aside class="wb-nav">
    <button
      class="wb-nav__item"
      :class="{ 'wb-nav__item--active': activeSection === 'products' }"
      type="button"
      @click="$emit('select-section', 'products')"
    >
      <span class="wb-nav__icon">
        <svg
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 6 h18 v12 H3 Z" />
          <path d="M9 6 v12" />
        </svg>
      </span>
      <span class="wb-nav__label">
        <span class="wb-nav__name">{{ t.ptmd.nav.products }}</span>
        <span class="wb-nav__desc">{{ t.ptmd.nav.productsDesc }}</span>
      </span>
    </button>

    <button
      class="wb-nav__item"
      :class="{ 'wb-nav__item--active': activeSection === 'history' }"
      type="button"
      @click="$emit('select-section', 'history')"
    >
      <span class="wb-nav__icon">
        <svg
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 12 a9 9 0 1 0 3 -6.7 L3 8" />
          <path d="M3 3 v5 h5" />
          <path d="M12 7 v5 l3 2" />
        </svg>
      </span>
      <span class="wb-nav__label">
        <span class="wb-nav__name">{{ t.ptmd.nav.history }}</span>
        <span class="wb-nav__desc">{{ t.ptmd.nav.historyDesc }}</span>
      </span>
    </button>

    <button
      class="wb-nav__item"
      :class="{ 'wb-nav__item--active': activeSection === 'templates' }"
      type="button"
      @click="$emit('select-section', 'templates')"
    >
      <span class="wb-nav__icon">
        <svg
          class="icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="3" width="8" height="8" rx="1.5" />
          <rect x="13" y="3" width="8" height="8" rx="1.5" />
          <rect x="3" y="13" width="8" height="8" rx="1.5" />
          <rect x="13" y="13" width="8" height="8" rx="1.5" />
        </svg>
      </span>
      <span class="wb-nav__label">
        <span class="wb-nav__name">{{ t.ptmd.nav.templates }}</span>
        <span class="wb-nav__desc">{{ t.ptmd.nav.templatesDesc }}</span>
      </span>
    </button>

    <div class="wb-nav__body">
      <template v-if="activeSection === 'products'">
        <h4 class="wb-upload-heading">{{ t.account.breadcrumb==='Account'?'Upload main / product images':'上传主图 / 商品素材' }}</h4>
        <button v-if="selectedProduct" class="wb-delete" :disabled="busy" @click="emit('delete-asset',selectedProduct)">{{ t.account.breadcrumb==='Account'?'Delete selected original':'删除选中的原图' }}</button>
        <div
          class="wb-drop-zone"
          :class="{ 'wb-drop-zone--active': isDragging }"
          @dragover.prevent="handleDragOver"
          @dragleave="handleDragLeave"
          @drop.prevent="handleDrop"
        >
        <input
          ref="fileInput"
          class="wb-file-input"
          type="file"
          accept="image/jpeg,image/png"
          multiple
          @change="onFileChange"
        />
        <button
          class="wb-upload"
          :disabled="uploadLoading||busy"
          type="button"
          @click="triggerUpload"
        >
          <svg
            v-if="!uploadLoading"
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 19 V5" />
            <path d="M5 12 l7 -7 l7 7" />
          </svg>
          <span v-if="!uploadLoading">{{ t.account.breadcrumb==='Account'?'Upload main images':'上传主图' }}</span>
          <span v-else class="wb-spin">{{ t.ptmd.products.uploading }}</span>
        </button>

        <div v-if="!uploadLoading && !productsLoading" class="wb-drop-hint">
          <svg
            class="icon wb-drop-hint__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 3 v12" />
            <path d="M7 8 l5 -5 l5 5" />
            <path d="M4 21 h16" />
          </svg>
          <span>{{ t.ptmd.products.dropHere }}</span>
        </div>

        <div v-if="productsLoading && !products.length" class="wb-nav__loading">{{ t.ptmd.taskRunning }}…</div>

        <div v-else-if="products.length === 0" class="wb-empty">
          <p class="wb-empty__title">{{ t.ptmd.products.emptyList }}</p>
          <p class="wb-empty__note">{{ t.ptmd.products.pendingNote }}</p>
        </div>

        <div v-else class="wb-thumbs">
          <button
            v-for="product in products"
            :key="product.asset_id"
            class="wb-thumb"
            :class="{ 'wb-thumb--active': selectedId === product.asset_id }"
            type="button"
            :disabled="busy"
            @click="$emit('select-product', product)"
          >
            <img
              class="wb-thumb__img"
              :src="assetPreviewUrl(product.asset_id)"
              :alt="product.filename"
              loading="lazy"
            />
            <span class="wb-thumb__overlay">
              <svg
                class="icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="M21 21 l-4.3 -4.3" />
              </svg>
            </span>
          </button>
        </div>
        <button v-if="products.length < productsTotal" class="wb-products-more wb-load-more" type="button" :disabled="productsLoading" @click="emit('load-more-products')">
          {{ productsLoading ? t.ptmd.taskRunning : (t.account.breadcrumb==='Account'?'Load more originals':'加载更多商品素材') }} · {{ products.length }} / {{ productsTotal }}
        </button>
        </div>
        <ReferenceLibrary :initial-folder-id="referenceFolderId" :selected="selectedReferences" :busy="busy||referenceUploading" :english="t.account.breadcrumb==='Account'" @toggle="emit('toggle-reference',$event)" @deleted="emit('reference-deleted',$event)" />
      </template>

      <template v-else-if="activeSection === 'history'">
        <div class="wb-gen-filters">
          <select class="wb-gen-filter" :value="filterScene" @change="onFilterScene">
            <option value="">{{ t.ptmd.history.filterScene }}：{{ t.ptmd.history.filterAll }}</option>
            <option v-for="(opt, index) in t.ptmd.params.options.scene" :key="opt" :value="values.scene[index]">{{ opt }}</option>
          </select>
          <select class="wb-gen-filter" :value="filterPlatform" @change="onFilterPlatform">
            <option value="">{{ t.ptmd.history.filterPlatform }}：{{ t.ptmd.history.filterAll }}</option>
            <option v-for="(opt, index) in t.ptmd.params.options.platform" :key="opt" :value="values.platform[index]">{{ opt }}</option>
          </select>
          <select class="wb-gen-filter" :value="filterStyle" @change="onFilterStyle">
            <option value="">{{ t.ptmd.history.filterStyle }}：{{ t.ptmd.history.filterAll }}</option>
            <option v-for="(opt, index) in t.ptmd.params.options.style" :key="opt" :value="values.style[index]">{{ opt }}</option>
          </select>
          <div v-if="generationsTotal > 0" class="wb-gen-count">
            {{ t.ptmd.history.count.replace('{n}', generationsTotal) }}
          </div>
        </div>

        <div v-if="generationsError" class="wb-history-error" role="alert">
          <p>{{ generationsError }}</p>
          <button type="button" :disabled="generationsLoading" @click="emit('retry-history')">{{ t.account.breadcrumb==='Account'?'Retry':'重试' }}</button>
        </div>
        <div v-if="generationsLoading && !generations.length" class="wb-nav__loading">{{ t.ptmd.taskRunning }}…</div>
        <div v-else-if="generations.length === 0 && !generationsError" class="wb-empty">
          <p class="wb-empty__title">{{ t.ptmd.history.empty }}</p>
          <p class="wb-empty__note">{{ t.ptmd.history.emptyNote }}</p>
        </div>
        <div v-else class="wb-gen-list">
          <button
            v-for="gen in generations"
            :key="gen.generation_id"
            class="wb-gen-item"
            type="button"
            :disabled="busy"
            @click="$emit('select-generation', gen)"
          >
            <img
              class="wb-gen-item__img"
              v-if="gen.status === 'completed'" :src="generationPreviewUrl(gen.generation_id)"
              :alt="gen.prompt || 'generation'"
              loading="lazy"
            />
            <span class="wb-gen-item__info">
              <span class="wb-gen-item__prompt">{{ gen.prompt || '—' }}</span>
              <span class="wb-gen-item__tags">
                <span v-if="gen.scene" class="wb-gen-tag">{{ parameterLabel(t, 'scene', gen.scene) }}</span>
                <span v-if="gen.platform" class="wb-gen-tag">{{ parameterLabel(t, 'platform', gen.platform) }}</span>
                <span v-if="gen.style" class="wb-gen-tag">{{ parameterLabel(t, 'style', gen.style) }}</span>
              </span>
              <span class="wb-gen-item__status">{{ gen.status }}</span>
            </span>
          </button>
        </div>
        <button v-if="generations.length < generationsTotal" class="wb-history-more wb-load-more" type="button" :disabled="generationsLoading" @click="emit('load-more-history')">
          {{ generationsLoading ? t.ptmd.taskRunning : (t.account.breadcrumb==='Account'?'Load more history':'加载更多历史') }} · {{ generations.length }} / {{ generationsTotal }}
        </button>
      </template>

      <template v-else><slot name="templates">
        <div class="wb-empty">
          <p class="wb-empty__title">{{ t.ptmd.templates.empty }}</p>
          <p class="wb-empty__note">{{ t.ptmd.templates.emptyNote }}</p>
        </div></slot>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.wb-load-more{width:100%;margin-top:12px;padding:9px;border:1px solid var(--border-dim);border-radius:8px;background:var(--bg-glass);color:var(--text-primary);cursor:pointer}.wb-nav button:disabled{opacity:.5;cursor:not-allowed}.wb-history-error{font-size:12px;color:var(--text-secondary);overflow-wrap:anywhere}.wb-history-error button{padding:6px 12px;color:var(--text-primary);background:var(--bg-glass);border:1px solid var(--border-dim);border-radius:8px}
.wb-delete{padding:8px;margin:6px 0;border:1px solid #b65e69;border-radius:8px;background:var(--bg-sidebar);color:var(--text-primary);cursor:pointer}
.wb-upload-heading{font-size:13px;margin:8px 0 12px;color:var(--text-primary)}.wb-reference-zone{padding-top:16px;border-top:1px solid var(--border-dim);margin-top:18px}.wb-reference-zone p{font-size:11px;line-height:1.65;color:var(--text-secondary)}.wb-reference-check{position:absolute;top:2px;right:3px;background:var(--neon-blue);color:white;border-radius:50%;padding:1px 5px}
.wb-nav {
  position: relative;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: var(--wb-panel-w);
  min-width: var(--wb-panel-w);
  padding: 16px 14px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-dim);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow: hidden;
}

.wb-nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  color: var(--text-secondary);
  text-align: left;
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-smooth);
}

.wb-nav__item:hover {
  color: var(--text-primary);
  background: var(--bg-glass);
}

.wb-nav__item--active {
  background: var(--grad-active);
  color: #ffffff;
  box-shadow: 0 0 16px rgba(59, 130, 246, 0.4);
}

.wb-nav__icon {
  display: inline-flex;
  flex: none;
}

.wb-nav__label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.wb-nav__name {
  font-size: 14px;
  font-weight: 600;
}

.wb-nav__desc {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wb-nav__item--active .wb-nav__desc {
  color: rgba(255, 255, 255, 0.85);
}

.wb-nav__body {
  flex: 1;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-dim);
  overflow-y: auto;
}

.wb-upload {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-full);
  background: var(--grad-btn);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 0 14px var(--glow-purple);
  transition: filter var(--transition-fast), transform var(--transition-fast),
    box-shadow var(--transition-smooth);
}

.wb-upload:hover {
  filter: brightness(1.12) saturate(1.1);
  box-shadow: 0 0 20px var(--glow-purple);
  transform: translateY(-1px);
}

.wb-upload:active {
  transform: scale(0.97);
}

.wb-empty {
  padding: 28px 12px;
  text-align: center;
}

.wb-empty__title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.wb-empty__note {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.wb-nav__loading {
  padding: 20px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.wb-thumbs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 12px;
}

.wb-thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 12px;
  border: 1px solid var(--border-dim);
  overflow: hidden;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast);
}

.wb-thumb:hover {
  border-color: var(--neon-blue);
  box-shadow: 0 0 12px var(--glow-blue);
  transform: translateY(-1px);
}

.wb-thumb--active {
  border-color: var(--neon-blue);
  box-shadow: 0 0 14px var(--glow-blue), inset 0 0 0 2px var(--neon-blue);
}

.wb-thumb__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.wb-thumb__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 10, 26, 0.35);
  color: #ffffff;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.wb-thumb:hover .wb-thumb__overlay,
.wb-thumb--active .wb-thumb__overlay {
  opacity: 1;
}

.wb-drop-zone {
  position: relative;
  border-radius: 12px;
  transition: border-color var(--transition-fast), background var(--transition-smooth),
    box-shadow var(--transition-smooth);
}

.wb-drop-zone--active {
  background: rgba(59, 130, 246, 0.08);
  box-shadow: inset 0 0 0 2px var(--neon-blue), 0 0 16px var(--glow-blue);
}

.wb-drop-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 10px;
  padding: 14px 12px;
  border-radius: 12px;
  border: 1.5px dashed var(--border-dim);
  color: var(--text-secondary);
  font-size: 12px;
  transition: border-color var(--transition-fast), color var(--transition-fast);
}

.wb-drop-hint__icon {
  width: 18px;
  height: 18px;
  opacity: 0.7;
}

.wb-drop-zone--active .wb-drop-hint {
  border-color: var(--neon-blue);
  color: var(--neon-blue);
}

.wb-file-input {
  display: none;
}

.wb-upload:disabled,
.wb-spin {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.wb-spin::before {
  content: '';
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: wbSpin 0.8s linear infinite;
}

@keyframes wbSpin {
  to {
    transform: rotate(360deg);
  }
}

.wb-gen-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}

.wb-gen-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  text-align: left;
  transition: border-color var(--transition-fast), box-shadow var(--transition-smooth),
    transform var(--transition-fast);
}

.wb-gen-item:hover {
  border-color: var(--neon-purple);
  box-shadow: 0 0 10px var(--glow-purple);
  transform: translateY(-1px);
}

.wb-gen-item__img {
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 8px;
  object-fit: cover;
  display: block;
}

.wb-gen-item__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.wb-gen-item__prompt {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wb-gen-item__status {
  font-size: 11px;
  color: var(--text-secondary);
}

.wb-gen-filters {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.wb-gen-filter {
  width: 100%;
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-dim);
  background: var(--bg-glass);
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.wb-gen-filter:hover {
  border-color: var(--neon-blue);
}

.wb-gen-filter:focus {
  outline: none;
  border-color: var(--neon-blue);
  box-shadow: 0 0 8px var(--glow-blue);
}

.wb-gen-count {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 2px 4px;
}

.wb-gen-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.wb-gen-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.15);
  color: var(--neon-blue);
  font-size: 10px;
  font-weight: 500;
  white-space: nowrap;
}
</style>
