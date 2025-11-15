<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <!-- Header -->
      <div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
          Neurosurgical DCS
        </h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          Discharge Communication Summary Generator
        </p>
      </div>

      <!-- Login Form -->
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="rounded-md shadow-sm space-y-4">
          <div>
            <label for="username" class="sr-only">Username</label>
            <input
              id="username"
              v-model="credentials.username"
              type="text"
              required
              class="input"
              placeholder="Username"
              autocomplete="username"
            />
          </div>
          <div>
            <label for="password" class="sr-only">Password</label>
            <input
              id="password"
              v-model="credentials.password"
              type="password"
              required
              class="input"
              placeholder="Password"
              autocomplete="current-password"
            />
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="rounded-md bg-error-50 p-4">
          <p class="text-sm text-error-800">
            {{ error }}
          </p>
        </div>

        <!-- Submit Button -->
        <div>
          <button
            type="submit"
            :disabled="isLoading"
            class="w-full btn-primary flex justify-center py-3"
          >
            <span v-if="isLoading" class="flex items-center gap-2">
              <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Signing in...
            </span>
            <span v-else>
              Sign in
            </span>
          </button>
        </div>
      </form>

      <!-- Default Credentials (Development Only) -->
      <div v-if="isDevelopment" class="mt-4 p-4 bg-blue-50 rounded-lg">
        <p class="text-xs text-blue-800 font-medium mb-2">Development Mode - Default Credentials:</p>
        <p class="text-xs text-blue-700">Username: admin</p>
        <p class="text-xs text-blue-700">Password: admin123</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuth } from '@/composables/useAuth';
import { useToast } from '@/composables/useToast';

const router = useRouter();
const route = useRoute();
const { login } = useAuth();
const { success, error: showError } = useToast();

const credentials = ref({
  username: '',
  password: ''
});

const isLoading = ref(false);
const error = ref('');

const isDevelopment = import.meta.env.VITE_APP_ENV === 'development';

async function handleLogin() {
  isLoading.value = true;
  error.value = '';

  const result = await login(credentials.value);

  isLoading.value = false;

  if (result.success) {
    success('Login successful');
    const redirect = (route.query.redirect as string) || '/';
    router.push(redirect);
  } else {
    error.value = result.error || 'Login failed';
    showError(error.value);
  }
}
</script>
