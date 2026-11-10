# -*- coding: utf-8 -*-
"""
集芳阁云搜 · TVBox Python 爬虫 (单文件 / 零第三方依赖)

适配站点: 集芳阁云搜 (纯搜索站, 关键词搜全站, 无分类栏目)

站点特性:
  * 搜索关键词走 AES-128-CBC 加密后拼进路由: /search-{分类}-{排序}-{密文}[-页码].html
    密钥/偏移量硬编码在站点 js 里, 这里用纯 Python 实现(手机端没有 pycryptodome)
  * 结果页/详情页都是服务端渲染的 HTML, 直接正则解析, 不依赖任何接口
  * 封面 = 结果页里的 background-image, 直接可用
  * 播放直链 = 详情页 <a playdata="..."> 里的 m3u8, 需要带 UA/Referer
  * 站点域名经常换: 走地址发布页 302 + jfg.js 域名池自动解析当前入口, 换域名不用重装

TVBox 配置(json 站点里加一条):
  {
    "key": "jfgyunsou",
    "name": "集芳阁云搜",
    "type": 3,
    "api": "jfgyunsou_tvbox.py",
    "searchable": 1,
    "quickSearch": 1,
    "filterable": 0
  }

ext 可选参数(填在站点配置的 "ext" 里, JSON 字符串, 全都可以不填):
  {"entry": "https://xxx.xxx",   # 手动指定入口域名, 跳过自动解析
   "proxy": "",                  # 网络代理, 如 http://127.0.0.1:7890, 默认直连
   "proxy_play": 0,              # 1 = 播放走本机代理转发(播放器不带 header 时用)
   "timeout": 15}

装好后先自己验一遍:
  python3 jfgyunsou_tvbox.py host                  解析当前可用入口域名
  python3 jfgyunsou_tvbox.py home                  首页列表
  python3 jfgyunsou_tvbox.py search 红 1           搜索 + 打印前 5 条
  python3 jfgyunsou_tvbox.py cat top 2             分类列表(今日热播 第2页)
  python3 jfgyunsou_tvbox.py detail <vod_id>       详情 + 播放地址
  python3 jfgyunsou_tvbox.py play <vod_id>         只打印播放直链
  (想要走代理加 --proxy http://127.0.0.1:7890)
"""

import base64
import gzip
import json
import re
import sys
import threading
import time
import urllib.parse

try:
    import urllib.request as _urlreq
    import urllib.error as _urlerr
except Exception:  # pragma: no cover
    _urlreq = None
    _urlerr = None

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def __init__(self):
            pass


# ============================================================================
# 0. 常量
# ============================================================================
_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

# 站点 js 里硬编码的搜索加密参数(纯 Python AES-128-CBC / ZeroPadding)
_AES_KEY = b"2d4ebb7cb767dab1"
_AES_IV = b"7563ca4af41bd0fb"

# 入口域名池: 易记永久域名优先, 后面是地址发布页 / jfg.js 里会补进来的
_SEED_HOSTS = [
    "https://jifangge.club",
    "https://xn--u2uy07cd3d2mxd2a.com",   # 集芳阁.com
    "https://jifangge.com",
    "https://jfgsou.com",
]

# 地址发布页的域名 js(里面是当前一批入口域名)
_PUBLISH_JS = "https://jsd.load-faster.com/jfg.js"

# 站点真实页面特征: 命中说明域名是对的那个搜素站, 不是地址发布页/封锁页
_SITE_MARK = u"搜你所想"

# 分类(站点自带的两个榜单页)
_CLASSES = [
    {"type_id": "top", "type_name": u"今日热播"},
    {"type_id": "new", "type_name": u"今日更新"},
]

# 搜索分类 / 排序(拼搜索路由用)
_SEARCH_CIDS = {u"全部": 0, u"国产": 1, u"日韩": 2, u"欧美": 3, u"猎奇": 4, u"动漫": 5, u"R级": 6}
_SEARCH_SORTS = {"1": u"相关度", "2": u"播放量", "3": u"时长", "4": u"收录时间"}

# 一页几条(站点固定 20 条一页)
_PAGE_SIZE = 20


# ============================================================================
# 1. 纯 Python AES-128-CBC 加密 (ZeroPadding, 对齐站点 js 的 CryptoJS 行为)
# ============================================================================
def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _build_sbox():
    sbox = [0] * 256
    p = q = 1
    while True:
        p = (p ^ ((p << 1) & 0xFF) ^ (0x1B if (p & 0x80) else 0)) & 0xFF
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        q &= 0xFF
        x = q
        for sh in (1, 2, 3, 4):
            x ^= ((q << sh) | (q >> (8 - sh))) & 0xFF
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _build_sbox()


def _expand_key(key):
    sbox = _SBOX
    rcon = 1
    w = [key[i] | (key[i + 1] << 8) | (key[i + 2] << 16) | (key[i + 3] << 24)
         for i in range(0, 16, 4)]
    for i in range(4, 44):
        t = w[i - 1]
        if i % 4 == 0:
            t = ((t >> 8) | ((t & 0xFF) << 24)) & 0xFFFFFFFF
            t = (sbox[t & 0xFF] | (sbox[(t >> 8) & 0xFF] << 8) |
                 (sbox[(t >> 16) & 0xFF] << 16) | (sbox[(t >> 24) & 0xFF] << 24))
            t ^= rcon
            rcon = _xtime(rcon)
        w.append((w[i - 4] ^ t) & 0xFFFFFFFF)
    return w


def _shift_rows(st):
    return [st[4 * ((c + r) % 4) + r] for c in range(4) for r in range(4)]


def _mix_columns(st):
    out = []
    for c in range(4):
        a0, a1, a2, a3 = st[4 * c], st[4 * c + 1], st[4 * c + 2], st[4 * c + 3]
        t = a0 ^ a1 ^ a2 ^ a3
        out += [a0 ^ t ^ _xtime(a0 ^ a1), a1 ^ t ^ _xtime(a1 ^ a2),
                a2 ^ t ^ _xtime(a2 ^ a3), a3 ^ t ^ _xtime(a3 ^ a0)]
    return out


def _add_rk(st, w, rnd):
    return [st[i] ^ ((w[rnd * 4 + (i >> 2)] >> (8 * (i & 3))) & 0xFF) for i in range(16)]


def _encrypt_block(blk, w):
    sbox = _SBOX
    st = _add_rk(list(blk), w, 0)
    for rnd in range(1, 10):
        st = [sbox[b] for b in st]
        st = _shift_rows(st)
        st = _mix_columns(st)
        st = _add_rk(st, w, rnd)
    st = [sbox[b] for b in st]
    st = _shift_rows(st)
    st = _add_rk(st, w, 10)
    return bytes(st)


def aes_cbc_zero(data, key, iv):
    """AES-128-CBC + ZeroPadding(块对齐时不补块), 返回密文 bytes"""
    pad = (16 - len(data) % 16) % 16
    data = data + b"\x00" * pad
    w = _expand_key(key)
    prev = iv
    out = b""
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        ct = _encrypt_block(blk, w)
        out += ct
        prev = ct
    return out


def jfg_encrypt(keyword):
    """站点 encrypt(): AES 后 base64, 再 urlencode"""
    raw = keyword.encode("utf-8") if not isinstance(keyword, bytes) else keyword
    return urllib.parse.quote(base64.b64encode(aes_cbc_zero(raw, _AES_KEY, _AES_IV)).decode("ascii"))


# ============================================================================
# 2. 小工具
# ============================================================================
def _clean(s):
    if s is None:
        return ""
    if isinstance(s, bytes):
        s = s.decode("utf-8", "ignore")
    return re.sub(r"\s+", " ", str(s)).strip()


def _secs(v):
    """秒 -> 00:13:24"""
    try:
        n = int(float(v))
    except Exception:
        return ""
    if n <= 0:
        return ""
    h, r = divmod(n, 3600)
    m, s = divmod(r, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))


def _to_ascii_host(host):
    """中文域名 -> punycode"""
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except Exception:
        try:
            parts = host.split(".")
            out = []
            for p in parts:
                if any(ord(ch) > 127 for ch in p):
                    out.append(p.encode("punycode").decode("ascii"))
                else:
                    out.append(p)
            return ".".join(out)
        except Exception:
            return ""


def _split_host(url):
    try:
        p = urllib.parse.urlsplit(url)
        return "%s://%s" % (p.scheme, p.netloc)
    except Exception:
        return ""


# ============================================================================
# 3. Spider
# ============================================================================
class Spider(BaseSpider):

    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.host = None
        self.cfg = {
            "entry": "",
            "proxy": "",
            "proxy_play": 0,
            "timeout": 15,
        }
        self._lock = threading.Lock()
        self._opener = None
        self._last_resolve = 0.0

    # ------------------------------------------------------------- 基础接口
    def getName(self):
        return u"集芳阁云搜"

    def getDepend(self):
        return []

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self._opener = None
        except Exception:
            pass

    def init(self, extend=""):
        ext = extend
        if isinstance(ext, (bytes, bytearray)):
            ext = ext.decode("utf-8", "ignore")
        if isinstance(ext, str) and ext.strip():
            t = ext.strip()
            try:
                obj = json.loads(t)
                if isinstance(obj, dict):
                    self.cfg.update(obj)
            except Exception:
                if t.startswith("http"):
                    self.cfg["entry"] = t
        entry = _clean(self.cfg.get("entry"))
        if entry.startswith("http"):
            entry = entry.rstrip("/")
            if entry not in _SEED_HOSTS:
                _SEED_HOSTS.insert(0, entry)
            self.host = entry
        return self

    # --------------------------------------------------------------- 网络层
    def _headers(self, referer=None):
        h = {
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
        }
        ref = referer or ((self.host or _SEED_HOSTS[0]) + "/")
        if ref:
            h["Referer"] = ref
        return h

    def _get_opener(self):
        if self._opener is not None:
            return self._opener
        proxy = _clean(self.cfg.get("proxy"))
        if proxy:
            handler = _urlreq.ProxyHandler({"http": proxy, "https": proxy})
            self._opener = _urlreq.build_opener(handler)
        else:
            self._opener = _urlreq.build_opener()
        return self._opener

    def _open(self, url, referer=None, raw=False):
        """返回 (bytes, 最终URL); 失败返回 (b'', '')"""
        if _urlreq is None:
            return b"", ""
        req = _urlreq.Request(url, headers=self._headers(referer))
        try:
            r = self._get_opener().open(req, timeout=self.cfg.get("timeout", 15))
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            return data or b"", (r.geturl() or url)
        except _urlerr.HTTPError as e:
            try:
                # 有些域名会 302 到封锁页, 这里也把最终地址读出来
                return e.read() or b"", (e.geturl() if hasattr(e, "geturl") else url)
            except Exception:
                return b"", ""
        except Exception:
            return b"", ""

    def _get_html(self, url, referer=None):
        data, final = self._open(url, referer=referer)
        return data.decode("utf-8", "ignore"), final

    # ------------------------------------------------------------ 入口域名
    def _looks_like_site(self, html):
        if not html:
            return False
        if _SITE_MARK in html:
            return True
        return ("/static/jfgyunsou.js" in html) and ("ucontent" in html or "contentlist" in html)

    def _publish_candidates(self):
        """从地址发布页的 js 里捞一批当前入口域名"""
        out = []
        try:
            raw, _ = self._open(_PUBLISH_JS)
            txt = (raw or b"").decode("utf-8", "ignore")
            for host in re.findall(r'"([^"]+)"', txt):
                host = _clean(host)
                if not host or host in ("var domains = [",):
                    continue
                if host.count(".") < 1:
                    continue
                ascii_host = _to_ascii_host(host)
                if not ascii_host:
                    continue
                url = "https://" + ascii_host
                if url not in out:
                    out.append(url)
        except Exception:
            pass
        return out

    def _resolve_host(self, force=False):
        """挑一个真正能通、且是搜索站的入口域名"""
        with self._lock:
            now = time.time()
            if self.host and not force and (now - self._last_resolve) < 1800:
                return self.host
            candidates = []
            entry = _clean(self.cfg.get("entry")).rstrip("/")
            if entry.startswith("http"):
                candidates.append(entry)
            for h in _SEED_HOSTS:
                if h not in candidates:
                    candidates.append(h)
            if not self.host:
                for h in self._publish_candidates():
                    if h not in candidates:
                        candidates.append(h)
            for h in candidates:
                try:
                    html, final = self._get_html(h.rstrip("/") + "/", referer=h.rstrip("/") + "/")
                    if self._looks_like_site(html):
                        base = _split_host(final) or _split_host(h)
                        if base:
                            self.host = base
                            self._last_resolve = now
                            if base not in _SEED_HOSTS:
                                _SEED_HOSTS.append(base)
                            return self.host
                except Exception:
                    continue
            # 全没通: 拿发布页补一轮域名再试一次
            if not force:
                extra = self._publish_candidates()
                for h in extra:
                    try:
                        html, final = self._get_html(h.rstrip("/") + "/", referer=h.rstrip("/") + "/")
                        if self._looks_like_site(html):
                            base = _split_host(final) or _split_host(h)
                            if base:
                                self.host = base
                                self._last_resolve = now
                                return self.host
                    except Exception:
                        continue
            self.host = self.host or candidates[0]
            self._last_resolve = now
            return self.host

    def _fetch(self, path, referer=None):
        """取一个站内页面, 失败自动换域名重试一次"""
        self._resolve_host()
        base = self.host or _SEED_HOSTS[0]
        url = path if path.startswith("http") else (base.rstrip("/") + path)
        html, final = self._get_html(url, referer=referer or (base + "/"))
        if self._looks_like_site(html) or "ucontent" in html or "contentlist" in html:
            return html
        # 域名挂了 / 被换: 重解析一次再打
        self._resolve_host(force=True)
        base = self.host or base
        url = path if path.startswith("http") else (base.rstrip("/") + path)
        html, _ = self._get_html(url, referer=base + "/")
        return html

    # ----------------------------------------------------------- 列表解析
    _RE_LI = re.compile(r"<li>(.*?)</li>", re.S)
    _RE_ID = re.compile(r"content/([0-9a-fA-F]{16,64})\.html")
    _RE_COVER = re.compile(r"background-image:url\('([^']+)'\)")
    _RE_PIC_H = re.compile(r'class="h_d_pic"\s+value="([^"]+)"')
    _RE_NAME = re.compile(r'<div class="ctitle">\s*<p>(.*?)</p>', re.S)
    _RE_TIME = re.compile(r'class="vodtime">\s*([^<]*?)\s*<')
    _RE_DATE = re.compile(r'class="time">.*?(\d{4}-\d{2}-\d{2})', re.S)

    def _parse_items(self, html):
        out = []
        seen = set()
        if not html:
            return out
        for m in self._RE_LI.finditer(html):
            blk = m.group(1)
            mid = self._RE_ID.search(blk)
            if not mid:
                continue
            vid = mid.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            pic = ""
            mm = self._RE_COVER.search(blk)
            if mm:
                pic = mm.group(1)
            if not pic:
                mm = self._RE_PIC_H.search(blk)
                if mm:
                    pic = mm.group(1)
            name = ""
            mm = self._RE_NAME.search(blk)
            if mm:
                name = _clean(re.sub(r"<[^>]+>", "", mm.group(1)))
            dur = ""
            mm = self._RE_TIME.search(blk)
            if mm:
                dur = _clean(mm.group(1))
            date = ""
            mm = self._RE_DATE.search(blk)
            if mm:
                date = mm.group(1)
            mark = " · ".join([x for x in [dur, date] if x])
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic.replace("&amp;", "&"),
                "vod_remarks": mark,
                "vod_year": date[:4] if date else "",
            })
        return out

    def _page_count(self, html):
        """结果页页码 1/609"""
        try:
            m = re.search(r'<span class="num">\s*\d+\s*/\s*(\d+)\s*</span>', html)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 1

    def _total(self, html):
        try:
            m = re.search(u"搜索到\\s*(\\d+)\\s*个视频", html)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 0

    # --------------------------------------------------------- 搜索路由拼装
    def _search_url(self, key, pg=1, cid=0, sort=1):
        enc = jfg_encrypt(_clean(key))
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        if pg <= 1:
            return "/search-%d-%d-%s.html" % (cid, sort, enc)
        return "/search-%d-%d-%s-%d.html" % (cid, sort, enc, pg)

    # ------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter=False):
        return {"class": list(_CLASSES), "filters": {}, "list": []}

    def homeVideoContent(self):
        try:
            html = self._fetch("/toplist.html")
            return {"list": self._parse_items(html)[:_PAGE_SIZE]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = _clean(tid) or "top"
        path = ("/newlist.php?p=%d" % page) if tid == "new" else ("/toplist.php?p=%d" % page)
        lst, pc = [], 1
        try:
            html = self._fetch(path)
            lst = self._parse_items(html)
            pc = self._page_count(html)
        except Exception:
            lst = []
        return {
            "page": page,
            "pagecount": max(pc, 1),
            "limit": _PAGE_SIZE,
            "total": pc * _PAGE_SIZE,
            "list": lst,
        }

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        kw = _clean(key)
        lst, pc, total = [], 1, 0
        try:
            html = self._fetch(self._search_url(kw, page))
            lst = self._parse_items(html)
            pc = self._page_count(html)
            total = self._total(html)
            if not total and pc:
                total = pc * _PAGE_SIZE
        except Exception:
            lst = []
        return {
            "page": page,
            "pagecount": max(pc, 1),
            "limit": _PAGE_SIZE,
            "total": total,
            "list": lst,
        }

    # ------------------------------------------------------------ 详情/播放
    _RE_D_NAME = re.compile(r'<div class="single-strong">(.*?)</div>', re.S)
    _RE_D_PIC = re.compile(r"poster='([^']+)'")
    _RE_D_PLAY = re.compile(r'playdata="([^"]+)"\s*>([^<]*)<')

    def _detail(self, vid):
        vid = _clean(vid)
        if not vid:
            return None
        html = self._fetch("/content/%s.html" % vid)
        if not html:
            return None
        name = ""
        m = self._RE_D_NAME.search(html)
        if m:
            name = _clean(re.sub(r"<[^>]+>", "", m.group(1)))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = _clean(m.group(1)).split(" - ")[0]
        pic = ""
        m = self._RE_D_PIC.search(html)
        if m:
            pic = m.group(1)
        if not pic:
            m = self._RE_COVER.search(html)
            if m:
                pic = m.group(1)
        plays = []
        for url, nm in self._RE_D_PLAY.findall(html):
            url = _clean(url).replace("&amp;", "&")
            if not url or not url.startswith("http"):
                continue
            if url in [p[0] for p in plays]:
                continue
            plays.append((url, _clean(nm) or (u"线路%d" % (len(plays) + 1))))
        if not plays:
            # 兜底: 页面里任何 m3u8/mp4
            for url in re.findall(r"https?://[^\s'\"]+?\.(?:m3u8|mp4)[^\s'\"]*", html):
                if url not in [p[0] for p in plays]:
                    plays.append((url, u"线路%d" % (len(plays) + 1)))
        if not plays and not name:
            return None
        return {"id": vid, "name": name, "pic": pic, "plays": plays}

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = _clean(ids[0]) if ids else ""
        else:
            vid = _clean(ids)
        if "|" in vid:
            vid = vid.split("|")[0]
        if vid.startswith("http"):
            # 直接给的播放地址: 反查不到 id 就原样交给播放器
            return {"list": [{
                "vod_id": vid,
                "vod_name": u"集芳阁云搜",
                "vod_pic": "",
                "vod_play_from": u"集芳阁",
                "vod_play_url": u"直链$" + vid,
            }]}
        d = self._detail(vid)
        if not d:
            return {"list": []}
        if d["plays"]:
            urls = "#".join([(nm + "$" + url) for url, nm in d["plays"]])
        else:
            urls = u"无$"
        return {"list": [{
            "vod_id": vid,
            "vod_name": d["name"],
            "vod_pic": d["pic"],
            "vod_remarks": "",
            "vod_play_from": u"集芳阁",
            "vod_play_url": urls,
        }]}

    def playerContent(self, flag, vid, vipFlags=None):
        raw = _clean(vid)
        url = ""
        if raw.startswith("http"):
            url = raw
        else:
            cid = raw.split("|")[0] if "|" in raw else raw
            d = self._detail(cid)
            if d and d["plays"]:
                url = d["plays"][0][0]
        if not url:
            return {"parse": 0, "playUrl": "", "header": ""}
        ref = (self.host or _SEED_HOSTS[0]) + "/"
        header = json.dumps({"User-Agent": _UA, "Referer": ref})
        if int(self.cfg.get("proxy_play", 0) or 0) == 1:
            b = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
            return {"parse": 0, "playUrl": "proxy://do=py&type=m3u8&p=" + b, "header": header}
        return {"parse": 0, "playUrl": url, "header": header}

    # ------------------------------------------------------------- 本机代理
    def localProxy(self, param):
        """proxy://do=py&type=m3u8|ts&p=<base64>"""
        try:
            if isinstance(param, (bytes, bytearray)):
                param = param.decode("utf-8", "ignore")
            q = urllib.parse.parse_qs(_clean(param))
            typ = (q.get("type") or [""])[0]
            p = (q.get("p") or [""])[0]
            if not p:
                return json.dumps({"code": 404, "content-type": "text/plain", "content": ""})
            p += "=" * (-len(p) % 4)
            path = base64.urlsafe_b64decode(p.encode("ascii")).decode("utf-8", "ignore")
            if not path.startswith("http"):
                return json.dumps({"code": 404, "content-type": "text/plain", "content": ""})
            ref = (self.host or _SEED_HOSTS[0]) + "/"
            raw, _ = self._open(path, referer=ref)
            if typ == "m3u8":
                if not raw:
                    return json.dumps({"code": 404, "content-type": "text/plain", "content": ""})
                txt = raw.decode("utf-8", "ignore")
                base = path.split("?")[0].rsplit("/", 1)[0] + "/"
                out_lines = []
                for line in txt.splitlines():
                    s = line.strip()
                    if not s:
                        out_lines.append(line)
                        continue
                    if s.startswith("#"):
                        def _rep(m):
                            u = m.group(1)
                            full = u if u.startswith("http") else (base + u)
                            b2 = base64.urlsafe_b64encode(full.encode()).decode().rstrip("=")
                            return 'URI="proxy://do=py&type=ts&p=%s"' % b2
                        out_lines.append(re.sub(r'URI="([^"]+)"', _rep, line))
                    else:
                        full = s if s.startswith("http") else (base + s)
                        b2 = base64.urlsafe_b64encode(full.encode()).decode().rstrip("=")
                        out_lines.append("proxy://do=py&type=ts&p=" + b2)
                body = "\n".join(out_lines)
                return json.dumps({
                    "code": 200,
                    "content-type": "application/vnd.apple.mpegurl",
                    "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
                })
            if typ == "ts":
                return json.dumps({
                    "code": 200 if raw else 404,
                    "content-type": "video/mp2t",
                    "content": base64.b64encode(raw or b"").decode("ascii"),
                })
        except Exception:
            pass
        return json.dumps({"code": 404, "content-type": "text/plain", "content": ""})

    # ------------------------------------------------------------- 自测入口
    def selftest(self, args):
        cmd = args[0] if args else "host"
        proxy = ""
        if "--proxy" in args:
            i = args.index("--proxy")
            if i + 1 < len(args):
                proxy = args[i + 1]
            args = [a for a in args if a != "--proxy" and a != proxy]
            cmd = args[0] if args else "host"
        if proxy:
            self.cfg["proxy"] = proxy
            self._opener = None
        if cmd == "host":
            h = self._resolve_host(force=True)
            print("HOST =", h)
            return 0
        if cmd == "home":
            d = self.homeVideoContent()
            print("首页 %d 条" % len(d.get("list", [])))
            for it in d.get("list", [])[:5]:
                print("  ", it["vod_id"], it["vod_name"][:40], "|", it["vod_remarks"])
            return 0
        if cmd == "search":
            kw = args[1] if len(args) > 1 else u"红"
            pg = args[2] if len(args) > 2 else "1"
            d = self.searchContent(kw, False, pg)
            print(u"搜索 %s 第%s页: 共 %s 条 / %s 页, 本页 %d 条" % (
                kw, pg, d["total"], d["pagecount"], len(d["list"])))
            for it in d["list"][:5]:
                print("  ", it["vod_id"], it["vod_name"][:40], "|", it["vod_remarks"], "|", it["vod_pic"][:70])
            if d["list"]:
                print("DETAIL_TEST_ID =", d["list"][0]["vod_id"])
            return 0
        if cmd == "cat":
            tid = args[1] if len(args) > 1 else "top"
            pg = args[2] if len(args) > 2 else "1"
            d = self.categoryContent(tid, pg)
            print(u"分类 %s 第%s页: %d 条 (共 %s 页)" % (tid, pg, len(d["list"]), d["pagecount"]))
            for it in d["list"][:5]:
                print("  ", it["vod_id"], it["vod_name"][:40], "|", it["vod_remarks"])
            return 0
        if cmd in ("detail", "play"):
            vid = args[1] if len(args) > 1 else ""
            if not vid:
                print("用法: detail <vod_id>")
                return 1
            d = self.detailContent([vid])
            lst = d.get("list") or []
            if not lst:
                print("详情拿不到:", vid)
                return 1
            v = lst[0]
            print(u"标题:", v.get("vod_name"))
            print(u"封面:", v.get("vod_pic"))
            print(u"线路:", v.get("vod_play_url"))
            if cmd == "play":
                first = (v.get("vod_play_url") or "").split("#")[0].split("$")[-1]
                pc = self.playerContent("", first)
                print(u"playerContent =", json.dumps(pc, ensure_ascii=False))
            return 0
        print(__doc__)
        return 0


# ============================================================================
if __name__ == "__main__":
    _sp = Spider()
    _sp.init("")
    try:
        sys.exit(_sp.selftest(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
