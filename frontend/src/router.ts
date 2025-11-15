/**
 * Vue Router Configuration
 * Two main routes: Clinical Workflow + Admin Dashboard
 */

import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth.store';
import type { Permission } from '@/types';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Clinical',
    component: () => import('@/views/ClinicalView.vue'),
    meta: {
      requiresAuth: true,
      permission: 'write' as Permission
    }
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/AdminView.vue'),
    meta: {
      requiresAuth: true,
      permission: 'approve' as Permission
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();

  // Initialize auth on first load
  if (!authStore.user && authStore.getStoredToken()) {
    await authStore.initializeAuth();
  }

  const requiresAuth = to.meta.requiresAuth !== false;
  const requiredPermission = to.meta.permission as Permission | undefined;

  if (requiresAuth && !authStore.isAuthenticated) {
    // Redirect to login
    next({
      name: 'Login',
      query: { redirect: to.fullPath }
    });
  } else if (requiredPermission && !authStore.hasPermission(requiredPermission)) {
    // User doesn't have required permission
    console.warn(`Access denied: requires ${requiredPermission} permission`);
    next({ name: 'Clinical' }); // Redirect to clinical view
  } else {
    next();
  }
});

export default router;
