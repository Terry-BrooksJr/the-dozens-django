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

const ANONYMOUS_KEY_STORAGE = 'ld-anonymous-key';

const WINDOW_NAME_PREFIX = `${ANONYMOUS_KEY_STORAGE}:`;

// localStorage throws SecurityError when storage is blocked. window.name isn't
// covered by storage blocking and survives same-site navigation in the tab, so
// it keeps page-to-page continuity for the visit.
function getWindowNameKey() {
    if (window.name.startsWith(WINDOW_NAME_PREFIX)) {
        return window.name.slice(WINDOW_NAME_PREFIX.length);
    }
    const key = crypto.randomUUID();
    // Only claim window.name when nothing else is using it.
    if (!window.name) window.name = WINDOW_NAME_PREFIX + key;
    return key;
}

function getAnonymousKey() {
    try {
        const stored = localStorage.getItem(ANONYMOUS_KEY_STORAGE);
        if (stored) return stored;
        const key = crypto.randomUUID();
        localStorage.setItem(ANONYMOUS_KEY_STORAGE, key);
        return key;
    } catch {
        return getWindowNameKey();
    }
}

const anonymousKey = getAnonymousKey();

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

// createClient returns a stopped client; start() fetches flags and initializes the plugins.
void ldClient.start().catch((error) => {
    console.error('LaunchDarkly client startup failed:', error);
});

window.dozensLD = ldClient;
