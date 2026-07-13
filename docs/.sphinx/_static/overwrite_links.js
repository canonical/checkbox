// Replaces rtd-address with new-address in links

const rtd_address = 'canonical-checkbox-documentation.readthedocs-hosted.com';
const new_address = 'ubuntu.com/docs/checkbox';

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function overwriteMatchingAnchorUrls(container) {
    if (!container) return;

    const rtd_addressRegex = new RegExp(escapeRegExp(rtd_address), 'g');
    container.querySelectorAll('a[href], link[href]').forEach((anchor) => {
        anchor.href = anchor.href.replace(rtd_addressRegex, new_address);
    });
}

function patchFlyout() {
    const rtdFlyout = document.querySelector('readthedocs-flyout');
    if (!rtdFlyout) return false;

    overwriteMatchingAnchorUrls(rtdFlyout);
    overwriteMatchingAnchorUrls(rtdFlyout.shadowRoot);

    rtdFlyout.addEventListener('click', () => {
        overwriteMatchingAnchorUrls(rtdFlyout);
        overwriteMatchingAnchorUrls(rtdFlyout.shadowRoot);
    });

    return true;
}

function init() {
    overwriteMatchingAnchorUrls(document.querySelector('header'));

    if (patchFlyout()) return;

    const observer = new MutationObserver(() => {
        if (patchFlyout()) {
            observer.disconnect();
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

if (document.body) {
    init();
} else {
    document.addEventListener('DOMContentLoaded', init);
}
