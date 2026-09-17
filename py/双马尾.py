import re
import json
from urllib.parse import urljoin, quote, unquote

try:
    import requests
except ImportError:
    requests = None


class Spider:
    def __init__(self):
        self.host = "https://172608.smawei.top"
        self.session = None
        self.s = None
        self.sess = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://172608.smawei.top/"
        }

    def getDependence(self):
        return []

    def init(self, extend=""):
        if isinstance(extend, str) and extend.strip().startswith("{"):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        if requests:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            self.s = self.session
            self.sess = self.session

    def _get(self, url):
        if requests and self.session:
            try:
                r = self.session.get(url, timeout=15)
                if r.encoding and r.encoding.lower() == "iso-8859-1" and r.apparent_encoding:
                    r.encoding = r.apparent_encoding
                return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                try:
                    return data.decode("utf-8")
                except Exception:
                    return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self.host.rstrip("/") + "/", url)

    def _clean(self, text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        return text.strip()

    def _extract_m3u8(self, html):
        m3u8 = ""
        m = re.search(r"hls\.loadSource\(['\"]([^'\"]+)['\"]\)", html)
        if not m:
            m = re.search(r"video\.src\s*=\s*['\"]([^'\"]+)['\"]", html)
        if not m:
            m = re.search(r"var\s+now\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]", html)
        if not m:
            m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    m3u8 = obj.get("url", "")
                except Exception:
                    pass
        if not m and not m3u8:
            m = re.search(r"player_data\s*=\s*(\{.*?\})\s*;?\s*</script>", html, re.S)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    m3u8 = obj.get("url", "")
                except Exception:
                    pass
        if not m and not m3u8:
            m = re.search(r"<video[^>]+src=\"([^\"]+\.m3u8[^\"]*)\"", html)
        if not m and not m3u8:
            m = re.search(r"<iframe[^>]+src=\"([^\"]+)\"", html)
            if m:
                iframe_src = self._fix_url(m.group(1))
                if iframe_src.startswith("http"):
                    iframe_html = self._get(iframe_src)
                    if iframe_html:
                        m = re.search(r"(https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", iframe_html)
        if m and not m3u8:
            m3u8 = m.group(1)
        return m3u8

    def _resolve_m3u8(self, master_url):
        text = self._get(master_url)
        if not text or "#EXTM3U" not in text:
            return master_url
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            return master_url
        sub = lines[0]
        if sub.startswith("http"):
            return sub
        base = master_url.rsplit("/", 1)[0] + "/"
        if sub.startswith("/"):
            parsed = re.search(r"(https?://[^/]+)", master_url)
            if parsed:
                return parsed.group(1) + sub
        return base + sub

    def _clean_m3u8(self, text, m3u8_url):
        if not text or "#EXTM3U" not in text:
            return text
        lines = text.replace("\r", "").split("\n")
        out = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("#EXTINF"):
                extinf = line
                tags = []
                j = i + 1
                while j < len(lines):
                    l2 = lines[j].strip()
                    if not l2:
                        j += 1
                        continue
                    if l2.startswith("#EXT") and not l2.startswith("#EXTINF"):
                        tags.append(l2)
                        j += 1
                        continue
                    if not l2.startswith("#"):
                        break
                    j += 1
                if j < len(lines):
                    ts = lines[j].strip()
                    is_ad = False
                    if ts.startswith("/") and "/20260731/" in ts:
                        is_ad = True
                    if not is_ad:
                        out.append(extinf)
                        out.extend(tags)
                        if ts.startswith("/"):
                            parsed = re.search(r"(https?://[^/]+)", m3u8_url)
                            if parsed:
                                ts = parsed.group(1) + ts
                        elif not ts.startswith("http"):
                            ts = m3u8_url.rsplit("/", 1)[0] + "/" + ts
                        out.append(ts)
                    i = j + 1
                else:
                    i += 1
            elif line.startswith("#EXTM3U"):
                out.append(line)
                i += 1
            elif line.startswith("#EXT-X-ENDLIST"):
                out.append(line)
                i += 1
            elif line.startswith("#EXT-X-DISCONTINUITY"):
                i += 1
            elif line.startswith("#EXT-X-MEDIA-SEQUENCE"):
                i += 1
            elif line.startswith("#EXT-X-"):
                out.append(line)
                i += 1
            else:
                i += 1
        return "\n".join(out)

    def _proxy_url(self, m3u8_url):
        return "proxy://do=localProxy&url=" + quote(m3u8_url, safe="") + "&referer=" + quote(self.host + "/", safe="")

    def homeContent(self, filter=None):
        return {
            "class": [
                {"type_id": "1", "type_name": "日韩"},
                {"type_id": "2", "type_name": "国产"},
                {"type_id": "3", "type_name": "欧美"},
                {"type_id": "4", "type_name": "动漫"}
            ],
            "filters": {}
        }

    def homeVideoContent(self):
        return {"list": []}

    def _parse_list(self, html):
        items = []
        seen = set()
        pattern = r'<div class="item[^"]*"[^>]*>.*?<a class="clip-link" href="([^"]+)"[^>]*>.*?<img[^>]*(?:src|data-original)="([^"]+)"[^>]*>.*?<h2[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h2>'
        for href, pic, title in re.findall(pattern, html, re.S):
            vid = self._fix_url(href)
            if vid in seen:
                continue
            seen.add(vid)
            items.append({
                "vod_id": vid,
                "vod_name": self._clean(title),
                "vod_pic": self._fix_url(pic)
            })
        return items

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        url = f"{self.host}/list.php?cid={tid}&page={pg}"
        html = self._get(url)
        items = self._parse_list(html)
        has_next = bool(re.search(r'<a[^>]*href="[^"]*page=\d+"[^>]*>\d+</a>', html))
        pagecount = int(pg) + 1 if has_next else int(pg)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 24,
            "total": 24
        }

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids or "")
        html = self._get(vid)
        title = ""
        t_match = re.search(r'<title>(.*?)</title>', html, re.S)
        if t_match:
            raw = t_match.group(1)
            try:
                raw = raw.encode("latin1").decode("utf-8")
            except Exception:
                pass
            title = self._clean(raw).split(" -")[0].strip()
        pic = ""
        p_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if not p_match:
            p_match = re.search(r'<img[^>]*(?:src|data-original)="([^"]+)"[^>]*width="192"', html)
        if p_match:
            pic = self._fix_url(p_match.group(1))
        desc = "资源来自网络，本站仅做聚合展示。"
        d_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
        if d_match:
            raw_desc = d_match.group(1)
            try:
                raw_desc = raw_desc.encode("latin1").decode("utf-8")
            except Exception:
                pass
            desc = self._clean(raw_desc) or desc
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "双马尾",
                "vod_play_url": "播放$" + vid
            }]
        }

    def searchContent(self, key, quick=False, pg="1"):
        key = key[:30] if len(key) > 30 else key
        url = f"{self.host}/search.php?keyword={quote(key)}&page={pg}"
        html = self._get(url)
        items = self._parse_list(html)
        has_next = bool(re.search(r'<a[^>]*href="[^"]*page=\d+"[^>]*>\d+</a>', html))
        pagecount = int(pg) + 1 if has_next else int(pg)
        return {
            "list": items,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 24,
            "total": 24
        }

    def playerContent(self, flag, ids, vipFlags=None):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids or "")
        if not vid:
            return {"parse": 1, "jx": 0, "playUrl": "", "url": "", "header": {}}
        if ".m3u8" in vid:
            proxy = self._proxy_url(vid)
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": proxy,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                },
                "format": "application/x-mpegURL"
            }
        html = self._get(vid)
        m3u8 = self._extract_m3u8(html)
        if m3u8 and m3u8.startswith("http"):
            sub = self._resolve_m3u8(m3u8)
            if sub and sub.startswith("http"):
                m3u8 = sub
        if not m3u8:
            return {"parse": 1, "jx": 0, "playUrl": "", "url": vid, "header": {}}
        proxy = self._proxy_url(m3u8)
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": proxy,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/"
            },
            "format": "application/x-mpegURL"
        }

    def localProxy(self, param):
        if isinstance(param, str):
            if param.startswith("proxy://"):
                param = param[8:]
            try:
                pairs = param.split("&")
                d = {}
                for p in pairs:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        d[k] = unquote(v)
                param = d
            except Exception:
                param = {}
        if not isinstance(param, dict):
            param = {}
        url = param.get("url", "")
        if not url:
            return [404, "text/plain", b"Not Found", {}]
        text = self._get(url)
        if not text:
            return [404, "text/plain", b"Not Found", {}]
        cleaned = self._clean_m3u8(text, url)
        return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8"), {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/vnd.apple.mpegurl"
        }]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        return False

    def action(self, action):
        return {}

    def destroy(self):
        return None
