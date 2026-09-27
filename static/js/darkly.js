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
        return window.name.slice(WINDOW_NAME_PREFIX.length).split(':', 1)[0];
    }
    const key = crypto.randomUUID();
    // Prepend rather than overwrite so any existing window.name value is preserved.
    window.name = `${WINDOW_NAME_PREFIX}${key}:${window.name}`;
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

// Pages render the logged-in user's context via {{ ld_user|json_script:"ld-user" }};
// it's null for anonymous visitors. Module scripts are deferred, so the element exists.
function getServerContext() {
    const el = document.getElementById('ld-user');
    if (!el) return null;
    try {
        return JSON.parse(el.textContent);
    } catch {
        return null;
    }
}

const context = getServerContext() ?? {
    kind: 'user',
    key: getAnonymousKey(),
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
const started = ldClient.start().catch((error) => {
    console.error('LaunchDarkly client startup failed:', error);
});

window.dozensLD = ldClient;

// The Swagger UI and GraphiQL templates push Authorization values onto
// window.dozensLDTokenQueue (possibly before this module loads). The raw token
// is a secret, so only a SHA-256 digest of it is ever sent to LaunchDarkly.
async function hashToken(value) {
    const token = String(value).replace(/^\s*(token|bearer)\s+/i, '').trim();
    if (!token) return null;
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

let lastTokenKey = null;
// Chain identify calls so they apply in queue order and never overlap.
let identifyChain = started;

function identifyToken(value) {
    identifyChain = identifyChain
        .then(() => hashToken(value))
        .then((tokenKey) => {
            if (!tokenKey || tokenKey === lastTokenKey) return undefined;
            lastTokenKey = tokenKey;
            return ldClient.identify({
                kind: 'multi',
                user: context,
                'api-token': { key: tokenKey },
            });
        })
        .catch((error) => {
            console.error('LaunchDarkly API-token identify failed:', error);
        });
}

const pendingTokens = Array.isArray(window.dozensLDTokenQueue) ? window.dozensLDTokenQueue : [];
// Replace the array with a push-compatible consumer so later tokens are handled immediately.
window.dozensLDTokenQueue = { push: (...values) => values.forEach(identifyToken) };
pendingTokens.forEach(identifyToken);
