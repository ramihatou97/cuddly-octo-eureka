<template>
  <Transition name="toast">
    <div
      v-if="isVisible"
      :class="[
        'toast',
        'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg',
        'min-w-[300px] max-w-md',
        toastClasses
      ]"
      role="alert"
    >
      <!-- Icon -->
      <div class="flex-shrink-0">
        <component :is="icon" class="w-5 h-5" />
      </div>

      <!-- Message -->
      <p class="flex-1 text-sm font-medium">
        {{ message }}
      </p>

      <!-- Close Button -->
      <button
        @click="handleClose"
        class="flex-shrink-0 text-current opacity-70 hover:opacity-100 transition-opacity"
        aria-label="Close"
      >
        <XMarkIcon class="w-5 h-5" />
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon
} from '@heroicons/vue/24/outline';
import type { ToastType } from '@/types';

const props = withDefaults(defineProps<{
  type: ToastType;
  message: string;
  duration?: number;
}>(), {
  duration: 5000
});

const emit = defineEmits<{
  close: [];
}>();

const isVisible = ref(false);

const toastClasses = computed(() => {
  const classes = {
    success: 'bg-success-50 text-success-800 border border-success-200',
    error: 'bg-error-50 text-error-800 border border-error-200',
    warning: 'bg-warning-50 text-warning-800 border border-warning-200',
    info: 'bg-primary-50 text-primary-800 border border-primary-200'
  };
  return classes[props.type];
});

const icon = computed(() => {
  const icons = {
    success: CheckCircleIcon,
    error: XCircleIcon,
    warning: ExclamationTriangleIcon,
    info: InformationCircleIcon
  };
  return icons[props.type];
});

function handleClose() {
  isVisible.value = false;
  setTimeout(() => {
    emit('close');
  }, 300);
}

onMounted(() => {
  // Fade in
  isVisible.value = true;

  // Auto-close
  if (props.duration > 0) {
    setTimeout(() => {
      handleClose();
    }, props.duration);
  }
});
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
