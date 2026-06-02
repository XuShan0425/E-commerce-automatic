import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';

const STORAGE_KEYS = {
  JWT_TOKEN: 'jwt_token',
  API_KEY: 'api_key',
  API_BASE_URL: 'api_base_url',
} as const;

let apiClient: AxiosInstance | null = null;

function createClient(baseURL: string): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: 15000,
    headers: { 'Content-Type': 'application/json' },
  });

  // Request interceptor: attach auth headers
  client.interceptors.request.use(async (config) => {
    const token = await SecureStore.getItemAsync(STORAGE_KEYS.JWT_TOKEN);
    const apiKey = await SecureStore.getItemAsync(STORAGE_KEYS.API_KEY);

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey;
    }
    return config;
  });

  return client;
}

export async function initClient(baseURL?: string): Promise<AxiosInstance> {
  const url = baseURL || (await SecureStore.getItemAsync(STORAGE_KEYS.API_BASE_URL)) || 'http://localhost:8000';
  if (!baseURL) {
    await SecureStore.setItemAsync(STORAGE_KEYS.API_BASE_URL, url);
  }
  apiClient = createClient(url);
  return apiClient;
}

export function getClient(): AxiosInstance {
  if (!apiClient) {
    throw new Error('API client not initialized. Call initClient() first.');
  }
  return apiClient;
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(STORAGE_KEYS.JWT_TOKEN, token);
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(STORAGE_KEYS.JWT_TOKEN);
}

export async function setApiKey(key: string): Promise<void> {
  await SecureStore.setItemAsync(STORAGE_KEYS.API_KEY, key);
}

export async function getApiKey(): Promise<string | null> {
  return SecureStore.getItemAsync(STORAGE_KEYS.API_KEY);
}

export async function clearAuth(): Promise<void> {
  await SecureStore.deleteItemAsync(STORAGE_KEYS.JWT_TOKEN);
  await SecureStore.deleteItemAsync(STORAGE_KEYS.API_KEY);
}

export { STORAGE_KEYS };
