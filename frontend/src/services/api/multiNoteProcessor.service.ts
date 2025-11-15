/**
 * Multi-Note Processor Service
 * Handles bulk document import and parsing
 *
 * SAFETY ARCHITECTURE:
 * - parseBulkText() calls PARSE-ONLY endpoint (/api/bulk-import/parse)
 * - Returns SUGGESTIONS, never auto-processes
 * - processVerifiedDocuments() calls EXISTING /api/process endpoint
 * - All processing goes through human-verified data only
 */

import { apiClient } from './client';
import type {
  BulkImportRequest,
  ParseResult,
  VerifiedDocument
} from '@/types/multiNoteProcessor.types';
import type { ProcessingRequest, ProcessingResult } from '@/types/processing.types';

export class MultiNoteProcessorService {
  /**
   * Step 1: Parse bulk text into suggested documents
   *
   * SAFETY: This endpoint ONLY parses and suggests.
   * It does NOT process documents or call the engine.
   *
   * @param bulkText - Raw clinical text with multiple documents
   * @param separatorType - 'auto' or 'custom'
   * @param customSeparator - Optional custom separator string
   * @returns Suggested documents with confidence scores
   */
  async parseBulkText(
    bulkText: string,
    separatorType: 'auto' | 'custom' = 'auto',
    customSeparator?: string
  ): Promise<ParseResult> {
    const request: BulkImportRequest = {
      bulkText,
      separatorType,
      customSeparator
    };

    // Call PARSE-ONLY endpoint
    // This endpoint returns suggestions but does NOT process
    const response = await apiClient.post<ParseResult>(
      '/api/bulk-import/parse',
      {
        bulk_text: request.bulkText,
        separator_type: request.separatorType,
        custom_separator: request.customSeparator
      }
    );

    return response;
  }

  /**
   * Step 3: Process human-verified documents
   *
   * SAFETY: This calls the EXISTING /api/process endpoint (187 tests).
   * All documents have been human-verified in Step 2.
   * Types and dates are confirmed by user, not auto-suggested.
   *
   * @param verifiedDocuments - Documents verified by human in UI
   * @returns Processing result with session ID
   */
  async processVerifiedDocuments(
    verifiedDocuments: VerifiedDocument[]
  ): Promise<ProcessingResult> {
    // Transform to format expected by existing /api/process endpoint
    const processRequest: ProcessingRequest = {
      documents: verifiedDocuments.map(doc => ({
        name: `document_${doc.index}.txt`,
        content: doc.content, // May have been edited by user
        date: doc.userConfirmedDate.toISOString(), // HUMAN-VERIFIED
        type: doc.userConfirmedType, // HUMAN-VERIFIED (not suggested)
        metadata: {
          author: doc.detectedAuthor || undefined,
          imported_via: 'bulk_upload',
          // Track original suggestion vs user choice
          original_suggestion: doc.originalSuggestion,
          original_confidence: doc.originalConfidence
        }
      })),
      options: {},
      useParallel: true,
      useCache: true,
      applyLearning: true
    };

    // Call EXISTING endpoint (not a new processing endpoint)
    // This ensures all processing goes through validated code
    const response = await apiClient.post<ProcessingResult>(
      '/api/process',
      {
        documents: processRequest.documents,
        options: processRequest.options,
        use_parallel: processRequest.useParallel,
        use_cache: processRequest.useCache,
        apply_learning: processRequest.applyLearning
      }
    );

    return response;
  }

  /**
   * Get list of supported separator patterns
   * For UI display/selection
   */
  getSupportedSeparators(): Array<{ value: string; label: string; example: string }> {
    return [
      {
        value: 'auto',
        label: 'Auto-detect',
        example: 'System will detect horizontal rules, blank lines, or headers'
      },
      {
        value: 'custom',
        label: 'Custom separator',
        example: 'Specify your own separator pattern'
      }
    ];
  }

  /**
   * Validate bulk text before parsing
   * Pre-flight check to provide immediate feedback
   */
  validateBulkText(bulkText: string): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!bulkText || bulkText.trim().length === 0) {
      errors.push('Bulk text cannot be empty');
    }

    if (bulkText.length < 100) {
      errors.push('Bulk text seems too short. Are you sure it contains multiple documents?');
    }

    if (bulkText.length > 1000000) {
      errors.push('Bulk text is too large (max 1MB)');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }
}

// Export singleton instance
export const multiNoteProcessorService = new MultiNoteProcessorService();
