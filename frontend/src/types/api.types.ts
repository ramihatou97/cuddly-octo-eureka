/**
 * API Types
 * Type definitions matching backend API contracts
 */

export interface APIResponse<T = any> {
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  perPage: number;
}

export interface ErrorResponse {
  detail: string;
  status: number;
}
