# coding: utf-8
"""金牌影院 · TVBox/影视仓 Python Spider
依赖宿主 base.spider，以及 requests、lxml。仅读取公开网页，不绕过登录/付费。
播放采用公开直链优先、网页嗅探回退；网页动态播放是否可用取决于宿主 WebView。
"""
import json
import re
from urllib.parse import urljoin, urlparse, quote
import requests
from lxml import etree
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # m 站在移动 UA 下部分页面仅客户端渲染，采用同站 www 的服务端页面。
    host = 'https://www.hellorlgzf7sn.com'
    ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    def init(self, extend=''):
        self.session = requests.Session()
        if extend:
            try:
                config = json.loads(extend) if isinstance(extend, str) else extend
                host = config.get('host', '') if isinstance(config, dict) else ''
                if host.startswith(('https://', 'http://')):
                    self.host = host.rstrip('/')
            except (ValueError, TypeError):
                pass

    def getName(self):
        return '金牌影院'

    def _get(self, path):
        if not hasattr(self, 'session'):
            self.init()
        r = self.session.get(urljoin(self.host + '/', path),
                             headers={'User-Agent': self.ua, 'Referer': self.host + '/'},
                             timeout=(10, 25))
        r.raise_for_status()
        parsed = urlparse(r.url)
        self.host = '{}://{}'.format(parsed.scheme, parsed.netloc)
        r.encoding = 'utf-8'
        return r.text

    @staticmethod
    def _flight(text):
        # Next.js Flight 的字符串可能拆分在多个 script 中，先拼接再解码记录。
        chunks = []
        for match in re.finditer(r'self\.__next_f\.push\((.*?)\)</script>', text, re.S):
            try:
                item = json.loads(match.group(1))
                if item[0] == 1 and isinstance(item[1], str):
                    chunks.append(item[1])
            except (ValueError, IndexError, TypeError):
                continue
        records = []
        for line in ''.join(chunks).splitlines():
            if ':' not in line:
                continue
            try:
                records.append(json.loads(line.split(':', 1)[1]))
            except ValueError:
                pass
        return records

    @staticmethod
    def _walk(obj):
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from Spider._walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from Spider._walk(v)

    def _objects(self, text):
        for record in self._flight(text):
            yield from self._walk(record)

    def _card(self, d):
        return {'vod_id': str(d['vodId']), 'vod_name': d.get('vodName', ''),
                'vod_pic': urljoin(self.host, d.get('vodPic') or ''),
                'vod_remarks': str(d.get('vodRemarks') or d.get('vodVersion') or '')}

    def _cards(self, text):
        result, seen = [], set()
        for d in self._objects(text):
            if d.get('vodId') and d.get('vodName') and str(d['vodId']) not in seen:
                seen.add(str(d['vodId']))
                result.append(self._card(d))
        if result:
            return result
        root = etree.HTML(text)
        if root is None:
            return []
        for a in root.xpath('//a[contains(@href,"/detail/")]'):
            match = re.search(r'/detail/(\d+)', a.get('href', ''))
            if not match or match.group(1) in seen:
                continue
            images = a.xpath('.//img')
            if not images:
                continue
            img = images[0]
            name = img.get('alt') or ''.join(a.xpath('.//h3//text()')).strip()
            if not name:
                continue
            seen.add(match.group(1))
            result.append({'vod_id': match.group(1), 'vod_name': name,
                           'vod_pic': urljoin(self.host, img.get('data-src') or img.get('src') or ''),
                           'vod_remarks': ''})
        return result

    def homeContent(self, filter):
        return {'class': [{'type_id': k, 'type_name': v} for k, v in
                          [('1', '电影'), ('2', '电视剧'), ('3', '综艺'),
                           ('4', '动漫'), ('88', '短剧')]],
                'list': self._cards(self._get('/'))[:48], 'filters': {}}

    def homeVideoContent(self):
        return {'list': self._cards(self._get('/'))[:48]}

    def _page(self, text, pg, search=False):
        for d in self._objects(text):
            if all(k in d for k in ('totalCount', 'pageNum', 'list')) and isinstance(d['list'], list):
                # 搜索页还包含一个通常为空的 typeResult，优先选 result。
                if search:
                    continue
                return self._page_result(d, pg)
        if search:
            for d in self._objects(text):
                if isinstance(d.get('result'), dict) and 'list' in d['result']:
                    return self._page_result(d['result'], pg)
        items = self._cards(text)
        return {'list': items, 'page': int(pg), 'pagecount': int(pg),
                'limit': len(items), 'total': len(items)}

    def _page_result(self, d, pg):
        items = [self._card(x) for x in d.get('list', []) if x.get('vodId')]
        size = int(d.get('pageSize') or 48)
        total = int(d.get('totalCount') or 0)
        return {'list': items, 'page': int(d.get('pageNum') or pg),
                'pagecount': max(1, int(d.get('totalPage') or (total + size - 1) // size)),
                'limit': size, 'total': total}

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid)
        if tid not in ('1', '2', '3', '4', '88'):
            raise ValueError('不支持的分类')
        pg = max(1, int(pg))
        return self._page(self._get('/vod/show/id/{}/page/{}'.format(tid, pg)), pg)

    def searchContent(self, key, quick, pg='1'):
        pg = max(1, int(pg))
        return self._page(self._get('/vod/search/{}?page={}'.format(quote(key, safe=''), pg)), pg, True)

    def detailContent(self, ids):
        vid = str(ids[0]).rstrip('/').split('/')[-1]
        if not vid.isdigit():
            raise ValueError('影片 ID 格式无效')
        text = self._get('/detail/' + vid)
        for d in self._objects(text):
            if str(d.get('vodId')) != vid or 'episodeList' not in d:
                continue
            vod = self._card(d)
            for source, target in [('vodYear', 'vod_year'), ('vodArea', 'vod_area'),
                                   ('vodActor', 'vod_actor'), ('vodDirector', 'vod_director'),
                                   ('typeName', 'type_name'), ('vodLang', 'vod_lang')]:
                vod[target] = str(d.get(source) or '')
            content = etree.HTML(d.get('vodContent') or d.get('vodBlurb') or '<p></p>')
            vod['vod_content'] = ''.join(content.itertext()) if content is not None else ''
            episodes = []
            for ep in d.get('episodeList') or []:
                if not ep.get('nid'):
                    continue
                label = str(ep.get('name') or ep['nid']).replace('$', '＄').replace('#', '＃')
                link = urljoin(self.host, '/vod/play/{}/sid/{}'.format(vid, ep['nid']))
                episodes.append(label + '$' + link)
            vod['vod_play_from'] = '金牌影院（网页嗅探）'
            vod['vod_play_url'] = '#'.join(episodes)
            return {'list': [vod]}
        raise RuntimeError('未找到影片选集数据，网站结构可能已变化')

    def playerContent(self, flag, id, vipFlags):
        url = urljoin(self.host + '/', id)
        if re.search(r'\.(m3u8|mp4|flv)(?:[?#]|$)', url, re.I):
            return {'parse': 0, 'url': url, 'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}
        # 不伪造接口签名，不解密受保护数据。交给宿主 WebView 执行站点播放器。
        return {'parse': 1, 'jx': 0, 'url': url,
                'header': {'User-Agent': self.ua, 'Referer': self.host + '/'}}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv)(?:[?#]|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', 'Not supported']

    def getDependence(self):
        return []

    def destroy(self):
        if hasattr(self, 'session'):
            self.session.close()
