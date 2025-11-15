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
  type: 'ambiguous_dose' | 'unclear_timeline' | 'conflicting_information' | 'missing_data';
  description: string;
  context: string;
  options?: string[];
  resolved: boolean;
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
