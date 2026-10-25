<script setup>
defineProps({
  code: { type: String, required: true },
  subtitle: { type: String, required: true },
  icon: { type: String, required: true },
})

defineEmits(['click'])
</script>

<template>
  <button class="feature-card glass" type="button" @click="$emit('click')">
    <span class="feature-card__icon">
      <img class="feature-card__icon-img" :src="icon" alt="" />
    </span>
    <span class="feature-card__text">
      <span class="feature-card__code">{{ code }}</span>
      <span class="feature-card__subtitle">{{ subtitle }}</span>
    </span>
    <span class="feature-card__arrow">
      <svg
        class="icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M5 12 h14" />
        <path d="m12 5 7 7 -7 7" />
      </svg>
    </span>
  </button>
</template>

<style scoped>
.feature-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  text-align: left;
  color: var(--text-primary);
  min-width: 0;
}

:global([data-theme='light']) .feature-card {
  background: linear-gradient(135deg, #FFE8A3 0%, #FFC65C 55%, #F5A623 100%);
  border-color: rgba(245, 166, 35, 0.4);
}

.feature-card:hover {
  transform: translateY(-5px);
  border-color: var(--neon-blue);
  box-shadow: 0 0 24px var(--glow-blue), 0 16px 36px rgba(0, 0, 0, 0.35);
}

.feature-card:active {
  transform: translateY(-2px) scale(0.985);
}

.feature-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  flex: none;
  border-radius: 14px;
  transition: box-shadow var(--transition-smooth), transform var(--transition-fast),
    filter var(--transition-smooth);
}

:global([data-theme='light']) .feature-card__icon {
  background: linear-gradient(135deg, #FFF0B3 0%, #FFD36A 55%, #F6B94A 100%);
  box-shadow: 0 2px 8px rgba(246, 185, 74, 0.3);
}

.feature-card__icon-img {
  width: 52px;
  height: 52px;
  filter: drop-shadow(0 0 10px var(--glow-purple));
  transition: filter var(--transition-smooth);
}

.feature-card:hover .feature-card__icon {
  transform: scale(1.05);
}

.feature-card:hover .feature-card__icon-img {
  filter: drop-shadow(0 0 14px var(--glow-purple)) drop-shadow(0 0 24px var(--glow-blue));
}

.feature-card__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.feature-card__code {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 2px;
}

.feature-card__subtitle {
  font-size: 13px;
  color: var(--text-secondary);
}

.feature-card__arrow {
  margin-left: auto;
  color: var(--text-secondary);
  transition: transform var(--transition-fast), color var(--transition-fast);
}

.feature-card:hover .feature-card__arrow {
  transform: translateX(4px);
  color: var(--neon-blue);
}
</style>