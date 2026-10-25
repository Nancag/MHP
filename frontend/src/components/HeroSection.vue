<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  t: { type: Object, required: true },
})

const app = inject('appContext')
const english = computed(() => props.t.account.breadcrumb === 'Account')

function startCreate() {
  if (app.user) app.showView('ptmd')
  else app.openAuth('register')
}
</script>

<template>
  <section class="hx-hero">
    <div>
      <div class="hx-eyebrow">
        <span class="dot"></span>
        <span class="micro">{{ english ? 'Product photo studio' : '商品图工作室' }}</span>
        <span class="rule"></span>
        <span class="micro">PTMD 1.0</span>
      </div>

      <h1 class="hx-title">
        <template v-if="english">Put your product<br />into <em>a beam of light</em>.</template>
        <template v-else>把你的商品<br />放进<em>一束光</em>里<em>。</em></template>
      </h1>

      <p class="hx-lede">
        <template v-if="english">
          Start with your product photos. Choose a layout, write your copy,
          and create independent listing images. <b>Your original product stays visible.</b>
          Crop details and review every page before exporting.
        </template>
        <template v-else>
          上传真实商品图、选择版式、填写文案，制作独立商品图。
          <b>保留原图中的商品</b>，支持局部裁切、卖点排版和逐页审核后导出。
        </template>
      </p>

      <div class="hx-cta">
        <button class="hx-big" type="button" @click="startCreate">
          {{ english ? 'Start creating' : '开始制作' }}
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
               stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
        <button class="hx-outline" type="button" @click="app.showView('templates')">
          {{ english ? 'My templates' : '查看我的模板' }}
        </button>
      </div>

      <div class="hx-trust">
        <span>{{ english ? 'New account: 5 free images' : '新号送 5 张' }}</span>
        <span class="sep"></span>
        <span>{{ english ? 'Daily check-in +2' : '每天签到 +2 张' }}</span>
        <span class="sep"></span>
        <span>{{ english ? 'No card needed' : '不用绑卡' }}</span>
      </div>
    </div>

    <div class="hx-gallery">
      <span class="gallery-disclosure">{{ english ? 'Layout illustrations · not generated examples' : '版式示意插画 · 非真实生成案例' }}</span>
      <article class="hx-print hx-p1">
        <div class="hx-print__img">
          <div class="hx-glow"></div>
          <div class="hx-floor"></div>
          <div class="hx-shadow"></div>
          <div class="hx-prod">
            <span class="pb"></span>
            <span class="ps"></span>
            <span class="pl bl"></span>
            <span class="pl br"></span>
            <span class="pl l"></span>
            <span class="pl r"></span>
          </div>
          <span class="hx-stamp">1 / 3</span>
        </div>
        <div class="hx-print__cap"><b>{{ english ? 'Nordic chair · ivory' : '北欧单椅 · 米白' }}</b><span>{{ english ? 'Balcony' : '阳台' }}</span></div>
      </article>

      <article class="hx-print hx-p2">
        <div class="hx-print__img" style="background: linear-gradient(180deg, #f5f0e6, #e2e6eb)">
          <div class="hx-glow"></div>
          <div class="hx-floor"></div>
          <div class="hx-ru">
            Мягкое кресло
            <small>натуральная ткань</small>
          </div>
          <div class="hx-shadow" style="top: 80%"></div>
          <div class="hx-prod hx-prod--sofa">
            <span class="pb"></span>
            <span class="ps"></span>
            <span class="pl l"></span>
            <span class="pl r"></span>
          </div>
          <span class="hx-stamp">2 / 3</span>
        </div>
        <div class="hx-print__cap"><b>{{ english ? 'Linen sofa · grey' : '亚麻沙发 · 灰' }}</b><span>{{ english ? 'Solid' : '纯色底' }}</span></div>
      </article>

      <article class="hx-print hx-p3">
        <div class="hx-print__img" style="background: linear-gradient(180deg, #f7f1e4, #e8dac2)">
          <div class="hx-glow"></div>
          <div class="hx-floor"></div>
          <div class="hx-shadow"></div>
          <div class="hx-prod hx-prod--lamp">
            <span class="shade"></span>
            <span class="stem"></span>
            <span class="base"></span>
          </div>
          <span class="hx-stamp">3 / 3</span>
        </div>
        <div class="hx-print__cap"><b>{{ english ? 'Ceramic lamp' : '陶瓷台灯' }}</b><span>{{ english ? 'Bedroom' : '卧室' }}</span></div>
      </article>
    </div>
  </section>
</template>
