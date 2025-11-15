/**
 * UI Types
 * Types for UI state and components
 */

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

export interface LoadingState {
  isLoading: boolean;
  message?: string;
  progress?: number;
}

export interface ModalState {
  isOpen: boolean;
  title?: string;
  content?: string;
}

export type WorkflowStep = 1 | 2 | 3;

export interface ConfidenceLevel {
  value: number;
  label: 'high' | 'medium' | 'low';
  color: string;
}
