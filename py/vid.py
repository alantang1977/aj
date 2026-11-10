# -*- coding: utf-8 -*-
"""
Vidhub视频库 (https://vidhub2.top) —— TVBox / Py4 单站点源
=====================================================================
站点结构 (2026-10-17 实测):
  分类导航 : /vodtype/{tid}.html         (1电影/2电视剧/3综艺/4动漫, 一次全量返回)
  筛选列表 : /vodshow/{12段}.html?page=N  (影片库路由, 72条/页, 全站6.9万+片源)
  详情     : /voddetail/{vid}.html
  播放     : /vodplay/{vid}-{sid}-{nid}.html  -> 内嵌 /player/?u=密文  -> config.url=明文m3u8
  搜索     : /vodsearch/-------------.html?wd=xx (被"人机验证"拦截, 见 searchContent)

详情页多线路结构 (2026-10-17 实测, 修复"每集显示两遍"问题):
  线路名 tabs[] = module-tab-item 的 data-dropdown-value(文档序)
  剧集块 glist[] = id="glist-{sid}"(文档序)
  站点 script.js 的切换逻辑: $('.tab-item').click -> $('.tab-list').eq(index)
  => 第i个tab名对应第i个glist(按文档序位置对齐, 与站点行为一致)
  每个glist块内每集链接出现两次: 桌面 module-blocklist + 移动端
  shortcuts-mobile-overlay 副本(306326/140387/213593 多样本验证),
  detailContent 按 nid 去重只保留首次出现。

/vodshow/ 12段URL段位语义 (实测有效, 全部可选, 位置固定):
  seg0=tid(类型) seg1=地区 seg2=排序(time/hits/score) seg3=类别 seg4=语言
  seg5..seg10=空 seg11=年份
  例: /vodshow/1-中国大陆--剧情--国语-----------2026.html
      (电影+中国大陆+默认排序+剧情+国语+2026)
  站点同款示例(抓自详情页tag): /vodshow/3---真人秀--------.html (综艺+真人秀)

抓取策略: 全站(首页/类型/影片库/详情/播放/player)直连无验证, 桌面UA与蜘蛛UA
  返回同样内容; UA池双备份。搜索路由例外: 每次搜索强制4位数字人机验证
  (POST vod_search_verify_code, 状态绑定PHP会话, TVBox运行时可解法库缺失),
  故 searchContent 探测到验证页即优雅返回空列表。

播放链路 (2跳, 均为明文, 已实测):
  1) GET /vodplay/{vid}-{sid}-{nid}.html 取 iframe src=/player/?u=...&i=..&n=..&s=..
  2) GET /player/?u=... (Referer=播放页) 得 var config={...,"url":"https://...index.m3u8"}
  3) m3u8为母分组(单变体 2000k/hls/index.m3u8), 变体/TS全为相对路径(实测),
     部分播放器对裸相对TS段解析不良(黑屏/转圈), 故必须先母分组→改写为
     绝对路径 media playlist 再交付.

播放交付 (2026-10-18 修复"播放页黑屏/缓存中不播放"问题):
  parse=0 纯直连: playerContent 内部直接把母分组解析为最高码率分组的
  绝对 media playlist URL 返回(直连解析, 不依赖运行时 localProxy/
  127.0.0.1:9978 代理服务器 —— MPV 等外部播放器环境无该服务, 走代理
  URL 会永远"缓存中")。media playlist 内裸相对 .ts 由播放器基于
  playlist URL 自动解析(标准 HLS 行为), TS 直连CDN无防盗链(200,
  无需Referer)。localProxy 保留仅作为支持代理运行时的可选路径。
"""
import gzip
import json
import re
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as _Base
    _HAS_BASE = True
except Exception:
    _HAS_BASE = False


class Spider(_Base if _HAS_BASE else object):
    HOST = 'https://vidhub2.top'
    # 全站直连无验证; 桌面UA优先(与实测解析一致), 蜘蛛UA兜底
    UA_PC = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
    UA_POOL = [
        UA_PC,
        'Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)',
        'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    ]
    TIMEOUT = 15
    MAX_PAGE = 60          # 分类翻页硬上限(片库极深, 防失控请求)
    PAGE_SIZE = 72         # 影片库每页条数(实测)

    # 分类只放4大类; 类型/地区/年份/排序/语言全部进筛选栏(参照需求约定)
    CATS = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '4', 'type_name': '动漫'},
    ]
    # 筛选"类型"(seg3 类别): 站点类别为宽松LIKE匹配(如"动作"命中"动作片")
    CLASS_MAP = {
        '1': ['动作', '喜剧', '爱情', '科幻', '恐怖', '剧情', '战争', '犯罪',
              '惊悚', '冒险', '悬疑', '武侠', '奇幻', '动画', '纪录片', '古装',
              '情色', '灾难', '伦理', '歌舞', '传记', '历史'],
        '2': ['内地', '港台', '日韩', '欧美', '泰国', '剧情', '喜剧', '爱情',
              '悬疑', '犯罪', '古装', '历史', '战争', '武侠', '奇幻', '科幻',
              '惊悚', '都市', '家庭', '偶像', '青春', '校园', '军旅', '谍战',
              '年代', '传记', '短剧'],
        '3': ['真人秀', '脱口秀', '音乐', '舞蹈', '访谈', '美食', '旅游',
              '亲子', '竞技', '晚会', '资讯', '大陆综艺', '日韩综艺', '欧美综艺', '港台综艺'],
        '4': ['动画', '热血', '格斗', '恋爱', '奇幻', '搞笑', '日常', '悬疑',
              '科幻', '治愈', '校园', '魔幻', '冒险', '历史', '战争', '神魔',
              '亲子', '真人', '国产动漫', '日韩动漫', '欧美动漫', '剧场版'],
    }
    # 筛选"地区"(seg1): 值抓自站点详情页tag + 全量验证有效(72卡纯地区分布)
    AREAS = ['中国大陆', '中国香港', '中国台湾', '内地', '香港', '台湾',
             '美国', '日本', '韩国', '英国', '法国', '德国', '意大利', '西班牙',
             '泰国', '印度', '新加坡', '俄罗斯', '加拿大', '澳大利亚',
             '波兰', '巴西', '墨西哥', '苏联', '其它']
    # 筛选"排序"(seg2): 默认即time
    SORTS = [('最新', 'time'), ('最热', 'hits'), ('评分', 'score')]
    # 筛选"语言"(seg4): 实测地区分布/卡片数验证
    LANGS = ['国语', '英语', '粤语', '日语', '韩语', '无对白']
    YEARS = [str(y) for y in range(2026, 2008, -1)]  # seg11 年份

    # (vid,sid,nid) -> m3u8 播放直链缓存
    _play_cache = {}

    # ---------------- 生命周期 ----------------
    def init(self, extend=''):
        return self

    def getName(self):
        return 'Vidhub视频库'

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- HTTP (标准库实现, 无外部依赖) ----------------
    def _hd(self, ref=None, ua=None):
        return {'User-Agent': ua or self.UA_POOL[0],
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Referer': ref or self.HOST + '/'}

    def _get(self, url, ref=None, ua=None):
        """urllib GET, 返回文本; 失败返回 ''"""
        req = urllib.request.Request(url, headers=self._hd(ref, ua))
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                data = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)
                return data.decode('utf-8', 'ignore')
        except Exception:
            return ''

    def fetch(self, url, ref=None):
        """UA池依次尝试, 避开验证/错误页"""
        for ua in self.UA_POOL:
            txt = self._get(url, ref=ref, ua=ua)
            if txt and '系统安全验证' not in txt and '人机验证' not in txt \
                    and len(txt) > 300:
                return txt
        # 最后尝试框架自带fetch
        if _HAS_BASE:
            try:
                rsp = super().fetch(url, headers=self._hd(ref))
                if rsp is not None:
                    txt = getattr(rsp, 'text', '') or ''
                    if '系统安全验证' not in txt and '人机验证' not in txt:
                        return txt
            except Exception:
                pass
        return ''

    # ---------------- 工具 ----------------
    @staticmethod
    def _txt(s):
        if not s:
            return ''
        s = re.sub(r'<script[\s\S]*?</script>', ' ', s, flags=re.I)
        s = re.sub(r'<style[\s\S]*?</style>', ' ', s, flags=re.I)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = re.sub(r'&nbsp;?', ' ', s)
        s = re.sub(r'&amp;', '&', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _first(text, pats):
        for p in pats:
            m = re.search(p, text or '', re.S | re.I)
            if m:
                return Spider._txt(m.group(1))
        return ''

    @staticmethod
    def _abs(u):
        if not u:
            return ''
        u = u.strip()
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        return Spider.HOST.rstrip('/') + '/' + u.lstrip('/')

    @staticmethod
    def _int(s, d=1):
        try:
            return int(re.sub(r'\D', '', str(s)) or d)
        except Exception:
            return d

    # ---------------- 卡片解析 ----------------
    def _cards(self, html):
        """影片库/列表页卡片: <div class="module-item"> 块"""
        if not html:
            return []
        out, seen = [], set()
        for m in re.finditer(r'<div class="module-item">', html):
            blk = html[m.start():m.start() + 4000]
            idm = re.search(r'href="/voddetail/(\d+)\.html"', blk)
            if not idm:
                continue
            vid = idm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            nm = (re.search(r'\btitle="([^"]{1,80})"', blk) or
                  re.search(r'\balt="([^"]{1,80})"', blk))
            name = self._txt(nm.group(1)) if nm else ''
            if not name:
                continue
            pic = (re.search(r'data-src="([^"]+)"', blk) or
                   re.search(r'\bsrc="([^"]+)"', blk))
            cap = re.search(r'module-item-caption">([\s\S]{0,220}?)</div>', blk)
            marks = []
            if cap:
                marks = [self._txt(x) for x in
                         re.findall(r'<span[^>]*>([^<]*)</span>', cap.group(1))]
            out.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._abs(pic.group(1)) if pic else '',
                'vod_remarks': ' / '.join(x for x in marks if x)[:60],
            })
        return out

    # ---------------- 筛选与列表URL ----------------
    def _filters(self, tid):
        """T4/Py4 筛选结构; 全部走 vodshow 段位"""
        def opts(vals):
            return [{'n': '全部', 'v': ''}] + [{'n': v, 'v': v} for v in vals]

        def sopts():
            return [{'n': n, 'v': v} for n, v in self.SORTS]

        return [
            {'name': '类型', 'key': 'cls', 'value': opts(self.CLASS_MAP.get(tid, []))},
            {'name': '地区', 'key': 'area', 'value': opts(self.AREAS)},
            {'name': '年份', 'key': 'year', 'value': opts(self.YEARS)},
            {'name': '排序', 'key': 'sort', 'value': sopts()},
            {'name': '语言', 'key': 'lang', 'value': opts(self.LANGS)},
        ]

    @staticmethod
    def _ext(extend):
        """解析客户端回传的筛选值(JSON串或 k=v&.. 串)"""
        d = {'cls': '', 'area': '', 'sort': '', 'lang': '', 'year': ''}
        s = str(extend or '').strip()
        if s.startswith('{'):
            try:
                j = json.loads(s)
                for k in d:
                    if k in j and j[k] not in (None, '全部'):
                        d[k] = str(j[k])
            except Exception:
                pass
        elif '=' in s:
            for part in s.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    k = k.strip()
                    if k in d and v and v != '全部':
                        d[k] = urllib.parse.unquote(v)
        # sort 只认白名单值
        if d['sort'] not in ('time', 'hits', 'score'):
            d['sort'] = ''
        # 年份校验4位数字
        if not re.fullmatch(r'\d{4}', d['year']):
            d['year'] = ''
        return d

    def _list_url(self, tid, extend, page=1):
        d = self._ext(extend)
        segs = [str(tid), d['area'], d['sort'], d['cls'], d['lang']] + [''] * 6 + [d['year']]
        u = '%s/vodshow/%s.html' % (self.HOST, '-'.join(
            urllib.parse.quote(x, safe='') if x else '' for x in segs))
        if page > 1:
            u += '?page=%d' % page
        return u

    # ---------------- 首页/分类 ----------------
    def homeContent(self, filter):
        return {'class': [dict(c) for c in self.CATS],
                'filters': {c['type_id']: self._filters(c['type_id']) for c in self.CATS},
                'list': self._cards(self.fetch(self.HOST + '/'))}

    def homeVideoContent(self):
        return {'list': self._cards(self.fetch(self.HOST + '/'))}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(self._int(pg, 1), 1)
        if page > self.MAX_PAGE:
            return {'list': [], 'page': page, 'pagecount': self.MAX_PAGE,
                    'limit': 0, 'total': 0}
        url = self._list_url(tid, extend, page)
        cards = self._cards(self.fetch(url))
        pagecount = page + 1 if cards else max(page - 1, 1)
        return {'list': cards, 'page': page, 'pagecount': pagecount,
                'limit': len(cards), 'total': len(cards)}

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0] if isinstance(ids, list) else ids))
        html = self.fetch('%s/voddetail/%s.html' % (self.HOST, vid))
        if not html:
            return {'list': []}
        title = self._first(html, [r'<h1 class="page-title">([^<]+)</h1>'])
        pic = self._first(html, [r'property="og:image"\s+content="([^"]+)"'])
        if not pic:
            picm = re.search(r'<img[^>]+data-src="([^"]+)"', html)
            pic = self._abs(picm.group(1)) if picm else ''

        # ---- 信息区(分类/地区/年份抓 /vodshow/ tag) ----
        ia_start = html.find('video-info')
        ia_end = html.find('vod_content')
        ia = html[max(0, ia_start - 50): ia_end + 200] if ia_end > 0 else html
        area = cls = year = cate = ''
        for m in re.finditer(r'href="/vodshow/(\d+(?:-[^"]*)?)"[^>]*>\s*([^<]{1,12})\s*</a>', ia):
            segs = urllib.parse.unquote(m.group(1)).replace('.html', '').split('-')
            txt = self._txt(m.group(2))
            if len(segs) >= 12 and segs[11] and re.fullmatch(r'\d{4}', segs[11]):
                year = segs[11] or year
            elif len(segs) >= 4 and segs[3] and segs[1] == '':
                cls = txt or cls
            elif len(segs) >= 2 and segs[1] and segs[3] == '':
                area = txt or area
        cm = re.search(r'href="/vodtype/(\d+)\.html"[^>]*>[\s\S]{0,80}?([^<>]{1,10})</a>', ia)
        if cm:
            cate = self._txt(cm.group(2))

        def row_names(label):
            mm = re.search(label + r'\s*：?\s*</span><div class="video-info-item[^"]*">([\s\S]{0,500}?)</div>',
                           ia)
            if not mm:
                return ''
            return ' / '.join(dict.fromkeys(
                self._txt(x) for x in re.findall(r'>([^<>]{1,30})</a>', mm.group(1))))

        director, actor = row_names('导演'), row_names('主演')
        remark = ' / '.join(x for x in [cate, cls, area, year, director, actor] if x)

        # ---- 简介 ----
        desc = self._first(html, [
            r'video-info-content vod_content"><span>([\s\S]{5,2000}?)</span>'])
        if not desc:
            desc = self._first(html, [r'name="description"\s+content="([^"]{10,600})"'])

        # ---- 播放线路: tab名(文档序) 与 glist列表(文档序) 按位对齐 ----
        tabs = re.findall(r'data-dropdown-value="([^"]+)"', html)
        glists = [(m.group(1), m.start())
                  for m in re.finditer(r'id="glist-(\d+)"', html)]
        lines, play = [], []
        for i, (sid, pos) in enumerate(glists):
            blk = html[pos: pos + 400000]
            # 截断到下一个glist
            if i + 1 < len(glists):
                blk = blk[:glists[i + 1][1] - pos]
            # 块内每集链接出现两次(桌面 module-blocklist + 移动端
            # shortcuts-mobile-overlay 副本, 经306326/140387/213593 多样本
            # 验证结构一致), 按 nid 去重只保留首次出现, 否则TVBox里每集显示两遍
            eps, seen = [], set()
            for em in re.finditer(
                    r'href="/vodplay/%s-(\d+)-(\d+)\.html"[^>]*>(?:<i[^>]*></i>)?'
                    r'(?:<span>([^<]*)</span>)?' % re.escape(vid), blk):
                _, nid, epname = em.group(1), em.group(2), em.group(3)
                if nid in seen:
                    continue
                seen.add(nid)
                epname = self._txt(epname) or ('第%s集' % nid)
                eps.append('%s$/vodplay/%s-%s-%s.html' % (epname, vid, sid, nid))
            if not eps:
                continue
            name = tabs[i] if i < len(tabs) else ('线路%d' % (i + 1))
            lines.append(name)
            play.append('#'.join(eps))
        if not lines:
            return {'list': []}

        return {'list': [{
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_year': year,
            'vod_area': area,
            'vod_remarks': remark[:80],
            'vod_content': desc,
            'vod_play_from': '$$$'.join(lines),
            'vod_play_url': '$$$'.join(play),
            'style': '{\"type\":\"list\"}',
        }]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg='1'):
        page = self._int(pg, 1)
        kw = str(key or '').strip()
        if not kw or page > 1:
            return {'list': [], 'page': max(page, 1)}
        url = '%s/vodsearch/-------------.html?wd=%s' % (
            self.HOST, urllib.parse.quote(kw, safe=''))
        html = self.fetch(url)
        if 'vod_search_verify_code' in html or '人机验证' in html:
            # 站点对搜索启用每次请求4位数字人机验证(状态绑定PHP会话);
            # TVBox运行时无OCR环境, 无法自动过码 -> 优雅跳过
            print('Vidhub搜索被人机验证拦截(需4位验证码, 会话绑定), 已跳过')
            return {'list': [], 'page': 1}
        cards = self._cards(html)
        kw_l = kw.lower()
        cards.sort(key=lambda c: 0 if c['vod_name'] == kw else
                   1 if c['vod_name'].startswith(kw) else
                   2 if kw_l in c['vod_name'].lower() else 3)
        return {'list': cards, 'page': 1}

    # ---------------- 播放 ----------------
    def _extract_config(self, html):
        """从 /player/ 页提取 var config = {...} (括号深度匹配)"""
        idx = html.find('var config')
        if idx < 0:
            return None
        b = html.find('{', idx)
        if b < 0:
            return None
        depth = 0
        for i in range(b, min(len(html), b + 20000)):
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[b:i + 1])
                    except Exception:
                        return None
        return None

    def playerContent(self, flag, id, vipFlags):
        play_url = self._abs(str(id))
        m = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', play_url)
        if not m:
            return {'parse': 1, 'playUrl': '', 'url': play_url,
                    'header': {'User-Agent': self.UA_PC}, 'jx': 1}
        vid, sid, nid = m.group(1), m.group(2), m.group(3)

        key = (vid, sid, nid)
        if key in self._play_cache:
            return self._play_cache[key]
        if len(self._play_cache) > 600:
            self._play_cache.clear()

        # 第1跳: 播放页取 /player/ iframe
        html = self.fetch(play_url)
        srcm = re.search(r'src="(/player/\?[^"]+)"', html)
        if not srcm:
            # 兜底: 播放页本身可能带明文直链(少数源)
            dm = re.search(r'(https?:[^"\'\s<>]+?\.m3u8[^"\'\s<>]*)', html, re.I)
            if dm:
                r = {'parse': 0, 'playUrl': '', 'url': dm.group(1),
                     'header': {'User-Agent': self.UA_PC}}
                self._play_cache[key] = r
                return r
            r = {'parse': 1, 'playUrl': '', 'url': play_url,
                 'header': {'User-Agent': self.UA_PC, 'Referer': self.HOST + '/'}, 'jx': 1}
            return r

        # 第2跳: /player/ 取 config.url (明文m3u8母分组)
        purl = self._abs(srcm.group(1).replace('&amp;', '&'))
        phtml = self._get(purl, ref=play_url, ua=self.UA_PC)
        if not phtml:
            phtml = self._get(purl, ref=play_url, ua=self.UA_POOL[1])
        if not phtml:
            phtml = self.fetch(purl, ref=play_url)
        cfg = self._extract_config(phtml) or {}
        m3u8 = (cfg.get('url') or '').strip()
        if not m3u8:
            # 兜底: 配置块解析失败时在页面全文里扫明文m3u8
            # (config 结构并非永远是标准JSON, JSON只带给fldEsc=false的站点)
            dm = re.search(r'(https?:(?:\\/\\/|//)[^"\'\s<>]+?\.m3u8'
                           r'(?:\?[^"\'\s<>]*)?)', phtml or '', re.I)
            if dm:
                m3u8 = dm.group(1).replace('\\/', '/')
        if m3u8 and self.isVideoFormat(m3u8):
            # 直连解析: 母分组->最高码率分组的绝对 media playlist URL。
            # 不走 127.0.0.1:9978 代理(MPV等外部播放器环境无运行时代理
            # 服务, 代理URL会永远"缓存中"), parse=0 纯直连播放
            r = {'parse': 0, 'playUrl': '', 'url': self._resolve_direct(m3u8),
                 'header': {'User-Agent': self.UA_PC,
                            'Referer': self.HOST + '/'}}
            self._play_cache[key] = r
            return r
        # 无明文直链: 交框架webview加载播放页自行处理
        r = {'parse': 1, 'playUrl': '', 'url': play_url,
             'header': {'User-Agent': self.UA_PC, 'Referer': self.HOST + '/'}, 'jx': 1}
        return r

    # ---------------- 播放直连解析(母分组->最高码率分组绝对URL) ----------------
    def _variants(self, base_url, text):
        """母分组文本 -> [(BANDWIDTH, 绝对URL)] 按带宽降序; 非母分组返回 []"""
        if '#EXT-X-STREAM-INF' not in (text or ''):
            return []
        vlist, bw = [], 1
        for line in text.splitlines():
            s = line.strip()
            mb = re.search(r'\bBANDWIDTH=(\d+)', s, re.I)
            if s.startswith('#EXT-X-STREAM-INF') and mb:
                bw = int(mb.group(1))
                continue
            if s and not s.startswith('#'):
                vlist.append((bw, urllib.parse.urljoin(base_url, s)))
                bw = 1
        vlist.sort(key=lambda x: -x[0])
        return vlist

    def _resolve_direct(self, m3u8):
        """母分组直连解析: 取最高码率分组的绝对 media playlist URL。
        解析失败时回退母分组自身(播放器标准HLS亦能解析相对段)。"""
        try:
            text = self._b2t(self._live(m3u8))
            vl = self._variants(m3u8, text)
            for _, vurl in vl:
                vtext = self._b2t(self._live(vurl))
                if vtext and '#EXTM3U' in vtext:
                    return vurl
        except Exception:
            pass
        return m3u8

    # ---------------- 本地代理(母分组→最高码率分组→绝对路径playlist) ----------------
    @staticmethod
    def _proxy_url(target):
        """TVBox/Py4/DY 运行时本地代理标准接线形式:
        GET /proxy?do=py&url=... -> spider.localProxy(query dict)"""
        q = urllib.parse.urlencode({'do': 'py', 'url': target})
        return 'https://127.0.0.1:9978/proxy?' + q

    def _live(self, url):
        """UA池 x Referer 多路重试取二进制(自动gzip), 全失败返回 None"""
        atts = [(self.UA_PC, self.HOST + '/'), (self.UA_POOL[1], self.HOST + '/'),
                (self.UA_PC, None)]
        for ua, ref in atts:
            hd = {'User-Agent': ua, 'Accept': '*/*'}
            if ref:
                hd['Referer'] = ref
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(url, headers=hd),
                        timeout=self.TIMEOUT) as r:
                    data = r.read()
                    if r.headers.get('Content-Encoding') == 'gzip':
                        data = gzip.decompress(data)
                    if data:
                        return data
            except Exception:
                pass
        return None

    @staticmethod
    def _b2t(data):
        return (data or b'').decode('utf-8', 'ignore').\
            lstrip('﻿').strip()

    @staticmethod
    def _rewrite_playlist(base_url, text):
        """m3u8 文本内非注释的相对 URI 全部补全为绝对 URL(基于 playlist 目录)"""
        lines = []
        for line in (text or '').splitlines():
            s = line.strip()
            if s and not s.startswith('#') and not re.match(r'^https?://', s, re.I):
                s = urllib.parse.urljoin(base_url, s)
            lines.append(s)
        return '\n'.join(lines) + '\n'

    def localProxy(self, param):
        """运行时经 https://127.0.0.1:9978/proxy?do=py&url=... 调入;
        param 为该请求的 query dict (部分运行时传 str, 兼容解析)"""
        tgt = None
        if isinstance(param, dict):
            tgt = param.get('url')
        elif isinstance(param, str):
            qs = urllib.parse.parse_qs(param.strip().split('?', 1)[-1])
            tgt = (qs.get('url') or [''])[0]
        if isinstance(tgt, str):
            tgt = tgt.strip().replace('&amp;', '&')
            if '%' in tgt:
                tgt = urllib.parse.unquote(tgt)
        if not tgt:
            return [502, 'text/html',
                    'localProxy: missing url'.encode('utf-8')]
        raw = self._live(tgt)
        if raw is None:
            return [504, 'text/html',
                    'localProxy: fetch failed'.encode('utf-8')]
        if self.isVideoFormat(tgt) and re.search(r'\.m3u8(\?|$)', tgt, re.I):
            text = self._b2t(raw)
            vlist = self._variants(tgt, text)
            if vlist:
                # 母分组: 按带宽降序逐个尝试变体, 取第一个有效
                # media playlist 改写为绝对路径返回
                for _, vurl in vlist:
                    vraw = self._live(vurl)
                    vtext = self._b2t(vraw)
                    if vtext and '#EXTM3U' in vtext:
                        out = self._rewrite_playlist(vurl, vtext)
                        return [200, 'application/vnd.apple.mpegurl',
                                out.encode('utf-8')]
            # 已是 media playlist(或全部变体失败退回): 重写相对URI
            out = self._rewrite_playlist(tgt, text)
            return [200, 'application/vnd.apple.mpegurl',
                    out.encode('utf-8')]
        # 非m3u8直链(mp4/flv): 二进制原样转发
        mime = ('video/mp4' if re.search(r'\.mp4(\?|$)', tgt, re.I)
                else 'video/x-flv' if re.search(r'\.flv(\?|$)', tgt, re.I)
                else 'video/mp2t')
        return [200, mime, raw]


if __name__ == '__main__':
    sp = Spider()
    sp.init('')
    h = sp.homeContent(True)
    print('分类:', [c['type_name'] for c in h['class']])
    print('筛选[电影]:', [(f['name'], f['value'][1]['n']) for f in h['filters']['1']])

    c1 = sp.categoryContent('1', '1', True, '')
    print('分类页1: %d个, 前3: %s' % (len(c1['list']),
          [(x['vod_name'], x['vod_remarks']) for x in c1['list'][:3]]))
    print('分类页2: %d个' % len(sp.categoryContent('1', '2', True, '')['list']))

    for ext in ['{"area":"美国","year":"2026","cls":"剧情"}',
                '{"sort":"hits"}', '{"lang":"日语"}',
                'area=%E7%BE%8E%E5%9B%BD&year=2020']:
        r = sp.categoryContent('1', '1', True, ext)
        print('筛选[%s]: %d个, 前2: %s' % (ext[:40], len(r['list']),
              [x['vod_name'] for x in r['list'][:2]]))

    # 电视剧详情(多集多线路)
    tv = sp.categoryContent('2', '1', True, '')['list'][0]['vod_id']
    d = sp.detailContent([tv])['list'][0]
    lines = d['vod_play_from'].split('$$$')
    print('电视剧详情: %s | %s | 线路: %s' % (d['vod_name'], d['vod_remarks'], lines))

    # 电影详情+播放(完整链路: 详情->首集->playerContent->localProxy->TS)
    vid = c1['list'][0]['vod_id']
    d = sp.detailContent([vid])['list'][0]
    print('电影详情: %s | %s | 线路: %s' % (
        d['vod_name'], d['vod_remarks'], d['vod_play_from'].split('$$$')))
    print('  简介: %s' % d['vod_content'][:60])
    eps = d['vod_play_url'].split('$$$')[0].split('#')
    print('  线路1共%d集, 首集: %s' % (len(eps), eps[0]))
    p = sp.playerContent(lines[0] if False else d['vod_play_from'].split('$$$')[0],
                         eps[0].split('$')[1], [])
    print('  播放解析: parse=%s url=%s' % (p.get('parse'), str(p.get('url'))))
    # 直连验证: media playlist 可取且 TS 段可直连
    du = str(p.get('url'))
    if p.get('parse') == 0 and du.startswith('http'):
        mt = sp._b2t(sp._live(du))
        segs = [l.strip() for l in mt.splitlines()
                if l.strip() and not l.startswith('#')] if mt else []
        print('  直连playlist: %s 分段=%d 首段=%s' % (
            'OK' if mt and '#EXTM3U' in mt else 'FAIL',
            len(segs), segs[0] if segs else '-'))
        if segs and segs[0].startswith('http'):
            ts = sp._live(segs[0])
            print('  TS直连: %s bytes' % (len(ts) if ts else 'FAIL'))

    s = sp.searchContent('庆余年', False, '1')
    print('搜索: %d个 (被人机验证则为0)' % len(s['list']))
