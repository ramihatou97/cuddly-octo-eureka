/**
 * useAuth Composable
 * Authentication logic for components
 */

import { computed } from 'vue';
import { useAuthStore } from '@/stores/auth.store';
import type { LoginCredentials, Permission } from '@/types';

export function useAuth() {
  const authStore = useAuthStore();

  const isAuthenticated = computed(() => authStore.isAuthenticated);
  const user = computed(() => authStore.user);
  const permissions = computed(() => authStore.userPermissions);

  async function login(credentials: LoginCredentials) {
    return await authStore.login(credentials);
  }

  async function logout() {
    await authStore.logout();
  }

  function hasPermission(permission: Permission): boolean {
    return authStore.hasPermission(permission);
  }

  async function initialize() {
    await authStore.initializeAuth();
  }

  return {
    // State
    isAuthenticated,
    user,
    permissions,

    // Methods
    login,
    logout,
    hasPermission,
    initialize
  };
}
