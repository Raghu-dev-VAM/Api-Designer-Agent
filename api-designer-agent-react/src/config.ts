// Get environment type (defaults to 'development' for dev server, 'production' for build)
const getEnvironment = (): 'local' | 'dev' | 'staging' | 'production' => {
  const env = import.meta.env.VITE_ENV || import.meta.env.MODE;
  return (env as 'local' | 'dev' | 'staging' | 'production') || 'local';
};

// Environment-specific API configurations
const environmentConfigs = {
  local: {
    apiBaseUrl: 'http://localhost:8000',
    apiTimeout: 30000,
  },
  dev: {
    apiBaseUrl: 'https://api-designer-agent-api.onrender.com',
    apiTimeout: 30000,
  },
  staging: {
    apiBaseUrl: 'https://api-staging.example.com',
    apiTimeout: 30000,
  },
  production: {
    apiBaseUrl: 'https://api.example.com',
    apiTimeout: 20000,
  },
} as const;

/** Validate that a URL is safe to use as an API base (http/https only, no credentials). */
function validateApiBaseUrl(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`Unsafe protocol: ${parsed.protocol}`);
    }
    if (parsed.username || parsed.password) {
      throw new Error('API base URL must not contain credentials');
    }
    return url;
  } catch (e) {
    console.error('[config] Invalid VITE_API_BASE_URL:', url, e);
    // Fall back to localhost so the app doesn't silently hit an unexpected host
    return 'http://localhost:8000';
  }
}

// Get config based on environment variable or default to local
const environment = getEnvironment();
const environmentConfig = environmentConfigs[environment];

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || environmentConfig.apiBaseUrl;

// Allow override via environment variables
export const config = {
  environment,
  apiBaseUrl: validateApiBaseUrl(rawApiBaseUrl),
  apiTimeout: parseInt(import.meta.env.VITE_API_TIMEOUT || String(environmentConfig.apiTimeout), 10),
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;
