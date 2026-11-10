# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════
# 判型记录(卡01 第四节;跨会话可读 —— 接手先读这段,别重新判一遍)
#   RE_TARGET   : https://91yyz.com/  (夜映者 · 会员制视频平台)
#   RE_PATH     : SPA(Vue/React, #root 空壳)+ REST API(/api/v1,纯 JSON)
#                 播放地址 POST /videos/{id}/playback-session → /api/v1/media/media-token/video.mp4
#                 (media-token 为服务端签发的一次性令牌;1 小时有效,每次播放重拿,天然防过期;
#                 adaptive=false 是 mp4 直链非 HLS)
#   RE_OBSTACLE : ① 瑞数信息动态 WAF:API 直连返回 /_guard/html.js JS 挑战,
#                 沙箱内 headed Chromium(xvfb+stealth)过挑战后 IP 级放行窗口,
#                 壳端无浏览器无法破,赌家庭/基站 IP 宽松(标注风险)
#                 ② 播放必须登录:POST /auth/login 拿 XSRF-TOKEN cookie,
#                 登录态 = XSRF-TOKEN cookie + X-Visitor-Id header 双要素
#                 (服务端把 visitor 与会话绑定;X-XSRF-TOKEN header 双提交防 CSRF)
#                 ③ 会员制:未登录连唯一一条免费视频都拿不到播放地址;
#                 非会员播 VIP 只有 preview 试看(previewSeconds=120)
#   RE_EVIDENCE : register 接口可注册且注册赠 3 天会员(实测账号打通全链路);
#                 media 媒体域(封面图)不设防,200 直连
#   RE_TOOLS    : playwright headed 抓包 / curl 链路复测 / main.js 静态分析
#   RE_CREATED  : 2026-10-17
#   RE_FIX      : v1 首版。登录态双要素/XSRF 双提交/playback-session 均为实测
#                 v2 分类参数修正(核心坑):catalog/options 的 category_video 组
#                 option value≠label —— value 是 /videos?category= 的参数值,
#                 label 是展示名(例 value=热门博主原创 → label=淫妻绿帽);
#                 v1 误用 search_video 组(搜索联想词)当分类 → 全部 0 条。
#                 现:主分类=category_video 组 value + 并发探活剔空分类
#                 (实测剔 夜映者原创);search_video 组 14 词转 filters 标签维度走 q
#                 (实测剔 灌精);filters 三维度(标签/会员/排序),壳回传多形态兼容。
#                 播放形态实测 mp4/m3u8 皆有,format 按返回动态判定。
# ══════════════════════════════════════════════════════════════
# TVBox 源 · 夜映者(91yyz)
# 站点档案(SITE)是唯一需要按站改的地方,其余逻辑通用。
# 自检:python3 shellsim.py 本文件 --run --strict   (AUDIT_OK 才算成)
#
# ── 壳接口约定(四壳:TVBox/FongMi/CatVod 等,type=3 的 py 源)────────
# 13 个标准接口一个不能少:
#   getDependence / init / homeContent / homeVideoContent / categoryContent
#   / detailContent / searchContent / playerContent / localProxy
#   / isVideoFormat / manualVideoCheck / action / destroy
# 1. 双协议兼容继承 + 方法签名 *args 收尾
# 2. playerContent 的 header 是 dict,另带 format/contentType
# 3. homeContent 返回 class + filters(dict)+ list 三键
# 4. detailContent 的 ids 必须遍历
# 5. 只用标准库(urllib),别 import requests

import gzip
import http.cookiejar
import json
import re
import threading
import time
import html as _html
import urllib.parse
import urllib.request

# ──────────────────────────────────────────────────────────────
# 站点档案:换站只改这一段
# ──────────────────────────────────────────────────────────────
SITE = {
    "name": "夜映者",
    "site": "https://91yyz.com",
    "api": "https://91yyz.com/api/v1",
    # 账号配置:优先 ext(壳的源配置框传 {"account":"..","password":".."}),
    # 其次改这里。留空则匿名浏览(列表可看,播放提示需登录)。
    # 注意:账号密码明文存在源文件里,分享源=分享账号,建议用次要账号。
    # 下面是探站时注册的测试号(站方注册赠 3 天会员,到期后失效):
    #   换自己的号有两种改法 —— ① 直接改下面两行;② 壳的源配置框传 ext。
    "account": "tvboxtest24618@proton.me",
    "password": "Tvbox#2026x",
    # 主分类:catalog/options 的 category_video 组动态拉取。
    # 坑(实测):该组 option 的 value≠label —— value 是传给 /videos?category= 的
    # 参数值,label 才是给用户看的名字。例:value=热门博主原创 → label=淫妻绿帽。
    # 传 label 进 category 参数会 0 条(曾踩坑);search_video 组那 14 个中文词
    # (绿帽/换妻/...)是搜索联想词,不是分类参数,只能走 q。
    # 此处为动态拉取失败时的兜底静态表:(category参数值, 展示名)
    "cats_static": [("店长推荐", "店长推荐"), ("热门博主原创", "淫妻绿帽"),
                    ("夜映者原创", "夜映者原创"), ("AI短剧", "AI合集"),
                    ("刷锅", "刷锅"), ("媚黑", "媚黑"),
                    ("双龙入洞", "双龙入洞"), ("露出勾引", "露出勾引")],
    # 标签维度(搜索联想词组):点进去走 q 参数,壳 filters 回传后拼 q
    "tags_static": [("绿帽", "绿帽"), ("换妻", "换妻"), ("乱伦", "乱伦"),
                    ("群P", "群P"), ("媚黑", "媚黑"), ("内射", "内射"),
                    ("调教", "调教"), ("偷拍", "偷拍"), ("熟女", "熟女"),
                    ("少妇", "少妇"), ("颜值", "颜值"), ("SM", "SM"),
                    ("露出", "露出")],
    # 分类级黑名单(铁律13:命中即剔除,不采集不写入)
    "cat_block_kw": ["萝莉", "幼女", "少女", "幼齿", "teen", "loli", "schoolgirl"],
    # 条目级黑名单(标题命中即丢弃)
    "title_block_kw": ["萝莉", "幼女", "少女", "幼齿", "teen", "loli", "schoolgirl"],
    # 排序 filters(sort 参数)
    "sorts": [("最新发布", "latest"), ("观看最多", "popular"), ("最早发布", "oldest")],
    # 访问权限 filters(access 参数)
    "accesses": [("全部", ""), ("免费内容", "free"), ("会员内容", "vip"), ("单片解锁", "single_unlock")],
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 15
RETRY = 3
PER_PAGE = 20
LOGIN_TTL = 3600        # 登录态复用时长(秒);过期自动重登
CACHE_TTL = 60          # 页面/接口短 TTL 缓存(秒)

# 瑞数 WAF 挑战页特征(命中即判被拦,壳内无浏览器破不了,明确失败别假装成功)
GUARD_MARK = "_guard/html.js"


def _dec(raw):
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def _blocked(text, keywords):
    low = str(text or "").lower()
    return any(kw in low for kw in keywords)


def _to_int(v, default=1):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _pic_full(pic, base=None):
    """封面补全为绝对 URL(详情接口返回的是 /media/... 相对路径)"""
    if not pic:
        return ""
    pic = str(pic)
    if pic.startswith("//"):
        return "https:" + pic
    if pic.startswith("http"):
        return pic
    return urllib.parse.urljoin(base or SITE["site"], pic)


# ──────────────────────────────────────────────────────────────
# TVBox 四壳接口(13 个标准接口,全部可调用)
# ──────────────────────────────────────────────────────────────
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        def init(self, extend=""):
            pass


class Spider(_BaseSpider):
    def __init__(self):
        self.ext = {}
        self.account = SITE["account"]
        self.password = SITE["password"]
        self.visitor = ""            # X-Visitor-Id(登录态双要素之一,进程内固定)
        self.xsrf = ""               # XSRF-TOKEN cookie 值(双要素之二)
        self.login_at = 0.0
        self.logged = False
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar))
        self._cache = {}             # (method,url,body) -> (json, at)
        self._cache_lock = threading.RLock()
        self._login_lock = threading.RLock()
        self._warmed = False
        self._cats_cache = None       # (时间戳, cats) 分类探活缓存(10 分钟)
        self._tags_cache = None       # (时间戳, tags) 标签探活缓存(10 分钟)

    # ---- 壳启动即调 ----
    def getDependence(self):
        return ""

    def getName(self):
        return SITE["name"]

    def init(self, extend=""):
        # 配置解析兼容 dict / list / JSON 字符串(壳各版本传法不同)
        cfg = {}
        try:
            if isinstance(extend, dict):
                cfg = extend
            elif isinstance(extend, (list, tuple)):
                cfg = {}
            elif extend:
                cfg = json.loads(extend)
                if not isinstance(cfg, dict):
                    cfg = {}
        except Exception:
            cfg = {}
        self.ext = cfg
        # ext 优先覆盖账号(壳的源配置框);其次源码顶部 SITE 配置
        acc = str(cfg.get("account") or "").strip()
        pwd = str(cfg.get("password") or "").strip()
        if acc:
            self.account, self.password = acc, pwd
        self.visitor = str(cfg.get("visitorId") or "").strip() or self._new_visitor()
        # 有账号就登录(拿 XSRF-TOKEN + 服务端按 visitor 绑会话)
        if self.account and self.password:
            try:
                self._login()
            except Exception:
                pass
        # 预热:拉一次分类(同时验证 API 通不通)
        try:
            self._catalog()
        except Exception:
            pass
        self._warmed = True
        return ""

    def getCategory(self):
        return ""

    def getFilter(self):
        return {}

    def action(self, action):
        return ""

    def destroy(self):
        with self._cache_lock:
            self._cache.clear()
        return ""

    def localProxy(self, param):
        # 封面与片流都是直链,不经本地代理;返回三元组,勿返回 None
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        text = str(url or "").lower()
        return bool(re.search(r"\.(?:m3u8|mp4|mkv|flv|avi|ts)(?:[?#]|$)", text))

    def manualVideoCheck(self):
        return False

    # ---- 网络层 ----
    def _new_visitor(self):
        import uuid
        return str(uuid.uuid4())

    def _req(self, path, method="GET", body=None, form=False):
        """统一请求:带 UA + X-Visitor-Id + cookie jar(XSRF-TOKEN 自动带)。
        返回 (json_obj_or_None, err_str)。瑞数挑战/网络失败明确返回错误。"""
        url = path if str(path).startswith("http") else SITE["api"] + path
        data = None
        headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                   "Referer": SITE["site"] + "/", "Origin": SITE["site"],
                   "X-Visitor-Id": self.visitor or "anon"}
        if body is not None:
            if form:
                data = urllib.parse.urlencode(body).encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                data = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
        # XSRF 双提交:写操作必须带 X-XSRF-TOKEN header(值=XSRF-TOKEN cookie)
        if method != "GET" and self.xsrf:
            headers["X-XSRF-TOKEN"] = self.xsrf
        last = ""
        for attempt in range(RETRY):
            try:
                req = urllib.request.Request(url, data=data, method=method)
                for k, v in headers.items():
                    req.add_header(k, v)
                with self._opener.open(req, timeout=TIMEOUT) as r:
                    raw = r.read()
                    if raw[:2] == b"\x1f\x8b":
                        raw = gzip.decompress(raw)
                    # 登录响应 Set-Cookie 自动进 jar;同步 XSRF 值供 header 用
                    self._sync_xsrf()
                    text = _dec(raw)
                    if GUARD_MARK in text:
                        return None, "waf_guard"   # 瑞数挑战,壳内破不了
                    try:
                        return json.loads(text), ""
                    except Exception:
                        return None, "bad_json:" + text[:60]
            except Exception as e:
                last = "%s:%s" % (type(e).__name__, str(e)[:60])
                time.sleep(0.4 * (attempt + 1))
        return None, last or "fail"

    def _sync_xsrf(self):
        try:
            for c in self._jar:
                if c.name == "XSRF-TOKEN":
                    self.xsrf = c.value
        except Exception:
            pass

    def _api(self, path, params=None, ttl=CACHE_TTL):
        """带 TTL 缓存的 GET(列表/详情/分类这类幂等请求)"""
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        key = ("GET", path + q, "")
        now = time.time()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit and now - hit[1] < ttl:
                return hit[0]
        data, err = self._req(path + q)
        if data is None:
            return None
        with self._cache_lock:
            self._cache[key] = (data, now)
        return data

    # ---- 登录(播放前置) ----
    def _login(self):
        with self._login_lock:
            now = time.time()
            if self.logged and now - self.login_at < LOGIN_TTL:
                return True
            if not (self.account and self.password):
                return False
            if not self.visitor:
                self.visitor = self._new_visitor()
            data, err = self._req("/auth/login", method="POST",
                                  body={"email": self.account, "password": self.password})
            if data and isinstance(data, dict) and data.get("user"):
                self._sync_xsrf()
                self.logged = True
                self.login_at = time.time()
                return True
            self.logged = False
            return False

    def _ensure_login(self):
        """播放前确保登录;失效自动重登一次"""
        if self._login():
            return True
        # 可能是 session 过期:清掉旧态重来
        self.xsrf = ""
        try:
            self._jar.clear()
        except Exception:
            pass
        self.visitor = self._new_visitor()
        return self._login()

    # ---- 分类(catalog/options 动态;category_video 组) ----
    def _catalog(self):
        return self._api("/catalog/options", ttl=600)

    def _probe_total(self, params):
        """并发探活:perPage=1 拿 total,0 条即空(剔除用)。失败返回 None(保守保留)。"""
        try:
            d = self._api("/videos", dict(params, page=1, perPage=1), ttl=600)
            if not isinstance(d, dict):
                return None
            meta = d.get("meta") or {}
            if "total" not in meta:
                return None
            return _to_int(meta.get("total"), 0)
        except Exception:
            return None

    def _probe_alive(self, pairs, param_key):
        """pairs: [(参数值, 展示名)];并发探活剔除 0 条项,失败保守保留"""
        if not pairs:
            return []
        alive = []
        lock = threading.Lock()

        def work(p):
            t = self._probe_total({param_key: p[0]})
            if t is None or t > 0:
                with lock:
                    alive.append(p)

        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(work, pairs))
        except Exception:
            return pairs
        # 保持原顺序
        order = {p[0]: i for i, p in enumerate(pairs)}
        alive.sort(key=lambda p: order.get(p[0], 999))
        return alive

    def _parse_cats(self):
        """主分类:category_video 组,type_id=value(API 参数),type_name=label(展示名)。
        探活剔除空分类(实测夜映者原创 0 条),10 分钟缓存避免每次首页都探。"""
        now = time.time()
        with self._cache_lock:
            cached = self._cats_cache
            if cached and now - cached[0] < 600:
                return list(cached[1])
        pairs = []
        try:
            d = self._catalog()
            groups = ((d or {}).get("data") or {}).get("groups") or []
            for g in groups:
                if g.get("key") != "category_video":
                    continue
                for o in g.get("options") or []:
                    val = str(o.get("value") or "").strip()
                    label = str(o.get("label") or "").strip() or val
                    if not val:
                        continue
                    if _blocked(val, SITE["cat_block_kw"]) or _blocked(label, SITE["cat_block_kw"]):
                        continue
                    pairs.append((val, label))
                break
        except Exception:
            pairs = []
        if not pairs:
            pairs = [(v, n) for v, n in SITE["cats_static"]]
        pairs = self._probe_alive(pairs, "category")
        cats = [{"type_id": v, "type_name": n} for v, n in pairs]
        with self._cache_lock:
            self._cats_cache = (now, cats)
        return list(cats)

    def _parse_tags(self):
        """标签维度:search_video 组(搜索联想词),点中走 q 参数。探活剔除空词。"""
        now = time.time()
        with self._cache_lock:
            cached = self._tags_cache
            if cached and now - cached[0] < 600:
                return list(cached[1])
        pairs = []
        try:
            d = self._catalog()
            groups = ((d or {}).get("data") or {}).get("groups") or []
            for g in groups:
                if g.get("key") != "search_video":
                    continue
                for o in g.get("options") or []:
                    val = str(o.get("value") or "").strip()
                    label = str(o.get("label") or "").strip() or val
                    if not val:
                        continue
                    if _blocked(val, SITE["cat_block_kw"]) or _blocked(label, SITE["cat_block_kw"]):
                        continue
                    pairs.append((val, label))
                break
        except Exception:
            pairs = []
        if not pairs:
            pairs = [(v, n) for v, n in SITE["tags_static"]]
        pairs = self._probe_alive(pairs, "q")
        tags = [{"n": n, "v": v} for v, n in pairs]
        with self._cache_lock:
            self._tags_cache = (now, tags)
        return list(tags)

    def _filters_of(self):
        """壳 filters(dict):键=筛选维度名,值=[{n:展示名, v:参数值}]。
        壳回传 extend 时用同名键;categoryContent 负责映射到 API 参数。"""
        tag_list = [{"n": "全部", "v": ""}] + self._parse_tags()
        acc_list = [{"n": n, "v": v} for n, v in SITE["accesses"]]
        sort_list = [{"n": n, "v": v} for n, v in SITE["sorts"]]
        return {"标签": tag_list, "会员": acc_list, "排序": sort_list}

    # ---- 列表条目解析 ----
    def _parse_videos(self, data):
        out = []
        items = (data or {}).get("data")
        if not isinstance(items, list):
            items = (items or {}).get("items") if isinstance(items, dict) else []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            if not title:
                continue
            # 铁律13:标题命中未成年关键词,丢弃不返回
            if _blocked(title, SITE["title_block_kw"]):
                continue
            vid, slug = it.get("id"), str(it.get("slug") or "")
            if not vid or not slug:
                continue
            pic = _pic_full(it.get("poster") or it.get("avatar"))
            access = str(it.get("accessType") or "")
            remarks = ""
            if access == "free":
                remarks = "免费"
            elif access == "vip":
                remarks = "会员试看" if not it.get("hasAccess") else "会员"
            elif access == "single_unlock":
                remarks = "解锁"
            out.append({
                "vod_id": "%s|%s" % (vid, slug),
                "vod_name": title[:80],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_year": str(it.get("publishedAt") or "")[:10],
                "vod_area": "",
                "vod_type": "",
            })
        return out

    def _page_of(self, data, fallback=1):
        meta = (data or {}).get("meta") or {}
        return {"page": _to_int(meta.get("page"), fallback),
                "pagecount": _to_int(meta.get("lastPage"), fallback),
                "limit": _to_int(meta.get("perPage"), PER_PAGE),
                "total": _to_int(meta.get("total"), 0)}

    # ---- 首页 ----
    def homeContent(self, *args):
        cats = self._parse_cats()
        data = self._api("/videos", {"sort": "latest", "page": 1, "perPage": PER_PAGE}, ttl=30)
        items = self._parse_videos(data)
        if not items:
            items = []
        return {"class": cats, "filters": self._filters_of(), "list": items}

    def homeVideoContent(self):
        data = self._api("/videos", {"sort": "latest", "page": 1, "perPage": PER_PAGE}, ttl=30)
        return {"list": self._parse_videos(data)}

    # ---- 分类 ----
    # 筛选维度同义 key 归一化表:壳各家回传键名不统一,全部映射到 API 参数
    _EXT_KEYS = {
        "q": ("标签", "tag", "keyword", "key", "q", "关键字", "关键词", "搜索"),
        "access": ("会员", "access", "权限", "权限类型"),
        "sort": ("排序", "sort", "order", "orderby"),
    }

    def _flatten_ext(self, ext, depth=0):
        """壳回传的 extend 拍平成 {归一化参数: 值}。
        兼容:dict / JSON 字符串 / {"filters": {...}} 嵌套 / 值带"全部" """
        out = {}
        if depth > 3 or ext is None:
            return out
        if isinstance(ext, str):
            ext = ext.strip()
            if not ext:
                return out
            try:
                ext = json.loads(ext)
            except Exception:
                return out
        if isinstance(ext, dict):
            # 嵌套 filters 形态:{"filters": {...}} 或 {"filter": [...]}
            for nest in ("filters", "filter", "extend"):
                nv = ext.get(nest)
                if isinstance(nv, (dict, str)):
                    out.update(self._flatten_ext(nv, depth + 1))
            for k, v in ext.items():
                if k in ("filters", "filter", "extend"):
                    continue
                out[str(k)] = v
        elif isinstance(ext, (list, tuple)):
            for item in ext:
                if isinstance(item, dict):
                    out.update(self._flatten_ext(item, depth + 1))
        return out

    def _ext_params(self, ext):
        """extend → /videos 查询参数(标签→q, 会员→access, 排序→sort)"""
        flat = self._flatten_ext(ext)
        params = {}
        for api_key, aliases in self._EXT_KEYS.items():
            for alias in aliases:
                v = flat.get(alias)
                if v is None:
                    continue
                v = str(v).strip()
                if v and v not in ("全部", "all", "All"):
                    params[api_key] = v
                    break
        return params

    def categoryContent(self, tid, pg, filter, extend, *args):
        slug = str(tid or "").strip()
        page = _to_int(pg, 1)
        if not slug:
            return {"page": page, "pagecount": page, "limit": 0, "total": 0, "list": []}
        params = {"category": slug, "sort": "latest", "page": page, "perPage": PER_PAGE}
        # 壳筛选回传:标签(走 q)/会员(access)/排序(sort)
        params.update(self._ext_params(extend))
        data = self._api("/videos", params, ttl=30)
        items = self._parse_videos(data)
        pg_info = self._page_of(data, page)
        if not items:
            pg_info = {"page": page, "pagecount": page, "limit": 0, "total": 0}
        return {"list": items,
                "page": pg_info["page"], "pagecount": pg_info["pagecount"],
                "limit": pg_info["limit"] or len(items), "total": pg_info["total"]}

    # ---- 详情 ----
    def detailContent(self, ids, *args):
        # 致命坑:ids 是 list/tuple 必须遍历
        id_list = list(ids) if isinstance(ids, (list, tuple)) else [ids]
        result_list = []
        for source_id in id_list:
            raw = str(source_id or "").strip()
            if not raw:
                continue
            # vod_id 形态 "{id}|{slug}";详情要 slug
            parts = raw.split("|", 1)
            slug = parts[1] if len(parts) == 2 else raw
            if not slug:
                continue
            data = self._api("/videos/" + urllib.parse.quote(slug, safe=""), ttl=60)
            v = (data or {}).get("data")
            if not isinstance(v, dict) or not v.get("title"):
                continue
            title = str(v.get("title") or "").strip()
            if _blocked(title, SITE["title_block_kw"]):
                continue
            pic = _pic_full(v.get("poster") or v.get("avatar"))
            access = str(v.get("accessType") or "")
            remarks = ""
            if access == "free":
                remarks = "免费"
            elif access == "vip":
                remarks = "会员试看" if not v.get("hasAccess") else "会员"
            creator = str(v.get("creator") or "")
            tags = " ".join(str(t) for t in (v.get("tags") or []))
            duration = str(v.get("duration") or "")
            # 单集直链(本站是单视频非剧集):「正片$数字id.mp4」。
            # .mp4 后缀只是给壳看的线路形态(壳校验地址后缀;真实地址由
            # playerContent 拿数字 id 换 playback-session,可能是 mp4 也可能是 m3u8)。
            # 只传数字 id 就够,slug 走 vod_id 带回。
            vid = v.get("id")
            play = "正片$%s.mp4" % vid if vid else ""
            result_list.append({
                "vod_id": raw,
                "vod_name": title[:80],
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_year": str(v.get("publishedAt") or "")[:10],
                "vod_area": "",
                "vod_actor": creator,
                "vod_director": creator,
                "vod_type": duration,
                "vod_content": (str(v.get("description") or "") + " " + tags).strip()[:300],
                "vod_play_from": "线路1",
                "vod_play_url": play,
            })
        return {"list": result_list}

    # ---- 搜索 ----
    def searchContent(self, key, quick=False, pg=1, *args):
        page = _to_int(pg, 1)
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": page, "pagecount": page, "limit": 0, "total": 0}
        data = self._api("/videos", {"q": kw, "page": page, "perPage": PER_PAGE}, ttl=30)
        items = self._parse_videos(data)
        pg_info = self._page_of(data, page)
        if not items:
            pg_info = {"page": page, "pagecount": page, "limit": 0, "total": 0}
        return {"list": items,
                "page": pg_info["page"], "pagecount": pg_info["pagecount"],
                "limit": pg_info["limit"] or len(items), "total": pg_info["total"]}

    def searchContentA(self, key, quick, pg=1, *args):
        return self.searchContent(key, quick, pg)

    # ---- 播放 ----
    def playerContent(self, flag, id, vipFlags, *args):
        # id 形态 "数字id.mp4"(detail 里写的线路地址);playback-session 只要数字 id
        raw = str(id or "").strip()
        vid = raw.split("|", 1)[0]
        vid = re.sub(r"\.(?:mp4|m3u8|flv|ts)$", "", vid).strip()
        if not vid.isdigit():
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}, "format": "video/mp4",
                    "contentType": "video/mp4", "msg": "地址无效"}
        # 播放必须登录:无账号直接明确失败(别假装有地址)
        if not (self.account and self.password):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}, "format": "video/mp4",
                    "contentType": "video/mp4",
                    "msg": "本站播放需登录:在源配置里填 account/password"}
        if not self._ensure_login():
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}, "format": "video/mp4",
                    "contentType": "video/mp4", "msg": "登录失败,检查账号密码"}
        data, err = self._req("/videos/%s/playback-session" % vid, method="POST",
                              body={}, form=True)
        # 419 CSRF / 未登录:重登一次再试
        if data is None and err in ("waf_guard",):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}, "format": "video/mp4",
                    "contentType": "video/mp4", "msg": "被站点防护拦截,换网络重试"}
        if data is None:
            self.logged = False
            if self._ensure_login():
                data, err = self._req("/videos/%s/playback-session" % vid,
                                      method="POST", body={}, form=True)
        pb = (data or {}).get("data") if isinstance(data, dict) else None
        url = str((pb or {}).get("url") or "")
        if not url:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": {"User-Agent": UA}, "format": "video/mp4",
                    "contentType": "video/mp4", "msg": "未拿到播放地址(需会员?)"}
        head = {"User-Agent": UA, "Referer": SITE["site"] + "/"}
        # 形态按实际返回判:实测同站既有 video.mp4 直链也有 master.m3u8 清单
        if re.search(r"\.m3u8(?:[?#]|$)", url):
            fmt = "application/vnd.apple.mpegurl"
        else:
            fmt = "video/mp4"
        return {"parse": 0, "jx": 0, "playUrl": "", "url": url,
                "header": head, "format": fmt, "contentType": fmt}
