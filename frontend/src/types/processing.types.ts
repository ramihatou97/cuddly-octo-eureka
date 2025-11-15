/**
 * Processing Types
 * Types for discharge summary processing and generation
 */

import type { ClinicalDocument } from './document.types';

export interface ProcessingRequest {
  documents: ClinicalDocument[];
  options?: ProcessingOptions;
  useParallel?: boolean;
  useCache?: boolean;
  applyLearning?: boolean;
}

export interface ProcessingOptions {
  [key: string]: any;
}

export interface ProcessingResult {
  sessionId: string;
  summary: string;
  timeline: TimelineEvent[];
  uncertainties: Uncertainty[];
  metrics: ProcessingMetrics;
  status: 'processing' | 'completed' | 'failed';
}

export interface TimelineEvent {
  date: string;
  description: string;
  category: 'procedure' | 'medication' | 'lab' | 'complication' | 'other';
  confidence: number;
}

export interface Uncertainty {
  id: string;
  type: string; // Backend returns various types: MISSING_INFORMATION, CONFLICTING_INFORMATION, etc.
  uncertainty_type?: string; // Alias field from backend
  description: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW'; // Required for UI display
  suggested_resolution?: string; // Backend suggestion for resolution
  context: Record<string, any>; // Flexible context object
  sources?: string[]; // Conflicting sources (from backend: conflicting_sources)
  conflicting_sources?: string[]; // Alias from backend
  options?: string[];
  resolved: boolean;
}

/**
 * Learning feedback request (matches backend LearningFeedbackRequest)
 */
export interface LearningFeedbackRequest {
  uncertainty_id: string;
  original_extraction: string;
  correction: string;
  context: Record<string, any>;
  apply_immediately?: boolean;
}

/**
 * Learning feedback response (from POST /api/learning/feedback)
 */
export interface LearningFeedbackResponse {
  status: string;
  pattern_id: string;
  pattern_status: 'PENDING_APPROVAL' | 'APPROVED';
  message: string;
}

export interface ProcessingMetrics {
  totalDocuments: number;
  processingTimeMs: number;
  factsExtracted: number;
  validationsPassed: number;
  cacheHits: number;
}

export interface UncertaintyResolution {
  uncertaintyId: string;
  resolution: string;
  confidence: number;
}
