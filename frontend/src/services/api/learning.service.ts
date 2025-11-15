/**
 * Learning Service
 * Handles learning feedback and pattern management API calls
 */

import { apiClient } from './client';
import type { LearningFeedbackRequest, LearningFeedbackResponse } from '@/types/processing.types';

class LearningService {
  /**
   * Submit feedback for an uncertainty to teach the system new patterns
   * POST /api/learning/feedback
   */
  async submitFeedback(
    feedbackData: LearningFeedbackRequest
  ): Promise<LearningFeedbackResponse> {
    try {
      const response = await apiClient.post<LearningFeedbackResponse>(
        '/api/learning/feedback',
        feedbackData
      );
      return response;
    } catch (error: any) {
      console.error('Learning feedback submission error:', error);
      throw new Error(
        error.response?.data?.detail ||
        'Failed to submit learning feedback'
      );
    }
  }

  /**
   * Get pending patterns awaiting approval (for admin view)
   * GET /api/learning/pending
   */
  async getPendingPatterns(): Promise<any[]> {
    try {
      const response = await apiClient.get<any[]>('/api/learning/pending');
      return response;
    } catch (error: any) {
      console.error('Get pending patterns error:', error);
      throw new Error(
        error.response?.data?.detail ||
        'Failed to fetch pending patterns'
      );
    }
  }

  /**
   * Approve or reject a learning pattern (admin only)
   * POST /api/learning/approve
   */
  async approvePattern(patternId: string, approved: boolean, reason?: string): Promise<any> {
    try {
      const response = await apiClient.post<any>('/api/learning/approve', {
        pattern_id: patternId,
        approved,
        reason
      });
      return response;
    } catch (error: any) {
      console.error('Pattern approval error:', error);
      throw new Error(
        error.response?.data?.detail ||
        'Failed to approve pattern'
      );
    }
  }

  /**
   * Get learning statistics (for admin dashboard)
   * GET /api/learning/statistics
   */
  async getStatistics(): Promise<any> {
    try {
      const response = await apiClient.get<any>('/api/learning/statistics');
      return response;
    } catch (error: any) {
      console.error('Get learning statistics error:', error);
      throw new Error(
        error.response?.data?.detail ||
        'Failed to fetch learning statistics'
      );
    }
  }
}

// Export singleton instance
export const learningService = new LearningService();
export default learningService;
