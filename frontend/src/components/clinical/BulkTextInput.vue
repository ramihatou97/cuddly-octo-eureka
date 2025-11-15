<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h2 class="text-2xl font-bold text-gray-900">
        Step 1: Import Documents
      </h2>
      <p class="mt-2 text-sm text-gray-600">
        Paste multiple clinical notes below. The system will suggest how to separate them.
      </p>
    </div>

    <!-- Separator Selection -->
    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <label class="block text-sm font-medium text-gray-700 mb-3">
        Document Separator
      </label>

      <div class="space-y-3">
        <!-- Auto-detect -->
        <label class="flex items-start cursor-pointer">
          <input
            type="radio"
            :value="'auto'"
            v-model="localSeparatorType"
            class="mt-0.5 h-4 w-4 text-primary-600 focus:ring-primary-500"
          />
          <div class="ml-3">
            <div class="text-sm font-medium text-gray-900">
              Auto-detect (Recommended)
            </div>
            <div class="text-xs text-gray-600">
              System will detect horizontal rules (---), blank lines, or document headers
            </div>
          </div>
        </label>

        <!-- Custom separator -->
        <label class="flex items-start cursor-pointer">
          <input
            type="radio"
            :value="'custom'"
            v-model="localSeparatorType"
            class="mt-0.5 h-4 w-4 text-primary-600 focus:ring-primary-500"
          />
          <div class="ml-3 flex-1">
            <div class="text-sm font-medium text-gray-900">
              Custom separator
            </div>
            <div class="text-xs text-gray-600 mb-2">
              Specify your own separator pattern
            </div>

            <!-- Custom separator input -->
            <input
              v-if="localSeparatorType === 'custom'"
              type="text"
              v-model="localCustomSeparator"
              placeholder="e.g., ===END OF NOTE==="
              class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
              :disabled="localSeparatorType !== 'custom'"
            />
          </div>
        </label>
      </div>
    </div>

    <!-- Bulk Text Area -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-2">
        Clinical Notes
        <span class="text-gray-500 font-normal">
          ({{ characterCount.toLocaleString() }} characters)
        </span>
      </label>

      <textarea
        v-model="localBulkText"
        rows="20"
        placeholder="Paste all clinical notes here...

Example:
ADMISSION NOTE - 2024-01-15
Patient admitted with severe headache...
---
OPERATIVE NOTE - 2024-01-16
Procedure: Left craniotomy...
---
PROGRESS NOTE - 2024-01-17
Patient is alert and oriented..."
        class="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm font-mono"
        :class="{
          'border-red-300 focus:border-red-500 focus:ring-red-500': validationError
        }"
      />

      <!-- Validation Error -->
      <p v-if="validationError" class="mt-2 text-sm text-red-600">
        {{ validationError }}
      </p>

      <!-- Helper Text -->
      <p v-else class="mt-2 text-xs text-gray-500">
        Minimum 100 characters. The system will analyze and suggest document types, which you'll verify in Step 2.
      </p>
    </div>

    <!-- Example Link -->
    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <button
        type="button"
        @click="loadExample"
        class="text-sm text-primary-600 hover:text-primary-700 font-medium"
      >
        Load example documents
      </button>
      <span class="text-xs text-gray-500 ml-2">
        (3 sample clinical notes)
      </span>
    </div>

    <!-- Action Buttons -->
    <div class="flex justify-between items-center pt-4 border-t">
      <div class="text-sm text-gray-600">
        <span class="font-medium">Next:</span> Review and verify suggested document types
      </div>

      <div class="flex space-x-3">
        <button
          type="button"
          @click="handleReset"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
          :disabled="!localBulkText"
        >
          Clear
        </button>

        <button
          type="button"
          @click="handleParse"
          :disabled="!canParse || isLoading"
          class="px-6 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="isLoading" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Analyzing...
          </span>
          <span v-else>
            Parse Documents →
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

/**
 * BulkTextInput Component
 *
 * Step 1 of Clinical Workflow: Import bulk clinical text
 *
 * SAFETY NOTES:
 * - This component ONLY collects input and triggers parsing
 * - Parse button calls parse-only endpoint (returns suggestions)
 * - No processing happens until Step 2 verification is complete
 */

interface Props {
  bulkText: string;
  separatorType: 'auto' | 'custom';
  customSeparator: string;
  isLoading?: boolean;
  validationError?: string | null;
}

interface Emits {
  (e: 'update:bulkText', value: string): void;
  (e: 'update:separatorType', value: 'auto' | 'custom'): void;
  (e: 'update:customSeparator', value: string): void;
  (e: 'parse'): void;
  (e: 'reset'): void;
}

const props = withDefaults(defineProps<Props>(), {
  isLoading: false,
  validationError: null
});

const emit = defineEmits<Emits>();

// Local state synced with parent via v-model
const localBulkText = computed({
  get: () => props.bulkText,
  set: (value) => emit('update:bulkText', value)
});

const localSeparatorType = computed({
  get: () => props.separatorType,
  set: (value) => emit('update:separatorType', value)
});

const localCustomSeparator = computed({
  get: () => props.customSeparator,
  set: (value) => emit('update:customSeparator', value)
});

// Character count
const characterCount = computed(() => localBulkText.value.length);

// Can parse if text is valid
const canParse = computed(() => {
  const text = localBulkText.value.trim();
  if (text.length < 100) return false;
  if (text.length > 1000000) return false;
  if (localSeparatorType.value === 'custom' && !localCustomSeparator.value.trim()) return false;
  return true;
});

// Example data
const EXAMPLE_DOCUMENTS = `ADMISSION NOTE - January 15, 2024
Chief Complaint: Severe headache, visual disturbances
History of Present Illness: 45-year-old female presents with 3-day history of progressive headache, nausea, and blurred vision. No trauma. No fever.
Physical Examination: Alert and oriented x3. Papilledema noted on fundoscopic exam.
Assessment: Possible increased intracranial pressure. Rule out mass lesion.
Plan: MRI brain, neurosurgery consult.

Dr. Sarah Johnson, Internal Medicine
---
OPERATIVE NOTE - January 16, 2024
Surgeon: Dr. Michael Chen, Neurosurgery
Procedure: Left frontal craniotomy for tumor resection
Preoperative Diagnosis: Left frontal mass lesion
Postoperative Diagnosis: Meningioma (preliminary)
Anesthesia: General endotracheal
Estimated Blood Loss: 200 mL
Complications: None
Findings: Well-circumscribed extra-axial mass consistent with meningioma. Gross total resection achieved.
Patient tolerated procedure well and transferred to ICU in stable condition.
---
PROGRESS NOTE - January 17, 2024
Postoperative Day 1
Subjective: Patient reports mild headache, controlled with acetaminophen.
Objective: Vital signs stable. Neurologically intact. Incision clean, dry, intact.
Assessment: Uncomplicated postoperative course.
Plan: Continue current management. Physical therapy evaluation. Anticipate transfer to floor.

Dr. Michael Chen, Neurosurgery`;

function loadExample(): void {
  localBulkText.value = EXAMPLE_DOCUMENTS;
  localSeparatorType.value = 'auto';
}

function handleParse(): void {
  if (canParse.value && !props.isLoading) {
    emit('parse');
  }
}

function handleReset(): void {
  emit('reset');
}
</script>
