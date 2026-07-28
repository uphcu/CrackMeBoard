// CrackMeBoard — Common JS utilities

// CSRF token injection for all AJAX requests
document.addEventListener('DOMContentLoaded', function () {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
        const csrfToken = csrfMeta.content;
        // Override fetch to auto-include CSRF token
        const originalFetch = window.fetch;
        window.fetch = function (url, options = {}) {
            options.headers = options.headers || {};
            if (options.method && options.method.toUpperCase() !== 'GET') {
                options.headers['X-CSRFToken'] = csrfToken;
            }
            return originalFetch(url, options);
        };
    }
});