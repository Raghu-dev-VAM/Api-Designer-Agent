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

// Get config based on environment variable or default to local
const environment = getEnvironment();
const environmentConfig = environmentConfigs[environment];

// Allow override via environment variables
export const config = {
  environment,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || environmentConfig.apiBaseUrl,
  apiTimeout: parseInt(import.meta.env.VITE_API_TIMEOUT || String(environmentConfig.apiTimeout), 10),
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;
