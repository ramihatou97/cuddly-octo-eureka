<template>
  <div
    :class="[
      'border-l-4 rounded-r-lg p-4 mb-4 transition-all',
      severityBorderClass,
      severityBackgroundClass
    ]"
  >
    <!-- Header -->
    <div class="flex justify-between items-start">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <span
            :class="[
              'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
              severityBadgeClass
            ]"
          >
            {{ uncertainty.severity || 'MEDIUM' }}
          </span>
          <span class="text-sm font-medium text-gray-700">
            {{ displayType }}
          </span>
        </div>

        <p class="text-gray-900 mb-2">{{ uncertainty.description }}</p>

        <p v-if="uncertainty.suggested_resolution" class="text-sm text-gray-600 italic">
          💡 Suggestion: {{ uncertainty.suggested_resolution }}
        </p>

        <!-- Sources -->
        <div v-if="sources.length > 0" class="mt-2 text-xs text-gray-500">
          <span class="font-medium">Sources:</span> {{ sources.join(', ') }}
        </div>
      </div>

      <!-- Resolve Button -->
      <Button
        v-if="!showForm && !resolved"
        variant="primary"
        size="sm"
        @click="showForm = true"
        class="ml-4 flex-shrink-0"
      >
        Resolve
      </Button>

      <!-- Resolved Badge -->
      <div v-if="resolved" class="ml-4 flex-shrink-0">
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
          ✓ Resolved
        </span>
      </div>
    </div>

    <!-- Feedback Form (Expandable) -->
    <div
      v-if="showForm"
      class="mt-4 pt-4 border-t"
      :class="severityBorderClass"
    >
      <div class="bg-white rounded-md p-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Submit Correction
        </label>
        <p class="text-xs text-gray-500 mb-3">
          Teach the system how to extract this information correctly. Your correction will be reviewed before being applied to future extractions.
        </p>

        <textarea
          v-model="correctionText"
          class="w-full p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          rows="3"
          :placeholder="uncertainty.suggested_resolution || 'Enter the correct information...'"
          :disabled="isSubmitting"
        ></textarea>

        <!-- Context display (for transparency) -->
        <div v-if="Object.keys(uncertainty.context || {}).length > 0" class="mt-2 p-2 bg-gray-50 rounded text-xs">
          <span class="font-medium text-gray-700">Context:</span>
          <pre class="mt-1 text-gray-600 whitespace-pre-wrap">{{ JSON.stringify(uncertainty.context, null, 2) }}</pre>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
          <p class="text-sm text-red-800">{{ errorMessage }}</p>
        </div>

        <!-- Success Message -->
        <div v-if="successMessage" class="mt-3 p-3 bg-green-50 border border-green-200 rounded-md">
          <p class="text-sm text-green-800">{{ successMessage }}</p>
        </div>

        <!-- Action Buttons -->
        <div class="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            @click="handleCancel"
            :disabled="isSubmitting"
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            @click="handleSubmit"
            :disabled="!correctionText.trim() || isSubmitting"
            :loading="isSubmitting"
          >
            Submit Correction
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { Uncertainty, LearningFeedbackRequest } from '@/types/processing.types';
import { learningService } from '@/services/api/learning.service';
import Button from './shared/Button.vue';

export interface UncertaintyCardProps {
  uncertainty: Uncertainty;
  sessionId?: string;
}

const props = defineProps<UncertaintyCardProps>();

const emit = defineEmits<{
  feedbackSubmitted: [uncertaintyId: string];
  resolved: [uncertaintyId: string];
}>();

// Component state
const showForm = ref(false);
const correctionText = ref('');
const isSubmitting = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const resolved = ref(props.uncertainty.resolved || false);

// Computed properties
const displayType = computed(() => {
  return (props.uncertainty.uncertainty_type || props.uncertainty.type || 'UNKNOWN')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, char => char.toUpperCase());
});

const sources = computed(() => {
  return props.uncertainty.sources ||
         props.uncertainty.conflicting_sources ||
         [];
});

const severityBorderClass = computed(() => {
  switch (props.uncertainty.severity) {
    case 'HIGH':
      return 'border-red-500';
    case 'MEDIUM':
      return 'border-yellow-500';
    case 'LOW':
      return 'border-blue-500';
    default:
      return 'border-gray-500';
  }
});

const severityBackgroundClass = computed(() => {
  switch (props.uncertainty.severity) {
    case 'HIGH':
      return 'bg-red-50';
    case 'MEDIUM':
      return 'bg-yellow-50';
    case 'LOW':
      return 'bg-blue-50';
    default:
      return 'bg-gray-50';
  }
});

const severityBadgeClass = computed(() => {
  switch (props.uncertainty.severity) {
    case 'HIGH':
      return 'bg-red-100 text-red-800';
    case 'MEDIUM':
      return 'bg-yellow-100 text-yellow-800';
    case 'LOW':
      return 'bg-blue-100 text-blue-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
});

// Methods
async function handleSubmit() {
  if (!correctionText.value.trim()) {
    return;
  }

  isSubmitting.value = true;
  errorMessage.value = '';
  successMessage.value = '';

  try {
    const feedbackData: LearningFeedbackRequest = {
      uncertainty_id: props.uncertainty.id,
      original_extraction: props.uncertainty.context?.original_fact || props.uncertainty.description,
      correction: correctionText.value.trim(),
      context: {
        ...props.uncertainty.context,
        session_id: props.sessionId,
        uncertainty_type: props.uncertainty.type
      },
      apply_immediately: false // Require admin approval
    };

    const response = await learningService.submitFeedback(feedbackData);

    // Success!
    successMessage.value = response.message || 'Correction submitted successfully!';

    if (response.pattern_status === 'APPROVED') {
      successMessage.value += ' This pattern has been auto-approved and will be applied immediately.';
    } else {
      successMessage.value += ' Your correction is pending admin review.';
    }

    // Mark as resolved locally
    resolved.value = true;

    // Emit events
    emit('feedbackSubmitted', props.uncertainty.id);
    emit('resolved', props.uncertainty.id);

    // Close form after 2 seconds
    setTimeout(() => {
      showForm.value = false;
      correctionText.value = '';
    }, 2000);

  } catch (error: any) {
    errorMessage.value = error.message || 'Failed to submit correction. Please try again.';
  } finally {
    isSubmitting.value = false;
  }
}

function handleCancel() {
  showForm.value = false;
  correctionText.value = '';
  errorMessage.value = '';
  successMessage.value = '';
}
</script>
