/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" serves fixture data from src/mock/ instead of calling /api */
  readonly VITE_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
