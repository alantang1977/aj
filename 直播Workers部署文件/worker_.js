// ==========================================
// 1. 多源直播源配置（可自由增删）
// ==========================================
const SOURCE_URL_LIST = [
    "https://0701.tv1288.xyz",
    "https://123.tv1288.xyz/sm2.txt",
    "https://iptv.445569.xyz/live.m3u"
];

// ==========================================
// 2. 全局引流信息（保留原始配置）
// ==========================================
const PROMO_TITLE = "加入TG频道https://t.me/letjun";
const PROMO_URL = "https://cnb.cool/junchao.tang/jtv/-/git/raw/main/Pictures/Robot.mp4";
const PROMO_PIC = "https://cnb.cool/junchao.tang/jtv/-/git/raw/main/Pictures/junmeng.gif";
const PROMO_GROUP = "📢 频道关注";
const GLOBAL_PLAY_FROM = "✈️TG频道https://t.me/letjun";

// 黑名单拦截库
const SPAM_KEYWORDS = ["注意事项", "加群", "群", "TG", "tg", "交流", "防失联", "关注", "网址", "官网", "广告", "微信", "QQ", "最新", "获取资源", "备用", "防丢", "关于", "频道"];

// 请求超时时间（毫秒）—— 已从 8000 增加到 15000，适配大文件源
const FETCH_TIMEOUT = 15000;

function getPromoVodItem() {
    return {
        vod_id: "live_promo",
        vod_name: PROMO_TITLE,
        vod_pic: PROMO_PIC,
        vod_remarks: "置顶引流",
        vod_play_from: GLOBAL_PLAY_FROM,
        vod_play_url: `引流视频$${PROMO_URL}`
    };
}

function isSpam(text) {
    if (!text) return false;
    return SPAM_KEYWORDS.some(kw => text.includes(kw));
}

// 安全转义M3U字段中的双引号
function escapeM3UField(str) {
    return String(str).replace(/"/g, '\\"');
}

// 生成默认台标URL（带编码，防止特殊字符导致404）
function getDefaultLogo(title) {
    const encoded = encodeURIComponent(title);
    return `https://epg.112114.xyz/logo/${encoded}.png`;
}

/**
 * 带超时的 fetch 封装
 */
async function fetchWithTimeout(url, timeout = FETCH_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    try {
        return await fetch(url, {
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": new URL(url).origin,
                "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            },
            redirect: "follow",
            signal: controller.signal,
            cf: { cacheTtl: 600, cacheEverything: true }
        });
    } finally {
        clearTimeout(timeoutId);
    }
}

/**
 * 解码响应体，自动处理编码（GBK / UTF-8）
 */
function decodeBuffer(buffer, contentType) {
    let isGBK = /gbk|gb2312|gb18030/i.test(contentType || "");

    if (!isGBK) {
        const utf8Text = new TextDecoder("utf-8").decode(buffer);
        const fffdCount = (utf8Text.match(/\uFFFD/g) || []).length;
        if (fffdCount > 0 && (fffdCount / utf8Text.length > 0.05 || fffdCount > 50)) {
            isGBK = true;
        } else {
            return utf8Text;
        }
    }

    try {
        return new TextDecoder("gbk").decode(buffer);
    } catch (e) {
        console.warn("TextDecoder 不支持 GBK，回退为 UTF-8 解码");
        return new TextDecoder("utf-8").decode(buffer);
    }
}

/**
 * 解析单份源文本，输出频道对象数组
 * 支持 M3U 格式 / DIYP TXT 格式
 */
function parseSourceText(sourceText) {
    let tempList = [];
    const lines = sourceText.split('\n');
    const isM3uFormat = sourceText.includes('#EXTM3U') || sourceText.includes('#EXTINF');

    if (isM3uFormat) {
        let currentInfo = null;
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (!line) continue;

            if (line.startsWith('#EXTINF')) {
                const attrRegex = /([a-zA-Z-]+)="([^"]*)"|([a-zA-Z-]+)='([^']*)'|([a-zA-Z-]+)=([^,\s]+)/g;
                let attrs = {};
                let match;
                while ((match = attrRegex.exec(line)) !== null) {
                    if (match[2] !== undefined) attrs[match[1]] = match[2];
                    else if (match[4] !== undefined) attrs[match[3]] = match[4];
                    else if (match[6] !== undefined) attrs[match[5]] = match[6];
                }
                let group = attrs['group-title'] || "默认频道";
                let logo = attrs['tvg-logo'] || "";
                let commaIdx = line.indexOf(',');
                let title = commaIdx > -1 ? line.substring(commaIdx + 1).trim() : "未知频道";
                if (!logo) {
                    logo = getDefaultLogo(title);
                }
                currentInfo = { group, logo, title };
            }
            else if (!line.startsWith('#') && currentInfo) {
                currentInfo.url = line;
                if (!isSpam(currentInfo.group) && !isSpam(currentInfo.title)) {
                    tempList.push(currentInfo);
                }
                currentInfo = null;
            }
        }
    } else {
        let currentGroup = "默认频道";
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (!line) continue;
            if (line.includes(',#genre#')) {
                currentGroup = line.split(',')[0].trim();
            }
            else if (line.includes(',')) {
                let lastCommaIdx = line.lastIndexOf(',');
                let title = line.substring(0, lastCommaIdx).trim();
                let playUrl = line.substring(lastCommaIdx + 1).trim();
                let logo = getDefaultLogo(title);
                let currentInfo = { group: currentGroup, logo, title, url: playUrl };
                if (!isSpam(currentGroup) && !isSpam(title)) {
                    tempList.push(currentInfo);
                }
            }
        }
    }
    return tempList;
}

/**
 * 抓取单个源并解析
 */
async function fetchAndParseSource(srcUrl) {
    try {
        const response = await fetchWithTimeout(srcUrl);
        if (!response.ok) {
            console.warn(`源抓取失败 ${srcUrl} status:${response.status}`);
            return [];
        }
        const buffer = await response.arrayBuffer();
        const contentType = response.headers.get("content-type") || "";
        const sourceText = decodeBuffer(buffer, contentType);
        const parsed = parseSourceText(sourceText);
        console.log(`[源统计] ${srcUrl} 解析得到频道数量:${parsed.length}`);
        return parsed;
    } catch (err) {
        if (err.name === 'AbortError') {
            console.warn(`源请求超时 ${srcUrl}`);
        } else {
            console.warn(`源异常跳过 ${srcUrl}`, err.message);
        }
        return [];
    }
}

/**
 * 获取所有频道（并行抓取多源 + 去重）
 */
async function getAllChannels() {
    const results = await Promise.allSettled(SOURCE_URL_LIST.map(src => fetchAndParseSource(src)));

    let allRawList = [];
    let successCount = 0;
    results.forEach((result, index) => {
        if (result.status === 'fulfilled') {
            successCount++;
            allRawList.push(...result.value);
        } else {
            console.warn(`源 ${SOURCE_URL_LIST[index]} 抓取失败:`, result.reason?.message || result.reason);
        }
    });

    // 去重：频道标题 + 播放链接作为唯一 key
    const seen = new Set();
    let filteredList = [];
    for (const item of allRawList) {
        const key = `${item.title}||${item.url}`;
        if (!seen.has(key)) {
            seen.add(key);
            filteredList.push(item);
        }
    }

    console.log(`多源抓取完成，成功 ${successCount}/${SOURCE_URL_LIST.length} 个源，有效频道 ${filteredList.length} 个`);
    return filteredList;
}

// ==========================================
// Worker 入口
// ==========================================
export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const path = url.pathname;
        const params = url.searchParams;

        const corsHeaders = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Content-Type": "application/json; charset=utf-8"
        };

        if (request.method === "OPTIONS") {
            return new Response(null, { headers: corsHeaders });
        }

        // 健康检查接口
        if (path === "/health") {
            return new Response(JSON.stringify({
                status: "ok",
                sources: SOURCE_URL_LIST
            }), { headers: corsHeaders });
        }

        try {
            const filteredList = await getAllChannels();

            // ==========================================
            // 路由 1：纯净版 M3U 输出 (/live.m3u)
            // ==========================================
            if (path === "/live.m3u" || path.endsWith(".m3u")) {
                let outM3u = "#EXTM3U\n";
                outM3u += `#EXTINF:-1 group-title="${escapeM3UField(PROMO_GROUP)}",${escapeM3UField(PROMO_TITLE)}\n${PROMO_URL}\n`;
                filteredList.forEach(item => {
                    let logoAttr = item.logo ? ` tvg-logo="${escapeM3UField(item.logo)}"` : "";
                    outM3u += `#EXTINF:-1${logoAttr} group-title="${escapeM3UField(item.group)}",${escapeM3UField(item.title)}\n`;
                    outM3u += `${item.url}\n`;
                });
                return new Response(outM3u, {
                    headers: {
                        "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
                        "Access-Control-Allow-Origin": "*"
                    }
                });
            }

            // ==========================================
            // 路由 2：TVBox / 影视仓 T4 接口 (JSON)
            // ==========================================
            let ac = params.get("ac");
            let t = params.get("t");
            let ids = params.get("ids");
            let wd = params.get("wd");

            if (t && typeof t !== 'string') {
                return new Response(JSON.stringify({ error: '参数 t 类型错误' }), { status: 400, headers: corsHeaders });
            }
            if (wd && typeof wd !== 'string') {
                return new Response(JSON.stringify({ error: '参数 wd 类型错误' }), { status: 400, headers: corsHeaders });
            }
            if (wd && wd.length > 50) {
                return new Response(JSON.stringify({ error: '参数 wd 过长' }), { status: 400, headers: corsHeaders });
            }

            let classes = [
                { type_id: "all", type_name: "全部直播" },
                { type_id: "promo", type_name: PROMO_GROUP }
            ];
            let vodList = [];

            let uniqueGroups = [...new Set(filteredList.map(i => i.group))];
            uniqueGroups.forEach(g => {
                if (g !== "默认频道") {
                    classes.push({ type_id: `group_${g}`, type_name: g });
                }
            });

            if (!t || t === "all" || t === "promo") {
                vodList.push(getPromoVodItem());
            }

            filteredList.forEach((item, index) => {
                let typeId = `group_${item.group}`;
                if (!t || t === "all" || t === typeId) {
                    if (wd && !item.title.toLowerCase().includes(wd.toLowerCase())) return;
                    let remarks = item.group === "默认频道" ? "在线" : item.group;
                    vodList.push({
                        vod_id: `live_${index}`,
                        vod_name: item.title,
                        vod_pic: item.logo,
                        vod_remarks: remarks,
                        vod_play_from: "在线直播",
                        vod_play_url: `主线路$${item.url}`
                    });
                }
            });

            // 详情接口
            if (ac === "detail" && ids) {
                let idArr = String(ids).split(",");
                let detailList = [];
                if (idArr.includes("live_promo")) {
                    detailList.push({
                        vod_id: "live_promo",
                        vod_name: PROMO_TITLE,
                        vod_pic: PROMO_PIC,
                        vod_content: "请关注我的TG频道 https://t.me/letjun",
                        vod_play_from: GLOBAL_PLAY_FROM,
                        vod_play_url: `引流视频$${PROMO_URL}`
                    });
                }
                let regularItems = vodList.filter(v => idArr.includes(v.vod_id) && v.vod_id !== "live_promo");
                detailList.push(...regularItems);
                return new Response(JSON.stringify({ list: detailList }), { headers: corsHeaders });
            }

            return new Response(JSON.stringify({
                class: classes,
                list: vodList
            }), { headers: corsHeaders });

        } catch (err) {
            console.error("Worker 运行报错:", err);
            return new Response(JSON.stringify({ "error": err.message, "list": [] }), {
                status: 500,
                headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" }
            });
        }
    }
};
