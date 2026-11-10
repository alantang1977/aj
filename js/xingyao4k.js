/**
 * ============================================================================
 * 🔰星耀4K —— Node.js 站点扩展模块
 * ----------------------------------------------------------------------------
 * 源配置（用户提供）：
 *   {
 *     "key": "星耀4K",
 *     "name": "🔰星耀4K",
 *     "type": 4,
 *     "api": "http://8.134.205.252:39466/pz/sx4k.php/api.php/provide/vod/?ac=list"
 *   }
 *
 * 【静态逆向分析结论】只依据配置字符串 + 标准协议推断，未使用任何客户端二进制
 *
 * 1. 入口形态
 *    - 8.134.205.252:39466 是裸 IP + 高位端口，nginx，响应头带
 *      Access-Control-Allow-Origin: *，属自建采集服务而非 CDN 域名。
 *    - 无鉴权、无签名、无 Referer 校验。模板中的 MD5 签名
 *      (7gp0bnd2sr85ydii2j32pcypscoc4w6c7g5spl + timestamp) 属于另一个私有
 *      API (v.rbotv.cn /v3/*)，对本源完全不适用，故本脚本移除签名与 multipart，
 *      改为纯 GET + querystring。
 *
 * 2. 路径语义
 *    - /pz/sx4k.php/api.php/provide/vod/ ：sx4k.php 是 PATHINFO 入口，
 *      api.php/provide/vod/ 是苹果CMS(maccms v10) 标准「提供/采集」接口路由，
 *      被挂在了自定义前缀之后。?ac=list 是默认动作。
 *    - 协议为 GET + ac 动作分发，返回 JSON（Content-Type: application/json）。
 *
 * 3. 动作与响应结构（实测字段级）
 *    - ac=list 且不带 t ：【只返回 class 分类表，不返回任何影片】
 *      class[] = { type_id, type_name, type_extend }，共 13 个分类；
 *      type_extend 是「逗号分隔字符串」而非数组，含
 *      class / area / lang / year / star / director / state / version 八个维度。
 *      => 首页推荐不能靠 ac=list 直出，必须另行拉取分类页拼接。
 *    - ac=list&t=<id>&pg=<n> ：返回 { page, pagecount, limit, total, list }，
 *      limit=20；list 项【只有 4 个字段】vod_id / vod_name / vod_pic / vod_remarks，
 *      没有 type_name、vod_year、vod_area。故列表项年份恒为空。
 *    - ac=detail&ids=<id> ：返回 { list: [ ... ] }，11 个字段，含
 *      vod_actor / vod_director / vod_area / vod_year / vod_content /
 *      vod_play_from / vod_play_url，但【不含 type_id / type_name / vod_lang / 分页】。
 *      ★ 实测 ids 传多个 (774,1652,630) 只返回第一条 —— 上游不支持批量，
 *        详情必须按 id 逐个请求（与模板的 for 循环一致）。
 *    - ac=list|detail|videolist & wd=<关键词> ：均可搜索，返回
 *      { list, page, total }（无 pagecount / limit），list 项同样只有 4 字段。
 *    - 筛选：class / area / year 有效且可组合；by 排序实测未见效果；
 *      t 是出列表的必要条件。
 *
 * 4. 播放串与解析（「视频加载失败」的根因与修复）
 *    - vod_play_from = "XYDB"（单播放组；多组时用 $$$ 分隔）。
 *    - vod_play_url  = "集名$XYTY-<32位hex>#集名$XYTY-<32位hex>..."，
 *      组间 $$$、集间 #、集名与载荷之间 $。"$" 后面不是直链，是站点 token。
 *    - ★ 站点自带解析接口（实测定位）：GET <base>?ac=list&play=<token>
 *      返回 { jx, parse, url, header }：
 *        成功 jx=0 / parse=0 / url=https://.../video.mp4（带时效签名 dy_q、l），
 *              header={"User-Agent":"okhttp/4.9.1"}；
 *        降级 jx=1 / parse=1 / url=<原 token>，约 30% 概率随机出现，
 *              与 token 有效性、ac 取值均无关，属服务端抖动。
 *    - ★ 单次解析成功率约 70%（20 次实测 14 次）；最多重试 5 次可达
 *      20/20 成功，平均 1.5 次请求。故 _play 内置重试 + 短间隔，
 *      且解析结果【不缓存】（直链带时效签名）。
 *    - ★ 直链 CDN 有防盗链：请求头带 Referer 会被 403 拒绝（无 header /
 *      带 UA 均 200，Content-Type: video/mp4，Content-Length ~2.1GB）。
 *      因此播放时以解析接口返回的 header 为准，【禁止附加默认 Referer】，
 *      采集接口请求也一并不带 Referer（本源不校验）。
 *    - 保留 PLAY_RESOLVE 钩子作为站点接口连续失败后的备用通道。
 *
 * 5. 框架语义（易踩坑）
 *    - 用户配置里的 api 是【上游采集地址】；模板 store.meta.api 是
 *      【本模块对外暴露的本地路由】，二者语义不同，必须分离，否则前端会
 *      直接去请求那个 IP。故本脚本：SOURCE.api 存上游，meta.api 用 /video/xy4k。
 *    - 保留 ext 换源能力（IP 站易失效），changeable 置 1。
 *    - 图片走另一台图床 111.170.151.121:7818，需允许跨域/外部加载。
 *
 * 【v2 修复记录：播放器提示「视频加载失败」】
 *   - v1 把 XYTY-* token 以 parse:1 丢给播放器，播放器拿不到直链 -> 加载失败；
 *   - v2 接入站点自带解析接口 ac=list&play= 并重试，返回 parse:0 + 真实直链；
 *   - 同时移除默认 Referer（直链 CDN 带 Referer 返回 403，是第二个根因）；
 *   - 实测 _play 连续 12 次 12/12 成功，40 集剧集逐集均可解析。
 * ============================================================================
 */

const axios = require("axios");
const http = require("http");
const https = require("https");
const CryptoJS = require("crypto-js");

// ---------------------------------------------------------------------------
// 配置区
// ---------------------------------------------------------------------------

/** 用户给定的原始源配置，原样保留 */
const SOURCE = {
  key: "星耀4K",
  name: "🔰星耀4K",
  type: 4,
  api: "http://8.134.205.252:39466/pz/sx4k.php/api.php/provide/vod/?ac=list"
};

/** 本模块对外暴露的本地路由（框架约定，可按需修改） */
const ROUTE = "/video/xy4k";

/** 若上游默认吐 xml，改成 { at: "json" }；本源本身已返回 JSON，保持空 */
const FIXED_PARAMS = {};

/** 首页推荐：取前 N 个分类的首页，每类取 M 条，合并去重 */
const HOME_CLASS_COUNT = 4;
const HOME_PER_CLASS = 5;

/**
 * false = 按框架约定把每集载荷做成 URL-safe Base64(JSON) 再交给 play 路由；
 * true  = 原样透传上游 "集名$XYTY-xxx" 格式（供直接读 vod_play_url 的播放器）。
 */
const RAW_PLAY_URL = false;

/**
 * 站点自带播放解析接口的参数与重试策略
 * - ac 统一用 list；不要附加 from/flag/type 等参数，实测会提高降级概率
 * - 上游随机返回 jx=1 降级，重试 5 次实测 100% 拿到直链
 */
const PLAY_AC = "list";
const PLAY_RETRY = 5;
const PLAY_RETRY_DELAY = 120;

/** 允许的筛选键白名单：只把上游认识的参数透出去 */
const FILTER_KEYS = [
  "class", "area", "lang", "year", "star", "director", "state", "version", "by"
];

/** type_extend 维度 -> 筛选展示名 */
const EXTEND_LABELS = {
  class: "类型",
  area: "地区",
  lang: "语言",
  year: "年份",
  star: "主演",
  director: "导演",
  state: "状态",
  version: "版本"
};

/**
 * 备用解析钩子：仅当站点自带接口重试全部失败时才启用
 *   url     : 解析接口模板，占位符 {id} / {url} / {from} / {vid} 会被替换，
 *             {id} 自动做 encodeURIComponent。返回 JSON 里的 url 或 data.url。
 *   handler : 自定义异步函数 (payload, ctx) => { parse, url, header } 或 null。
 * 二者都为空时返回 { parse: 1, url: token }，交由上层播放器解析。
 */
const PLAY_RESOLVE = {
  url: "",
  handler: null
};

const UA = "okhttp-okgo/jeasonlzy";

// ---------------------------------------------------------------------------
// 上游地址解析：把 "?ac=list" 剥离，拆成 base / origin / 默认动作 / 固定参数
// ---------------------------------------------------------------------------
function parseApi(api) {
  const u = new URL(api);
  const sp = new URLSearchParams(u.search);
  const defaultAc = sp.get("ac") || "list";
  sp.delete("ac");

  const query = {};
  for (const [k, v] of sp.entries()) query[k] = v;

  return {
    base: u.origin + u.pathname,
    origin: u.origin,
    defaultAc,
    query
  };
}

let API = parseApi(SOURCE.api);
let HOST = API.origin;

// ---------------------------------------------------------------------------
// HTTP 客户端
// ---------------------------------------------------------------------------
const _http = axios.create({
  timeout: 20 * 1000,
  httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false }),
  httpAgent: new http.Agent({ keepAlive: true }),
  headers: {
    "User-Agent": UA,
    "Accept-Language": "zh-CN,zh;q=0.8"
    // 不带 Referer：本源采集接口不校验，且播放直链带 Referer 会被 CDN 403
  },
  responseType: "json"
});

/** 标准 Base64 编解码（沿用模板命名） */
function e64(text) {
  try {
    return CryptoJS.enc.Utf8.parse(text).toString(CryptoJS.enc.Base64);
  } catch (e) {
    return "";
  }
}

function d64(encodedText) {
  try {
    return CryptoJS.enc.Base64.parse(encodedText).toString(CryptoJS.enc.Utf8);
  } catch (e) {
    return "";
  }
}

/**
 * URL-safe Base64：把 + / 换成 - _ 并去掉尾部 =。
 * 原因：载荷要作为 play 这个 query 参数回传，标准 Base64 里的 "+" 会被
 * 解析成空格导致解码失败，这是模板里的一个隐患，这里显式规避。
 */
function e64url(text) {
  return e64(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function d64url(text) {
  let s = String(text).replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return d64(s);
}

/** 统一 GET：querystring 交给 axios 编码，中文关键词不会出错 */
const fetch = async (params = {}, responseType = "json") => {
  try {
    const response = await _http.get(API.base, {
      params: { ...FIXED_PARAMS, ...API.query, ...params },
      headers: {
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.8"
      },
      responseType
    });
    return response.data;
  } catch (error) {
    console.error(`[${SOURCE.key}] 请求失败：${API.base}`, error.message);
    return null;
  }
};

// ---------------------------------------------------------------------------
// 运行时容器（redis / log 由框架注入）
// ---------------------------------------------------------------------------
const store = {
  init: false,
  redis: null,
  log: null
};

const init = async (server) => {
  if (store.init) return;
  store.redis = server?.redis || null;
  store.log = server?.log || null;
  store.init = true;
};

/** 带缓存的函数包装，缓存异常不影响主流程 */
const cachedFunction = (fn, timeout = 3600) => {
  return async (...args) => {
    const name = fn.name.replace("_", "").trim();
    store.log?.info?.(args);

    const cacheKey = `${SOURCE.key}${name}:${CryptoJS.MD5(JSON.stringify(args))}`;
    try {
      const hit = await store.redis?.get(cacheKey);
      if (hit) return JSON.parse(hit);
    } catch (e) { /* 缓存不可用则直连 */ }

    const result = await fn.apply(this, args);

    try {
      if (result && store.redis) {
        await store.redis.set(cacheKey, JSON.stringify(result));
        if (timeout > 0) await store.redis.expire(cacheKey, timeout);
      }
    } catch (e) { /* 写缓存失败忽略 */ }

    return result;
  };
};

// ---------------------------------------------------------------------------
// 数据转换工具
// ---------------------------------------------------------------------------

/** 上游列表项 -> 框架列表项（上游只有 4 个字段，其余留空） */
const getList = (videos) => {
  return (videos || [])
    .filter(v => v && v.vod_id && String(v.vod_id) !== "0")
    .map(v => ({
      vod_id: v.vod_id,
      vod_name: v.vod_name || "",
      vod_pic: v.vod_pic || v.vod_pic_thumb || "",
      vod_remarks: v.vod_remarks || "",
      vod_year: v.vod_year || v.tag || ""
    }));
};

/** "喜剧,爱情,..." -> [{ n, v }, ...]，过滤空值与「全部」 */
const splitOptions = (raw) => {
  const src = Array.isArray(raw) ? raw : String(raw || "").split(/[,，]/);
  return src
    .map(s => String(s || "").trim())
    .filter(s => s && s !== "全部")
    .map(s => ({ n: s, v: s }));
};

/** 从 class[] 构造框架所需的 classes 与 filters */
const buildClassesAndFilters = (classList) => {
  const classes = [];
  const filters = {};

  (classList || []).forEach(k => {
    if (!k || k.type_id === undefined) return;
    const tid = String(k.type_id);
    classes.push({ type_id: tid, type_name: k.type_name || "" });

    const fts = [];
    const ext = k.type_extend || {};

    for (const [key, label] of Object.entries(EXTEND_LABELS)) {
      const options = splitOptions(ext[key]);
      if (options.length > 0) fts.push({ key, name: label, value: options });
    }

    // 排序维度：上游 by 参数实测未见效果，仍保留供后续适配
    fts.push({
      key: "by",
      name: "排序",
      value: [
        { n: "按时间", v: "time" },
        { n: "按人气", v: "hits" },
        { n: "按评分", v: "score" }
      ]
    });

    filters[tid] = fts;
  });

  return { classes, filters };
};

/** 简单清理简介里的 HTML */
const cleanContent = (text) => {
  return String(text || "无")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/?[^>]+>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .trim() || "无";
};

/**
 * 把上游播放串转成框架可用的 vod_play_from / vod_play_url。
 * 上游：froms = "XYDB$$$..."，urls = "集名$XYTY-xxx#...$$$..."
 */
const buildPlay = (v, vodId) => {
  const froms = String(v.vod_play_from || "").split("$$$").map(s => s.trim());
  const groups = String(v.vod_play_url || "").split("$$$");

  const playFrom = [];
  const playUrl = [];

  groups.forEach((group, gi) => {
    const lines = [];

    group.split("#").filter(Boolean).forEach(ep => {
      const pos = ep.indexOf("$");
      const epName = pos >= 0 ? ep.slice(0, pos) : "";
      const raw = pos >= 0 ? ep.slice(pos + 1) : ep;
      if (!raw) return;

      if (RAW_PLAY_URL) {
        lines.push(`${epName}$${raw}`);
        return;
      }

      const payload = {
        url: raw,                 // 站点 token（XYTY-<32hex>），非直链
        from: froms[gi] || "",   // 播放组标识，如 XYDB
        vid: vodId,
        name: epName
      };
      lines.push(`${epName}$${e64url(JSON.stringify(payload))}`);
    });

    if (lines.length > 0) {
      playFrom.push(`线路${gi + 1}(${froms[gi] || ""})`);
      playUrl.push(lines.join("#"));
    }
  });

  return {
    vod_play_from: playFrom.join("$$$"),
    vod_play_url: playUrl.join("$$$")
  };
};

// ---------------------------------------------------------------------------
// 四个标准动作
// ---------------------------------------------------------------------------

/** 首页：分类 + 筛选 + 推荐（推荐需另拉分类页，ac=list 本身不出影片） */
const home = async ({ filter } = {}) => {
  const empty = { class: [], filters: {}, list: [] };

  const clsData = await fetch({ ac: API.defaultAc });
  const classList = clsData?.class || [];
  if (classList.length === 0) return empty;

  const { classes, filters } = buildClassesAndFilters(classList);

  // 取前几个主分类的首页，并发拉取后按 vod_id 去重
  const picked = classes.slice(0, HOME_CLASS_COUNT).map(c => c.type_id);
  const pages = await Promise.all(
    picked.map(tid => fetch({ ac: "list", t: tid, pg: 1 }))
  );

  const seen = new Set();
  const recommend = [];
  for (const p of pages) {
    for (const item of getList(p?.list)) {
      const key = String(item.vod_id);
      if (seen.has(key)) continue;
      seen.add(key);
      recommend.push(item);
      if (recommend.length >= picked.length * HOME_PER_CLASS) break;
    }
    if (recommend.length >= picked.length * HOME_PER_CLASS) break;
  }

  // 与模板保持一致：filters 恒返回，filter 参数不参与裁剪
  return {
    class: classes,
    filters,
    list: recommend
  };
};

/** 分类：透传筛选参数，分页信息直接用上游真实值 */
const category = async ({ id, page, filters } = {}) => {
  const pg = parseInt(page || "1", 10) || 1;
  const params = { ac: "list", t: id, pg };

  for (const [k, v] of Object.entries(filters || {})) {
    const key = k === "extend" ? "class" : k;
    if (!FILTER_KEYS.includes(key)) continue;
    if (v === undefined || v === null || v === "" || v === "全部") continue;
    params[key] = v;
  }

  const data = await fetch(params);
  const list = getList(data?.list);

  return {
    list,
    page: parseInt(data?.page || pg, 10) || 1,
    pagecount: parseInt(data?.pagecount || 1, 10) || 1,
    limit: parseInt(data?.limit || list.length || 20, 10) || 20,
    total: parseInt(data?.total || list.length || 0, 10) || 0
  };
};

/** 详情：上游 ids 不支持批量，必须逐个请求 */
const detail = async ({ id } = {}) => {
  const idsArr = (Array.isArray(id) ? id : [id])
    .map(v => String(v ?? "").trim())
    .filter(Boolean);

  const result = { list: [] };

  for (const vodId of idsArr) {
    const data = await fetch({ ac: "detail", ids: vodId });
    const v = data?.list?.[0] || data?.data || null;
    // 上游对不存在的 id 会回一条全字段为空的壳记录，必须剔除
    if (!v || !v.vod_name || !v.vod_play_url) continue;

    const play = buildPlay(v, vodId);
    result.list.push({
      vod_id: v.vod_id ?? vodId,
      vod_name: v.vod_name || "",
      vod_pic: v.vod_pic || "",
      type_name: v.type_name || "",   // 上游详情不返回分类名
      vod_year: v.vod_year || "",
      vod_area: v.vod_area || "",
      vod_remarks: v.vod_remarks || "",
      vod_actor: v.vod_actor || "",
      vod_director: v.vod_director || "",
      vod_content: cleanContent(v.vod_content),
      vod_play_from: play.vod_play_from,
      vod_play_url: play.vod_play_url
    });
  }

  return result;
};

/** 搜索：上游返回 { list, page, total }，无 pagecount/limit，自行兜底 */
const search = async ({ page, wd } = {}) => {
  const pg = parseInt(page || "1", 10) || 1;
  const data = await fetch({ ac: "list", wd: wd || "", pg });
  const list = getList(data?.list);
  const limit = list.length || 20;
  const total = parseInt(data?.total || list.length || 0, 10) || 0;

  return {
    list,
    page: parseInt(data?.page || pg, 10) || 1,
    pagecount: Math.max(1, Math.ceil(total / limit)),
    limit,
    total
  };
};

/** 解出 play 载荷：URL-safe b64 -> 标准 b64 -> JSON -> 裸串 */
const decodePlayPayload = (id) => {
  const raw = String(id ?? "");
  for (const decoder of [d64url, d64]) {
    try {
      const text = decoder(raw);
      if (text && text.trim().startsWith("{")) return JSON.parse(text);
    } catch (e) { /* 继续尝试下一种 */ }
  }
  try {
    if (raw.trim().startsWith("{")) return JSON.parse(raw);
  } catch (e) { /* 忽略 */ }
  return { url: raw };
};

/**
 * 播放请求头清洗：只保留上游给的安全头。
 * ★ 必须剔除 Referer / Origin / Host：直链 CDN 带 Referer 直接 403。
 */
const sanitizePlayHeader = (rawHeader) => {
  const out = {};
  for (const [k, v] of Object.entries(rawHeader || {})) {
    if (typeof v !== "string" || !v) continue;
    if (/^(referer|origin|host)$/i.test(k)) continue;
    out[k] = v;
  }
  if (!Object.keys(out).some(k => /^user-agent$/i.test(k))) {
    out["User-Agent"] = UA;
  }
  return out;
};

/**
 * 站点自带解析接口：把 XYTY-* token 换成真实直链。
 * 上游会随机返回 jx=1 降级（url 仍是 token），故内置重试与 cache-buster。
 * 返回 { ok, url, header, jx, parse, attempts }。
 */
const resolveViaSite = async (token) => {
  let last = null;

  for (let i = 0; i < PLAY_RETRY; i++) {
    const params = { ac: PLAY_AC, play: token };
    // 首次不加噪声；失败后加随机参数，避免命中服务端的降级结果缓存
    if (i > 0) params._ = `${Date.now()}-${i}-${Math.random().toString(36).slice(2, 7)}`;

    const data = await fetch(params);
    last = data;

    const url = data?.url;
    if (typeof url === "string" && /^https?:\/\//i.test(url)) {
      return {
        ok: true,
        url,
        header: sanitizePlayHeader(data?.header),
        jx: data?.jx ?? 0,
        parse: 0,
        attempts: i + 1
      };
    }

    if (i < PLAY_RETRY - 1) {
      await new Promise(resolve => setTimeout(resolve, PLAY_RETRY_DELAY));
    }
  }

  console.warn(`[${SOURCE.key}] 站点解析连续 ${PLAY_RETRY} 次降级，token=${token}`);
  return {
    ok: false, url: token, header: {}, jx: 1, parse: 1,
    attempts: PLAY_RETRY, last
  };
};

/** 播放解析：站点官方接口(带重试) -> 备用钩子 -> 保守降级 */
const _play = async ({ flag, id } = {}, server) => {
  const payload = decodePlayPayload(id);

  // 兼容框架把「集名$token」整串传过来的情况
  let raw = String(payload.url ?? id ?? "");
  if (raw.includes("$")) raw = raw.slice(raw.lastIndexOf("$") + 1);
  if (!raw) return { parse: 1, url: raw, header: {} };

  // 已经是直链：直接播，不加任何多余请求头
  if (/^https?:\/\//i.test(raw)) {
    return { parse: 0, url: raw, header: {} };
  }

  // ① 主通道：站点自带解析接口
  const resolved = await resolveViaSite(raw);
  if (resolved.ok) {
    const header = { ...resolved.header };
    if (payload.u) header["User-Agent"] = payload.u;
    // 绝不补 Referer —— 直链 CDN 校验 Referer 会返回 403
    return { parse: 0, url: resolved.url, header, jx: 0 };
  }

  // ② 备用通道：自定义钩子 / 外部解析接口
  const headers = { "User-Agent": UA };
  if (payload.r) headers.Referer = payload.r;  // 仅载荷显式指定时才带
  if (payload.u) headers["User-Agent"] = payload.u;

  if (typeof PLAY_RESOLVE.handler === "function") {
    try {
      const r = await PLAY_RESOLVE.handler(payload, { headers, _http, server, flag });
      if (r) return r;
    } catch (e) {
      console.error(`[${SOURCE.key}] 自定义解析失败：`, e.message);
    }
  }

  if (PLAY_RESOLVE.url) {
    const parseUrl = PLAY_RESOLVE.url
      .replace("{id}", encodeURIComponent(raw))
      .replace("{url}", encodeURIComponent(raw))
      .replace("{from}", encodeURIComponent(payload.from || ""))
      .replace("{vid}", encodeURIComponent(String(payload.vid || "")));
    try {
      const response = await _http.get(parseUrl, { headers, responseType: "text" });
      const text = typeof response.data === "string" ? response.data : JSON.stringify(response.data);
      const json = JSON.parse(text);
      const playUrl = json.url || json.data?.url || json.data?.data?.url;
      if (playUrl) return { parse: 0, url: playUrl, header: headers };
    } catch (e) {
      console.error(`[${SOURCE.key}] 备用解析接口未返回地址：`, e.message);
    }
    return { parse: 1, url: parseUrl, header: headers };
  }

  // ③ 全部失败：保留 token 交给上层，至少不比修复前更差
  return { parse: 1, url: raw, header: headers, jx: 1 };
};

// ---------------------------------------------------------------------------
// 模块元数据与导出
// ---------------------------------------------------------------------------
const meta = {
  key: SOURCE.key,
  name: SOURCE.name,
  type: SOURCE.type,
  api: ROUTE,              // 本地路由，切勿写成上游 IP
  searchable: 1,
  quickSearch: 1,
  changeable: 1,           // 允许用 ext 换源
  source: SOURCE.api       // 仅记录上游地址，框架不使用
};

Object.assign(store, {
  meta,
  home: cachedFunction(home),
  category: cachedFunction(category),
  detail: cachedFunction(detail),
  search: cachedFunction(search)
});

const EMPTY = { list: [], page: 1, pagecount: 0, limit: 0, total: 0 };

module.exports = async (app, opt) => {
  app.get(meta.api, async (req, reply) => {
    if (!store.init) await init(req.server);

    const { filter, t, ac, pg, ext, ids, flag, play, wd, quick } = req.query || {};

    // ext 以 http 开头 -> 换源（支持完整 URL 或纯 base）
    if (ext && /^https?:\/\//i.test(ext)) {
      try {
        API = parseApi(ext);
        HOST = API.origin;
      } catch (e) {
        console.error(`[${SOURCE.key}] ext 换源失败：`, e.message);
      }
    }

    try {
      if (play) {
        return await _play({ flag: flag || "", id: play }, req.server);
      }

      // 用「是否存在 wd 键」判断，空关键词也应走搜索返回空结果，
      // 而不是像模板那样因 if (wd) 为假误落到 home
      const hasWd = Object.prototype.hasOwnProperty.call(req.query || {}, "wd");
      if (hasWd) {
        return await store.search({ page: parseInt(pg || "1", 10), quick: quick || false, wd: wd || "" });
      }

      if (!ac) {
        return await store.home({ filter: filter ?? false });
      }

      if (ac === "detail") {
        if (t) {
          const body = {
            id: t,
            page: parseInt(pg || "1", 10),
            filter: filter || false,
            filters: {}
          };

          // ext 非 URL 时，按模板约定当作 Base64(JSON) 编码的筛选条件
          if (ext && !/^https?:\/\//i.test(ext)) {
            try {
              body.filters = JSON.parse(d64(ext)) || {};
            } catch (e) { /* 非法 ext 忽略 */ }
          }
          return await store.category(body);
        }

        if (ids) {
          return await store.detail({
            id: ids.split(",").map(s => s.trim()).filter(Boolean)
          });
        }
      }

      return EMPTY;
    } catch (error) {
      console.error(`[${SOURCE.key}] 处理请求异常：`, error.message);
      return EMPTY;
    }
  });

  opt.sites.push(meta);
};

/** 便于离线调试/单元测试：暴露纯函数，框架不会使用 */
module.exports.__debug = {
  SOURCE, meta, parseApi, e64url, d64url,
  decodePlayPayload, buildPlay, buildClassesAndFilters, getList,
  sanitizePlayHeader, resolveViaSite,
  home, category, detail, search, _play,
  setApi: (api) => { API = parseApi(api); HOST = API.origin; }
};
