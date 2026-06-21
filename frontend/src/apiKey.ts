import axios from "axios";

const STORAGE_KEY = "visionnaire_api_key";

export function getApiKey(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function setApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key);
}

type UnauthorizedListener = () => void;
let unauthorizedListener: UnauthorizedListener | null = null;

export function onUnauthorized(listener: UnauthorizedListener): void {
  unauthorizedListener = listener;
}

export function installApiKeyInterceptors(): void {
  axios.interceptors.request.use((config) => {
    const key = getApiKey();
    if (key) config.headers["X-API-Key"] = key;
    return config;
  });

  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        unauthorizedListener?.();
      }
      return Promise.reject(error);
    },
  );
}
