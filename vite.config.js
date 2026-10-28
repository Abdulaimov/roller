import { defineConfig } from 'vite';

// relative paths so the built app (dist/) can be copied to any computer or kiosk;
// fixed file names so the online version can be republished to the same link
export default defineConfig({
  base: './',
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: { entryFileNames: 'assets/app.js', assetFileNames: 'assets/[name][extname]' },
    },
  },
});
