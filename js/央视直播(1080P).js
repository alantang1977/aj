/**
 * 央视频 1080P
 * 依据 wv.js-spider 规范修复重构
 * 发布页 https://m.yangshipin.cn/
 *
 * @config
 * timeout: 20
 * blockImages: false
 * blockList: *.[ico|gif]* .analytics* .google* .facebook*
 * debug: false
 */

// fetch-only 站，顶层不声明 baseUrl
const SITE_API = 'https://h5access.yangshipin.cn/web/tv_web_share?raw=1&pid=600002485';
const PC_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36';

let channelCache = null;

async function fetchChannelList() {
    if (channelCache && channelCache.length > 0) {
        return channelCache;
    }
    try {
        const resp = await fetch(SITE_API);
        const data = await resp.json();
        const pidInfo = data?.data?.pidInfo || [];
        channelCache = pidInfo;
        return channelCache;
    } catch (e) {
        return [];
    }
}

function isCentralTV(name) {
    return /^CCTV|^CGTN/i.test(name || '');
}

/**
 * 初始化
 */
async function init(cfg) {
    return {};
}

/**
 * 首页分类与筛选
 * 规范要求：class 中的每个 type_id 都必须在 filters 中有对应键；无筛选时设为 []
 */
async function homeContent(filter) {
    return {
        class: [
            { type_id: '1', type_name: '央视' },
            { type_id: '2', type_name: '卫视' }
        ],
        filters: {
            '1': [],
            '2': []
        }
    };
}

/**
 * 首页推荐视频
 */
async function homeVideoContent() {
    const list = await fetchChannelList();
    const vods = list
        .filter(item => item.vipInfo?.isVip !== true && item.pid && item.channelName)
        .slice(0, 12)
        .map(item => {
            const isCentral = isCentralTV(item.channelName);
            return {
                vod_id: item.pid,
                vod_name: item.channelName,
                vod_pic: item.audioPosterUrl || item.horizontalPosterUrl || '',
                vod_remarks: isCentral ? '央视高清' : '卫视高清',
                style: { type: 'rect', ratio: isCentral ? 1.66 : 1 }
            };
        });

    return { list: vods };
}

/**
 * 分类内容
 */
async function categoryContent(tid, pg, filter, extend) {
    const page = parseInt(pg, 10) || 1;
    const pidInfo = await fetchChannelList();

    const vods = pidInfo
        .filter(item => {
            // 过滤 VIP 及无效项
            if (item.vipInfo?.isVip === true) return false;
            if (!item.pid || !item.channelName) return false;
            const isCentral = isCentralTV(item.channelName);
            return tid === '1' ? isCentral : !isCentral;
        })
        .map(item => {
            const isCentral = isCentralTV(item.channelName);
            const vodPic = item.audioPosterUrl || item.horizontalPosterUrl || '';
            return {
                vod_id: item.pid,
                vod_name: item.channelName,
                vod_pic: vodPic,
                vod_remarks: isCentral ? '央视频 · 央视' : '央视频 · 卫视',
                // 兼顾某些专属壳端对 action 属性的支持
                action: item.pid,
                style: { type: 'rect', ratio: isCentral ? 1.66 : 1 }
            };
        })
        .filter(item => item.vod_pic);

    return {
        code: 1,
        msg: '数据列表',
        list: vods,
        page: 1,
        pagecount: 1,
        limit: vods.length,
        total: vods.length
    };
}

/**
 * 详情页
 * 标准规范：根据传入的 ids 获取详情并生成真实播放线路
 */
async function detailContent(ids) {
    const targetPid = Array.isArray(ids) ? String(ids[0] || '') : String(ids || '');
    if (!targetPid) return { list: [] };

    const list = await fetchChannelList();
    const item = list.find(x => String(x.pid) === targetPid);

    if (!item) {
        return {
            list: [{
                vod_id: targetPid,
                vod_name: '直播频道',
                vod_pic: '',
                vod_remarks: '1080P',
                vod_play_from: '央视频',
                vod_play_url: '1080P$' + targetPid
            }]
        };
    }

    const isCentral = isCentralTV(item.channelName);
    return {
        list: [{
            vod_id: item.pid,
            vod_name: item.channelName,
            vod_pic: item.audioPosterUrl || item.horizontalPosterUrl || '',
            vod_remarks: isCentral ? '央视直播' : '卫视直播',
            vod_actor: item.channelName,
            vod_content: (item.channelName || '') + ' 高清网络电视直播',
            vod_play_from: '央视频1080P',
            vod_play_url: '高清直播$' + item.pid
        }]
    };
}

/**
 * 搜索
 * 对已知电视频道做本地模糊匹配
 */
async function searchContent(key, quick, pg) {
    if (!key) return { list: [] };
    const keyword = String(key).trim().toLowerCase();
    const list = await fetchChannelList();

    const matches = list
        .filter(item => {
            if (item.vipInfo?.isVip === true || !item.pid || !item.channelName) return false;
            return item.channelName.toLowerCase().includes(keyword);
        })
        .map(item => {
            const isCentral = isCentralTV(item.channelName);
            return {
                vod_id: item.pid,
                vod_name: item.channelName,
                vod_pic: item.audioPosterUrl || item.horizontalPosterUrl || '',
                vod_remarks: isCentral ? '央视' : '卫视',
                style: { type: 'rect', ratio: isCentral ? 1.66 : 1 }
            };
        });

    return { list: matches };
}

/**
 * 播放器
 * 央视频网页端使用防盗链及动态流签名，此处按规范返回标准的 wvplayer 模式
 */
async function playerContent(flag, id, vipFlags) {
    const pid = String(id || '').trim();
    if (!pid) return {};

    const playUrl = 'https://yangshipin.cn/tv/home?pid=' + pid;

    return {
        type: 'wvplayer',
        url: playUrl,
        headers: {
            'User-Agent': PC_UA,
            'Referer': 'https://yangshipin.cn/'
        },
        playerSelector: '#player-root, .player-wrap, .player-box, .video-player',
        selectors: [
            'video',
            '.xgplayer video',
            '.video-js video'
        ],
        click: "var btn=document.querySelector('.play-btn, .xgplayer-play');if(btn)btn.click();",
        script: "(function(){" +
            "var junk=['.app-down','.down-bar','.top-header','.footer','.float-layer','.open-app','.recommend-wrap'];" +
            "junk.forEach(function(s){document.querySelectorAll(s).forEach(function(el){el.remove();});});" +
            "var timer=setInterval(function(){" +
            "var m=document.querySelector('.player-mask');if(m){m.remove();clearInterval(timer);}" +
            "},300);" +
            "setTimeout(function(){clearInterval(timer);},5000);" +
        "})();",
        timeout: 20
    };
}

/**
 * 兼顾非标准壳子的 action 调用
 */
async function action(pid) {
    if (typeof Java !== 'undefined' && Java.wvPlayer) {
        if (typeof Java.wvPlayerSetAllowInteraction === 'function') {
            Java.wvPlayerSetAllowInteraction(false);
        }
        if (typeof Java.wvPlayerSetScale === 'function') {
            Java.wvPlayerSetScale(0);
        }
        Java.wvPlayer({
            url: 'https://yangshipin.cn/tv/home?pid=' + pid,
            headers: {
                'user-agent': PC_UA
            }
        });
    }
}
