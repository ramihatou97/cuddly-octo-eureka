<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      colorClasses
    ]"
    :title="tooltipText"
  >
    <svg
      v-if="showIcon"
      :class="[
        '-ml-0.5 mr-1.5 h-3 w-3',
        iconColorClass
      ]"
      fill="currentColor"
      viewBox="0 0 8 8"
    >
      <circle cx="4" cy="4" r="3" />
    </svg>

    {{ displayText }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

/**
 * ConfidenceBadge Component
 *
 * Displays AI confidence scores with color-coded visual feedback
 *
 * CONFIDENCE LEVELS:
 * - High (≥ 0.7): Green - System is confident in suggestion
 * - Medium (0.5-0.7): Yellow - Moderate confidence, review recommended
 * - Low (< 0.5): Red - Low confidence, careful verification required
 *
 * SAFETY NOTE:
 * Even with high confidence, user MUST verify in Step 2.
 * This badge is informational only - not a bypass mechanism.
 */

interface Props {
  confidence: number; // 0-1 scale
  showIcon?: boolean;
  showPercentage?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const props = withDefaults(defineProps<Props>(), {
  showIcon: true,
  showPercentage: true,
  size: 'md'
});

// Confidence level classification
const confidenceLevel = computed<'high' | 'medium' | 'low'>(() => {
  if (props.confidence >= 0.7) return 'high';
  if (props.confidence >= 0.5) return 'medium';
  return 'low';
});

// Display text
const displayText = computed(() => {
  const percentage = Math.round(props.confidence * 100);

  if (props.showPercentage) {
    return `${percentage}% ${confidenceLevel.value}`;
  }

  return confidenceLevel.value.charAt(0).toUpperCase() + confidenceLevel.value.slice(1);
});

// Color classes based on confidence level
const colorClasses = computed(() => {
  const baseClasses = {
    high: 'bg-green-100 text-green-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-red-100 text-red-800'
  };

  return baseClasses[confidenceLevel.value];
});

// Icon color (slightly darker than background)
const iconColorClass = computed(() => {
  const iconClasses = {
    high: 'text-green-600',
    medium: 'text-yellow-600',
    low: 'text-red-600'
  };

  return iconClasses[confidenceLevel.value];
});

// Tooltip text
const tooltipText = computed(() => {
  const percentage = Math.round(props.confidence * 100);

  const descriptions = {
    high: 'System is confident in this suggestion, but please verify.',
    medium: 'Moderate confidence. Please review carefully.',
    low: 'Low confidence. Careful verification required.'
  };

  return `${percentage}% confidence - ${descriptions[confidenceLevel.value]}`;
});
</script>
