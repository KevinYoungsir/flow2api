/*
 * Run in the DevTools Console of an already open flow.google.com project.
 * GET only the page's already loaded, public Google frontend JavaScript.
 * No Cookie/storage reads, authenticated requests, RPCs, uploads or generation.
 * Output contains only approved public script URLs, model constants and
 * redacted public-code context. Private resource URLs are never output.
 */
void (async () => {
    const prefix = 'FLOW_PUBLIC_MODEL_DIAGNOSTIC ';
    const approved = raw => {
        try {
            const url = new URL(raw);
            return url.protocol === 'https:' && url.hostname === 'www.gstatic.com'
                && !url.username && !url.password && !url.search && !url.hash
                && url.pathname.startsWith('/_/mss/boq-labs-ai-sandbox/_/js/')
                && /\/k=[A-Za-z0-9_.-]+\//.test(url.pathname)
                && /\/m=[A-Za-z0-9_,.-]+$/.test(url.pathname);
        } catch { return false; }
    };
    const candidates = [
        ...performance.getEntriesByType('resource').map(item => item.name).reverse(),
        ...Array.from(document.scripts, item => item.src)
    ];
    const urls = [...new Set(candidates.filter(approved))];
    const keys = new Set();
    const resolutions = new Set();
    const rpcIds = new Set();
    const contexts = new Map();
    const report = {
        version: 1, public_assets_found: urls.length, inspected: 0, failed: 0,
        skipped: Math.max(0, urls.length - 12), stream_chat_in_public_source: false
    };
    const safeContext = text => text
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(["'`])(?:\\.|(?!\1)[^\\])*?\1/g, literal => {
            const value = literal.slice(1, -1);
            return /^(?:veo_[a-z0-9_]+|VIDEO_RESOLUTION_[A-Z0-9_]+|(?:Veo )?3\.1(?: -)? Fast|Fast|Lower Priority|720p|1080p|landscape|portrait)$/.test(value)
                ? literal : '"[omitted]"';
        })
        .replace(/[A-Za-z0-9_@./:+-]{24,}/g, word =>
            /^(?:veo_[a-z0-9_]+|VIDEO_RESOLUTION_[A-Z0-9_]+)$/.test(word) ? word : '[omitted]')
        .replace(/\s+/g, ' ').slice(0, 700);
    const inspect = text => {
        for (const match of text.matchAll(/\bveo_[a-z0-9_]{1,110}\b/g)) {
            if (keys.size < 120) keys.add(match[0]);
            if (/^veo_3_1_t2v_fast(?:_|$)/.test(match[0]) && !contexts.has(match[0]) && contexts.size < 8) {
                contexts.set(match[0], safeContext(text.slice(Math.max(0, match.index - 180), match.index + match[0].length + 300)));
            }
        }
        for (const match of text.matchAll(/\bVIDEO_RESOLUTION_[A-Z0-9_]{1,50}\b/g)) resolutions.add(match[0]);
        for (const match of text.matchAll(/Wa:["']([A-Za-z0-9]{1,16})["'],hb:["']\/(?:VideoFxService|FlowService)\.([A-Za-z0-9]*Video[A-Za-z0-9]*)["']/g)) {
            if (rpcIds.size < 30) rpcIds.add(match[1] + ':' + match[2]);
        }
        report.stream_chat_in_public_source ||= text.includes('FlowCreationAgentService/StreamChat');
    };
    const selected = urls.slice(0, 12);
    report.public_script_urls = selected;
    for (let offset = 0; offset < selected.length; offset += 3) {
        await Promise.all(selected.slice(offset, offset + 3).map(async url => {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 12000);
            try {
                const response = await fetch(url, {
                    method: 'GET', credentials: 'omit', redirect: 'error',
                    cache: 'force-cache', signal: controller.signal
                });
                if (!response.ok || Number(response.headers.get('content-length') || 0) > 8 * 1024 * 1024) throw new Error('unavailable');
                const text = await response.text();
                if (text.length > 8 * 1024 * 1024) throw new Error('too_large');
                inspect(text);
                report.inspected += 1;
            } catch { report.failed += 1; }
            finally { clearTimeout(timer); }
        }));
    }
    report.model_keys = [...keys].sort();
    report.resolution_constants = [...resolutions].sort().slice(0, 30);
    report.public_video_rpcs = [...rpcIds].sort();
    report.fast_public_contexts = [...contexts].map(([model_key, public_context]) => ({model_key, public_context}));
    console.log(prefix + JSON.stringify(report));
})().catch(() => {
    console.log('FLOW_PUBLIC_MODEL_DIAGNOSTIC {"unavailable":true}');
});
