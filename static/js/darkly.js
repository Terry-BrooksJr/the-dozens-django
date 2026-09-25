/**
 * LaunchDarkly bootstrap: feature flags, observability, and session replay.
 *
 * The client-side SDK ships ESM-only (no UMD/CDN bundle), so it's imported
 * directly from jsdelivr as a module rather than added to js/scripts.js.
 */
import { createClient } from 'https://cdn.jsdelivr.net/npm/@launchdarkly/js-client-sdk@4.10.0/dist/index.js';
import Observability from 'https://cdn.jsdelivr.net/npm/@launchdarkly/observability@1.1.20/dist/index.js';
import SessionReplay from 'https://cdn.jsdelivr.net/npm/@launchdarkly/session-replay@1.1.20/dist/index.js';

const LD_CLIENT_SIDE_ID = '69998d933f61550a0651d1f9';

const anonymousKey = localStorage.getItem('ld-anonymous-key') || crypto.randomUUID();
localStorage.setItem('ld-anonymous-key', anonymousKey);

const context = {
    kind: 'user',
    key: anonymousKey,
    anonymous: true,
};

const ldClient = createClient(LD_CLIENT_SIDE_ID, context, {
    plugins: [
        new Observability(),
        new SessionReplay(),
    ],
});

ldClient.on('error', (error) => {
    console.error('LaunchDarkly client error:', error);
});

window.dozensLD = ldClient;
