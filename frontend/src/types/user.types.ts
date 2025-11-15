/**
 * User & Authentication Types
 */

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  permissions: Permission[];
  created_at: string;
}

export type Permission = 'read' | 'write' | 'approve' | 'admin';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}
