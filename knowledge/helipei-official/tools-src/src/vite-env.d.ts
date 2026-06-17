/// <reference types="vite/client" />

interface Window {
  gtag?: (command: string, action: string, params?: Record<string, unknown>) => void;
}
