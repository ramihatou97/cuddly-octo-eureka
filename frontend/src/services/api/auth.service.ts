/**
 * Authentication Service
 * Handles login, logout, and user authentication
 */

import { apiClient } from './client';
import type { LoginCredentials, LoginResponse, User } from '@/types';

export class AuthService {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    // Backend expects form data
    const formData = new URLSearchParams();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await apiClient.post<LoginResponse>('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    });

    return response;
  }

  async getCurrentUser(): Promise<User> {
    return apiClient.get<User>('/api/auth/me');
  }

  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  }

  getStoredToken(): string | null {
    return localStorage.getItem('access_token');
  }

  getStoredUser(): User | null {
    const userStr = localStorage.getItem('user');
    if (!userStr) return null;

    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }

  storeAuth(token: string, user: User): void {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }
}

export const authService = new AuthService();
