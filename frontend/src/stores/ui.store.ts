/**
 * UI Store
 * Pinia store for global UI state (toasts, modals, loading)
 */

import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { Toast, ToastType } from '@/types';

export const useUIStore = defineStore('ui', () => {
  // State
  const toasts = ref<Toast[]>([]);
  const isGlobalLoading = ref(false);
  const globalLoadingMessage = ref('');

  // Actions
  function addToast(type: ToastType, message: string, duration = 5000) {
    const id = `toast-${Date.now()}-${Math.random()}`;

    const toast: Toast = {
      id,
      type,
      message,
      duration
    };

    toasts.value.push(toast);

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }

    return id;
  }

  function removeToast(id: string) {
    const index = toasts.value.findIndex(t => t.id === id);
    if (index > -1) {
      toasts.value.splice(index, 1);
    }
  }

  function clearToasts() {
    toasts.value = [];
  }

  function showLoading(message = 'Loading...') {
    isGlobalLoading.value = true;
    globalLoadingMessage.value = message;
  }

  function hideLoading() {
    isGlobalLoading.value = false;
    globalLoadingMessage.value = '';
  }

  // Convenience methods
  function success(message: string) {
    return addToast('success', message);
  }

  function error(message: string) {
    return addToast('error', message, 7000);
  }

  function warning(message: string) {
    return addToast('warning', message);
  }

  function info(message: string) {
    return addToast('info', message);
  }

  return {
    // State
    toasts,
    isGlobalLoading,
    globalLoadingMessage,

    // Actions
    addToast,
    removeToast,
    clearToasts,
    showLoading,
    hideLoading,

    // Convenience
    success,
    error,
    warning,
    info
  };
});
