/**
 * useToast Composable
 * Toast notifications for components
 */

import { computed } from 'vue';
import { useUIStore } from '@/stores/ui.store';
import type { ToastType } from '@/types';

export function useToast() {
  const uiStore = useUIStore();

  const toasts = computed(() => uiStore.toasts);

  function addToast(type: ToastType, message: string, duration?: number) {
    return uiStore.addToast(type, message, duration);
  }

  function removeToast(id: string) {
    uiStore.removeToast(id);
  }

  function success(message: string) {
    return uiStore.success(message);
  }

  function error(message: string) {
    return uiStore.error(message);
  }

  function warning(message: string) {
    return uiStore.warning(message);
  }

  function info(message: string) {
    return uiStore.info(message);
  }

  return {
    toasts,
    addToast,
    removeToast,
    success,
    error,
    warning,
    info
  };
}
