import type { Browser } from '@e2e-dev/web';

// Anything on the open internet other than the app's own origin is aborted.
// Timeline QR codes are generated locally as data: URLs, so the app must not
// reach any external host — a regression back to remote assets (e.g. the
// former api.qrserver.com images) fails loudly instead of leaking user data.
const EXTERNAL = /^https?:\/\/(?!127\.0\.0\.1:4320)/;

/**
 * Keeps tests off the network: the app's own origin loads normally and every
 * external request is aborted. Register before `app.open()` — the route
 * holds for the rest of the attempt.
 */
export async function isolateNetwork(browser: Browser): Promise<void> {
  await browser.route(EXTERNAL, async (route) => {
    await route.abort();
  });
}

/** PNG files start with the 8-byte signature 89 50 4E 47 0D 0A 1A 0A. */
export function isPng(bytes: Uint8Array): boolean {
  const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  return signature.every((byte, index) => bytes[index] === byte);
}
