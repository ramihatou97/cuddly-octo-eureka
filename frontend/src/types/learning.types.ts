/**
 * Learning System Types
 * Types for feedback and learning pattern approval
 */

export type PatternStatus = 'pending' | 'approved' | 'rejected';

export interface LearningPattern {
  id: string;
  patternType: string;
  originalText: string;
  correctedText: string;
  context: string;
  status: PatternStatus;
  submittedBy: string;
  submittedAt: string;
  approvedBy?: string;
  approvedAt?: string;
  successRate?: number;
  applicationCount: number;
}

export interface FeedbackSubmission {
  sessionId: string;
  fieldType: string;
  originalValue: string;
  correctedValue: string;
  context: string;
}

export interface LearningStats {
  totalPatterns: number;
  pendingCount: number;
  approvedCount: number;
  rejectedCount: number;
  averageSuccessRate: number;
  totalApplications: number;
}

export interface PatternApprovalRequest {
  patternId: string;
  action: 'approve' | 'reject';
  notes?: string;
}
