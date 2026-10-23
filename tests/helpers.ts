import type { Browser } from '@e2e-dev/web';

// The QR placeholder service the app embeds in timeline CTA / share images.
const QR_SERVICE = /^https:\/\/api\.qrserver\.com\//;
// Anything on the open internet other than the app origin and the stubbed QR
// service (the negative lookahead keeps those two out of this route's hands).
const EXTERNAL = /^https?:\/\/(?!(127\.0\.0\.1:4320)|api\.qrserver\.com)/;

const QR_STUB_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>';

/**
 * Keeps tests off the network: the app's own origin loads normally, the QR
 * placeholder service is answered with a local stub, and every other
 * external request is aborted. Register before `app.open()` — the routes
 * hold for the rest of the attempt.
 */
export async function isolateNetwork(browser: Browser): Promise<void> {
  await browser.route(QR_SERVICE, async (route) => {
    await route.fulfill({ body: QR_STUB_SVG, contentType: 'image/svg+xml' });
  });
  await browser.route(EXTERNAL, async (route) => {
    await route.abort();
  });
}

/** PNG files start with the 8-byte signature 89 50 4E 47 0D 0A 1A 0A. */
export function isPng(bytes: Uint8Array): boolean {
  const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  return signature.every((byte, index) => bytes[index] === byte);
}
