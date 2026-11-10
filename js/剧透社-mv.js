/**
 * 剧透社[盘] - 网盘影视资源（夸克 / 百度）
 * ------------------------------------------------------------
 * 站点：https://1.star2.cn/
 * 说明：按「极速追剧 / 金牌影视」新式 export default 模块结构重写
 *      （init / home / homeVod / category / detail / search / play）
 *      纯正则解析，无第三方依赖；Quark / Baidu2 / ENV 由 drpy 沙箱注入
 * 作者：EylinSir（原规则），重写整理
 * 依赖：宿主需已配置 quark_cookie / baidu_cookie（网盘 Cookie）
 */

const baseUrl = 'https://1.star2.cn';
const UA = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36';
const HEADERS = {
    'User-Agent': UA,
    'Referer': baseUrl + '/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Connection': 'keep-alive'
};

// 分类（与站点导航一致，顺序沿用原规则）
const CLASSES = [
    { type_id: 'ju', type_name: '国剧' },
    { type_id: 'mv', type_name: '电影' },
    { type_id: 'dm', type_name: '动漫' },
    { type_id: 'dj', type_name: '短剧' },
    { type_id: 'zy', type_name: '综艺' },
    { type_id: 'rh', type_name: '韩日' },
    { type_id: 'ym', type_name: '英美' },
    { type_id: 'wj', type_name: '外剧' }
];

const PIC_QUARK = baseUrl + '/skin/images/kk.png';   // 列表占位图（夸克图标）
const PIC_BAIDU = baseUrl + '/skin/images/bd.png';

/* ----------------------------- 基础工具 ----------------------------- */

function output(v) { return JSON.stringify(v); }
function str(v) { return v == null ? '' : String(v); }
function stripTags(s) { return str(s).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim(); }

function backErr(err) {
    console.log('剧透社[盘] error:', err);
    return output({ msg: (err && err.message) || err || '请求失败' });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function parseRespText(resp) {
    if (resp == null) return '';
    if (typeof resp === 'string') return resp;
    if (typeof resp === 'object') {
        if (typeof resp.content === 'string') return resp.content;
        if (typeof resp.data === 'string') return resp.data;
        if (typeof resp.body === 'string') return resp.body;
    }
    return str(resp);
}

async function httpGet(url, headers) {
    try {
        const resp = await req(url, { headers: Object.assign({}, HEADERS, headers || {}) });
        return parseRespText(resp);
    } catch (e) {
        console.log('剧透社[盘] httpGet 失败:', url, e && e.message);
        return '';
    }
}

// 沙箱注入对象的安全读取（避免宿主缺少某网盘对象时整体崩溃）
function getPan(name) {
    try {
        if (name === 'Quark') return typeof Quark !== 'undefined' ? Quark : null;
        if (name === 'Baidu2') return typeof Baidu2 !== 'undefined' ? Baidu2 : null;
    } catch (e) { return null; }
    return null;
}
function envGet(key, def) {
    try {
        if (typeof ENV !== 'undefined' && ENV && typeof ENV.get === 'function') {
            const v = ENV.get(key);
            return v == null || v === '' ? def : v;
        }
    } catch (e) { }
    return def;
}

// 播放列表里的名称不能出现 $ # 分隔符
function safeName(s) {
    return str(s).replace(/\$/g, '＄').replace(/#/g, '＃').trim();
}

// 标题拆分：【标签】剧名.备注
// 例：【国剧】蒸蒸日上.全集          -> 蒸蒸日上 / 全集
//    【国剧】嫁金钗.更10【田曦薇】   -> 嫁金钗   / 更10【田曦薇】
//    【国剧】庆余年.第1季.特别版.全集 -> 庆余年   / 第1季.特别版.全集
function splitTitle(raw) {
    let s = stripTags(raw).replace(/^(?:【[^】]*】\s*)+/, '').trim();
    let name = s, remarks = '';
    const i = s.indexOf('.');
    if (i >= 0) {
        name = s.slice(0, i).trim();
        remarks = s.slice(i + 1).trim();
    }
    if (!name) name = s || stripTags(raw);
    return { name: name, remarks: remarks };
}

// 导航 / 推广项排除
function isGuideText(t) {
    return t.indexOf('看短剧') >= 0 || t.indexOf('网剧点我') >= 0 ||
        t.indexOf('连载短剧') >= 0 || t.indexOf('网剧更新') >= 0;
}

// 详情页相对路径，如 /ju/11748.html
const DETAIL_PATH_RE = /^\/[a-z]{2}\/\d+\.html$/;

/* ----------------------------- 列表解析 ----------------------------- */

// 抓取所有 class="main" 的条目链接（属性顺序无关）
function parseList(html) {
    const list = [];
    const seen = {};
    const reA = /<a\b(?=[^>]*\bclass="main[^"]*")(?=[^>]*\bhref="([^"]+)")[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = reA.exec(str(html))) !== null) {
        let href = m[1];
        let text = stripTags(m[2]);
        if (!DETAIL_PATH_RE.test(href)) continue;
        if (isGuideText(text)) continue;
        if (seen[href]) continue;
        seen[href] = 1;
        const t = splitTitle(text);
        if (!t.name) continue;
        list.push({
            vod_id: href,
            vod_name: t.name,
            vod_pic: PIC_QUARK,
            vod_remarks: t.remarks
        });
    }
    return list;
}

// 从分页条解析 当前页/总页数，如 1/142
function parsePageInfo(html, pg) {
    let page = parseInt(pg, 10) || 1;
    let pagecount = 1;
    const blockM = /<div class="pagination">([\s\S]*?)<\/div>/.exec(str(html));
    const scope = blockM ? blockM[1] : str(html);
    const pm = />(\d+)\s*\/\s*(\d+)</.exec(scope);
    if (pm) {
        page = parseInt(pm[1], 10) || page;
        pagecount = parseInt(pm[2], 10) || 1;
    }
    return { page: page, pagecount: pagecount };
}

// 首页排行榜解析（第一个榜单为全站更新）
function parseHomeRank(html) {
    const list = [];
    const seen = {};
    let box = /<ul class="ranking-box active">([\s\S]*?)<\/ul>/.exec(str(html));
    if (!box) box = /<ul class="ranking-box[^"]*">([\s\S]*?)<\/ul>/.exec(str(html));
    if (!box) return list;
    const reA = /<a\b([^>]*)>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = reA.exec(box[1])) !== null) {
        const attrs = m[1];
        const hrefM = /\bhref="([^"]+)"/.exec(attrs);
        const titleM = /\btitle="([^"]+)"/.exec(attrs);
        if (!hrefM) continue;
        const href = hrefM[1];
        if (!DETAIL_PATH_RE.test(href) || seen[href]) continue;
        const text = titleM ? titleM[1] : stripTags(m[2]);
        if (isGuideText(text)) continue;
        seen[href] = 1;
        const t = splitTitle(text);
        if (!t.name) continue;
        list.push({ vod_id: href, vod_name: t.name, vod_pic: PIC_QUARK, vod_remarks: t.remarks });
        if (list.length >= 30) break;
    }
    return list;
}

/* ----------------------------- 网盘资源 ----------------------------- */

// 解析单个夸克分享链接 -> { flag, line }
async function buildQuarkLine(link) {
    const Quark = getPan('Quark');
    if (!Quark) return null;
    await sleep(200);
    let shareData;
    try { shareData = await Quark.getShareData(link); } catch (e) { shareData = null; }
    if (!shareData) return null;
    let videos;
    try { videos = await Quark.getFilesByShareUrl(shareData); } catch (e) { videos = null; }
    if (!Array.isArray(videos) || videos.length === 0) return null;
    const line = videos.map(v => {
        const arr = [
            shareData.shareId,
            v.stoken,
            v.fid,
            v.share_fid_token,
            v.subtitle ? v.subtitle.fid : '',
            v.subtitle ? v.subtitle.share_fid_token : ''
        ];
        return safeName(v.file_name) + '$' + arr.join('*');
    }).join('#');
    return { flag: 'Quark-' + shareData.shareId, line: line };
}

// 解析单个百度分享链接 -> { flag, line }
async function buildBaiduLine(link, index) {
    const Baidu = getPan('Baidu2');
    if (!Baidu) return null;
    await sleep(200);
    let data;
    try { data = await Baidu.getShareData(link); } catch (e) { data = null; }
    if (!data) return null;
    const segs = [];
    Object.keys(data).forEach(k => {
        const videos = data[k];
        if (Array.isArray(videos) && videos.length > 0) {
            videos.forEach(item => {
                segs.push(safeName(item.name) + '$' + [item.path, item.uk, item.shareid, item.fsid].join('*'));
            });
        }
    });
    if (segs.length === 0) return null;
    return { flag: 'Baidu-' + index, line: segs.join('#') };
}

/* ----------------------------- 模块接口 ----------------------------- */

async function init(cfg) { return {}; }
function destroy() { return {}; }
function live(u) { return JSON.stringify([]); }
function sniffer() { return false; }
function isVideo(url) {
    const u = String(url || '').split(/[?#]/)[0].toLowerCase();
    return ['.m3u8', '.mp4', '.mkv', '.flv'].some(s => u.endsWith(s));
}
async function action(v) { return output({ msg: 'ok' }); }
async function proxy(p) { return [404, 'text/plain', 'no proxy']; }

// 分类
async function home(filter) {
    return output({
        class: CLASSES.map(c => ({
            type_id: c.type_id, type_name: c.type_name,
            id: c.type_id, name: c.type_name
        })),
        filters: {}
    });
}

// 首页推荐：站点首页排行榜
async function homeVod() {
    try {
        const html = await httpGet(baseUrl + '/');
        let list = parseHomeRank(html);
        if (list.length === 0) {
            // 兜底：取国剧第一页
            const c = await category('ju', 1);
            const o = JSON.parse(c);
            list = o.list || [];
        }
        return output({ list: list });
    } catch (e) {
        return output({ list: [] });
    }
}

// 分类列表：/ju/、/ju_2/ ...
async function category(tid, pg, filter, extend) {
    const page = parseInt(pg, 10) || 1;
    const t = /^[a-z]{2}$/.test(str(tid)) ? tid : 'ju';
    const url = page > 1 ? `${baseUrl}/${t}_${page}/` : `${baseUrl}/${t}/`;
    try {
        const html = await httpGet(url, { 'Referer': baseUrl + '/' + t + '/' });
        if (!html) return output({ list: [], page: page, pagecount: 1 });
        const list = parseList(html);
        const info = parsePageInfo(html, page);
        return output({
            list: list,
            page: info.page,
            pagecount: Math.max(info.pagecount, list.length ? info.page : 1),
            limit: list.length,
            total: list.length
        });
    } catch (e) {
        return output({ list: [], page: page, pagecount: 1 });
    }
}

// 详情：解析夸克 / 百度网盘文件
async function detail(id) {
    const path = str(id);
    const detailUrl = /^https?:\/\//.test(path) ? path : baseUrl + (path.charAt(0) === '/' ? path : '/' + path);
    const html = await httpGet(detailUrl, { 'Referer': baseUrl + '/' });
    if (!html) return backErr('详情页获取失败');

    const h1M = /<h1[^>]*>([\s\S]*?)<\/h1>/.exec(html);
    const t = splitTitle(h1M ? h1M[1] : path);
    const dateM = /<span class="time">([^<]*)<\/span>/.exec(html);
    const viewM = /<span class="view">([^<]*)<\/span>/.exec(html);

    // 收集所有资源块中的网盘链接
    const links = [];
    const seen = {};
    const reBlock = /<div class="dlipp-cont-bd">([\s\S]*?)<\/div>/g;
    let bm;
    while ((bm = reBlock.exec(html)) !== null) {
        const reA = /<a\b([^>]*)>([\s\S]*?)<\/a>/g;
        let am;
        while ((am = reA.exec(bm[1])) !== null) {
            const hrefM = /\bhref="([^"]+)"/.exec(am[1]);
            if (!hrefM) continue;
            const href = hrefM[1];
            if (seen[href]) continue;
            if (href.indexOf('pan.quark.cn') >= 0) { seen[href] = 1; links.push({ type: 'quark', url: href }); }
            else if (href.indexOf('pan.baidu.com') >= 0) { seen[href] = 1; links.push({ type: 'baidu', url: href }); }
        }
    }

    const playFrom = [];
    const playUrl = [];
    let baiduIndex = 0;
    let hasQuark = false, hasBaidu = false;

    for (const l of links) {
        try {
            if (l.type === 'quark') {
                hasQuark = true;
                const r = await buildQuarkLine(l.url);
                if (r) { playFrom.push(r.flag); playUrl.push(r.line); }
            } else if (l.type === 'baidu') {
                hasBaidu = true;
                baiduIndex++;
                const r = await buildBaiduLine(l.url, baiduIndex);
                if (r) { playFrom.push(r.flag); playUrl.push(r.line); }
            }
        } catch (e) {
            console.log('剧透社[盘] 网盘解析失败:', l.url, e && e.message);
        }
    }

    const panNames = [];
    if (hasQuark) panNames.push('夸克网盘');
    if (hasBaidu) panNames.push('百度网盘');
    const tips = [];
    if (dateM) tips.push('发布：' + dateM[1].trim());
    if (viewM) tips.push('浏览：' + viewM[1].trim());
    if (panNames.length) tips.push('资源：' + panNames.join('、'));
    if (playFrom.length === 0) {
        tips.push('暂未解析到可播放文件，请确认已在配置中填写对应网盘 Cookie 后重试');
    }

    const vod = {
        vod_id: path,
        vod_name: t.name,
        vod_pic: hasQuark ? PIC_QUARK : (hasBaidu ? PIC_BAIDU : PIC_QUARK),
        vod_remarks: t.remarks,
        vod_content: tips.join('\n'),
        vod_play_from: playFrom.join('$$$') || '无资源',
        vod_play_url: playUrl.join('$$$') || ''
    };
    return output({ list: [vod] });
}

// 搜索：/search/?keyword=xx（&page=2）
async function search(key, quick, pg) {
    const wd = str(key).trim();
    const page = parseInt(pg, 10) || 1;
    if (!wd) return output({ list: [], page: page, pagecount: 1 });
    let url = `${baseUrl}/search/?keyword=${encodeURIComponent(wd)}`;
    if (page > 1) url += `&page=${page}`;
    try {
        const html = await httpGet(url);
        if (!html) return output({ list: [], page: page, pagecount: 1 });
        const list = parseList(html);
        const info = parsePageInfo(html, page);
        return output({
            list: list,
            page: info.page,
            pagecount: Math.max(info.pagecount, list.length ? info.page : 1),
            limit: list.length,
            total: list.length
        });
    } catch (e) {
        return backErr(e);
    }
}

// 播放解析
async function play(flag, id, vipFlags) {
    flag = str(flag);
    const sid = str(id);

    // ---------------- 夸克 ----------------
    if (flag.indexOf('Quark-') === 0) {
        const Quark = getPan('Quark');
        if (!Quark) return output({ parse: 0, url: '' });
        const ids = sid.split('*');
        const urls = [];

        // 下载链接（本地代理“猫” + 原画直连）
        let down = null;
        try { down = await Quark.getDownload(ids[0], ids[1], ids[2], ids[3], true); } catch (e) { down = null; }
        if (Array.isArray(down)) {
            down.forEach(t => {
                if (t && t.url) {
                    urls.push('猫' + t.name, 'http://127.0.0.1:5575/proxy?thread=' + envGet('thread', 6) + '&chunkSize=256&url=' + encodeURIComponent(t.url));
                    urls.push(t.name, t.url + '#isVideo=true##fastPlayMode##threads=20#');
                }
            });
        }

        // 转码链接（流畅 / 高清 / 超清）
        let trans = [];
        try { trans = await Quark.getLiveTranscoding(ids[0], ids[1], ids[2], ids[3]) || []; } catch (e) { trans = []; }
        trans.filter(t => t && t.accessable).forEach(t => {
            const label = t.resolution === 'low' ? '流畅'
                : t.resolution === 'high' ? '高清'
                    : t.resolution === 'super' ? '超清' : t.resolution;
            urls.push(label, t.video_info.url + '#isVideo=true##fastPlayMode##threads=20#');
        });

        return output({ parse: 0, url: urls, header: { 'Cookie': envGet('quark_cookie', '') } });
    }

    // ---------------- 百度 ----------------
    if (flag.indexOf('Baidu-') === 0) {
        const Baidu = getPan('Baidu2');
        if (!Baidu) return output({ parse: 0, url: '' });
        const ids = sid.split('*');
        let url = '';
        try { url = await Baidu.getAppShareUrl(ids[0], ids[1], ids[2], ids[3]); } catch (e) { url = ''; }
        return output({
            parse: 0,
            url: ['原画', url + '#isVideo=true##fastPlayMode##threads=10#'],
            header: {
                'User-Agent': 'netdisk;P2SP;2.2.91.136;android-android;',
                'Cookie': envGet('baidu_cookie', '')
            }
        });
    }

    return output({ parse: 0, url: sid });
}

/* ------------------------- 兼容别名（不同壳子） ------------------------- */

async function homeContent(filter) { return home(filter); }
async function homeVideoContent() { return homeVod(); }
async function categoryContent(tid, pg, filter, extend) { return category(tid, pg, filter, extend); }
async function detailContent(ids) {
    const id = Array.isArray(ids) ? ids[0] : ids;
    return detail(id);
}
async function searchContent(key, quick, pg) { return search(key, quick, pg); }
async function playerContent(flag, id, vipFlags) { return play(flag, id, vipFlags); }

export default {
    init,
    home,
    homeVod,
    category,
    detail,
    search,
    play,
    live,
    proxy,
    action,
    sniffer,
    isVideo,
    destroy,
    homeContent,
    homeVideoContent,
    categoryContent,
    detailContent,
    searchContent,
    playerContent
};
