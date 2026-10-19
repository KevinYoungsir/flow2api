const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('scripts/diagnose_token_updater.js', 'utf8');

async function run({ partitionApi = true, getAllFails = false } = {}) {
    const calls = [];
    let resolveLog;
    const logged = new Promise(resolve => { resolveLog = resolve; });
    const cookies = {
        async getAll(details) {
            calls.push(details);
            if (getAllFails) throw new Error('private-cookie-and-email@example.com');
            return [{ name: details.partitionKey ? 'SID' : 'OSID',
                value: 'private-cookie-value', domain: 'flow.google.com',
                partitionKey: details.partitionKey,
                extra_identity: 'private-email@example.com' },
                {name: 'private-unknown-cookie-name', value: 'private-other-value'}];
        },
        async getAllCookieStores() { return [{id: 'private-store-id', tabIds: [11]}]; }
    };
    if (partitionApi) cookies.getPartitionKey = async () => ({partitionKey: {
        topLevelSite: 'https://google.com', hasCrossSiteAncestor: false
    }});
    const result = vm.runInNewContext(source, {
        chrome: {
            cookies,
            runtime: {getManifest: () => ({version: '1.3.1'})},
            tabs: {query: async () => [{id: 11, url: 'https://flow.google.com/projects?private=query', incognito: false}]}
        },
        console: {log: resolveLog}
    });
    assert.equal(result, undefined, 'DevTools evaluation never returns cookie objects');
    const output = await logged;
    assert(!output.includes('private-'), 'No cookie values, unknown names, identifiers, URLs, or error details');
    return {report: JSON.parse(output.slice('TOKEN_UPDATER_DIAGNOSTIC '.length)), calls};
}

(async () => {
    const normal = await run();
    assert.equal(normal.report.default_context.auth_names[0], 'OSID');
    assert.equal(normal.report.flow_tabs[0].current_partition.auth_names[0], 'SID');
    assert.equal(normal.calls[1].storeId, 'private-store-id');
    assert.equal(normal.calls[2].partitionKey.topLevelSite, 'https://google.com');
    assert.equal(normal.calls.length, 3);
    const older = await run({partitionApi: false});
    assert.equal(older.report.flow_tabs[0].partition_key_api_available, false);
    const failure = await run({getAllFails: true});
    assert.equal(failure.report.default_context.unavailable, true);
    console.log('PASS: local-only output, matching tab store/partition, older Chrome, suppressed errors');
})().catch(error => { console.error(error); process.exitCode = 1; });
