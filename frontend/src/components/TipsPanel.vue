<script setup>
defineProps({
  t: { type: Object, required: true },
})
</script>

<template>
  <div class="tips-card">
    <div class="tips-card__icon">
      <svg
        class="tips-card__icon-svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M9 18h6" />
        <path d="M10 22h4" />
        <path d="M15.09 14c.18-.8.14-1.63-.12-2.4-.3-.86-.8-1.5-1.4-2.1-1.2-1.2-1.8-2.5-1.8-4.5 0-.5-.2-1-.5-1.4-.7-.8-1.8-.8-2.5 0-.3.4-.5.9-.5 1.4 0 2-.6 3.3-1.8 4.5-.6.6-1.1 1.24-1.4 2.1-.26.77-.3 1.6-.12 2.4" />
      </svg>
    </div>
    <div class="tips-card__body">
      <p class="tips-card__title">{{ t.tips.title }}</p>
      <p class="tips-card__content">{{ t.tips.content }}</p>
    </div>
  </div>
</template>

<style scoped>
.tips-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-md);
  background: var(--bg-card);
  border: 1px solid var(--border-glow);
  box-shadow: var(--shadow-card);
  transition: transform var(--transition-smooth), border-color var(--transition-smooth);
}

.tips-card:hover {
  transform: translateY(-2px);
  border-color: var(--neon-purple);
}

.tips-card__icon {
  display: flex;
  align-items: flex-start;
}

.tips-card__icon-svg {
  width: 24px;
  height: 24px;
  color: var(--neon-purple);
  filter: drop-shadow(0 0 6px var(--glow-purple));
}

.tips-card__title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.tips-card__content {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>