/**
 * useMultiNoteProcessor Composable
 * Business logic for bulk document import
 *
 * SAFETY ARCHITECTURE:
 * - parseBulkText() returns SUGGESTIONS only
 * - User MUST verify each document in Step 2 (human-in-the-loop)
 * - processVerifiedDocuments() only accepts human-confirmed data
 * - No bypass paths exist
 */

import { ref, computed } from 'vue';
import { multiNoteProcessorService } from '@/services/api/multiNoteProcessor.service';
import type { SuggestedDocument, VerifiedDocument } from '@/types/multiNoteProcessor.types';
import type { DocumentType } from '@/types/document.types';

export function useMultiNoteProcessor() {
  // ===== STATE =====

  // Step 1: Input
  const bulkText = ref('');
  const separatorType = ref<'auto' | 'custom'>('auto');
  const customSeparator = ref('');

  // Step 2: Suggestions (from parser)
  const suggestedDocs = ref<SuggestedDocument[]>([]);

  // Step 2: Verified (by human)
  const verifiedDocs = ref<VerifiedDocument[]>([]);

  // Loading & Error
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const parseWarnings = ref<string[]>([]);

  // ===== COMPUTED =====

  const hasDocuments = computed(() => verifiedDocs.value.length > 0);

  const lowConfidenceCount = computed(() =>
    suggestedDocs.value.filter(doc => doc.typeConfidence < 0.5).length
  );

  const hasWarnings = computed(() =>
    parseWarnings.value.length > 0 ||
    suggestedDocs.value.some(doc => doc.warnings.length > 0)
  );

  const allDocumentsVerified = computed(() => {
    return verifiedDocs.value.every(doc =>
      doc.userConfirmedType &&
      doc.userConfirmedDate
    );
  });

  // ===== ACTIONS =====

  /**
   * Step 1: Parse bulk text
   *
   * SAFETY: Calls parse-only endpoint. Returns suggestions, not decisions.
   */
  async function parseBulkText(): Promise<boolean> {
    // Validate input
    const validation = multiNoteProcessorService.validateBulkText(bulkText.value);
    if (!validation.valid) {
      error.value = validation.errors.join('. ');
      return false;
    }

    isLoading.value = true;
    error.value = null;
    parseWarnings.value = [];

    try {
      // Call PARSE-ONLY endpoint
      const result = await multiNoteProcessorService.parseBulkText(
        bulkText.value,
        separatorType.value,
        customSeparator.value
      );

      // Store suggestions
      suggestedDocs.value = result.suggestedDocuments;
      parseWarnings.value = result.warnings;

      // Initialize verified documents with suggestions
      // User will confirm/edit these in Step 2
      verifiedDocs.value = result.suggestedDocuments.map(suggested => ({
        index: suggested.index,
        content: suggested.content,
        userConfirmedType: suggested.suggestedType as DocumentType, // Start with suggestion
        userConfirmedDate: suggested.detectedDate
          ? new Date(suggested.detectedDate)
          : new Date(), // Default to now if not detected
        detectedAuthor: suggested.detectedAuthor,
        originalSuggestion: suggested.suggestedType as DocumentType,
        originalConfidence: suggested.typeConfidence,
        warnings: suggested.warnings
      }));

      return true;
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to parse bulk text';
      console.error('Parse error:', err);
      return false;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Step 2: Update verified document
   *
   * Human makes changes to suggested type, date, or content
   */
  function updateVerifiedDocument(
    index: number,
    updates: Partial<VerifiedDocument>
  ): void {
    const doc = verifiedDocs.value.find(d => d.index === index);
    if (doc) {
      Object.assign(doc, updates);
    }
  }

  /**
   * Step 2: Delete document
   *
   * User decides a document shouldn't be included
   */
  function deleteDocument(index: number): void {
    verifiedDocs.value = verifiedDocs.value.filter(d => d.index !== index);
    suggestedDocs.value = suggestedDocs.value.filter(d => d.index !== index);
  }

  /**
   * Step 3: Process verified documents
   *
   * SAFETY: All documents have been human-verified.
   * Calls EXISTING /api/process endpoint.
   */
  async function processVerifiedDocuments() {
    if (!allDocumentsVerified.value) {
      error.value = 'Please verify all documents before processing';
      return null;
    }

    isLoading.value = true;
    error.value = null;

    try {
      // Call EXISTING /api/process with human-verified data
      const result = await multiNoteProcessorService.processVerifiedDocuments(
        verifiedDocs.value
      );

      return result;
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to process documents';
      console.error('Processing error:', err);
      return null;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Reset all state
   */
  function reset(): void {
    bulkText.value = '';
    separatorType.value = 'auto';
    customSeparator.value = '';
    suggestedDocs.value = [];
    verifiedDocs.value = [];
    error.value = null;
    parseWarnings.value = [];
  }

  /**
   * Get supported separators (for UI display)
   */
  function getSupportedSeparators() {
    return multiNoteProcessorService.getSupportedSeparators();
  }

  // ===== RETURN =====

  return {
    // State - Input
    bulkText,
    separatorType,
    customSeparator,

    // State - Results
    suggestedDocs,
    verifiedDocs,
    parseWarnings,

    // State - UI
    isLoading,
    error,

    // Computed
    hasDocuments,
    lowConfidenceCount,
    hasWarnings,
    allDocumentsVerified,

    // Actions
    parseBulkText,
    updateVerifiedDocument,
    deleteDocument,
    processVerifiedDocuments,
    reset,
    getSupportedSeparators
  };
}
