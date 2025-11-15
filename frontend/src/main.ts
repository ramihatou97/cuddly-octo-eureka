import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { VueQueryPlugin } from '@tanstack/vue-query';
import App from './App.vue';
import router from './router';
import './style.css';

const app = createApp(App);

// State management
const pinia = createPinia();
app.use(pinia);

// Router
app.use(router);

// Vue Query (React Query for Vue)
app.use(VueQueryPlugin, {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000, // 5 minutes
        cacheTime: 10 * 60 * 1000, // 10 minutes
        refetchOnWindowFocus: false,
        retry: 1
      }
    }
  }
});

app.mount('#app');
