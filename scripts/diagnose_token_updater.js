/*
 * Run in the Token Updater extension's service-worker DevTools console.
 * Read only: no network, cookie writes, storage reads, or secret output.
 * Only standard authentication-cookie names and counts are printed.
 */
void (async () => {
    const flowUrl = 'https://flow.google.com/projects';
    const authNames = new Set([
        'OSID', '__Secure-OSID', 'SID', 'HSID', 'SSID', 'APISID',
        'SAPISID', '__Secure-1PSID', '__Secure-3PSID'
    ]);
    const summarize = cookies => ({
        count: cookies.length,
        auth_names: cookies.filter(cookie => authNames.has(cookie.name))
            .map(cookie => cookie.name).sort(),
        partitioned_count: cookies.filter(cookie => Boolean(cookie.partitionKey)).length
    });
    const safeRead = async details => {
        try {
            return summarize(await chrome.cookies.getAll(details));
        } catch {
            return { unavailable: true };
        }
    };
    const rawVersion = chrome.runtime.getManifest().version;
    const report = {
        extension_version: /^\d+(\.\d+){0,3}$/.test(rawVersion) ? rawVersion : 'unknown',
        default_context: await safeRead({ url: flowUrl }),
        flow_tabs: []
    };
    const tabs = await chrome.tabs.query({ url: 'https://flow.google.com/*' });
    const stores = await chrome.cookies.getAllCookieStores();
    for (const tab of tabs) {
        const store = stores.find(item => item.tabIds.includes(tab.id));
        const entry = {
            incognito: Boolean(tab.incognito),
            store_identified: Boolean(store)
        };
        if (store) {
            entry.unpartitioned = await safeRead({ url: flowUrl, storeId: store.id });
            if (typeof chrome.cookies.getPartitionKey === 'function') {
                try {
                    const details = await chrome.cookies.getPartitionKey({ tabId: tab.id, frameId: 0 });
                    const key = details?.partitionKey;
                    entry.partition_key_available = Boolean(key?.topLevelSite);
                    if (key?.topLevelSite) {
                        entry.current_partition = await safeRead({
                            url: flowUrl, storeId: store.id, partitionKey: key
                        });
                    }
                } catch {
                    entry.partition_key_available = false;
                }
            } else {
                entry.partition_key_api_available = false;
            }
        }
        report.flow_tabs.push(entry);
    }
    console.log('TOKEN_UPDATER_DIAGNOSTIC ' + JSON.stringify(report));
})().catch(() => {
    console.log('TOKEN_UPDATER_DIAGNOSTIC {"unavailable":true}');
});
