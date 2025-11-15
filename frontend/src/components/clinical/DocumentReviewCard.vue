<template>
  <div
    class="bg-white border rounded-lg shadow-sm hover:shadow-md transition-shadow"
    :class="{
      'border-gray-300': !hasWarnings,
      'border-yellow-400 bg-yellow-50': hasWarnings
    }"
  >
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <span class="text-lg font-semibold text-gray-900">
          Document {{ document.index + 1 }}
        </span>

        <ConfidenceBadge
          :confidence="document.originalConfidence"
          :showPercentage="true"
        />

        <!-- Changed indicator -->
        <span
          v-if="hasUserChanges"
          class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
          title="You modified the suggested type or date"
        >
          Modified
        </span>
      </div>

      <!-- Delete button -->
      <button
        type="button"
        @click="handleDelete"
        class="text-gray-400 hover:text-red-600 transition-colors"
        title="Remove this document"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>

    <!-- Warnings -->
    <div
      v-if="hasWarnings"
      class="px-6 py-3 bg-yellow-50 border-b border-yellow-200"
    >
      <div class="flex items-start">
        <svg class="h-5 w-5 text-yellow-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        <div class="ml-3 flex-1">
          <h4 class="text-sm font-medium text-yellow-800">
            Parser Warnings
          </h4>
          <ul class="mt-1 text-sm text-yellow-700 list-disc list-inside space-y-1">
            <li v-for="(warning, idx) in document.warnings" :key="idx">
              {{ warning }}
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Form -->
    <div class="px-6 py-5 space-y-5">
      <!-- Document Type Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Document Type
          <span class="text-red-600">*</span>
        </label>

        <select
          :value="localDocument.userConfirmedType"
          @change="handleTypeChange"
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        >
          <option
            v-for="type in documentTypes"
            :key="type.value"
            :value="type.value"
          >
            {{ type.label }}
            <span v-if="type.value === document.originalSuggestion">
              (Suggested)
            </span>
          </option>
        </select>

        <p class="mt-1 text-xs text-gray-500">
          Original suggestion: <span class="font-medium">{{ formatDocumentType(document.originalSuggestion) }}</span>
        </p>
      </div>

      <!-- Date Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Document Date
          <span class="text-red-600">*</span>
        </label>

        <input
          type="date"
          :value="dateInputValue"
          @input="handleDateChange"
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
        />

        <p v-if="document.detectedAuthor" class="mt-1 text-xs text-gray-500">
          Detected author: <span class="font-medium">{{ document.detectedAuthor }}</span>
        </p>
      </div>

      <!-- Content Preview (Collapsible) -->
      <div>
        <button
          type="button"
          @click="showContent = !showContent"
          class="flex items-center justify-between w-full text-left text-sm font-medium text-gray-700"
        >
          <span>Document Content</span>
          <svg
            class="h-5 w-5 text-gray-400 transition-transform"
            :class="{ 'rotate-180': showContent }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <div v-if="showContent" class="mt-3">
          <textarea
            :value="localDocument.content"
            @input="handleContentChange"
            rows="12"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm font-mono text-xs"
            placeholder="Document content..."
          />

          <p class="mt-1 text-xs text-gray-500">
            {{ contentLength.toLocaleString() }} characters
            {{ contentModified ? '(modified)' : '' }}
          </p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="px-6 py-4 bg-gray-50 border-t border-gray-200 rounded-b-lg">
      <div class="flex items-center justify-between">
        <div class="text-xs text-gray-600">
          <span v-if="isVerified" class="flex items-center text-green-700">
            <svg class="h-4 w-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            Verified
          </span>
          <span v-else class="text-yellow-700">
            Please confirm type and date
          </span>
        </div>

        <button
          v-if="showContent"
          type="button"
          @click="showContent = false"
          class="text-xs text-primary-600 hover:text-primary-700 font-medium"
        >
          Collapse content
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { VerifiedDocument, DocumentType } from '@/types/multiNoteProcessor.types';
import ConfidenceBadge from './ConfidenceBadge.vue';

/**
 * DocumentReviewCard Component
 *
 * Step 2 of Clinical Workflow: Human verification of suggested documents
 *
 * CRITICAL SAFETY COMPONENT:
 * - This is the MANDATORY human gate
 * - User must verify type and date for each document
 * - Content can be edited if needed
 * - No bypass mechanism exists
 * - Document cannot proceed to Step 3 without verification
 */

interface Props {
  document: VerifiedDocument;
}

interface Emits {
  (e: 'update', updates: Partial<VerifiedDocument>): void;
  (e: 'delete'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

// Local state
const showContent = ref(false);
const localDocument = ref({ ...props.document });
const contentModified = ref(false);

// Document types (matching backend)
const documentTypes = [
  { value: 'admission', label: 'Admission Note' },
  { value: 'operative', label: 'Operative Note' },
  { value: 'progress', label: 'Progress Note' },
  { value: 'consult', label: 'Consultation Note' },
  { value: 'lab', label: 'Lab Report' },
  { value: 'imaging', label: 'Imaging Report' },
  { value: 'nursing', label: 'Nursing Note' },
  { value: 'discharge_planning', label: 'Discharge Planning Note' }
];

// Computed
const hasWarnings = computed(() =>
  props.document.warnings && props.document.warnings.length > 0
);

const hasUserChanges = computed(() =>
  props.document.userConfirmedType !== props.document.originalSuggestion ||
  contentModified.value
);

const isVerified = computed(() =>
  !!props.document.userConfirmedType && !!props.document.userConfirmedDate
);

const contentLength = computed(() =>
  localDocument.value.content?.length || 0
);

// Date formatting for input
const dateInputValue = computed(() => {
  const date = props.document.userConfirmedDate;
  if (!date) return '';

  const d = date instanceof Date ? date : new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
});

// Handlers
function handleTypeChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  emit('update', {
    userConfirmedType: target.value as DocumentType
  });
}

function handleDateChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('update', {
    userConfirmedDate: new Date(target.value)
  });
}

function handleContentChange(event: Event): void {
  const target = event.target as HTMLTextAreaElement;
  contentModified.value = target.value !== props.document.content;
  localDocument.value.content = target.value;

  emit('update', {
    content: target.value
  });
}

function handleDelete(): void {
  if (confirm('Are you sure you want to remove this document?')) {
    emit('delete');
  }
}

function formatDocumentType(type: DocumentType): string {
  const typeObj = documentTypes.find(t => t.value === type);
  return typeObj?.label || type;
}
</script>
