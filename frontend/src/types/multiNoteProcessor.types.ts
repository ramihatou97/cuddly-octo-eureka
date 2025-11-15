/**
 * Multi-Note Processor Types
 * Types for bulk document import and parsing
 */

import type { DocumentType } from './document.types';

export interface SuggestedDocument {
  index: number;
  content: string;
  suggestedType: DocumentType;
  typeConfidence: number; // 0-1
  detectedDate: string | null; // ISO 8601
  detectedAuthor: string | null;
  separatorUsed: string;
  warnings: string[];
}

export interface ParseResult {
  suggestedDocuments: SuggestedDocument[];
  totalCount: number;
  warnings: string[];
  separatorUsed: string;
  metadata: {
    processorVersion: string;
    processingTimeMs: number;
    separatorType: string;
  };
}

export interface VerifiedDocument {
  index: number;
  content: string;
  userConfirmedType: DocumentType;  // HUMAN-VERIFIED
  userConfirmedDate: Date;           // HUMAN-VERIFIED
  detectedAuthor: string | null;
  originalSuggestion: DocumentType;
  originalConfidence: number;
  warnings?: string[];
}

export interface BulkImportRequest {
  bulkText: string;
  separatorType: 'auto' | 'custom';
  customSeparator?: string;
}
