# -*- coding: utf-8 -*-
"""
久久热 (jjri.cc) —— TVBox / 影视仓 Python 爬虫
=================================================

站点类型：服务端渲染 HTML（不是苹果 CMS，没有 JSON 接口）
  - 列表页   /category/cateN/P/            带分页，每页 20 条
  - 大分类   /group-category/cateN/        一次给 300+ 条，无分页
  - 搜索     /search/<关键词>/P/
  - 详情页   /video/<id>/
  - 播放直链 详情页里的 window.__ARCHIVE_PLAYER__.rawPath 就是 m3u8 相对路径，
            前面拼上同页 cdn_lines 里的 cdnLine 就是完整直链（双线路）

本文件只用 Python 标准库，TVBox 手机端（没第三方库的环境）能直接跑。

站点配置示例（配置 json 的 sites 里加一条）：

{
  "key": "jjri",
  "name": "久久热",
  "type": 3,
  "api": "jjri_tvbox.py",
  "searchable": 1,
  "quickSearch": 1,
  "filterable": 0
}

可选参数（填在 site 的 ext 里，JSON 字符串）：

  {"host": "https://自定义镜像"}   手动指定入口，默认自动探测
  {"all_cats": 1}                  分类列表里追加全部 237 个演员 / 厂牌 / 题材子分类
  {"proxy": 1}                     播放改走本机代理（播放器不给 CDN 发请求时用）
  {"no_cache": 1}                  关掉 10 分钟缓存，每次都取最新

本地自测：
  python3 jjri_tvbox.py            # 跑一遍全链路
  python3 jjri_tvbox.py home       # 只看首页
  python3 jjri_tvbox.py cat cate38
  python3 jjri_tvbox.py detail 9761994279891067260
  python3 jjri_tvbox.py search 护士
  python3 jjri_tvbox.py play 9761994279891067260
"""

import json
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TIMEOUT = 20
CACHE_TTL = 600

# 入口域名池，第一个不通自动往后退（久久热的域名是轮换制的）
HOSTS = [
    "https://jjri.cc",
    "https://www.jjri.cc",
    "https://xxvv1.tw",
]

# 大分类：/group-category/<id>/ 一次吐 300+ 条
GROUPS = [
    ("cate38", "网黄"),
    ("cate68", "传媒"),
    ("cate93", "福利姬"),
    ("cate114", "黑料"),
    ("cate127", "P站"),
    ("cate147", "探花"),
    ("cate163", "乱伦"),
    ("cate174", "三级片"),
    ("cate185", "直播"),
    ("cate199", "制服"),
    ("cate213", "日韩"),
    ("cate236", "欧美"),
    ("cate257", "综艺"),
    ("cate278", "影院"),
]

# 热门板块：/category/<id>/<页码>/ 每页 20 条，可以一直翻
SECTIONS = [
    ("cate4", "福利姬"),
    ("cate5", "主播勾引"),
    ("cate6", "传媒精选"),
    ("cate7", "JVID"),
    ("cate8", "锅锅酱"),
    ("cate9", "巨乳大奶"),
    ("cate10", "抖音风"),
    ("cate11", "制服诱惑"),
    ("cate12", "樱花小猫"),
    ("cate13", "反差女友"),
    ("cate14", "探花约炮"),
    ("cate15", "调教性奴"),
    ("cate16", "ASMR"),
    ("cate17", "颜值网红"),
    ("cate18", "高潮自慰"),
    ("cate19", "欧美洋马"),
    ("cate20", "露出野战"),
    ("cate21", "SWAG"),
    ("cate22", "热门吃瓜"),
    ("cate23", "绿帽淫妻"),
    ("cate24", "群交滥交"),
    ("cate25", "风骚少妇"),
    ("cate26", "逆天乱伦"),
    ("cate27", "AI女神"),
    ("cate28", "风骚母狗"),
    ("cate29", "断袖男同"),
    ("cate30", "原创短剧"),
    ("cate31", "足交口爆"),
    ("cate32", "炮桶小屋"),
    ("cate33", "无套内射"),
    ("cate34", "黑鬼长屌"),
    ("cate35", "女同百合"),
    ("cate36", "伪娘人妖"),
    ("cate37", "吴梦梦"),
]

# 导航里的全部子分类（演员 / 厂牌 / 题材），ext 里开 all_cats 才会用到
SUBCATS = [
    ("网黄",
     [("cate39","umate原创"),("cate40","Naomii"),("cate41","YuiPeach"),("cate42","唐伯虎"),("cate43","饼干姐姐"),("cate44","台北娜娜"),("cate45","MASKU"),("cate46","Xreind"),("cate47","小桃酱"),("cate48","安安小晗"),("cate49","柚子猫"),("cate50","王梨奈"),("cate51","辛尤里"),("cate52","粉色情人"),("cate53","阿朱"),("cate54","奶咪"),("cate55","有根棒棒"),("cate56","不见星空"),("cate57","Kitty"),("cate58","妮可"),("cate59","Cos女神"),("cate60","玩偶姊姊"),("cate61","司雨"),("cate62","谭晓彤"),("cate63","刘玥"),("cate64","Vivian"),("cate65","多乙"),("cate66","朱可儿"),("cate67","周大萌")]),
    ("传媒",
     [("cate69","麻豆传媒"),("cate70","蜜桃传媒"),("cate71","葫芦影业"),("cate72","香蕉视频"),("cate73","兔子先生"),("cate74","OnlyFans"),("cate75","91制片厂"),("cate76","ED Mosaic"),("cate77","IBiZa Media"),("cate78","SA国际传媒"),("cate79","乌托邦"),("cate80","大象传媒"),("cate81","天美传媒"),("cate82","扣扣传媒"),("cate83","性视界"),("cate84","星空传媒"),("cate85","映秀传媒"),("cate86","杏吧原版"),("cate87","果冻传媒"),("cate88","爱神传媒"),("cate89","爱豆传媒"),("cate90","精东影业"),("cate91","糖心Vlog"),("cate92","萝莉社")]),
    ("福利姬",
     [("cate94","桥本香菜"),("cate95","米菲兔"),("cate96","捅主任"),("cate97","npxvip"),("cate98","Andm"),("cate99","liburin"),("cate100","谭晓彤"),("cate101","小水水"),("cate102","小鸟酱"),("cate103","HAMAR"),("cate104","铃木美子"),("cate105","占星猫"),("cate106","芋圆呀"),("cate107","小丁妹妹"),("cate108","米娜学姐"),("cate109","米胡桃"),("cate110","萌白酱"),("cate111","麻酥酥"),("cate112","白桃少女"),("cate113","八月未央")]),
    ("黑料",
     [("cate115","网红大瓜"),("cate116","校园猛料"),("cate117","大奶孕妇"),("cate118","独家泄密"),("cate119","热门吃瓜"),("cate120","潜规则"),("cate121","反差泄露"),("cate122","裸贷风波"),("cate123","轮奸呀"),("cate124","饥渴新娘"),("cate125","强奸醉奸"),("cate126","迷奸")]),
    ("P站",
     [("cate128","AnnyWalker"),("cate129","MilaAzul"),("cate130","Comatozze"),("cate131","Honey"),("cate132","Luxury"),("cate133","kittyxk"),("cate134","JennyKitty"),("cate135","LeoLulu"),("cate136","PurpleB"),("cate137","MilaLioness"),("cate138","Pinklov"),("cate139","PornForce"),("cate140","Shinaryen"),("cate141","EvaElfie"),("cate142","Candy"),("cate143","Kenzie"),("cate144","CarlaCu"),("cate145","webto"),("cate146","SiaSib")]),
    ("探花",
     [("cate148","沈先生"),("cate149","赵总寻花"),("cate150","小天探花"),("cate151","换妻探花"),("cate152","七天探花"),("cate153","千人斩"),("cate154","午夜尋花"),("cate155","91大神"),("cate156","按摩会所"),("cate157","韩国嫖妓"),("cate158","陈先生"),("cate159","太子寻花"),("cate160","翼屌寻花"),("cate161","小宝寻花"),("cate162","文轩探花")]),
    ("乱伦",
     [("cate164","兄妹情深"),("cate165","最爱岳母"),("cate166","淫荡儿媳"),("cate167","淫乱父女"),("cate168","照顾小侄女"),("cate169","师生恋情"),("cate170","母子情深"),("cate171","姐弟爱恋"),("cate172","调教嫂子"),("cate173","照顾小姨子")]),
    ("三级片",
     [("cate175","韩国三级"),("cate176","香港三级"),("cate177","台湾三级"),("cate178","欧洲情色"),("cate179","俄乌色情"),("cate180","越南菲律宾"),("cate181","印度情色"),("cate182","日本三级"),("cate183","美国色情"),("cate184","东南亚情色")]),
    ("直播",
     [("cate186","多人淫交"),("cate187","车震直播"),("cate188","日韩主播"),("cate189","户外直播"),("cate190","抖音网红"),("cate191","主播勾引"),("cate192","快手网红"),("cate193","对着你"),("cate194","AVOVE"),("cate195","MISSWAEM"),("cate196","妖骚蛇姬"),("cate197","大啵啵"),("cate198","虎牙辣妹")]),
    ("制服",
     [("cate200","古装诱惑"),("cate201","萝莉塔"),("cate202","空姐诱惑"),("cate203","丝袜诱惑"),("cate204","职场OL"),("cate205","清涩校服"),("cate206","三点泳装"),("cate207","JK短裙"),("cate208","女仆装"),("cate209","护士打针"),("cate210","国风旗袍"),("cate211","体操运动"),("cate212","其他制服")]),
    ("日韩",
     [("cate214","骑兵精选"),("cate215","高清优质"),("cate216","FC2高清"),("cate217","VR视觉"),("cate218","人妻巨乳"),("cate219","少女制服"),("cate220","药物迷奸"),("cate221","强暴系列"),("cate222","轮奸系列"),("cate223","筱田佑"),("cate224","森澤佳奈"),("cate225","三上悠亜"),("cate226","AkihoYoshizawa"),("cate227","神宮寺奈緒"),("cate228","藤森里穗"),("cate229","松本一香"),("cate230","乙爱丽丝"),("cate231","沙月芽衣"),("cate232","姬咲華"),("cate233","AliceOtsu"),("cate234","佐山愛"),("cate235","水果解說")]),
    ("欧美",
     [("cate237","推荐观看"),("cate238","颜值少女"),("cate239","网红洋马"),("cate240","CandyLove"),("cate241","丝袜制服"),("cate242","欧美剧情"),("cate243","AngelX"),("cate244","商场性交"),("cate245","情色按摩"),("cate246","捷克搭讪"),("cate247","肤若凝脂"),("cate248","SweetieFox"),("cate249","Morgpie"),("cate250","DianRider"),("cate251","BadCuteGirl"),("cate252","Ailish"),("cate253","SamanthaFlair"),("cate254","滥交群交"),("cate255","巨乳少女"),("cate256","黑人大屌")]),
    ("综艺",
     [("cate258","深夜保健室"),("cate259","王竹子教学"),("cate260","中指通一下"),("cate261","Misa米砂"),("cate262","小哥哥艾理"),("cate263","Dr.She"),("cate264","1G老湿"),("cate265","两性知识"),("cate266","麻豆综艺"),("cate267","户外搭讪"),("cate268","性愛大秀"),("cate269","女优训练营"),("cate270","情趣k歌房"),("cate271","小鹏奇啪行"),("cate272","性爱自修室"),("cate273","女神体育祭"),("cate274","屁孩日记"),("cate275","薇傲的性趣"),("cate276","一三蜜桃说"),("cate277","Carrie雨千")]),
    ("影院",
     [("cate279","喜剧片"),("cate280","古装片"),("cate281","武侠片"),("cate282","枪战片"),("cate283","灾难片"),("cate284","冒险片"),("cate285","犯罪片"),("cate286","科幻片"),("cate287","动作片"),("cate288","恐怖片")]),
]


# TVBox 的 py 加载器会注入 base.spider.Spider，本地直接跑时兜底一个空类
try:
    from base.spider import Spider as BaseSpider  # type: ignore
except Exception:
    class BaseSpider(object):
        pass


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def _clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
          .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", s).strip()


def _abs(url, host):
    """补全成绝对地址"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if re.match(r"^https?://", url, re.I):
        return url
    if url.startswith("/"):
        return host.rstrip("/") + url
    return host.rstrip("/") + "/" + url


class _Http(object):
    """极简 HTTP 客户端：多入口自动切换 + 重试"""

    def __init__(self, hosts=None):
        self.hosts = list(hosts or HOSTS)
        self.host = self.hosts[0]
        self._probed = False

    # ---------- 入口探测 ----------

    def probe(self):
        for h in self.hosts:
            try:
                html = self._get(h.rstrip("/") + "/", referer=None, retry=1)
                if html and "久久热" in html:
                    self.host = h.rstrip("/")
                    self._probed = True
                    return self.host
            except Exception:
                continue
        self.host = self.hosts[0].rstrip("/")
        self._probed = True
        return self.host

    def ensure(self):
        if not self._probed:
            self.probe()
        return self.host

    def switch(self):
        """当前入口挂了，换下一个"""
        self.hosts = self.hosts[1:] + self.hosts[:1]
        self.host = self.hosts[0].rstrip("/")
        return self.host

    # ---------- 请求 ----------

    def _get(self, url, referer=None, retry=1):
        last = None
        for _ in range(max(1, retry)):
            try:
                req = urllib.request.Request(url)
                req.add_header("User-Agent", UA)
                req.add_header("Accept", "text/html,application/xhtml+xml,*/*;q=0.8")
                req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
                if referer:
                    req.add_header("Referer", referer)
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    raw = r.read()
                for enc in ("utf-8", "gbk", "latin-1"):
                    try:
                        return raw.decode(enc)
                    except Exception:
                        continue
                return raw.decode("utf-8", "ignore")
            except Exception as e:
                last = e
                time.sleep(0.4)
        if last:
            raise last
        return ""

    def get(self, path, referer=None, retry=2):
        """path 可以是相对路径，也可以是完整 URL"""
        if re.match(r"^https?://", path or "", re.I):
            return self._get(path, referer=referer, retry=retry)
        host = self.ensure()
        url = host + ("" if str(path).startswith("/") else "/") + str(path)
        try:
            return self._get(url, referer=referer or (host + "/"), retry=retry)
        except Exception:
            alt = self.switch()
            url2 = alt + ("" if str(path).startswith("/") else "/") + str(path)
            return self._get(url2, referer=referer or (alt + "/"), retry=retry)

    def get_bytes(self, url, referer=None, rng=None, retry=2):
        last = None
        for _ in range(max(1, retry)):
            try:
                req = urllib.request.Request(url)
                req.add_header("User-Agent", UA)
                if referer:
                    req.add_header("Referer", referer)
                if rng:
                    req.add_header("Range", rng)
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    return r.read(), dict(r.headers)
            except Exception as e:
                last = e
                time.sleep(0.4)
        if last:
            raise last
        return b"", {}


# --------------------------------------------------------------------------
# HTML 解析
# --------------------------------------------------------------------------

# 列表卡片的两种形态：主列表 tp5-section-content__item / 详情页右侧 tp5-detail-right-item
# 广告位虽然也是 <li class="...__item">，但 href 不是 /video/<纯数字>/，会被自然过滤掉
_CARD_RE = re.compile(r'<a[^>]*href="(/video/(\d+)/)"[^>]*>(.*?)</a>', re.S)
_PIC_RE = re.compile(r'data-src="([^"]+)"')
_DUR_RE = re.compile(r'tp5-duration">([^<]*)<')
_TAG_RE = re.compile(r'data-link="/tag/([^"/]+)/"')
_TITLE_RE = re.compile(r"<h[34][^>]*>(.*?)</h[34]>", re.S)


def parse_list(html, host):
    """解析列表页 / 首页 / 详情页右侧的所有影片卡片"""
    out, seen = [], set()
    for m in _CARD_RE.finditer(html or ""):
        href, vid, body = m.group(1), m.group(2), m.group(3)
        if vid in seen:
            continue
        seen.add(vid)

        name = ""
        tm = _TITLE_RE.search(body)
        if tm:
            name = _clean(tm.group(1))
        if not name:
            am = re.search(r'alt="([^"]*)"', body)
            if am:
                name = _clean(am.group(1))
        if not name:
            name = vid

        pic = ""
        pm = _PIC_RE.search(body)
        if pm:
            pic = _abs(pm.group(1), host)

        remark = ""
        dm = _DUR_RE.search(body)
        if dm:
            remark = _clean(dm.group(1))

        tags = [t for t in _TAG_RE.findall(body) if t][:3]
        if tags:
            remark = (remark + " " + "/".join(tags)).strip()

        out.append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
        })
    return out


def parse_detail(html, host, vid):
    """解析详情页：标题 / 封面 / 标签 / 分类 / 日期 / 播放地址"""
    h = html or ""
    v = {
        "vod_id": vid,
        "vod_name": "",
        "vod_pic": "",
        "type_name": "",
        "vod_year": "",
        "vod_area": "",
        "vod_remarks": "",
        "vod_actor": "",
        "vod_director": "",
        "vod_content": "",
        "vod_play_from": "",
        "vod_play_url": "",
    }

    # ---- 播放配置：rawPath + cdn_lines ----
    raw_path = ""
    lines = []
    m = re.search(r"window\.__ARCHIVE_PLAYER__\s*=\s*(\{.*?\})\s*;", h, re.S)
    if m:
        try:
            cfg = json.loads(m.group(1))
            raw_path = cfg.get("rawPath") or ""
            if not v["vod_pic"]:
                v["vod_pic"] = cfg.get("posterImg") or ""
            if cfg.get("cdnLine"):
                lines.append(("国际线路01", cfg["cdnLine"]))
        except Exception:
            pass

    m = re.search(r"cdn_lines\s*=\s*'(\[.*?\])'", h, re.S)
    if not m:
        m = re.search(r'cdn_lines\s*=\s*"(\[.*?\])"', h, re.S)
    if m:
        try:
            for item in json.loads(m.group(1)):
                base = (item.get("cdnLine") or "").rstrip("/")
                name = item.get("lineName") or item.get("cdnName") or ""
                if base and base not in [x[1] for x in lines]:
                    lines.append((name or ("线路%d" % (len(lines) + 1)), base))
        except Exception:
            pass

    # 兜底：从 rawPath 里推 CDN
    if raw_path and not lines:
        pm = re.search(r'"(https?://[^"]{6,60})"', h)
        if pm:
            lines.append(("线路01", pm.group(1)))

    # ---- 标题 ----
    for pat in (r'<h1 class="only-pc"[^>]*>(.*?)</h1>',
                r'<h2 class="[^"]*tp5-detail-title[^"]*"[^>]*>(.*?)</h2>',
                r"<title>(.*?)</title>"):
        tm = re.search(pat, h, re.S)
        if tm:
            v["vod_name"] = _clean(tm.group(1)).split(" - ")[0].strip()
            if v["vod_name"]:
                break

    # ---- 封面兜底 ----
    if not v["vod_pic"]:
        pm = re.search(r'<img[^>]+data-src="(https?://[^"]+)"[^>]*>', h)
        if pm:
            v["vod_pic"] = pm.group(1)
    v["vod_pic"] = _abs(v["vod_pic"], host)

    # ---- 标签 / 系列 / 播放量 ----
    tags = []
    tm = re.search(r'tp5-vd-tags(.*?)tp5-vd-shares', h, re.S)
    if tm:
        tags = [_clean(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", tm.group(1), re.S)]
        tags = [t for t in tags if t]
    series = ""
    sm = re.search(r"系列：\s*<a[^>]*>(.*?)</a>", h, re.S)
    if sm:
        series = _clean(sm.group(1))
    views = ""
    vm = re.search(r'tp5-eye2"[^>]*>(.*?)<', h, re.S)
    if vm:
        views = _clean(vm.group(1))

    # ---- 日期 ----
    date_str = ""
    dm = re.search(r'"datePublished"\s*:\s*"([^"]+)"', h)
    if dm:
        date_str = dm.group(1)
        v["vod_year"] = date_str[:4]

    v["type_name"] = series or "久久热"
    v["vod_director"] = series
    v["vod_actor"] = "/".join(tags)
    v["vod_remarks"] = " ".join(
        [x for x in (views, date_str[:10] if date_str else "") if x]).strip()

    # ---- 简介 ----
    intro = ""
    im = re.search(r'"description"\s*:\s*"([^"]*)"', h)
    if im:
        intro = _clean(im.group(1))
    if not intro:
        bits = []
        if series:
            bits.append("系列：" + series)
        if tags:
            bits.append("标签：" + "/".join(tags))
        if views:
            bits.append("播放：" + views)
        if date_str:
            bits.append("日期：" + date_str)
        intro = "  ".join(bits) if bits else (v["vod_name"] or "久久热")
    v["vod_content"] = intro

    # ---- 拼播放列表：一条正片 × N 条线路 ----
    if raw_path:
        rp = raw_path if raw_path.startswith("/") else "/" + raw_path
        froms, urls = [], []
        for name, base in lines:
            base = (base or "").rstrip("/")
            if not base:
                continue
            froms.append(name or ("线路%d" % (len(froms) + 1)))
            urls.append("正片$" + base + rp)
        if froms:
            v["vod_play_from"] = "$$$".join(froms)
            v["vod_play_url"] = "$$$".join(urls)
    return v


# --------------------------------------------------------------------------
# 本机代理（可选）：把 m3u8 里的密钥路径改写成绝对地址，顺手补 Referer
# --------------------------------------------------------------------------

def _rw_uri(uri, target):
    """把播放列表里的相对地址补成绝对，再包一层本机代理"""
    if not uri:
        return uri
    if re.match(r"^https?://", uri, re.I):
        absolute = uri
    else:
        p = urllib.parse.urlparse(target)
        if uri.startswith("/"):
            absolute = "%s://%s%s" % (p.scheme, p.netloc, uri)
        else:
            absolute = target.rsplit("/", 1)[0] + "/" + uri.lstrip("/")
    return "/jjri?u=" + urllib.parse.quote(absolute, safe="")


def _rewrite_playlist(text, target):
    """m3u8 里的密钥 / 分片地址全部改走本机代理（顺手把相对路径补成绝对）"""
    out = []
    for ln in (text or "").splitlines():
        if ln.startswith("#EXT-X-KEY") or ln.startswith("#EXT-X-MAP"):
            ln = re.sub(r'(URI=)"([^"]+)"',
                        lambda mo: '%s"%s"' % (mo.group(1), _rw_uri(mo.group(2), target)),
                        ln)
            out.append(ln)
            continue
        if ln and not ln.startswith("#"):
            out.append(_rw_uri(ln, target))
            continue
        out.append(ln)
    return "\n".join(out) + "\n"


class _Proxy(object):
    def __init__(self, http):
        self.http = http
        self.port = 0
        self._started = False

    def start(self):
        if self._started:
            return self.port
        from http.server import BaseHTTPRequestHandler, HTTPServer

        http = self.http

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _serve(self):
                q = urllib.parse.urlparse(self.path).query
                target = (urllib.parse.parse_qs(q).get("u") or [""])[0]
                if not target:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                rng = self.headers.get("Range")
                try:
                    req = urllib.request.Request(target)
                    req.add_header("User-Agent", UA)
                    req.add_header("Referer", http.host + "/")
                    if rng:
                        req.add_header("Range", rng)
                    resp = urllib.request.urlopen(req, timeout=60)
                except Exception as e:
                    body = ("proxy error: " + str(e)[:200]).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    try:
                        self.wfile.write(body)
                    except Exception:
                        pass
                    return

                ctype = resp.headers.get("Content-Type", "") or ""
                is_pl = (target.split("?")[0].endswith(".m3u8")
                         or "mpegurl" in ctype.lower())

                # 播放列表：小，读进来改写后一次性吐
                if is_pl:
                    try:
                        text = resp.read().decode("utf-8", "ignore")
                    finally:
                        try:
                            resp.close()
                        except Exception:
                            pass
                    data = _rewrite_playlist(text, target).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    try:
                        self.wfile.write(data)
                    except Exception:
                        pass
                    return

                # 分片/密钥：流式转发，别整段缓冲（单片动辄好几兆）
                code = 206 if (rng and getattr(resp, "status", 200) == 206) else 200
                clen = resp.headers.get("Content-Length")
                self.send_response(code)
                self.send_header("Content-Type", ctype or "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                if resp.headers.get("Content-Range"):
                    self.send_header("Content-Range", resp.headers["Content-Range"])
                    if clen:
                        self.send_header("Content-Length", clen)
                elif clen:
                    self.send_header("Content-Length", clen)
                else:
                    self.close_connection = True
                self.end_headers()
                try:
                    while True:
                        chunk = resp.read(262144)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except Exception:
                    pass
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass

            def do_GET(self):
                if self.path.startswith("/jjri"):
                    return self._serve()
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        srv = HTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True).start()
        self.port = port
        self._started = True
        return port


# --------------------------------------------------------------------------
# Spider
# --------------------------------------------------------------------------

class Spider(BaseSpider):

    def __init__(self):
        try:
            BaseSpider.__init__(self)
        except Exception:
            pass
        self.http = _Http(HOSTS)
        self.extend = {}
        self._cache = {}
        self._proxy = None

    # ---------------- 生命周期 ----------------

    def init(self, extend=""):
        self.http = _Http(HOSTS)
        self.extend = {}
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    self.extend = ext
            except Exception:
                self.extend = {}
        host = self.extend.get("host")
        if host:
            host = str(host).rstrip("/")
            self.http.hosts = [host] + [h for h in HOSTS if h != host]
            self.http.host = host
            self.http._probed = True
        self._cache = {}
        self._proxy = None
        return ""

    def getName(self):
        return "久久热"

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def _cached(self, key, producer):
        if self.extend.get("no_cache"):
            return producer()
        hit = self._cache.get(key)
        now = time.time()
        if hit and now - hit[0] < CACHE_TTL:
            return hit[1]
        val = producer()
        self._cache[key] = (now, val)
        return val

    # ---------------- 分类表 ----------------

    def _classes(self):
        out = [{"type_id": "home", "type_name": "推荐"}]
        for cid, name in GROUPS:
            out.append({"type_id": "g" + cid, "type_name": name})
        for cid, name in SECTIONS:
            out.append({"type_id": cid, "type_name": name})
        if self.extend.get("all_cats"):
            for gname, subs in SUBCATS:
                for cid, name in subs:
                    out.append({"type_id": cid, "type_name": "%s·%s" % (gname, name)})
        return out

    # ---------------- 首页 ----------------

    def homeContent(self, filter=False):
        d = {"class": self._classes(), "filters": {}}
        try:
            d["list"] = self._cached("home", self._home_list)
        except Exception:
            d["list"] = []
        return d

    def _home_list(self):
        host = self.http.ensure()
        html = self.http.get("/", referer=host + "/")
        items = parse_list(html, host)
        return items[:200]

    # ---------------- 分类 ----------------

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg or 1)
        if pg < 1:
            pg = 1
        tid = str(tid or "home")

        if tid == "home":
            lst = self._cached("home", self._home_list)
            return {"page": 1, "pagecount": 1, "limit": len(lst), "total": len(lst),
                    "list": lst}

        host = self.http.ensure()

        if tid.startswith("g") and tid[1:].startswith("cate"):
            # 大分类：一页吐完，没有分页
            cid = tid[1:]
            key = "grp:" + cid
            lst = self._cached(key, lambda: parse_list(
                self.http.get("/group-category/%s/" % cid, referer=host + "/"), host))
            return {"page": 1, "pagecount": 1, "limit": len(lst), "total": len(lst),
                    "list": lst}

        if not tid.startswith("cate"):
            tid = "cate4"

        path = "/category/%s/%d/" % (tid, pg)
        key = "cat:%s:%d" % (tid, pg)
        lst = self._cached(key, lambda: parse_list(
            self.http.get(path, referer=host + "/"), host))

        pagecount = pg if len(lst) >= 20 else pg
        # 满 20 条说明后面大概率还有页；TVBox 会一直翻到空页为止
        count = pagecount + 1 if len(lst) >= 20 else pagecount
        return {"page": pg, "pagecount": count, "limit": 20,
                "total": count * 20, "list": lst}

    # ---------------- 详情 ----------------

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = re.sub(r"\D", "", str(vid))
        if not vid:
            return {"list": []}
        host = self.http.ensure()
        html = self.http.get("/video/%s/" % vid, referer=host + "/")
        v = parse_detail(html, host, vid)
        if not v.get("vod_name"):
            v["vod_name"] = vid
        return {"list": [v]}

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg or 1)
        host = self.http.ensure()
        kw = urllib.parse.quote(str(key).strip(), safe="")
        path = "/search/%s/" % kw if pg <= 1 else "/search/%s/%d/" % (kw, pg)
        key_c = "search:%s:%d" % (kw, pg)
        lst = self._cached(key_c, lambda: parse_list(
            self.http.get(path, referer=host + "/"), host))
        return {"list": lst, "page": pg, "pagecount": pg + 1 if len(lst) >= 20 else pg}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        header = {
            "User-Agent": UA,
            "Referer": self.http.ensure() + "/",
        }
        if not url:
            return {"parse": 0, "playUrl": "", "header": header}
        if not re.match(r"^https?://", url, re.I):
            url = _abs(url, self.http.ensure())

        if self.extend.get("proxy"):
            try:
                if self._proxy is None:
                    self._proxy = _Proxy(self.http)
                port = self._proxy.start()
                if port:
                    return {"parse": 0,
                            "playUrl": "http://127.0.0.1:%d/jjri?u=%s" % (
                                port, urllib.parse.quote(url, safe="")),
                            "header": header}
            except Exception:
                pass
        return {"parse": 0, "playUrl": url, "header": header}

    # ---------------- 直播（本站没有） ----------------

    def liveContent(self, url):
        return ""


# --------------------------------------------------------------------------
# 本地自测
# --------------------------------------------------------------------------

def _self_test(which=None, arg=None):
    s = Spider()
    s.init("{}")
    print("入口:", s.http.ensure())

    def show(items, n=5):
        for it in items[:n]:
            print("   ", it.get("vod_id"), "|", it.get("vod_name", "")[:40], "|",
                  it.get("vod_remarks", ""))

    if which in (None, "home"):
        hc = s.homeContent(False)
        print("分类数:", len(hc["class"]))
        print("首页条数:", len(hc["list"]))
        show(hc["list"])

    if which in (None, "cat"):
        tid = arg or "g" + GROUPS[0][0]
        cc = s.categoryContent(tid, 1, False, {})
        print("分类", tid, "条数:", len(cc["list"]))
        show(cc["list"])
        if not str(tid).startswith("g"):
            cc2 = s.categoryContent(tid, 2, False, {})
            a = set(x["vod_id"] for x in cc["list"])
            b = set(x["vod_id"] for x in cc2["list"])
            print("第2页条数:", len(cc2["list"]), "与第1页重叠:", len(a & b))

    if which in (None, "detail"):
        vid = arg or (s.categoryContent("g" + GROUPS[0][0], 1, False, {})["list"][0]["vod_id"])
        dc = s.detailContent([vid])
        v = dc["list"][0]
        print("详情:", v["vod_name"])
        print("  封面:", v["vod_pic"][:80])
        print("  分类:", v["type_name"], "| 简介:", v["vod_content"][:60])
        print("  线路:", v["vod_play_from"])
        print("  播放:", v["vod_play_url"][:160])

    if which in (None, "search"):
        kw = arg or "护士"
        sc = s.searchContent(kw, True, "1")
        print("搜索", kw, "条数:", len(sc["list"]))
        show(sc["list"])

    if which in (None, "play"):
        vid = arg
        if not vid:
            vid = s.searchContent("护士", True, "1")["list"][0]["vod_id"]
        v = s.detailContent([vid])["list"][0]
        first = (v["vod_play_url"].split("$$$")[0] or "").split("$")[-1]
        print("播放地址:", first)
        p = s.playerContent("", first, None)
        print("playerContent:", json.dumps(p, ensure_ascii=False)[:200])
        try:
            data, hdr = s.http.get_bytes(first, referer=s.http.host + "/")
            head = data.decode("utf-8", "ignore").splitlines()[:6]
            print("直链返回:", len(data), "字节")
            for ln in head:
                print("   ", ln)
        except Exception as e:
            print("直链拉取失败:", e)


if __name__ == "__main__":
    args = sys.argv[1:]
    _self_test(args[0] if args else None, args[1] if len(args) > 1 else None)
