/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API base in a built deploy (defaults to "/api" via proxy). */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
