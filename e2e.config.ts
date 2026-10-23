import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';

/**
 * Model-free e2e config: every test is locator/screen driven and fully
 * deterministic (no agent.act / agent.assert, no model provider).
 *
 * The runner starts the Vite dev server itself on a dedicated port
 * (4320, strict) and stops it when the run ends.
 */
export default {
  targets: [
    {
      name: 'web',
      engine: web({ browser: 'chromium' }),
      app: {
        url: 'http://127.0.0.1:4320',
        command: {
          executable: 'node',
          args: ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4320', '--strictPort'],
          reuseExisting: true,
          log: '.e2e/logs/app.log',
        },
      },
    },
  ],
  workers: 1,
} satisfies E2EConfig;
