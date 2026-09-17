const axios = require('axios');
const cheerio = require('cheerio');
const http = require('http');
const https = require('https');
const CryptoJS = require('crypto-js');
const { Buffer } = require('buffer');

// 蜗牛 I 4K - https://zmi.kdns.fr
// MacCMS mxone 模板，详情页主要是 115cdn 分享链接；仿多多影音 drive 解析。
// 蜗牛4K站点请求使用容器当前网络路径，不依赖或生成 config/蜗牛4K.js.json。
// 普通 Node 环境仍可用 WONIU4K_PROXY/PROXY_HTTP 显式配置代理。
const HOST = 'https://zmi.kdns.fr';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36';

// 现有部署依赖站点登录态才能读取实际网盘分享 URL；保持原部署 Cookie。
const MANUAL_COOKIE = 'user_id=513; user_name=alantangappleid; group_id=2; group_name=%E6%99%AE%E9%80%9A%E4%BC%9A%E5%91%98; user_check=a192248003a2cf2bcc093178223d74c7; user_portrait=%2Fstatic_new%2Fimages%2Ftouxiang.png';

const COOKIE = (() => {
  const envCookie = (process.env.WONIU4K_COOKIE || '').trim();
  if (envCookie) return envCookie;
  return String(MANUAL_COOKIE || '').trim();
})();

const meta = {
  key: 'woniu4k',
  name: '蜗牛4K',
  type: 4,
  api: '/video/woniu4k',
  searchable: 0,
  quickSearch: 0,
  indexs: 1,
  changeable: 0,
  author: 'tcxp',
};

// WebHTV 的 indexs 来源会把首页封面标题送入全局搜索，但同一 indexs 来源中的
// 普通视频也会再次进入搜索。单独注册一个非 indexs 的目录来源，让搜索结果
// Folder 能继续下钻，并让最底层视频正常进入 VideoActivity。
const directoryMeta = {
  key: 'woniu4k_folder',
  name: '蜗牛4K目录',
  type: 4,
  api: '/video/woniu4k-folder',
  searchable: 1,
  quickSearch: 0,
  indexs: 0,
  changeable: 0,
  author: 'cupid',
};

const store = {
  init: false,
  log: console,
  redis: null,
  drives: [],
  resourceQueues: new Map(),
  resourceJobs: new Map(),
  resourceCache: new Map(),
};

const PROXY_URL = (process.env.WONIU4K_PROXY || process.env.PROXY_HTTP || process.env.HTTP_PROXY || process.env.http_proxy || '').trim();
const DRIVE_VOD_TIMEOUT_MS = 55_000;
const RESOURCE_CACHE_TTL_MS = 5 * 60_000;
const CACHE_VERSION = 'lazy-resource-playback-v169';

function parseAxiosProxy(raw) {
  if (!raw) return false;
  try {
    const u = new URL(raw);
    const out = {
      protocol: u.protocol.replace(':', ''),
      host: u.hostname,
      port: Number(u.port || (u.protocol === 'https:' ? 443 : 80)),
    };
    if (u.username) {
      out.auth = {
        username: decodeURIComponent(u.username),
        password: decodeURIComponent(u.password || ''),
      };
    }
    return out;
  } catch (_) {
    return false;
  }
}

const client = axios.create({
  timeout: 25000,
  proxy: parseAxiosProxy(PROXY_URL),
  maxRedirects: 5,
  httpAgent: new http.Agent({ keepAlive: true }),
  httpsAgent: new https.Agent({ keepAlive: true }),
  headers: {
    'User-Agent': UA,
    Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    Referer: `${HOST}/`,
  },
});

const CLASSES = [
  { type_id: '1', type_name: '电影' },
  { type_id: '2', type_name: '连续剧' },
  { type_id: '4', type_name: '动漫' },
  { type_id: '3', type_name: '综艺' },
];

function b64u(value) {
  return Buffer.from(String(value || ''), 'utf8').toString('base64url');
}

function unb64u(value) {
  try {
    return Buffer.from(String(value || ''), 'base64url').toString('utf8');
  } catch (_) {
    return '';
  }
}

function cookieHeader(cookie) {
  if (!cookie) return '';
  if (typeof cookie === 'string') return cookie;
  if (typeof cookie === 'object') return Object.entries(cookie).map(([k, v]) => `${k}=${v}`).join('; ');
  return String(cookie || '');
}

function requestBase(req) {
  const proto = String(req?.headers?.['x-forwarded-proto'] || 'http').split(',')[0].trim() || 'http';
  let host = String(req?.headers?.['x-forwarded-host'] || req?.headers?.host || '').split(',')[0].trim();
  if (!host || /^127\.0\.0\.1(?::|$)|^localhost(?::|$)/i.test(host)) host = '192.168.50.210:25002';
  return `${proto}://${host}`;
}

function requestToken(req) {
  return String(req?.query?.token || '').trim();
}

function siteProxyUrl(req, targetUrl) {
  const qs = new URLSearchParams({ proxy: 'quark', url: b64u(targetUrl) });
  const token = requestToken(req);
  if (token) qs.set('token', token);
  const path = `${meta.api}?${qs.toString()}`;
  return requestBase(req) ? requestBase(req) + path : path;
}

async function proxyQuarkDownload(req, reply) {
  const targetUrl = unb64u(req.query?.url || '');
  if (!/^https?:\/\//i.test(targetUrl)) {
    if (reply?.code) reply.code(400);
    return 'bad url';
  }
  const headers = {
    'User-Agent': (store.quarkHeaders && (store.quarkHeaders['user-agent'] || store.quarkHeaders['User-Agent'])) || 'AndroidDownloadManager',
    Referer: 'https://pan.quark.cn',
    Accept: '*/*',
    'x-ulrp': '1',
  };
  const ck = cookieHeader(store.quarkCookie);
  if (ck) headers.Cookie = ck;
  if (req.headers?.range) headers.Range = req.headers.range;
  try {
    const res = await client.get(targetUrl, {
      responseType: 'stream',
      headers,
      timeout: 30000,
      validateStatus: (s) => s >= 200 && s < 500,
      maxRedirects: 5,
    });
    if (reply?.code) reply.code(res.status || 200);
    if (reply?.header) {
      reply.header('Access-Control-Allow-Origin', '*');
      reply.header('Content-Type', 'video/mp4');
      for (const h of ['content-length', 'content-range', 'accept-ranges']) {
        if (res.headers?.[h]) reply.header(h, res.headers[h]);
      }
    }
    return res.data;
  } catch (e) {
    if (reply?.code) reply.code(502);
    return `proxy error: ${e.message}`;
  }
}

function absUrl(url) {
  if (!url) return '';
  let absolute;
  if (/^\/\//.test(url)) absolute = 'https:' + url;
  else if (/^https?:\/\//i.test(url)) absolute = url;
  else if (url.startsWith('/')) absolute = HOST + url;
  else absolute = HOST + '/' + url.replace(/^\/+/, '');
  if (
    absolute.startsWith(`${HOST}/`) &&
    !absolute.includes('@Referer=') &&
    !absolute.includes('@User-Agent=')
  ) {
    // 站点海报直接请求会返回 403，WebHTV ImgUtil 支持在图片 URL 后声明
    // 请求头。否则 Glide 回退为标题首字 TextDrawable，所有“115 · ...”
    // 资源都会显示成相同的“1”封面。
    return `${absolute}@Referer=${HOST}/@User-Agent=${UA}`;
  }
  return absolute;
}

function text($, el, sel = '') {
  let target;
  if (sel) target = el ? $(el).find(sel).first() : $(sel).first();
  else target = el ? $(el) : $.root();
  return target.text().replace(/\s+/g, ' ').trim();
}

function cleanContent(s) {
  return String(s || '')
    .replace(/收起|展开全部|内详/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function getIdFromHref(href) {
  const s = String(href || '');
  let m = s.match(/\/voddetail\/(\d+)\/?/i);
  if (m) return m[1];
  m = s.match(/\/vodplay\/(\d+)-\d+-\d+\/?/i);
  if (m) return m[1];
  m = s.match(/\/vod\/detail\/id\/(\d+)\.html/i);
  return m ? m[1] : '';
}

function pageUrl(tid, pg = 1) {
  const page = Math.max(1, parseInt(pg || '1', 10) || 1);
  if (page <= 1) return `${HOST}/vodtype/${tid}/`;
  return `${HOST}/vodtype/${tid}-${page}/`;
}

function searchUrl(wd, pg = 1) {
  const page = Math.max(1, parseInt(pg || '1', 10) || 1);
  const enc = encodeURIComponent(String(wd || '').trim());
  if (page <= 1) return `${HOST}/vodsearch/${enc}-------------/`;
  return `${HOST}/vodsearch/${enc}----------${page}---/`;
}

async function fetchHtml(url) {
  // Cookie 只在请求站点页面时携带，避免被 proxyQuarkDownload 等转发带到网盘 CDN。
  // 站点 TLS 建连或响应偶发失败时，只顺序重试当前站点页面，
  // 不调用网盘 getVod/play，也不会产生多资源并发解析。
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const res = await client.get(url, {
        responseType: 'text',
        headers: COOKIE ? { Cookie: COOKIE } : {},
        validateStatus: (s) => s >= 200 && s < 500,
      });
      if (res.status >= 400) throw new Error(`HTTP ${res.status} ${url}`);
      return res.data || '';
    } catch (error) {
      lastError = error;
      if (attempt >= 3) break;
      await new Promise((resolve) => setTimeout(resolve, attempt * 300));
    }
  }
  throw lastError || new Error(`fetch failed ${url}`);
}

function parseList(html) {
  const $ = cheerio.load(html || '');
  const seen = new Set();
  const list = [];

  $('.module-item,.module-search-item,a.video-card[href*="/voddetail/"],a.video-card[href*="/vodplay/"]').each((_, el) => {
    const root = $(el);
    let a = root.is('a[href*="/voddetail/"],a[href*="/vodplay/"]')
      ? root
      : root.find('a[href*="/voddetail/"]').first();
    if (!a.length) a = $(el).find('a[href*="/vodplay/"]').first();
    const href = a.attr('href') || '';
    const id = getIdFromHref(href);
    if (!id || seen.has(id)) return;
    seen.add(id);

    const img = $(el).find('img').first();
    let title = (
      a.attr('title') ||
      text($, el, '.video-title') ||
      text($, el, '.module-poster-item-title') ||
      text($, el, '.module-item-title') ||
      text($, el, '.video-name') ||
      text($, el, 'h3') ||
      text($, el, 'h4') ||
      ''
    )
      .replace(/^立刻播放/, '')
      .replace(/^下载/, '')
      .trim();
    if (!title) {
      const named = $(el).find('a[href*="/voddetail/"]').filter((__, n) => {
        const t = ($(n).attr('title') || $(n).text() || '').replace(/^立刻播放|^下载/, '').trim();
        return t && !/^\d+$/.test(t);
      }).first();
      title = (named.attr('title') || named.text() || '').replace(/^立刻播放|^下载/, '').trim();
    }
    if (!title) return;

    const pic = img.attr('data-src') || img.attr('data-original') || img.attr('src') || '';
    const caption = text($, el, '.module-item-caption');
    const note =
      text($, el, '.video-episode') ||
      text($, el, '.module-item-note') ||
      text($, el, '.module-poster-item-note') ||
      text($, el, '.video-serial') ||
      caption ||
      text($, el, '.module-item-text') ||
      '';

    list.push({
      vod_id: id,
      vod_name: title,
      vod_pic: absUrl(pic.includes('loading.gif') ? (img.attr('data-src') || img.attr('data-original') || '') : pic),
      vod_remarks: note,
    });
  });

  return list;
}

function parsePageCount(html, current = 1) {
  const $ = cheerio.load(html || '');
  let max = Math.max(1, parseInt(current || '1', 10) || 1);
  // 只认分页链接，避免年份筛选（如 2026）被当成页码
  $('a[href*="/vodtype/"],a[href*="/vodsearch/"]').each((_, a) => {
    const href = $(a).attr('href') || '';
    const txt = $(a).text().trim();
    let m = href.match(/\/vodtype\/\d+-(\d+)\/?/i);
    if (m) max = Math.max(max, parseInt(m[1], 10) || 1);
    m = href.match(/\/vodsearch\/[^/]*?----------+(\d+)---+\/?/i);
    if (m) max = Math.max(max, parseInt(m[1], 10) || 1);
    if (/^(首页|上一页|下一页|尾页|\d+)$/.test(txt)) {
      m = href.match(/\/vodtype\/\d+-(\d+)\/?/i) || href.match(/----------+(\d+)---+\/?/i);
      if (m) max = Math.max(max, parseInt(m[1], 10) || 1);
    }
  });
  return max || 1;
}

async function home() {
  return {
    class: CLASSES,
    // 保持 WebHTV 原首页行为：空列表会自动用第一分类回填影片封面墙。
    // HomeActivity 点击这些普通影片封面后发送 ids=<entry>；详情只构造
    // “网盘线路 + 资源标题选集”，不在首页或封面详情阶段解析网盘。
    list: [],
    page: 1,
    pagecount: 1,
    total: 0,
  };
}

async function category({ id, page }) {
  const pg = Math.max(1, parseInt(page || '1', 10) || 1);
  const html = await fetchHtml(pageUrl(id, pg));
  const list = wrapListAsEntries(parseList(html), { markCover: true });
  return {
    list,
    page: pg,
    pagecount: parsePageCount(html, pg),
    total: list.length,
  };
}

function classifyPan(url) {
  const u = String(url || '').toLowerCase();
  if (u.includes('pan.quark.cn')) return 'quark';
  if (u.includes('drive.uc.cn')) return 'uc';
  if (u.includes('aliyundrive.com') || u.includes('alipan.com')) return 'ali';
  if (u.includes('pan.baidu.com')) return 'baidu';
  if (u.includes('cloud.189.cn')) return 'a189';
  if (u.includes('115.com') || u.includes('115cdn.com') || u.includes('anxia.com')) return 'a115';
  if (u.includes('123pan.com') || u.includes('123684.com') || u.includes('123pan.cn')) return 'a123';
  if (u.includes('pan.xunlei.com') || u.includes('xunlei.com')) return 'xunlei';
  return 'push';
}

function driveName(key) {
  const map = {
    quark: '夸克',
    uc: 'UC',
    ali: '阿里',
    baidu: '百度',
    a189: '天翼',
    a115: '115',
    a123: '123',
    xunlei: '迅雷',
    push: '网盘',
  };
  return map[key] || key;
}

function encodePlayId(id) {
  return `b64://${Buffer.from(String(id || ''), 'utf8').toString('base64url')}`;
}

function decodePlayId(id) {
  const raw = String(id || '').trim();
  if (raw.startsWith('b64://')) {
    try {
      return Buffer.from(raw.slice(6), 'base64url').toString('utf8');
    } catch {
      return raw;
    }
  }
  return raw;
}

function withTimeout(promise, timeoutMs, label = 'operation') {
  const ms = Math.max(1, Number(timeoutMs) || 1);
  let timer;
  return Promise.race([
    Promise.resolve(promise),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} timeout after ${ms}ms`)), ms);
    }),
  ]).finally(() => clearTimeout(timer));
}

function compatibleDriveKeys(key) {
  const k = String(key || '').toLowerCase();
  const map = {
    ali: ['ali', 'aliyun'],
    aliyun: ['ali', 'aliyun'],
    a189: ['a189', 'tianyi'],
    tianyi: ['a189', 'tianyi'],
    a115: ['a115', '115'],
    115: ['a115', '115'],
    a123: ['a123', '123'],
    123: ['a123', '123'],
    quark: ['quark'],
    uc: ['uc'],
    baidu: ['baidu'],
    xunlei: ['xunlei'],
  };
  return map[k] || (k ? [k] : []);
}

function validVod(vod) {
  const playUrl = String(vod?.vod_play_url || '').trim();
  if (!playUrl || !playUrl.includes('$')) return false;
  const parts = playUrl.split('#').filter(Boolean);
  if (parts.length === 1) {
    const name = parts[0].split('$')[0];
    if (/^(播放|全集|点击播放|立即播放)$/i.test(name)) return false;
  }
  return true;
}

function findDriveByUrl(url, panKey = '') {
  const drives = store.drives || [];
  const keys = compatibleDriveKeys(panKey);
  let drive = drives.find((d) => keys.includes(String(d?.key || '').toLowerCase()));
  if (!drive && url) {
    drive = drives.find((d) => {
      try {
        return typeof d?.matchShare === 'function' && d.matchShare(url);
      } catch {
        return false;
      }
    });
  }
  return drive || null;
}

function normalizeQuarkPlayUrl(url) {
  return String(url || '').replace(/&amp;/g, '&').replace(/&#38;/g, '&');
}

function quarkPwdId(url) {
  return (String(url || '').match(/pan\.quark\.cn\/s\/([\w-]+)/i) || [])[1] || String(url || '').trim();
}

function quarkEncodePayload(obj) {
  return Buffer.from(JSON.stringify(obj), 'utf8').toString('base64url');
}

function quarkDecodePayload(id) {
  const raw = decodePlayId(id);
  try {
    return JSON.parse(raw);
  } catch {}
  try {
    return JSON.parse(Buffer.from(raw, 'base64url').toString('utf8'));
  } catch {}
  try {
    return JSON.parse(Buffer.from(raw, 'base64').toString('utf8'));
  } catch {}
  return null;
}

function isQuarkVideoItem(item) {
  const name = String(item?.name || item?.file_name || '');
  const ext = name.split('.').pop().toLowerCase();
  return (
    ['mp4', 'mkv', 'avi', 'mov', 'm4v', 'ts', 'webm', 'flv', 'wmv', 'mpg', 'mpeg', 'rmvb'].includes(ext) ||
    Number(item?.mimeType) === 1 ||
    Number(item?.category) === 1 ||
    Number(item?.file_type) === 1
  );
}

async function getQuarkFallbackVod(url, drive) {
  if (!drive || typeof drive.readFolder !== 'function') return null;
  const shareId = quarkPwdId(url);
  const stoken = typeof drive.getShareToken === 'function' ? await drive.getShareToken(shareId, '') : null;
  const root = [];
  await drive.readFolder({ shareId, folderId: '0', pwd: '' }, root, 1, stoken);
  const videos = [];
  const visit = async (folderId) => {
    const normalized = [];
    const ret = await drive.readFolder({ shareId, folderId, pwd: '' }, normalized, 1, stoken);
    const raw = (ret?.data?.list || []).map((f) => ({
      id: f.fid,
      pid: folderId,
      name: f.file_name,
      isDir: !!f.dir,
      size: f.size,
      mimeType: f.category,
      fidToken: f.share_fid_token || f.fid_token || f.share_fid_token_for_share,
    }));
    const all = normalized.length ? normalized : raw;
    for (const item of all) {
      if (item.isDir) await visit(item.id);
      else if (isQuarkVideoItem(item)) videos.push(item);
    }
  };
  for (const item of root) {
    if (item.isDir) await visit(item.id);
    else if (isQuarkVideoItem(item)) videos.push(item);
  }
  if (!videos.length) return null;
  videos.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), undefined, { numeric: true, sensitivity: 'base' }));
  const play = videos
    .map((f) => {
      const size = Number(f.size || 0) ? ` ${Math.round(Number(f.size) / 1024 / 1024)}MB` : '';
      const payload = quarkEncodePayload({
        quarkFallback: 1,
        shareId,
        fileId: f.id,
        fidToken: f.fidToken,
        folderId: f.pid || '0',
        pwd: '',
        name: f.name,
        raw: url,
      });
      return `${f.name || f.id}${size}$${encodePlayId(payload)}`;
    })
    .join('#');
  return {
    vod_id: url,
    vod_name: shareId,
    vod_pic: '',
    vod_content: url,
    type_name: '夸克',
    vod_play_from: 'quark',
    vod_play_url: play,
  };
}

async function playQuarkFallback(payload, drive, req) {
  if (!payload?.quarkFallback || !drive || typeof drive.fetch !== 'function' || typeof drive.getDownloadUrl !== 'function') return null;
  const stoken = typeof drive.getShareToken === 'function' ? await drive.getShareToken(payload.shareId, payload.pwd || '') : '';
  const fidTokens = [payload.fidToken].filter(Boolean);
  for (const fidToken of fidTokens) {
    const data = {
      fid_list: [payload.fileId],
      fid_token_list: [fidToken],
      to_pdir_fid: '0',
      pwd_id: payload.shareId,
      stoken,
      pdir_fid: '0',
      scene: 'link',
    };
    const apiUrl = drive._apiUrl || 'https://drive.quark.cn/1/clouddrive';
    const params = Object.assign({ fr: 'pc', uc_param_str: '' }, drive._params || {});
    const res = await drive.fetch(`${apiUrl}/share/sharepage/save`, { method: 'post', params, data });
    const taskId = res?.data?.task_id || res?.task_id;
    if (!taskId) continue;
    for (let i = 0; i < 10; i++) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      const tr = await drive.fetch(`${apiUrl}/task`, {
        params: Object.assign({ fr: 'pc', uc_param_str: '', task_id: taskId, retry_index: i }, drive._params || {}),
      });
      const saved = tr?.data?.save_as?.save_as_top_fids?.[0] || tr?.save_as?.save_as_top_fids?.[0];
      if (!saved) continue;
      try {
        const vlist = typeof drive.getVideoPreviewPlayInfo === 'function' ? await drive.getVideoPreviewPlayInfo(saved) : null;
        const preview = Array.isArray(vlist)
          ? vlist.find((x) => x?.video_info?.url)?.video_info?.url || vlist.find((x) => x?.url)?.url
          : vlist;
        if (preview) {
          return {
            parse: 0,
            jx: 0,
            url: siteProxyUrl(req, normalizeQuarkPlayUrl(preview)),
            header: Object.assign(
              { 'user-agent': 'AndroidDownloadManager' },
              drive._headers || {},
              cookieHeader(drive._cookie) ? { Cookie: cookieHeader(drive._cookie) } : {}
            ),
          };
        }
      } catch {}
      const url = await drive.getDownloadUrl(saved);
      if (url) {
        return {
          parse: 0,
          jx: 0,
          url: siteProxyUrl(req, normalizeQuarkPlayUrl(url)),
          header: Object.assign(
            { 'user-agent': 'AndroidDownloadManager' },
            drive._headers || {},
            cookieHeader(drive._cookie) ? { Cookie: cookieHeader(drive._cookie) } : {}
          ),
        };
      }
    }
  }
  return null;
}

async function getPanVod(url, panKey = '') {
  url = normalizeShareUrl(url);
  const drive = findDriveByUrl(url, panKey);
  const key = panKey || classifyPan(url);
  const actualKey = classifyPan(url);

  // MV 正式运行时只向插件暴露 getVod/play facade；始终优先走正式桥接，
  // 避免 115 先发起一轮宿主不支持的 cookie/proapi 请求后才进入 MV 链路。
  if (drive && typeof drive.getVod === 'function') {
    try {
      const vod = await withTimeout(
        drive.getVod(url),
        DRIVE_VOD_TIMEOUT_MS,
        `${drive.key || key || 'drive'} getVod`
      );
      if (
        validVod(vod) &&
        !((key === 'quark' || actualKey === 'quark') && String(vod.vod_play_url || '').includes('link://auto/'))
      ) {
        return { drive, vod };
      }
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 网盘详情解析失败 ${url}: ${e.message || e}`);
    }
    // facade 存在时不再回落到依赖驱动内部字段的旧实现。
    return null;
  }

  // 兼容旧版非 MV 宿主：只有没有正式 getVod facade 时才尝试历史 fallback。
  if (key === 'a115' || actualKey === 'a115') {
    try {
      const vod = await withTimeout(
        getA115FallbackVod(url),
        DRIVE_VOD_TIMEOUT_MS,
        'a115 fallback'
      );
      if (validVod(vod)) return { drive: drive || { key: 'a115' }, vod };
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] a115 fallback失败 ${url}: ${e.message || e}`);
    }
    return null;
  }

  // 夸克 fallback
  if (drive && (key === 'quark' || actualKey === 'quark') && typeof drive.readFolder === 'function') {
    try {
      const vod = await withTimeout(
        getQuarkFallbackVod(url, drive),
        DRIVE_VOD_TIMEOUT_MS,
        'quark fallback'
      );
      if (validVod(vod)) return { drive, vod };
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 夸克fallback详情失败 ${url}: ${e.message || e}`);
    }
  }
  return null;
}

function extractPanUrl(raw) {
  const s = String(raw || '').replace(/&amp;/g, '&').trim();
  const m = s.match(/https?:\/\/[^\s"'<>]+/i);
  return m ? normalizeShareUrl(m[0].replace(/[),.;]+$/, '')) : '';
}

function normalizeShareUrl(url) {
  let u = String(url || '').trim();
  if (!u) return '';
  // a115 驱动更认 115.com 域名
  u = u.replace(/^https?:\/\/(?:www\.)?115cdn\.com\//i, 'https://115.com/');
  u = u.replace(/^https?:\/\/(?:www\.)?anxia\.com\//i, 'https://115.com/');

  // 百度旧版分享页使用 /share/init?surl=...，驱动只识别 /s/1...。
  try {
    const parsed = new URL(u);
    if (
      parsed.hostname.toLowerCase() === 'pan.baidu.com'
      && parsed.pathname.replace(/\/+$/, '') === '/share/init'
    ) {
      let surl = String(parsed.searchParams.get('surl') || '').trim();
      const pwd = String(parsed.searchParams.get('pwd') || '').trim();
      if (surl) {
        if (!surl.startsWith('1')) surl = `1${surl}`;
        u = `https://pan.baidu.com/s/${surl}`;
        if (pwd) u += `?pwd=${encodeURIComponent(pwd)}`;
      }
    }
  } catch (_) {}

  return u;
}

function parse115Share(url) {
  const u = normalizeShareUrl(url);
  const m = String(u || '').match(/https?:\/\/(?:(?:www\.)?115\.com|(?:www\.)?115cdn\.com|(?:www\.)?anxia\.com)\/s\/([\w-]+)(?:\?([^#]*))?/i);
  if (!m) return null;
  const shareId = m[1];
  const qs = new URLSearchParams(m[2] || '');
  const pwd = qs.get('password') || qs.get('pwd') || qs.get('receive_code') || '';
  return { url: u, shareId, pwd };
}

function encodeA115PlayId(payload) {
  const json = JSON.stringify({
    shareId: String(payload.shareId || ''),
    pwd: String(payload.pwd || ''),
    fileId: String(payload.fileId || ''),
    sha: String(payload.sha || ''),
    subs: Array.isArray(payload.subs) ? payload.subs : [],
  });
  // 与内置 a115 驱动一致：b64url( hex(utf8(json)) )
  const hex = Buffer.from(json, 'utf8').toString('hex');
  return `b64://${Buffer.from(hex, 'utf8').toString('base64url')}`;
}

function isA115VideoItem(item) {
  const name = String(item?.fn || item?.n || item?.name || '');
  const ico = String(item?.ico || '').toLowerCase();
  const ext = (name.split('.').pop() || ico || '').toLowerCase();
  if (['mp4', 'mkv', 'ts', 'm2ts', 'avi', 'mov', 'wmv', 'flv', 'webm', 'rmvb', 'mpg', 'mpeg', 'm4v', 'iso'].includes(ext)) return true;
  if (Number(item?.isv) === 1) return true;
  if (item?.play_long) return true;
  return false;
}

function formatSize(n) {
  const v = Number(n || 0);
  if (!v) return '';
  if (v >= 1024 ** 3) return `${(v / 1024 ** 3).toFixed(2)}G`;
  if (v >= 1024 ** 2) return `${(v / 1024 ** 2).toFixed(2)}M`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)}K`;
  return `${v}B`;
}

async function loadA115Cookie() {
  if (store.a115Cookie && Date.now() - (store.a115CookieAt || 0) < 60_000) return store.a115Cookie;
  let cookie = '';
  let from = '';
  // 1) drive 对象上可能已有 cookie/account
  try {
    const drive = (store.drives || []).find((d) => String(d?.key || '').toLowerCase() === 'a115') || findDriveByUrl('https://115.com/s/x', 'a115');
    const rawCk = drive?.account?.cookie || drive?.cookie || drive?._cookie || drive?._account?.cookie || drive?.account || '';
    if (rawCk) {
      if (typeof rawCk === 'string') cookie = rawCk;
      else if (typeof rawCk === 'object') {
        if (rawCk.cookie) cookie = rawCk.cookie;
        else if (rawCk.CID || rawCk.UID || rawCk.SEID || rawCk.KID) {
          cookie = Object.entries(rawCk)
            .filter(([k, v]) => v != null && v !== '' && !['error', 'erro', 'msg'].includes(String(k)))
            .map(([k, v]) => `${k}=${v}`)
            .join('; ');
        } else {
          cookie = rawCk.value || '';
        }
      }
      if (cookie) from = 'drive';
    }
  } catch {}
  // 2) MV runtime cache facade：接口名仍是 server.redis，但后端实际映射到
  // PluginCache 进程内字典，不依赖外部 Redis 服务。缓存键由 MV 隔离处理。
  if (!cookie && store.redis) {
    const tryParse = (raw) => {
      if (raw === null || raw === undefined || raw === '') return '';
      if (Buffer.isBuffer(raw)) raw = raw.toString('utf8');
      if (typeof raw === 'object') return raw.cookie || raw.account?.cookie || '';
      const s = String(raw);
      try {
        const obj = JSON.parse(s);
        return obj?.cookie || obj?.account?.cookie || '';
      } catch {
        return /CID=|UID=|SEID=/.test(s) ? s : '';
      }
    };
    const keys = ['drive_a115', 'drive:a115', 'a115', 'vod:drive_a115'];
    for (const key of keys) {
      try {
        let raw;
        if (typeof store.redis.get === 'function') raw = await store.redis.get(key);
        if ((raw === null || raw === undefined || raw === '') && typeof store.redis.getAsync === 'function') {
          raw = await store.redis.getAsync(key);
        }
        const preview = raw == null ? String(raw) : (Buffer.isBuffer(raw) ? `buf:${raw.length}` : (typeof raw === 'object' ? `obj:${Object.keys(raw).slice(0,5)}` : `str:${String(raw).slice(0,40)}`));
        cookie = tryParse(raw);
        if (cookie) { from = `runtime-cache:${key}`; break; }
      } catch (e) {
        store.log?.warn?.(`[蜗牛4K] 读取 runtime cache ${key} 失败: ${e.message || e}`);
      }
    }
  }
  // 统一成纯 cookie 字符串
  if (cookie && typeof cookie === 'object') {
    cookie = cookie.cookie || cookie.value || cookie.account?.cookie || '';
  }
  cookie = String(cookie || '').trim();
  // 有些驱动存的是 JSON 字符串包一层
  if (cookie.startsWith('{') && cookie.includes('cookie')) {
    try {
      const obj = JSON.parse(cookie);
      cookie = String(obj?.cookie || obj?.account?.cookie || cookie).trim();
    } catch {}
  }
  store.a115Cookie = cookie;
  store.a115CookieAt = Date.now();
  if (!cookie) {
    store.log?.warn?.(
      `[蜗牛4K] a115 cookie empty from=${from || 'none'} runtimeCache=${!!store.redis}`,
    );
  }
  return cookie;
}

async function a115Request(pathname, params = {}) {
  // 内置驱动依赖的 bapi.115.com 已 NXDOMAIN；改走仍可用的 proapi android 接口
  const url = new URL(`https://proapi.115.com${pathname}`);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    url.searchParams.set(k, String(v));
  });
  const cookie = await loadA115Cookie();
  const headers = {
    'User-Agent': 'Mozilla/5.0 115disk/30.1.0',
    Accept: 'application/json, text/plain, */*',
    Referer: 'https://115.com/',
    Origin: 'https://115.com',
  };
  if (cookie) headers.Cookie = cookie;
  const r = await axios.get(url.toString(), {
    timeout: 20000,
    proxy: false, // 115 cookie 请求不走代理，避免风控
    headers,
    httpAgent: new http.Agent({ keepAlive: true }),
    httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false }),
    validateStatus: () => true,
  });
  const data = typeof r.data === 'string' ? (() => { try { return JSON.parse(r.data); } catch { return {}; } })() : (r.data || {});
  if (data && data.state === false) {
    const msg = data.error || data.msg || data.message || '';
    if (/登录|login|cookie|重新/i.test(String(msg))) {
      store.a115Cookie = '';
      store.a115CookieAt = 0;
    }
  }
  return data;
}

async function a115Snap(shareId, pwd = '', cid = '', offset = 0) {
  let data = await a115Request('/android/2.0/share/snap', {
    share_code: shareId,
    receive_code: pwd || '',
    offset,
    limit: 50,
    cid: cid || '',
  });
  // 缺访问码时，部分分享会回显 receive_code
  if (data && data.state === false && /访问码|密码|receive/i.test(String(data.error || data.msg || ''))) {
    const hint = data?.data?.shareinfo?.receive_code || data?.data?.receive_code || '';
    if (hint && hint !== pwd) {
      data = await a115Request('/android/2.0/share/snap', {
        share_code: shareId,
        receive_code: hint,
        offset,
        limit: 50,
        cid: cid || '',
      });
      if (data?.state) return { data, pwd: hint };
    }
  }
  return { data, pwd };
}

async function a115ListAll(shareId, pwd = '', cid = '', depth = 0, acc = []) {
  if (depth > 8) return acc;
  let offset = 0;
  let guard = 0;
  let usePwd = pwd;
  while (guard++ < 40) {
    const { data, pwd: newPwd } = await a115Snap(shareId, usePwd, cid, offset);
    if (newPwd) usePwd = newPwd;
    if (!data?.state) {
      throw new Error(data?.error || data?.msg || '115分享读取失败');
    }
    const list = data?.data?.list || [];
    const count = Number(data?.data?.count || list.length || 0);
    const folders = [];
    for (const item of list) {
      // proapi: fc='0' 目录, fc='1' 文件
      const isDir = String(item.fc) === '0' || (!item.sha1 && !item.ico && item.fn && !/\./.test(String(item.fn)));
      if (isDir) {
        const fid = String(item.fid || item.cid || '');
        if (fid) folders.push(fid);
        continue;
      }
      if (isA115VideoItem(item)) acc.push({ ...item, __pwd: usePwd });
    }
    offset += list.length;
    if (!list.length || offset >= count) {
      for (const fid of folders.filter(Boolean)) {
        await a115ListAll(shareId, usePwd, fid, depth + 1, acc);
      }
      break;
    }
  }
  return acc;
}

async function getA115FallbackVod(url) {
  const parsed = parse115Share(url);
  if (!parsed) return null;
  const ck = await loadA115Cookie();
  if (!ck) store.log?.warn?.(`[蜗牛4K] a115 fallback 无 cookie share=${parsed.shareId}`);
  const files = await a115ListAll(parsed.shareId, parsed.pwd, '', 0, []);
  if (!files.length) return null;
  const play = files
    .map((f) => {
      const name = f.fn || f.n || f.name || f.fid;
      const size = formatSize(f.fs || f.s || f.file_size);
      const title = size ? `[${size}] ${name}` : name;
      const id = encodeA115PlayId({
        shareId: parsed.shareId,
        pwd: f.__pwd || parsed.pwd || '',
        fileId: f.fid || f.file_id || '',
        sha: f.sha1 || f.sha || '',
        subs: [],
      });
      return `${title}$${id}`;
    })
    .join('#');
  return {
    vod_id: parsed.url,
    vod_name: files[0]?.fn || parsed.shareId,
    vod_pic: '',
    vod_content: parsed.url,
    type_name: '115',
    vod_play_from: 'a115',
    vod_play_url: play,
  };
}

function parsePanRows($) {
  const rows = [];
  const seen = new Set();

  const appendRow = (raw, title = '') => {
    const url = extractPanUrl(raw);
    if (!/^https?:\/\//i.test(url)) return;
    if (!/115|quark|aliyun|alipan|baidu|uc\.cn|123pan|189\.cn|xunlei|anxia/i.test(url)) return;
    if (seen.has(url)) return;
    seen.add(url);
    const pan = classifyPan(url);
    rows.push({ title: title || driveName(pan), url, pan });
  };

  // 2026 新版页面：每条网盘资源位于 .pan-link-item 中。
  $('.pan-link-item').each((_, el) => {
    const rowTitle =
      text($, el, '.pan-link-title') ||
      text($, el, '.pan-link-meta') ||
      text($, $(el).closest('.pan-group').get(0), '.pan-group-title') ||
      '';
    const candidates = [];
    $(el).find('[data-copy]').each((__, n) => candidates.push($(n).attr('data-copy')));
    $(el).find('[data-clipboard-text]').each((__, n) => candidates.push($(n).attr('data-clipboard-text')));
    $(el).find('a[href^="http"]').each((__, a) => candidates.push($(a).attr('href')));
    $(el).find('.pan-link-meta').each((__, n) => candidates.push($(n).text().trim()));
    for (const raw of candidates) appendRow(raw, rowTitle);
  });

  // 旧版 MacCMS 页面结构。
  $('.module-row-info').each((_, el) => {
    const rowTitle =
      text($, el, 'h4') ||
      text($, el, '.module-row-title h4') ||
      text($, el, '.module-row-title') ||
      '';
    const candidates = [];
    $(el).find('[data-clipboard-text]').each((__, n) => candidates.push($(n).attr('data-clipboard-text')));
    $(el).find('a[href^="http"]').each((__, a) => candidates.push($(a).attr('href')));
    $(el).find('i,p,span').each((__, p) => candidates.push($(p).text().trim()));

    for (const raw of candidates) {
      appendRow(raw, rowTitle);
    }
  });

  // 兜底：整页扫分享链接
  if (!rows.length) {
    const html = $.html() || '';
    const re =
      /https?:\/\/(?:115cdn\.com|115\.com|anxia\.com|pan\.quark\.cn|www\.aliyundrive\.com|www\.alipan\.com|pan\.baidu\.com|drive\.uc\.cn|cloud\.189\.cn|www\.123pan\.com|pan\.xunlei\.com)\/[^\s"'<>]+/gi;
    let m;
    while ((m = re.exec(html))) {
      const url = m[0].replace(/&amp;/g, '&').replace(/[),.;]+$/, '');
      appendRow(url);
    }
  }

  return rows;
}

function displayLineBase(key) {
  const base = String(key || '').trim().split('#')[0].toLowerCase();
  if (base === 'a115' || base === '115') return '115';
  return base || 'push';
}

function cleanPlayLabel(value, fallback = '资源') {
  const label = String(value || '')
    .replace(/[$#\r\n\t]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return label || fallback;
}

const FOLDER_PREFIX = 'wn4k_';
const ENTRY_MARKER_START = '\u2063';
const ENTRY_MARKER_END = '\u2064';
const ENTRY_MARKER_ZERO = '\u200b';
const ENTRY_MARKER_ONE = '\u200c';
// 目标安卓会在生成搜索词时清理 U+115F；该字符还会占用标题布局宽度，
// 使资源原始标题中真正有区分度的规格文字被推到可视区域之外。因此资源
// 展示必须直接返回网盘原始标题，不再尝试用隐藏字符绕过客户端的全局相似度过滤。
const SEARCH_FILTER_ANCHOR = '';
const DEFAULT_FOLDER_PIC = 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/folder.png';
const DRIVE_ICONS = {
  quark: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/quark.png',
  uc: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/uc.png',
  baidu: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/baidu.jpg',
  a189: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/189.png',
  a123: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/123.png',
  a115: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/115.jpg',
  115: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/115.jpg',
  ali: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/ali.jpg',
  xunlei: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/thunder.png',
  push: 'https://xget.xi-xu.me/gh/power721/alist-tvbox/raw/refs/heads/master/web-ui/public/quark.png',
};
const DRIVE_DISPLAY_ORDER = ['quark', 'uc', 'baidu', 'a189', 'a123', '115', 'xunlei', 'ali', 'push'];

function b64Encode(value) {
  return Buffer.from(typeof value === 'string' ? value : JSON.stringify(value), 'utf8').toString('base64url');
}

function b64Decode(value) {
  try {
    const raw = Buffer.from(String(value || ''), 'base64url').toString('utf8');
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  } catch {
    return null;
  }
}

function encodeFolder(data) {
  return `${FOLDER_PREFIX}${b64Encode(data)}`;
}

function decodeFolder(value) {
  const raw = String(value || '').trim();
  if (!raw.startsWith(FOLDER_PREFIX)) return null;
  return b64Decode(raw.slice(FOLDER_PREFIX.length));
}

function folderItem(id, name, pic = '', remarks = '') {
  return {
    vod_id: id,
    vod_name: name,
    vod_pic: pic || DEFAULT_FOLDER_PIC,
    vod_remarks: remarks || '',
    vod_tag: 'folder',
    type_id: 'pan_category',
    type_name: '网盘分类',
  };
}

function entryItem(id, name, pic = '', remarks = '') {
  return {
    vod_id: id,
    vod_name: name,
    vod_pic: pic || DEFAULT_FOLDER_PIC,
    vod_remarks: remarks || '',
    vod_tag: 'video',
  };
}

function encodeEntryMarker(vid) {
  const digits = String(vid || '').replace(/\D/g, '');
  if (!digits) return '';
  const bits = [...digits].map((digit) => (
    Number(digit).toString(2).padStart(4, '0')
      .replace(/0/g, ENTRY_MARKER_ZERO)
      .replace(/1/g, ENTRY_MARKER_ONE)
  )).join('');
  return `${ENTRY_MARKER_START}${bits}${ENTRY_MARKER_END}`;
}

function stripSearchFilterAnchor(value) {
  return String(value || '').split(SEARCH_FILTER_ANCHOR).join('');
}

function markCoverSearchName(title, vid) {
  return `${title}${SEARCH_FILTER_ANCHOR}${encodeEntryMarker(vid)}`;
}

function markResourceSearchTitle(resourceTitle, movieTitle) {
  return stripSearchFilterAnchor(resourceTitle);
}

function decodeEntryMarker(value) {
  const raw = String(value || '');
  const start = raw.indexOf(ENTRY_MARKER_START);
  if (start < 0) return null;
  const end = raw.indexOf(ENTRY_MARKER_END, start + ENTRY_MARKER_START.length);
  if (end < 0) return null;
  const encoded = raw.slice(start + ENTRY_MARKER_START.length, end);
  if (!encoded || encoded.length % 4 !== 0) return null;
  let vid = '';
  for (let offset = 0; offset < encoded.length; offset += 4) {
    const chunk = encoded.slice(offset, offset + 4);
    if ([...chunk].some((char) => char !== ENTRY_MARKER_ZERO && char !== ENTRY_MARKER_ONE)) {
      return null;
    }
    const digit = parseInt(
      [...chunk].map((char) => char === ENTRY_MARKER_ONE ? '1' : '0').join(''),
      2,
    );
    if (digit > 9) return null;
    vid += String(digit);
  }
  return {
    vid,
    title: stripSearchFilterAnchor(
      `${raw.slice(0, start)}${raw.slice(end + ENTRY_MARKER_END.length)}`,
    ).trim(),
  };
}

function iconForDrive(key) {
  const normalized = displayLineBase(key);
  return DRIVE_ICONS[normalized] || DRIVE_ICONS.push;
}

function firstDetailId(value = '') {
  return String(value || '').split(',').map((item) => item.trim()).filter(Boolean)[0] || '';
}

function wrapListAsEntries(list, { markCover = false } = {}) {
  return (Array.isArray(list) ? list : []).map((item) => {
    const vid = String(item?.vod_id || '').trim();
    if (!vid) return null;
    const entry = {
      vid,
      title: item?.vod_name || '',
      pic: item?.vod_pic || '',
      remarks: item?.vod_remarks || '',
    };
    return entryItem(
      encodeFolder({ kind: 'entry', entry }),
      markCover
        ? markCoverSearchName(entry.title || `蜗牛4K ${entry.vid}`, entry.vid)
        : (entry.title || `蜗牛4K ${entry.vid}`),
      entry.pic,
      entry.remarks,
    );
  }).filter(Boolean);
}

function groupPanRows(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = displayLineBase(row.pan);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return groups;
}

// 第一层只展示网盘资源分组；进入某个网盘后再展示该网盘下的具体资源标题。
// 这里和 buildPanTypeList() 都只读取站点详情页，不调用任何网盘 getVod/play。
function buildEntryTypesList(entry, ctx) {
  const list = [];
  const order = [
    ...DRIVE_DISPLAY_ORDER.filter((key) => (ctx.groups[key] || []).length),
    ...Object.keys(ctx.groups).filter((key) => !DRIVE_DISPLAY_ORDER.includes(key)),
  ];
  for (const key of order) {
    const rows = ctx.groups[key] || [];
    if (!rows.length) continue;
    list.push(folderItem(
      encodeFolder({ kind: 'panType', entry, drive: key }),
      driveName(key),
      iconForDrive(key),
      `${rows.length} 条资源`,
    ));
  }
  if (!list.length) {
    list.push(entryItem(
      encodeFolder({ kind: 'empty', entry }),
      '暂无网盘资源',
      entry.pic || ctx.pic || '',
      '当前页面未找到分享链接',
    ));
  }
  return list;
}

function buildEntryPlaybackVod(raw, ctx) {
  const playFrom = [];
  const playUrls = [];
  const order = [
    ...DRIVE_DISPLAY_ORDER.filter((key) => (ctx.groups[key] || []).length),
    ...Object.keys(ctx.groups).filter((key) => !DRIVE_DISPLAY_ORDER.includes(key)),
  ];
  for (const key of order) {
    const rows = ctx.groups[key] || [];
    if (!rows.length) continue;
    const episodes = rows.map((row, index) => {
      const title = cleanPlayLabel(
        row?.title || row?.groupTitle,
        `${driveName(key)}-${index + 1}`,
      );
      return `${title}$${encodeFolder({
        kind: 'panLink',
        entry: ctx.entry,
        drive: key,
        index,
      })}`;
    }).join('#');
    if (!episodes) continue;
    playFrom.push(driveName(key));
    playUrls.push(episodes);
  }
  return {
    vod_id: raw,
    vod_name: ctx.name,
    vod_pic: ctx.pic || ctx.entry?.pic || '',
    type_name: ctx.typeName || '',
    vod_year: ctx.year || '',
    vod_area: ctx.area || '',
    vod_remarks: ctx.remarks || '',
    vod_actor: ctx.actor || '',
    vod_director: ctx.director || '',
    vod_content: ctx.content || '',
    ...(playFrom.length ? {
      vod_play_from: playFrom.join('$$$'),
      vod_play_url: playUrls.join('$$$'),
    } : {}),
  };
}

function buildPanTypeList(folder, ctx) {
  const rows = ctx.groups[folder.drive] || [];
  const pic = ctx.pic || folder.entry?.pic || iconForDrive(folder.drive);
  if (!rows.length) {
    return [entryItem(
      encodeFolder({ kind: 'empty', entry: folder.entry, drive: folder.drive }),
      `${driveName(folder.drive)}暂无资源`,
      pic,
      '',
    )];
  }
  return rows.map((row, index) => {
    const title = cleanPlayLabel(
      row?.title || row?.groupTitle,
      `${driveName(folder.drive)}-${index + 1}`,
    );
    const remark = [
      row?.groupTitle && row.groupTitle !== title ? row.groupTitle : '',
      row?.pwd ? `码:${row.pwd}` : '',
    ].filter(Boolean).join(' / ');
    return folderItem(
      encodeFolder({ kind: 'panLink', entry: folder.entry, drive: folder.drive, index }),
      title,
      pic,
      remark,
    );
  });
}

function buildPanVodBase(link, ctx) {
  const url = normalizeShareUrl(link?.url || '');
  const pan = displayLineBase(link?.pan || classifyPan(url));
  return {
    vod_id: String(ctx?.entry?.vid || url),
    vod_name: ctx?.name || link?.title || `${driveName(pan)}资源`,
    vod_pic: ctx?.pic || ctx?.entry?.pic || '',
    type_name: ctx?.typeName || '',
    vod_year: ctx?.year || '',
    vod_area: ctx?.area || '',
    vod_remarks: ctx?.remarks || '',
    vod_actor: ctx?.actor || '',
    vod_director: ctx?.director || '',
    vod_content: ctx?.content || '',
  };
}

async function buildPanVod(link, ctx) {
  const url = normalizeShareUrl(link?.url || '');
  const pan = displayLineBase(link?.pan || classifyPan(url));
  const baseVod = buildPanVodBase(link, ctx);
  try {
    const parsed = await getPanVod(url, pan);
    if (parsed?.vod?.vod_play_url) {
      return {
        ...baseVod,
        ...parsed.vod,
        vod_id: baseVod.vod_id,
        vod_name: baseVod.vod_name,
        vod_pic: baseVod.vod_pic || parsed.vod.vod_pic || '',
        vod_content: baseVod.vod_content || parsed.vod.vod_content || '',
      };
    }
  } catch (error) {
    store.log?.warn?.(`[蜗牛4K] 单分享解析失败: ${error.message || error}`);
  }
  const epName = cleanPlayLabel(link?.title, `${driveName(pan)}资源`);
  return {
    ...baseVod,
    vod_play_from: pan,
    vod_play_url: `${epName}$${encodePlayId(url)}`,
  };
}

function resourceIdentity(folder = {}) {
  const drive = displayLineBase(folder.drive || 'push');
  const vid = String(folder.entry?.vid || '').trim();
  const index = Math.max(0, Number(folder.index || 0) || 0);
  return {
    drive,
    index,
    key: `${drive}:${vid}:${index}`,
  };
}

async function runSerializedResource(folder, task) {
  const identity = resourceIdentity(folder);
  const existing = store.resourceJobs.get(identity.key);
  if (existing) return await existing;

  const previous = store.resourceQueues.get(identity.drive) || Promise.resolve();
  const job = previous
    .catch(() => undefined)
    .then(task);

  store.resourceJobs.set(identity.key, job);
  store.resourceQueues.set(identity.drive, job);
  try {
    return await job;
  } finally {
    if (store.resourceJobs.get(identity.key) === job) {
      store.resourceJobs.delete(identity.key);
    }
    if (store.resourceQueues.get(identity.drive) === job) {
      store.resourceQueues.delete(identity.drive);
    }
  }
}

function resourceCacheKey(key) {
  return `${meta.key}:resource:${CryptoJS.MD5(String(key || '')).toString()}`;
}

async function getCachedResource(key) {
  const cached = store.resourceCache.get(key);
  if (cached) {
    if (Date.now() - Number(cached.createdAt || 0) < RESOURCE_CACHE_TTL_MS) {
      return cached.value || null;
    }
    store.resourceCache.delete(key);
  }
  if (!store.redis) return null;
  try {
    const raw = await store.redis.get(resourceCacheKey(key));
    if (!raw) return null;
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (parsed?.key !== key || !parsed?.value) return null;
    store.resourceCache.set(key, {
      createdAt: Number(parsed.createdAt || Date.now()),
      value: parsed.value,
    });
    return parsed.value;
  } catch (error) {
    store.log?.warn?.(`[蜗牛4K] 读取资源文件缓存失败: ${error.message || error}`);
    return null;
  }
}

async function cacheResource(key, value) {
  const createdAt = Date.now();
  store.resourceCache.set(key, { createdAt, value });
  if (store.resourceCache.size > 100) {
    const oldestKey = store.resourceCache.keys().next().value;
    if (oldestKey) store.resourceCache.delete(oldestKey);
  }
  if (!store.redis) return;
  try {
    await store.redis.set(
      resourceCacheKey(key),
      JSON.stringify({ key, createdAt, value }),
      'EX',
      Math.max(1, Math.floor(RESOURCE_CACHE_TTL_MS / 1000)),
    );
  } catch (error) {
    store.log?.warn?.(`[蜗牛4K] 写入资源文件缓存失败: ${error.message || error}`);
  }
}

async function loadPanResourceFiles(folder) {
  const identity = resourceIdentity(folder);
  const cached = await getCachedResource(identity.key);
  if (cached) return cached;

  return await runSerializedResource(folder, async () => {
    const queuedCache = await getCachedResource(identity.key);
    if (queuedCache) return queuedCache;

    const ctx = await loadEntryContext(folder.entry || {});
    const rows = ctx.groups[identity.drive] || [];
    const link = rows[identity.index] || null;
    if (!link) throw new Error('资源已失效');

    const url = normalizeShareUrl(link.url || '');
    const parsed = await getPanVod(url, identity.drive);
    if (!parsed?.vod || !validVod(parsed.vod)) {
      throw new Error('该资源解析失败或没有视频文件');
    }

    const files = splitVodPlayEntries(parsed.vod, identity.drive);
    if (!files.length) throw new Error('该资源没有视频文件');

    const value = {
      entry: ctx.entry,
      drive: identity.drive,
      resourceIndex: identity.index,
      resourceTitle: cleanPlayLabel(
        link.title || link.groupTitle,
        `${driveName(identity.drive)}-${identity.index + 1}`,
      ),
      pic: ctx.pic || folder.entry?.pic || iconForDrive(identity.drive),
      files,
    };
    await cacheResource(identity.key, value);
    return value;
  });
}

async function buildPanResourceVod(raw, folder) {
  const resource = await loadPanResourceFiles(folder);
  const episodes = resource.files.map((file) => {
    const fileName = cleanPlayLabel(file.name, '视频');
    const playId = encodeFolder({
      kind: 'playFile',
      drive: resource.drive,
      ref: String(file.ref || ''),
    });
    return `${fileName}$${playId}`;
  }).join('#');
  if (!episodes) throw new Error('该资源没有视频文件');

  return {
    vod_id: raw,
    vod_name: resource.resourceTitle,
    vod_pic: resource.pic || resource.entry?.pic || iconForDrive(resource.drive),
    vod_remarks: `${driveName(resource.drive)} · ${resource.files.length} 个视频`,
    vod_content: resource.resourceTitle,
    vod_play_from: driveName(resource.drive),
    vod_play_url: episodes,
  };
}

function playbackResultCandidates(result) {
  const ret = result && typeof result === 'object' ? result : {};
  const fallbackHeaders = ret.headers || ret.header || {};
  const fallback = {
    headers: fallbackHeaders,
    audio_url: ret.audio_url || ret.audioUrl || ret.extra?.audio || '',
    mode: ret.mode || '',
    transport: ret.transport || '',
    strategy: ret.strategy || '',
    strategy_label: ret.strategy_label || ret.strategyLabel || '',
    source_driver: ret.source_driver || ret.sourceDriver || '',
    playback_driver: ret.playback_driver || ret.playbackDriver || ret.driver || '',
    transfer_direction: ret.transfer_direction || ret.transferDirection || '',
    client_proxy_source: ret.client_proxy_source || ret.clientProxySource || '',
  };
  const candidates = [];
  const seen = new Set();
  const append = (item, index = 0) => {
    if (!item || typeof item !== 'object') return;
    const url = String(item.playback_url || item.url || '').trim();
    if (!url) return;
    const headers = item.headers || item.header || fallback.headers || {};
    const dedupeKey = `${url}\n${JSON.stringify(headers)}`;
    if (seen.has(dedupeKey)) return;
    seen.add(dedupeKey);
    candidates.push({
      name: cleanPlayLabel(item.name || item.quality, `线路${index + 1}`),
      url,
      headers,
      audio_url: item.audio_url || item.audioUrl || fallback.audio_url,
      mode: item.mode || fallback.mode,
      transport: item.transport || fallback.transport,
      strategy: item.strategy || fallback.strategy,
      strategy_label: item.strategy_label || item.strategyLabel || fallback.strategy_label,
      source_driver: item.source_driver || item.sourceDriver || fallback.source_driver,
      playback_driver: item.playback_driver || item.playbackDriver || item.driver || fallback.playback_driver,
      transfer_direction: item.transfer_direction || item.transferDirection || fallback.transfer_direction,
      client_proxy_source: item.client_proxy_source || item.clientProxySource || fallback.client_proxy_source,
    });
  };

  const structured = Array.isArray(ret.options)
    ? ret.options
    : (Array.isArray(ret.urls) ? ret.urls : []);
  structured.forEach((item, index) => append(item, index));

  if (Array.isArray(ret.url)) {
    for (let index = 0; index + 1 < ret.url.length; index += 2) {
      append({ name: ret.url[index], url: ret.url[index + 1] }, index / 2);
    }
  } else {
    append({
      name: ret.name || '默认',
      url: ret.playback_url || ret.default_url || ret.url,
    });
  }
  return candidates;
}

async function buildPanResourcePlayback(folder, req) {
  const resource = await loadPanResourceFiles(folder);
  const options = [];
  let parse = 0;
  let jx = 0;

  // 只处理用户已经选中的一个资源；资源内文件也必须顺序解析，禁止并发。
  for (const file of resource.files) {
    try {
      const result = await play({
        flag: resource.drive,
        id: file.ref,
        req,
        skipPanLink: true,
      });
      parse = parse || (result?.parse ? 1 : 0);
      jx = jx || (result?.jx ? 1 : 0);
      const routes = playbackResultCandidates(result);
      for (const route of routes) {
        options.push({
          ...route,
          name: routes.length > 1
            ? `${cleanPlayLabel(file.name, '视频')} · ${route.name}`
            : cleanPlayLabel(file.name, '视频'),
        });
      }
    } catch (error) {
      store.log?.warn?.(
        `[蜗牛4K] 解析已选资源中的文件失败 ${file.name}: ${error.message || error}`,
      );
    }
  }
  if (!options.length) throw new Error('该资源没有可播放的视频文件');

  return {
    parse,
    jx,
    url: options.flatMap((item) => [item.name, item.url]),
    urls: options,
    header: options[0].headers || {},
  };
}

async function buildPanFileList(folder) {
  const resource = await loadPanResourceFiles(folder);
  return resource.files.map((file, fileIndex) => entryItem(
    encodeFolder({
      kind: 'panFile',
      entry: resource.entry,
      drive: resource.drive,
      resourceIndex: resource.resourceIndex,
      resourceTitle: resource.resourceTitle,
      fileIndex,
      fileName: file.name,
      ref: file.ref,
      pic: resource.pic,
    }),
    file.name,
    resource.pic,
    resource.resourceTitle,
  ));
}

function buildPanFileVod(raw, folder) {
  const fileName = cleanPlayLabel(folder.fileName, '视频');
  const resourceTitle = cleanPlayLabel(
    folder.resourceTitle,
    folder.entry?.title || `${driveName(folder.drive)}资源`,
  );
  const playId = encodeFolder({
    kind: 'playFile',
    drive: displayLineBase(folder.drive),
    ref: String(folder.ref || ''),
  });
  return {
    vod_id: raw,
    vod_name: resourceTitle,
    vod_pic: folder.pic || folder.entry?.pic || iconForDrive(folder.drive),
    vod_remarks: fileName,
    vod_content: `${resourceTitle}\n${fileName}`,
    vod_play_from: driveName(folder.drive),
    vod_play_url: `${fileName}$${playId}`,
  };
}

async function loadEntryContext(entry = {}) {
  const vid = String(entry?.vid || '').trim();
  if (!vid) throw new Error('missing entry vid');
  const html = await fetchHtml(`${HOST}/voddetail/${vid}/`);
  const $ = cheerio.load(html);
  const rawName =
    text($, null, '.premium-title') ||
    text($, null, '.mobile-detail-title') ||
    $('h1').first().text().replace(/\s+/g, ' ').trim() ||
    text($, null, '.video-info-header h1') ||
    text($, null, '.module-info-heading h1') ||
    entry?.title ||
    `蜗牛4K ${vid}`;
  const name = /^蜗牛4K\s+\d+$/i.test(rawName) ? (entry?.title || `蜗牛4K ${vid}`) : rawName;
  const pic = absUrl(
    $('.premium-poster img,.module-item-pic img,.module-info-poster img,.video-cover img,img.lazyload,img.lazy')
      .first()
      .attr('data-src') ||
      $('.premium-poster img,.module-item-pic img,.module-info-poster img,.video-cover img,img.lazyload,img.lazy')
        .first()
        .attr('data-original') ||
      $('.premium-poster img,.module-item-pic img,.module-info-poster img,.video-cover img,img.lazyload,img.lazy').first().attr('src') ||
      entry?.pic ||
      ''
  );
  const infoText = text($, null, '.detail-info-premium') || text($, null, '.video-info,.module-info-main,.module-info');
  const content = cleanContent(
    $('.detail-desc-text,.vod_content,.module-info-introduction,.video-info-content,.module-info-main .module-info-item-content')
      .last()
      .text() || infoText
  );
  const tags = $('.premium-tags-top .p-tag')
    .map((_, el) => $(el).text().replace(/\s+/g, ' ').trim())
    .get()
    .filter(Boolean);
  const metaValues = {};
  $('.premium-meta-grid .meta-item').each((_, el) => {
    const label = text($, el, '.m-label');
    const value = text($, el, '.m-val');
    if (label && value) metaValues[label] = value;
  });
  const tagYear = tags.find((value) => /^(?:19|20)\d{2}$/.test(value)) || '';
  const tagArea =
    tags.find((value) => /^(?:[A-Z]{2})(?:,[A-Z]{2})*$/.test(value)) ||
    tags.find((value) => /^(大陆|香港|台湾|美国|日本|韩国|英国|法国|泰国|印度|中国)$/.test(value)) ||
    '';
  const rows = parsePanRows($);
  const groupMap = groupPanRows(rows);
  const groups = Object.fromEntries(groupMap.entries());
  const ctx = {
    entry: {
      vid,
      title: name,
      pic,
      remarks: metaValues['备注'] || entry?.remarks || '',
    },
    name,
    pic,
    content,
    typeName: CLASSES.find((item) => tags.includes(item.type_name) || infoText.includes(item.type_name))?.type_name || '',
    year: tagYear || (infoText.match(/(?:年代|年份)[:：]?\s*(\d{4})/) || infoText.match(/\b(19|20)\d{2}\b/) || [])[0]?.replace(/\D/g, '') || '',
    area: tagArea || (infoText.match(/(大陆|香港|台湾|美国|日本|韩国|英国|法国|泰国|印度|中国)/) || [])[1] || '',
    remarks: metaValues['备注'] || (infoText.match(/备注[:：]?\s*([^\s]+)/) || [])[1] || '',
    actor: metaValues['主演'] || '',
    director: metaValues['导演'] || '',
    rows,
    groups,
  };
  return ctx;
}

async function detail({ id }) {
  const raw = firstDetailId(id);
  if (/^https?:\/\//i.test(raw)) {
    const pan = classifyPan(raw);
    return { list: [await buildPanVod({ url: raw, pan, title: `${driveName(pan)}推送` }, null)] };
  }

  const folder = decodeFolder(raw);
  if (folder?.kind === 'panLink') {
    return { list: [await buildPanResourceVod(raw, folder)] };
  }

  if (folder?.kind === 'panFile') {
    if (!String(folder.ref || '').trim()) {
      return { list: [entryItem('noop', folder.fileName || '视频已失效', folder.pic || '', '缺少文件引用')] };
    }
    return { list: [buildPanFileVod(raw, folder)] };
  }

  if (folder?.kind === 'panType') {
    const ctx = await loadEntryContext(folder.entry || {});
    return { list: buildPanTypeList(folder, ctx) };
  }

  if (folder?.kind === 'entry') {
    const ctx = await loadEntryContext(folder.entry || {});
    return { list: [buildEntryPlaybackVod(raw, ctx)] };
  }

  if (folder?.kind === 'empty') {
    return { list: [entryItem('noop', '暂无可用资源', folder.entry?.pic || DEFAULT_FOLDER_PIC, '当前项目暂无分享链接')] };
  }

  const ctx = await loadEntryContext({ vid: raw });
  return { list: [buildEntryPlaybackVod(raw, ctx)] };
}

async function search({ wd, page }) {
  const pg = Math.max(1, parseInt(page || '1', 10) || 1);
  if (!wd) return { list: [], page: pg, pagecount: 1, total: 0 };
  if (/^https?:\/\//i.test(String(wd || ''))) {
    const pan = classifyPan(wd);
    return {
      list: [{ vod_id: String(wd), vod_name: `${driveName(pan)}推送`, vod_pic: '', vod_remarks: '网盘推送' }],
      page: pg,
      pagecount: 1,
      total: 1,
    };
  }
  const html = await fetchHtml(searchUrl(wd, pg));
  const list = parseList(html);
  const entries = wrapListAsEntries(list);
  return {
    list: entries,
    page: pg,
    pagecount: parsePageCount(html, pg),
    total: entries.length,
  };
}

function buildIndexedResourceSearchList(entry, ctx) {
  const list = [];
  const order = [
    ...DRIVE_DISPLAY_ORDER.filter((key) => (ctx.groups[key] || []).length),
    ...Object.keys(ctx.groups).filter((key) => !DRIVE_DISPLAY_ORDER.includes(key)),
  ];
  for (const key of order) {
    const rows = ctx.groups[key] || [];
    rows.forEach((row, index) => {
      const title = cleanPlayLabel(
        row?.title || row?.groupTitle,
        `${driveName(key)}-${index + 1}`,
      );
      const remark = [
        row?.groupTitle && row.groupTitle !== title ? row.groupTitle : '',
        row?.pwd ? `码:${row.pwd}` : '',
      ].filter(Boolean).join(' / ');
      list.push({
        vod_id: encodeFolder({ kind: 'panLink', entry, drive: key, index }),
        vod_name: `${driveName(key)} · ${markResourceSearchTitle(title, entry?.title || ctx.name)}`,
        vod_pic: ctx.pic || entry?.pic || ctx.entry?.pic || DEFAULT_FOLDER_PIC,
        vod_remarks: remark,
        vod_tag: 'video',
      });
    });
  }
  return list;
}

async function directorySearch({ wd, page }) {
  const marker = decodeEntryMarker(wd);
  if (marker?.vid) {
    const entry = { vid: marker.vid, title: marker.title, pic: '', remarks: '' };
    const ctx = await loadEntryContext(entry);
    return singlePageResult({
      list: buildIndexedResourceSearchList(ctx.entry || entry, ctx),
    }, 1);
  }

  // 手动搜索目录来源时仍返回影片 Folder；进入该 Folder 后才读取网盘分组。
  const ret = await search({ wd, page });
  return {
    ...ret,
    list: (ret.list || []).map((item) => ({ ...item, vod_tag: 'folder' })),
  };
}

async function directoryCategory({ id, page }) {
  const pg = Math.max(1, parseInt(page || '1', 10) || 1);
  if (pg > 1) return { list: [], page: pg, pagecount: 1, total: 0 };
  const raw = firstDetailId(id);
  const folder = decodeFolder(raw);

  if (folder?.kind === 'entry') {
    const ctx = await loadEntryContext(folder.entry || {});
    return singlePageResult({ list: buildEntryTypesList(ctx.entry, ctx) }, 1);
  }
  if (folder?.kind === 'panType') {
    const ctx = await loadEntryContext(folder.entry || {});
    return singlePageResult({ list: buildPanTypeList(folder, ctx) }, 1);
  }
  if (folder?.kind === 'panLink') {
    return singlePageResult({ list: await buildPanFileList(folder) }, 1);
  }
  if (folder?.kind === 'empty') {
    return singlePageResult({
      list: [entryItem('noop', '暂无可用资源', folder.entry?.pic || DEFAULT_FOLDER_PIC, '')],
    }, 1);
  }

  if (raw) {
    const ctx = await loadEntryContext({ vid: raw });
    return singlePageResult({ list: buildEntryTypesList(ctx.entry, ctx) }, 1);
  }
  return singlePageResult({ list: [] }, 1);
}

function splitVodPlayEntries(vod, preferredLine = '') {
  const lines = String(vod?.vod_play_url || '').split('$$$');
  const flags = String(vod?.vod_play_from || '').split('$$$');
  let lineIndex = flags.findIndex((value) => (
    String(value || '').trim().toLowerCase() === String(preferredLine || '').trim().toLowerCase()
  ));
  if (lineIndex < 0) lineIndex = 0;
  return String(lines[lineIndex] || '')
    .split('#')
    .map((entry) => {
      const separator = entry.indexOf('$');
      if (separator < 0) return null;
      const name = cleanPlayLabel(entry.slice(0, separator), '视频');
      const ref = entry.slice(separator + 1).trim();
      return ref ? { name, ref } : null;
    })
    .filter(Boolean);
}

async function play({ flag, id, req, skipPanLink = false }) {
  const decoded = decodePlayId(id);
  const selection = decodeFolder(decoded);
  if (selection?.kind === 'playFile') {
    if (!String(selection.ref || '').trim()) throw new Error('缺少视频文件引用');
    return await play({
      flag: selection.drive || flag,
      id: selection.ref,
      req,
      skipPanLink: true,
    });
  }
  if (!skipPanLink && selection?.kind === 'panLink') {
    throw new Error('资源标题必须先进入详情，禁止在 play 阶段批量解析资源文件');
  }
  let raw = normalizeShareUrl(decoded);
  raw = normalizeShareUrl(raw);
  const baseFlag = String(flag || '').split('#')[0];
  const quarkPayload = quarkDecodePayload(id);
  if (quarkPayload?.quarkFallback) {
    const drive = findDriveByUrl(quarkPayload.raw || '', 'quark');
    try {
      const ret = await playQuarkFallback(quarkPayload, drive, req);
      if (ret) return ret;
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 夸克fallback播放失败: ${e.message || e}`);
    }
  }

  if (raw.startsWith('link://')) {
    const match = raw.match(/^link:\/\/([^/]+)\/(.+)$/);
    if (match) {
      const driveKey = match[1];
      const url = decodeURIComponent(match[2]);
      const drive = findDriveByUrl(url, driveKey === 'auto' ? classifyPan(url) : driveKey);
      if (drive && typeof drive.play === 'function') {
        try {
          return await drive.play(url, drive.key || flag || driveKey);
        } catch (e) {
          store.log?.warn?.(`[蜗牛4K] link播放失败: ${e.message || e}`);
        }
      }
      return { parse: 0, jx: 0, url };
    }
  }

  const driveKey = classifyPan(raw);
  const drive = findDriveByUrl(raw, baseFlag || driveKey);
  if (drive && typeof drive.play === 'function') {
    try {
      const ret = await drive.play(raw, drive.key || flag || driveKey);
      if (ret) return ret;
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 网盘播放失败: ${e.message || e}`);
    }
  }
  return { parse: 0, jx: 0, url: raw };
}

function cached(fn, ttl = 60) {
  return async (...args) => {
    if (!store.redis || ttl <= 0) return await fn(...args);
    const key = `${meta.key}:${CACHE_VERSION}:${fn.name}:${CryptoJS.MD5(JSON.stringify(args)).toString()}`;
    let old = null;
    try {
      old = await store.redis.get(key);
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 读取缓存失败，继续实时请求: ${e.message || e}`);
    }
    if (old) {
      try {
        const parsed = JSON.parse(old);
        const first = parsed?.list?.[0];
        if (['home', 'category', 'search'].includes(fn.name) && Array.isArray(parsed?.list) && (
          parsed.list.length === 0 ||
          (parsed.list.length > 0 && Number(parsed.total) === 0)
        )) {
          // skip empty or stale non-empty/zero-total list cache
        } else if (!(fn.name === 'detail' && first?.vod_name && /^蜗牛4K\s+\d+$/i.test(first.vod_name))) {
          return parsed;
        }
      } catch {}
    }
    const ret = await fn(...args);
    try {
      await store.redis.set(key, JSON.stringify(ret), 'EX', ttl);
    } catch (e) {
      store.log?.warn?.(`[蜗牛4K] 写入缓存失败，忽略缓存故障: ${e.message || e}`);
    }
    return ret;
  };
}

const cachedHome = cached(home, 300);
const cachedCategory = cached(category, 300);
const cachedDetail = cached(detail, 0);
const cachedSearch = cached(search, 120);

function singlePageResult(ret, page = 1) {
  const list = Array.isArray(ret?.list) ? ret.list : [];
  return {
    ...ret,
    list,
    page,
    pagecount: 1,
    total: list.length,
  };
}

async function handle(req, reply = null) {
  const { ac, t, pg, ids, play: playId, wd, flag, proxy, id } = req.query;
  if (proxy === 'quark') return await proxyQuarkDownload(req, reply);

  if (playId) return await play({ flag: flag || '', id: playId, req });
  if (wd || ac === 'search') return await cachedSearch({ wd: wd || t || '', page: pg || 1 });

  // WebHTV HomeActivity 点击自动回填的首页封面时固定发送 ids=<entry>。
  // 详情直接用原生线路/选集展示“网盘/资源标题”；只有选中资源标题并
  // 发出 play 请求后，才解析该一个资源。
  const rawId = firstDetailId(ids || id || t || '');
  if (rawId.startsWith(FOLDER_PREFIX)) {
    const page = Math.max(1, parseInt(pg || '1', 10) || 1);
    if (page > 1) return { list: [], page, pagecount: 1, total: 0 };
    const folder = decodeFolder(rawId);
    const detailById = Boolean(ids || (id && ac === 'detail' && t === undefined));
    if (detailById && folder?.kind === 'entry') {
      const ctx = await loadEntryContext(folder.entry || {});
      return singlePageResult({ list: [buildEntryPlaybackVod(rawId, ctx)] }, 1);
    }
    return singlePageResult(await cachedDetail({ id: rawId }), 1);
  }

  // 有 ids 才是详情；部分壳会用 ac=detail&t=分类ID 拉分类
  if (ids || (id && ac === 'detail' && t === undefined)) {
    return await cachedDetail({ id: String(ids || id).split(',').filter(Boolean) });
  }

  if ((ac === 'detail' || ac === 'videolist') && t !== undefined) {
    return await cachedCategory({ id: t, page: pg || 1 });
  }
  if (t !== undefined && t !== '') return await cachedCategory({ id: t, page: pg || 1 });
  if (ac === 'class') return { class: CLASSES };
  if (!ac || ac === 'list' || ac === 'home' || ac === 'videolist') return await cachedHome();

  return { list: [], page: 1, pagecount: 1, total: 0 };
}

async function handleDirectory(req, reply = null) {
  const { ac, t, pg, ids, play: playId, wd, flag, proxy, id } = req.query;
  if (proxy === 'quark') return await proxyQuarkDownload(req, reply);
  if (playId) return await play({ flag: flag || '', id: playId, req });
  if (wd || ac === 'search') {
    return await directorySearch({ wd: wd || t || '', page: pg || 1 });
  }

  if (ids || (id && ac === 'detail' && t === undefined)) {
    return await cachedDetail({ id: String(ids || id).split(',').filter(Boolean) });
  }
  if ((ac === 'detail' || ac === 'videolist') && t !== undefined) {
    return await directoryCategory({ id: t, page: pg || 1 });
  }
  if (t !== undefined && t !== '') return await directoryCategory({ id: t, page: pg || 1 });
  if (ac === 'class') return { class: [] };
  return { list: [], page: 1, pagecount: 1, total: 0 };
}

async function init(server) {
  if (store.init) return;
  store.log = server.log || console;
  store.redis = server.redis;
  store.drives = server.drives || [];
  const qd = store.drives.find((d) => String(d?.key || '').toLowerCase() === 'quark');
  store.quarkHeaders = qd?._headers || {};
  store.quarkCookie = qd?._cookie || '';
  store.init = true;

  // 站点 Cookie 状态提示
  if (COOKIE) {
    store.log?.info?.(`[蜗牛4K] Cookie 已加载 (${COOKIE.length} chars)，登录态请求已启用`);
  } else {
    store.log?.warn?.('[蜗牛4K] 未配置 Cookie，部分需要登录的资源可能无法访问');
  }

  try {
    const ck = await loadA115Cookie();
    store.log?.info?.(
      `[蜗牛4K] init ${HOST}, proxy=${PROXY_URL ? 'on' : 'off'}, drives=${store.drives.map((d) => d.key).join(',')}, a115Cookie=${ck ? 'yes' : 'no'}`
    );
  } catch (e) {
    store.log?.info?.(
      `[蜗牛4K] init ${HOST}, proxy=${PROXY_URL ? 'on' : 'off'}, drives=${store.drives.map((d) => d.key).join(',')}, a115Cookie=err:${e.message || e}`
    );
  }
}

module.exports = async (app, opt) => {
  const register = (site, handler) => {
    app.head(site.api, async (req, reply) => {
      if (!store.init) await init(req.server);
      try {
        if (req.query?.proxy === 'quark') return await proxyQuarkDownload(req, reply);
        return '';
      } catch (e) {
        req.server.log.error(e);
        if (reply?.code) reply.code(502);
        return '';
      }
    });
    app.get(site.api, async (req, reply) => {
      if (!store.init) await init(req.server);
      try {
        return await handler(req, reply);
      } catch (e) {
        req.server.log.error(e);
        return { list: [], page: 1, pagecount: 1, total: 0, msg: e.message };
      }
    });
  };

  register(meta, handle);
  register(directoryMeta, handleDirectory);
  opt.sites.push(meta, directoryMeta);
};
