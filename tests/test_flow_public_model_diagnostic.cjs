const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('scripts/diagnose_flow_public_models.js', 'utf8');
const publicUrl = 'https://www.gstatic.com/_/mss/boq-labs-ai-sandbox/_/js/k=frontend.en.version/d=1/m=Project';

async function run({urls = [publicUrl], body = '', fails = false} = {}) {
    const calls = [];
    let resolveLog;
    const logged = new Promise(resolve => { resolveLog = resolve; });
    const document = {scripts: urls.map(src => ({src}))};
    Object.defineProperty(document, 'cookie', {get() { throw new Error('private-cookie-access'); }});
    const context = {
        URL, AbortController, setTimeout, clearTimeout,
        performance: {getEntriesByType: () => urls.map(name => ({name}))}, document,
        console: {log: resolveLog},
        fetch: async (url, options) => {
            calls.push({url, options});
            if (fails) throw new Error('private-error-account@example.com');
            return {ok: true, headers: {get: () => null}, text: async () => body};
        }
    };
    for (const name of ['localStorage', 'sessionStorage', 'chrome']) {
        Object.defineProperty(context, name, {get() { throw new Error('private-storage-access'); }});
    }
    assert.equal(vm.runInNewContext(source, context), undefined);
    const output = await logged;
    assert(!output.includes('private-'));
    return {report: JSON.parse(output.slice('FLOW_PUBLIC_MODEL_DIAGNOSTIC '.length)), calls};
}

(async () => {
    const normal = await run({body: 'const option={label:"Fast",model:"veo_3_1_t2v_fast_4s",unused:"private-cookie-value"};const res={2:"VIDEO_RESOLUTION_720P"};var rpc={Wa:"YhhmEf",hb:"/VideoFxService.GenerateVideo"};'});
    assert.equal(normal.report.model_keys[0], 'veo_3_1_t2v_fast_4s');
    assert.equal(normal.report.resolution_constants[0], 'VIDEO_RESOLUTION_720P');
    assert.equal(normal.report.public_video_rpcs[0], 'YhhmEf:GenerateVideo');
    assert.equal(normal.report.inspected, 1);
    assert.equal(normal.report.public_script_urls[0], publicUrl);
    assert.equal(normal.calls[0].options.credentials, 'omit');
    assert.equal(normal.calls[0].options.method, 'GET');
    assert.equal(normal.calls[0].options.redirect, 'error');
    assert.equal(normal.calls[0].options.headers, undefined);
    const excluded = await run({urls: [
        'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?private-session=1',
        'https://flow-content.google/video/private-result',
        publicUrl + '?private-query=1', publicUrl + '#private-fragment',
        publicUrl.replace('www.gstatic.com', 'www.gstatic.com.evil.test'),
        publicUrl.replace('https:', 'http:'), publicUrl.replace('www.gstatic.com', 'private-user@www.gstatic.com'),
        'https://www.gstatic.com/recaptcha/private-script.js'
    ]});
    assert.equal(excluded.calls.length, 0);
    assert.equal(excluded.report.public_assets_found, 0);
    assert.equal(excluded.report.public_script_urls.length, 0);
    const capped = await run({urls: Array.from({length: 15}, (_, i) => publicUrl + i)});
    assert.equal(capped.calls.length, 12);
    assert.equal(capped.report.skipped, 3);
    const failure = await run({fails: true});
    assert.equal(failure.report.failed, 1);
    assert.equal(failure.report.inspected, 0);
    console.log('PASS: public assets only, no credentials/storage/RPCs, safe output, bounded requests, suppressed failures');
})().catch(error => { console.error(error); process.exitCode = 1; });
