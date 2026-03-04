/// <reference types="vite/client" />

declare global {
  interface Window {
    aiLabDesktop?: {
      startStack: () => Promise<{ ok: boolean; stdout: string; stderr: string }>;
      stopStack: () => Promise<{ ok: boolean; stdout: string; stderr: string }>;
      stackStatus: () => Promise<{ ok: boolean; stdout: string; stderr: string }>;
    };
  }
}

export {};
