import { inject } from 'vue'

export function useAppContext() {
  const ctx = inject('appContext')
  if (!ctx) {
    throw new Error('appContext 未提供')
  }
  return ctx
}