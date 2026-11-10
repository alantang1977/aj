# -*- coding: utf-8 -*-
"""
YouTube 台湾新闻直播爬虫（稳定性增强版）
- 缩短缓存 TTL，移除硬冻结
- 失败立即清除缓存，快速自愈
- Session 自动重建
- 内置完整频道列表（油管直播.txt），支持外部文件覆盖
- 支持日志开启/关闭
"""

import re
import sys
import json
import html
import time
import base64
import os
import requests
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse
from base.spider import Spider
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.append('..')

# ==================== 内置频道列表（油管直播.txt 全部内容） ====================
DEFAULT_TXT_CONTENT = r"""台湾直播,#genre#
凤凰卫视资讯,https://www.youtube.com/watch?v=Ry--eMIjYLQ
中天新闻台,https://www.youtube.com/watch?v=vr3XyVCR4T0
TVBS新闻台,https://www.youtube.com/watch?v=2mCSYvcfhtc
TVBS网络台,https://www.youtube.com/watch?v=m_dhMSvUCIc
TVBS优选台,https://www.youtube.com/watch?v=WAUECPu9EOw
寰宇新闻台,https://www.youtube.com/watch?v=6IquAgfvYmc
寰宇新闻二,https://www.youtube.com/watch?v=Ej3LQM_lTEw
寰宇台湾台,https://www.youtube.com/watch?v=w87VGpgd90U
寰宇财经台,https://www.youtube.com/watch?v=yAUQQ0DhPxI
东森新闻台,https://www.youtube.com/watch?v=V1p33hqPrUk
东森直播台,https://www.youtube.com/watch?v=E0zhe2gkXBs
东森财经台,https://www.youtube.com/watch?v=1I2iq41Akmo
东森财经台,https://www.youtube.com/watch?v=AEBeWMM1atA
东森综合台,https://www.youtube.com/watch?v=cimbpAZUjzw
三立新闻台,https://www.youtube.com/watch?v=pF507BLtbqU
三立財經台,https://www.youtube.com/watch?v=pF507BLtbqU
公视新闻台,https://www.youtube.com/watch?v=quwqlazU-c8
民视新闻台,https://www.youtube.com/watch?v=ylYJSBUgaMA
华视新闻台,https://www.youtube.com/watch?v=wM0g8EoUZ_E
中视新闻台,https://www.youtube.com/watch?v=TCnaIE_SAtM
非凡新闻台,https://www.youtube.com/watch?v=wAUx3pywTt8
镜电视新闻,https://www.youtube.com/watch?v=5n0y6b0Q25o
倪珍播新闻,https://www.youtube.com/watch?v=RRybv1kEnCU
凤凰资讯台,https://www.youtube.com/watch?v=fN9uYWCjQaw
亚洲新闻台,https://www.youtube.com/watch?v=XWq5kBlakcQ
半岛新闻台,https://www.youtube.com/watch?v=gCNeDWCI0vo
新传媒娱乐,https://www.youtube.com/watch?v=ipqTkEH3mhE
台湾大搜索,https://www.youtube.com/watch?v=Q0jusAya5s4
经典综艺台,https://www.youtube.com/watch?v=ADDSmXoPDY8
信大电视台,https://www.youtube.com/watch?v=OqcwT72qe0k
大陆寻奇台,https://www.youtube.com/watch?v=LqXVZ_hK3Xs
大爱电视台,https://www.youtube.com/watch?v=MIqUplvSRWA
大爱电视二,https://www.youtube.com/watch?v=QDxRJP-wfeI
太阳马戏团,https://www.youtube.com/watch?v=swgouFE-5e4
台视新闻台,https://www.youtube.com/watch?v=xL0ch83RAK8
三立新闻,https://www.youtube.com/watch?v=MV9mI0GChwo
三立 iNEWS,https://www.youtube.com/watch?v=BlKaF8og0jo
寰宇财经新闻,https://www.youtube.com/watch?v=WTRQiVWK1jY
大爱电视2,https://www.youtube.com/watch?v=DTNkEm6jaqQ
中视综艺台,https://www.youtube.com/watch?v=A98LJq71BZg
TaiwanPlus,https://www.youtube.com/watch?v=Vrs-AeKZIEg
TVBS选新闻,https://www.youtube.com/watch?v=o_-hSMgpAzs
TVBS新闻,https://m.youtube.com/@TVBSNEWS01/streams/1
东森新闻,https://m.youtube.com/@newsebc/streams/1
民视新闻,https://m.youtube.com/@FTV_News/streams/1
中天新闻,https://m.youtube.com/@中天電視CtiTv/streams/1
三立财经,https://m.youtube.com/@setinews/live
东森财经,https://m.youtube.com/@57ETFN/streams/2
华视新闻,https://m.youtube.com/@CtsTw/streams/1
中视新闻,https://m.youtube.com/@twctvnews/streams/1

海外直播,#genre#
SEA POP,https://www.youtube.com/watch?v=RjZr3ksn_F8
SEA POP,https://www.youtube.com/watch?v=mHfL7Fl3XW8
DuaLipa,https://www.youtube.com/watch?v=Gt43Zqf3s0U
TheKPOP,https://www.youtube.com/watch?v=JVocS7Yftw8
SunWave,https://www.youtube.com/watch?v=RVk6c_SjOm8
AlanWalker,https://www.youtube.com/watch?v=9l63T77YL2c
RelaxingNature,https://www.youtube.com/watch?v=vdeJ3QY6w6g
DiscoveryRelaxation,https://www.youtube.com/watch?v=6iQCt1X8jZU
BBC Earth,https://www.youtube.com/watch?v=1LhlXiSc5NY
BBC Earth Science,https://www.youtube.com/watch?v=KGZtDK8hZ60
Discovery,https://www.youtube.com/watch?v=OnI-uUxJZuE
Discovery,https://www.youtube.com/watch?v=ohKj2ma9mfM
Love Nature,https://www.youtube.com/watch?v=Zns4k_dICzs
Love Nature,https://www.youtube.com/watch?v=QhahoVG0BfI
Earth Planet,https://www.youtube.com/watch?v=sYod9dCf5Cw
Earth Planet,https://www.youtube.com/watch?v=QXeCPubARfo
Nat Geo Kids,https://www.youtube.com/watch?v=q5xC6wv9Ut0
Nat Geo Kids,https://www.youtube.com/watch?v=H-h657jXQyA
Nat Geo Animals,https://www.youtube.com/watch?v=J4IYwyEUwrI
Nat Geo Animals,https://www.youtube.com/watch?v=MiQe9ob9aDc
National Geographic,https://www.youtube.com/watch?v=eVty8-fUGJY
National Geographic,https://www.youtube.com/watch?v=lJOROUvD8sU
Love Nature Predators,https://www.youtube.com/watch?v=YRIkyaX2in0
Love Nature Predators,https://www.youtube.com/watch?v=7ByKk5NPsRw
Ultimate Nature Documentaries,https://www.youtube.com/watch?v=i6DH-eLlLjo
Ultimate Nature Documentaries,https://www.youtube.com/watch?v=JVXC4DrH6PA
CCTV4 中文国际,https://www.youtube.com/watch?v=SdzewdkJa-o
FRANCE 24,https://www.youtube.com/watch?v=l8PMl7tUDIE
ANN新闻,https://www.youtube.com/watch?v=coYw-eVU0Ks
TBS新闻,https://www.youtube.com/watch?v=ohI356mwBp8
NHK WORLD,https://www.youtube.com/watch?v=f0lYkdA-Gtw
ABC新闻,https://www.youtube.com/watch?v=-mvUkiILTqI
ABC7纽约,https://www.youtube.com/watch?v=VrhYz4CL70I
CBS新闻,https://www.youtube.com/watch?v=e_vEct0OMT4
FOX,https://www.youtube.com/watch?v=YDfiTGGPYCk
联合国,https://www.youtube.com/watch?v=wfAa1GiNdgM
FRANCE24,https://www.youtube.com/watch?v=Ap-UM1O9RBU
欧洲新闻,https://www.youtube.com/watch?v=pykpO5kQJ98
Discovery,https://www.youtube.com/watch?v=Ucs_Kj6Yaog
BBC News,https://www.youtube.com/@BBCNews/streams
CNN,https://www.youtube.com/@CNN/streams
Sky News,https://www.youtube.com/@SkyNews/streams
Fox News,https://www.youtube.com/@FoxNews/streams
Al Jazeera,https://www.youtube.com/@aljazeera/streams
RT,https://www.youtube.com/@RT/streams
CCTV,https://www.youtube.com/@CCTV/streams
France 24,https://www.youtube.com/@France24/streams
DW News,https://www.youtube.com/@dwnews/streams
Bloomberg TV,https://www.youtube.com/@Bloomberg/streams
CNBC,https://www.youtube.com/@CNBC/streams
Sky Sports,https://www.youtube.com/@SkySports/streams
NBA,https://www.youtube.com/@NBA/streams
MLB,https://www.youtube.com/@MLB/streams
NFL,https://www.youtube.com/@NFL/streams
NASA,https://www.youtube.com/@NASA/streams
SpaceX,https://www.youtube.com/@SpaceX/streams
TED Talks,https://www.youtube.com/@TED/streams
Kurzgesagt – In a Nutshell,https://www.youtube.com/@kurzgesagt/streams
"""

# ==================== 日志全局开关 ====================
DEBUG_ENABLED = False
DEBUG_LOG = '/sdcard/Download/log/yt_tw_news_debug.log'

def debug_log(message, data=None):
    if not DEBUG_ENABLED:
        return
    try:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        if data is not None:
            if isinstance(data, (dict, list)):
                line += ' ' + json.dumps(data, ensure_ascii=False, default=str)
            else:
                line += ' ' + str(data)
        with open(DEBUG_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

# ==================== YouTubeLiveLite（原版不变） ====================
class YouTubeLiveLite:
    def __init__(self, session, headers=None, config=None):
        self.session = session
        self.headers = headers or {}
        self.config = config or {}
        self.cache = {}
        self.cache_ttl = int(self.config.get('live_cache_ttl') or 45)

    @staticmethod
    def extract_video_id(text):
        text = str(text or '').strip()
        for pattern in [
            r'(?:v=|/v/|/embed/|/shorts/|youtu\.be/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$',
        ]:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        raise Exception('无法识别 YouTube 视频 ID')

    def extract_live(self, url_or_id):
        video_id = self.extract_video_id(url_or_id)
        now = time.time()
        cached = self.cache.get(video_id)
        if cached and cached.get('expires', 0) > now:
            debug_log('live cache hit', {'video_id': video_id, 'ttl': int(cached.get('expires', 0) - now)})
            return cached.get('data')

        watch_url = f'https://www.youtube.com/watch?v={video_id}'
        debug_log('live extract start', {'input': url_or_id, 'video_id': video_id})
        response = self._get(watch_url)
        page = response.text
        player_response = self._extract_initial_player_response(page) or {}
        ytcfg = self._extract_ytcfg(page) or {}
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self._search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        visitor_data = self._extract_visitor_data(ytcfg, player_response)
        status_obj = player_response.get('playabilityStatus') or {}
        streaming = player_response.get('streamingData') or {}
        details = player_response.get('videoDetails') or {}

        debug_log('live page parsed', {
            'status': status_obj.get('status'),
            'reason': status_obj.get('reason'),
            'is_live': details.get('isLiveContent'),
            'has_hls': bool(streaming.get('hlsManifestUrl')),
            'has_api_key': bool(api_key),
            'has_visitor': bool(visitor_data),
        })

        page_hls_url = streaming.get('hlsManifestUrl') or ''
        hls_source = 'page' if page_hls_url else ''
        api_data = None
        if api_key:
            api_data = self._call_player_api(video_id, api_key, ytcfg, watch_url, visitor_data)
            if api_data:
                api_streaming = api_data.get('streamingData') or {}
                api_details = api_data.get('videoDetails') or {}
                api_hls_url = api_streaming.get('hlsManifestUrl') or ''
                if api_hls_url:
                    streaming = api_streaming
                    hls_source = api_data.get('_client_name') or 'api'
                elif not page_hls_url and api_streaming:
                    streaming = api_streaming
                    hls_source = api_data.get('_client_name') or 'api_no_hls'
                if api_details:
                    details = api_details
                status_obj = api_data.get('playabilityStatus') or status_obj
        if not (streaming.get('hlsManifestUrl') or '') and page_hls_url:
            streaming = dict(streaming or {})
            streaming['hlsManifestUrl'] = page_hls_url
            hls_source = 'page_fallback'

        hls_url = streaming.get('hlsManifestUrl') or ''
        is_live = bool(details.get('isLiveContent') or hls_url)
        status = status_obj.get('status') or ''
        reason = status_obj.get('reason') or ''
        title = details.get('title') or video_id

        data = {
            'id': video_id,
            'title': title,
            'is_live': is_live,
            'status': status,
            'reason': reason,
            'hls_url': hls_url,
            'duration': int(details.get('lengthSeconds') or 0),
        }
        debug_log('live extract result', {
            'video_id': video_id,
            'status': status,
            'is_live': is_live,
            'has_hls': bool(hls_url),
            'hls_source': hls_source,
            'duration': data.get('duration'),
        })
        self.cache[video_id] = {'data': data, 'expires': time.time() + self.cache_ttl}
        return data

    def _get(self, url, **kwargs):
        headers = self.headers.copy()
        headers.update(kwargs.pop('headers', {}) or {})
        response = self.session.get(url, headers=headers, timeout=kwargs.pop('timeout', 30), **kwargs)
        response.raise_for_status()
        return response

    def _post_json(self, url, payload, headers=None):
        final_headers = self.headers.copy()
        final_headers.update({'Content-Type': 'application/json', 'Origin': 'https://www.youtube.com'})
        if headers:
            final_headers.update({k: v for k, v in headers.items() if v})
        response = self.session.post(url, json=payload, headers=final_headers, timeout=30)
        response.raise_for_status()
        return response.json()

    def _call_player_api(self, video_id, api_key, ytcfg, referer, visitor_data=None):
        context = ytcfg.get('INNERTUBE_CONTEXT') or {
            'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'en', 'gl': 'US'}
        }
        clients = [
            {'client': {'clientName': 'ANDROID', 'clientVersion': '21.02.35', 'androidSdkVersion': 30, 'userAgent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip', 'osName': 'Android', 'osVersion': '11', 'hl': 'en', 'gl': 'US'}},
            {'client': {'clientName': 'IOS', 'clientVersion': '21.02.3', 'deviceMake': 'Apple', 'deviceModel': 'iPhone16,2', 'userAgent': 'com.google.ios.youtube/21.02.3 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)', 'osName': 'iPhone', 'osVersion': '18.3.2.22D82', 'hl': 'en', 'gl': 'US'}},
            {'client': {'clientName': 'MWEB', 'clientVersion': '2.20260115.01.00', 'userAgent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', 'hl': 'en', 'gl': 'US'}},
            context,
        ]
        for ctx in clients:
            client = ctx.get('client') or {}
            client_name = client.get('clientName') or 'WEB'
            try:
                url = f'https://www.youtube.com/youtubei/v1/player?key={quote(api_key)}&prettyPrint=false'
                headers = {
                    'Referer': referer,
                    'X-YouTube-Client-Name': str(self._client_name_id(client_name)),
                    'X-YouTube-Client-Version': client.get('clientVersion') or '',
                }
                if visitor_data:
                    headers['X-Goog-Visitor-Id'] = visitor_data
                if client.get('userAgent'):
                    headers['User-Agent'] = client.get('userAgent')
                payload = {
                    'context': ctx,
                    'videoId': video_id,
                    'contentCheckOk': True,
                    'racyCheckOk': True,
                }
                data = self._post_json(url, payload, headers=headers)
                streaming = data.get('streamingData') or {}
                status = (data.get('playabilityStatus') or {}).get('status')
                debug_log('live api client', {
                    'client': client_name,
                    'status': status,
                    'has_hls': bool(streaming.get('hlsManifestUrl')),
                    'has_streaming': bool(streaming),
                })
                if streaming.get('hlsManifestUrl'):
                    data['_client_name'] = client_name
                    return data
            except Exception as e:
                debug_log('live api client error', {'client': client_name, 'error': repr(e)})
        return None

    def _extract_visitor_data(self, ytcfg, player_response):
        return (
            self.config.get('visitor_data')
            or ytcfg.get('VISITOR_DATA')
            or (((ytcfg.get('INNERTUBE_CONTEXT') or {}).get('client') or {}).get('visitorData'))
            or ((player_response.get('responseContext') or {}).get('visitorData'))
        )

    def _extract_ytcfg(self, text):
        match = re.search(r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;', text or '', re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _extract_initial_player_response(self, text):
        return self._extract_json_after(text, 'ytInitialPlayerResponse')

    def _extract_json_after(self, text, marker):
        pos = (text or '').find(marker)
        if pos < 0:
            return None
        start = text.find('{', pos)
        if start < 0:
            return None
        depth = 0
        in_str = None
        escape = False
        for index in range(start, len(text)):
            char = text[index]
            if escape:
                escape = False
                continue
            if char == '\\':
                escape = True
                continue
            if in_str:
                if char == in_str:
                    in_str = None
                continue
            if char in ('"', "'"):
                in_str = char
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:index + 1])
                    except Exception:
                        return None
        return None

    @staticmethod
    def _search(pattern, text, default=None):
        match = re.search(pattern, text or '', re.S)
        return match.group(1) if match else default

    def _client_name_id(self, client_name):
        return {
            'WEB': 1,
            'MWEB': 2,
            'ANDROID': 3,
            'IOS': 5,
            'TVHTML5': 7,
            'ANDROID_VR': 28,
            'WEB_EMBEDDED_PLAYER': 56,
            'WEB_REMIX': 67,
        }.get(client_name, 1)

# ==================== Spider 类 ====================
class Spider(Spider):
    def getName(self):
        return "YouTube台湾新闻直播"

    def init(self, extend):
        global DEBUG_ENABLED

        try:
            self.extendDict = json.loads(extend) if extend else {}
        except:
            self.extendDict = {}

        # ----- 日志开关（默认开启） -----
        debug_setting = self.extendDict.get('debug') or self.extendDict.get('log_enabled')
        if debug_setting is not None:
            if isinstance(debug_setting, bool):
                DEBUG_ENABLED = debug_setting
            elif isinstance(debug_setting, str):
                DEBUG_ENABLED = debug_setting.lower() not in ('false', '0', 'no', 'off')
            else:
                DEBUG_ENABLED = bool(debug_setting)
        else:
            DEBUG_ENABLED = True  # 默认开启

        debug_log("日志开关", {"enabled": DEBUG_ENABLED})

        # 创建 Session 并配置重试策略
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.youtube.com/'
        })
        self._session_created_at = time.time()   # 记录创建时间

        # ----- 代理配置：支持数组自动探测 -----
        self.proxy_str = None
        self._proxy_configured = False
        proxy_val = self.extendDict.get('proxy')

        if proxy_val is not None:
            if isinstance(proxy_val, list):
                found = False
                for p in proxy_val:
                    p_norm = self._normalize_proxy_url(p)
                    if p_norm:
                        test_proxies = {'http': p_norm, 'https': p_norm}
                        try:
                            r = requests.get('https://www.youtube.com', proxies=test_proxies, timeout=2)
                            if r.status_code < 400:
                                self.session.proxies = test_proxies
                                self.proxy_str = p_norm.replace('http://', '').replace('https://', '')
                                self._proxy_configured = True
                                debug_log('使用用户列表代理', {'proxy': p_norm})
                                found = True
                                break
                        except Exception:
                            continue
                if not found:
                    self.session.proxies = {}
                    self.proxy_str = ''
                    self._proxy_configured = False
                    debug_log('用户列表代理均不可用，回退系统代理')
            elif isinstance(proxy_val, str):
                p_norm = self._normalize_proxy_url(proxy_val)
                if p_norm:
                    self.session.proxies = {'http': p_norm, 'https': p_norm}
                    self.proxy_str = p_norm.replace('http://', '').replace('https://', '')
                    self._proxy_configured = True
                    debug_log('使用 ext 传入代理（字符串）', {'proxy': p_norm})
                else:
                    self._auto_detect_proxy()
            elif isinstance(proxy_val, dict):
                proxies = {}
                for k, v in proxy_val.items():
                    if k in ('http', 'https') and v:
                        v = self._normalize_proxy_url(v)
                        if v:
                            proxies[k] = v
                if proxies:
                    self.session.proxies = proxies
                    self.proxy_str = (proxies.get('https') or proxies.get('http') or '').replace('http://', '').replace('https://', '')
                    self._proxy_configured = True
                    debug_log('使用 ext 传入的字典代理', proxies)
                else:
                    self._auto_detect_proxy()
            else:
                self._auto_detect_proxy()
        else:
            self._auto_detect_proxy()

        # 初始化 YouTube 提取器
        self.yt = YouTubeLiveLite(self.session, self.session.headers, {})
        # 缓存
        self.video_cache = {}
        self.m3u8_cache = {}
        self.video_ttl = 45
        self.m3u8_ttl = 15

        # ----- 频道列表加载：优先使用外部配置，否则使用内置 TXT -----
        self.channels = []
        custom = self.extendDict.get('channels')
        loaded = False

        if custom:
            if isinstance(custom, list):
                if all(isinstance(c, dict) and 'id' in c and 'name' in c and 'url' in c for c in custom):
                    self.channels = custom
                    loaded = True
                    debug_log("使用自定义频道列表（直接传入JSON列表）", {"count": len(self.channels)})
                else:
                    debug_log("自定义频道列表格式无效，回退内置列表")
            elif isinstance(custom, str):
                if custom.startswith('http://') or custom.startswith('https://'):
                    # 远程 URL
                    try:
                        resp = self.session.get(custom, timeout=10)
                        if resp.status_code == 200:
                            try:
                                txt_data = resp.content.decode('utf-8')
                            except UnicodeDecodeError:
                                txt_data = resp.content.decode('utf-8', errors='ignore')
                            # 尝试 JSON
                            try:
                                data = json.loads(txt_data)
                                if isinstance(data, list) and all(isinstance(c, dict) and 'id' in c and 'name' in c and 'url' in c for c in data):
                                    self.channels = data
                                    loaded = True
                                    debug_log("从远程 URL 加载频道列表（JSON）", {"url": custom, "count": len(self.channels)})
                                else:
                                    debug_log("远程 JSON 数据格式无效，尝试 TXT 解析", {"url": custom})
                            except Exception as e:
                                debug_log("远程 JSON 解析失败，尝试 TXT 解析", {"url": custom, "error": repr(e)})
                            if not loaded:
                                try:
                                    channels, group = self._parse_txt_channels(txt_data)
                                    if channels:
                                        self.channels = channels
                                        loaded = True
                                        self._current_group = group
                                        debug_log("从远程 URL 加载频道列表（TXT）", {"url": custom, "count": len(self.channels), "group": group})
                                    else:
                                        debug_log("远程 TXT 解析失败，无有效频道", {"url": custom})
                                except Exception as e2:
                                    debug_log("远程 TXT 解析异常", {"url": custom, "error": repr(e2)})
                        else:
                            debug_log("远程请求失败", {"url": custom, "status": resp.status_code})
                    except Exception as e:
                        debug_log("远程加载失败", {"url": custom, "error": repr(e)})
                else:
                    # 本地文件
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    if custom.startswith('./'):
                        file_path = os.path.join(script_dir, custom[2:])
                    else:
                        file_path = custom
                    if file_path.lower().endswith('.txt'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                txt_content = f.read()
                            channels, group = self._parse_txt_channels(txt_content)
                            if channels:
                                self.channels = channels
                                loaded = True
                                self._current_group = group
                                debug_log("从本地 TXT 文件加载频道列表", {"path": file_path, "count": len(self.channels), "group": group})
                            else:
                                debug_log("TXT 文件内容无效", {"path": file_path})
                        except Exception as e:
                            debug_log("读取本地 TXT 失败", {"path": file_path, "error": repr(e)})
                    else:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            if isinstance(data, list) and all(isinstance(c, dict) and 'id' in c and 'name' in c and 'url' in c for c in data):
                                self.channels = data
                                loaded = True
                                debug_log("从本地 JSON 文件加载频道列表", {"path": file_path, "count": len(self.channels)})
                            else:
                                debug_log("JSON 文件内容格式无效", {"path": file_path})
                        except Exception as e:
                            debug_log("读取本地 JSON 失败", {"path": file_path, "error": repr(e)})
            else:
                debug_log("channels 字段类型不支持，回退内置列表")

        # 如果未加载成功，使用内置 TXT 内容
        if not loaded:
            try:
                channels, group = self._parse_txt_channels(DEFAULT_TXT_CONTENT)
                if channels:
                    self.channels = channels
                    self._current_group = group
                    debug_log("使用内置频道列表（油管直播.txt）", {"count": len(self.channels)})
                else:
                    # 极端情况：内置解析失败，使用硬编码的默认列表（保留几个）
                    self.channels = [
                        {"id": "CTI", "name": "中天新聞", "url": "https://m.youtube.com/@中天電視CtiTv/streams/1"},
                        {"id": "TVBS", "name": "TVBS新聞", "url": "https://m.youtube.com/@TVBSNEWS01/streams/1"},
                        {"id": "EBC", "name": "東森新聞", "url": "https://m.youtube.com/@newsebc/streams/1"},
                        {"id": "FTV", "name": "民視新聞", "url": "https://m.youtube.com/@FTV_News/streams/1"},
                    ]
                    debug_log("内置解析失败，使用硬编码备用列表", {"count": len(self.channels)})
            except Exception as e:
                debug_log("内置 TXT 解析异常", {"error": repr(e)})
                self.channels = [
                    {"id": "CTI", "name": "中天新聞", "url": "https://m.youtube.com/@中天電視CtiTv/streams/1"},
                    {"id": "TVBS", "name": "TVBS新聞", "url": "https://m.youtube.com/@TVBSNEWS01/streams/1"},
                    {"id": "EBC", "name": "東森新聞", "url": "https://m.youtube.com/@newsebc/streams/1"},
                    {"id": "FTV", "name": "民視新聞", "url": "https://m.youtube.com/@FTV_News/streams/1"},
                ]
                debug_log("使用硬编码备用列表", {"count": len(self.channels)})

        debug_log("Spider init 完成", {"channels": len(self.channels)})

    # ==================== Session 健康检查 ====================
    def _ensure_session(self):
        """检查 Session 状态，必要时重建（每 5 分钟或连接异常时）"""
        if not hasattr(self, '_session_created_at'):
            self._session_created_at = time.time()
            return
        if time.time() - self._session_created_at > 300:
            self._rebuild_session()
            return
        try:
            self.session.head('https://www.youtube.com', timeout=3)
        except Exception:
            self._rebuild_session()

    def _rebuild_session(self):
        """重建 Session 并保留原有配置（代理、头等）"""
        old_session = self.session
        new_session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=10)
        new_session.mount('http://', adapter)
        new_session.mount('https://', adapter)
        new_session.headers.update(old_session.headers)
        if old_session.proxies:
            new_session.proxies = old_session.proxies.copy()
        self.session = new_session
        self.yt.session = self.session
        self._session_created_at = time.time()
        try:
            old_session.close()
        except:
            pass
        debug_log("Session 已重建")

    # ==================== 解析 TXT（原版） ====================
    def _parse_txt_channels(self, content):
        """解析 TXT 格式（M3U风格），正确识别 #genre# 分组"""
        lines = content.splitlines()
        channels = []
        current_group = "油管直播"
        seen = set()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if '#genre#' in line:
                parts = line.split(',')
                if len(parts) >= 1:
                    group_name = parts[0].strip()
                    if group_name.startswith('#'):
                        group_name = group_name[1:].strip()
                    if group_name:
                        current_group = group_name
                continue
            if line.startswith('#'):
                continue
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if not url or not name:
                    continue
                try:
                    video_id = YouTubeLiveLite.extract_video_id(url)
                except:
                    video_id = f"unknown_{abs(hash(url))}"
                base_id = video_id
                if base_id in seen:
                    idx = 1
                    while f"{base_id}_{idx}" in seen:
                        idx += 1
                    video_id = f"{base_id}_{idx}"
                seen.add(video_id)
                channels.append({
                    'id': video_id,
                    'name': name,
                    'url': url,
                    'group': current_group
                })
        return channels, current_group

    def _normalize_proxy_url(self, url):
        if not url:
            return ''
        url = url.strip()
        if not re.match(r'^[a-zA-Z]+://', url):
            url = 'http://' + url
        return url

    def _auto_detect_proxy(self):
        proxy_list = [
            "http://127.0.0.1:2080",
            "http://127.0.0.1:7890",
            "http://127.0.0.1:10809",
            "http://127.0.0.1:20172",
            "http://127.0.0.1:10172",
            "http://127.0.0.1:7891",
            "http://127.0.0.1:10808",
            "http://127.0.0.1:1087",
            "http://127.0.0.1:3128",
            "http://127.0.0.1:1080",
            "http://127.0.0.1:8080",
            "http://127.0.0.1:9090"
        ]
        for p in proxy_list:
            try:
                test_proxies = {'http': p, 'https': p}
                r = requests.get('https://www.youtube.com', proxies=test_proxies, timeout=2)
                if r.status_code < 400:
                    self.session.proxies = test_proxies
                    self.proxy_str = p.replace('http://', '').replace('https://', '')
                    self._proxy_configured = True
                    debug_log('内置代理探测成功', {'proxy': p})
                    return
            except Exception:
                continue
        self.session.proxies = {}
        self.proxy_str = ''
        self._proxy_configured = False
        debug_log('所有内置代理不可用，回退到系统/全局代理')

    def destroy(self):
        if self.session:
            self.session.close()
        debug_log("Spider destroyed")

    def liveContent(self, url):
        lines = ['#EXTM3U']
        for ch in self.channels:
            proxy_url = f"http://127.0.0.1:9978/proxy?do=py&type=youtube_live&channel={ch['id']}"
            name = ch["name"].replace('"', '\\"').replace(',', '\\,')
            group_attr = f' group-title="{ch.get("group", "油管直播")}"' if ch.get("group") else ''
            lines.append(f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{name}"{group_attr},{name}')
            lines.append(proxy_url)
        return '\n'.join(lines)

    def localProxy(self, params):
        t = params.get('type')
        if t == 'youtube_live':
            return self._handle_live(params)
        elif t == 'ts':
            return self._handle_ts(params)
        return [404, "text/plain", "未知请求"]

    # ==================== 核心方法 ====================
    def _handle_live(self, params):
        channel_id = params.get('channel')
        if not channel_id:
            return self._error_response("缺少频道ID")

        now = time.time()

        # 检查 m3u8 缓存
        cached_m3u8 = self.m3u8_cache.get(channel_id)
        if cached_m3u8 and cached_m3u8.get('expires', 0) > now:
            debug_log("M3U8 cache hit", {"channel": channel_id})
            return [200, "application/vnd.apple.mpegurl", cached_m3u8['content']]

        # 获取视频信息（video_cache 缓存 45 秒）
        video_info = self.video_cache.get(channel_id)
        if not video_info or video_info.get('expires', 0) <= now:
            debug_log("Refreshing video info", {"channel": channel_id})
            self._ensure_session()
            info = self._get_live_video_info(channel_id)
            if not info:
                return self._error_response("无法获取直播视频")
            self.video_cache[channel_id] = {
                'video_id': info['video_id'],
                'hls_url': info['hls_url'],
                'expires': now + self.video_ttl
            }
            video_info = self.video_cache[channel_id]

        # 获取并重写 m3u8
        m3u8_content = self._fetch_and_rewrite_m3u8(video_info['hls_url'], channel_id)
        if not m3u8_content:
            self.video_cache.pop(channel_id, None)
            debug_log("M3U8 fetch failed, cleared video_cache", {"channel": channel_id})
            return self._error_response("获取 M3U8 失败")

        self.m3u8_cache[channel_id] = {
            'content': m3u8_content,
            'expires': now + self.m3u8_ttl
        }
        return [200, "application/vnd.apple.mpegurl", m3u8_content]

    def _handle_ts(self, params):
        b64_url = params.get('url', '')
        if not b64_url:
            return self._error_response("缺少 TS URL")
        try:
            ts_url = self._b64_decode(b64_url)
        except:
            return self._error_response("TS URL 解码失败")

        self._ensure_session()

        try:
            resp = self.session.get(ts_url, headers={
                'User-Agent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip',
                'Accept': '*/*',
                'Referer': 'https://www.youtube.com/',
            }, timeout=30)
            if resp.status_code != 200:
                return self._error_response(f"TS 请求失败 {resp.status_code}")
            return [200, "video/MP2T", resp.content, {
                'Content-Type': 'video/MP2T',
                'Content-Length': str(len(resp.content)),
                'Cache-Control': 'no-cache'
            }]
        except Exception as e:
            debug_log("TS proxy error", {"url": ts_url, "error": repr(e)})
            return self._error_response(f"TS 代理异常: {str(e)}")

    def _get_live_video_info(self, channel_id):
        """根据频道ID获取当前直播视频ID和HLS URL，支持频道页和直接视频链接"""
        ch = next((c for c in self.channels if c['id'] == channel_id), None)
        if not ch:
            return None

        url = ch['url']

        # 直接视频链接
        if 'watch?v=' in url or 'youtu.be/' in url:
            try:
                video_id = YouTubeLiveLite.extract_video_id(url)
            except Exception as e:
                debug_log("提取视频ID失败", {"url": url, "error": repr(e)})
                return None
            try:
                data = self.yt.extract_live(video_id)
                if data.get('is_live') and data.get('hls_url'):
                    debug_log("直接视频链接 - 获取直播成功", {"video_id": video_id})
                    return {'video_id': video_id, 'hls_url': data['hls_url']}
                else:
                    debug_log("直接视频链接 - 非直播或无HLS", {"video_id": video_id, "is_live": data.get('is_live')})
                    return None
            except Exception as e:
                debug_log("直接视频链接 - extract_live失败", {"video_id": video_id, "error": repr(e)})
                return None

        # ----- 频道页逻辑：规范化 URL -----
        if 'm.youtube.com' in url:
            url = url.replace('m.youtube.com', 'www.youtube.com')
        try:
            parsed = urlparse(url)
            encoded_path = quote(parsed.path, safe='/')
            url = urlunparse((parsed.scheme, parsed.netloc, encoded_path, parsed.params, parsed.query, parsed.fragment))
        except Exception as e:
            debug_log("URL编码失败，使用原始URL", {"url": url, "error": repr(e)})

        self._ensure_session()

        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html_text = resp.text
        except Exception as e:
            debug_log("获取频道页失败", {"url": url, "error": repr(e)})
            return None

        video_ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', html_text)
        if not video_ids:
            debug_log("频道页未找到视频ID", {"url": url})
            return None

        seen = set()
        for vid in video_ids:
            if vid in seen:
                continue
            seen.add(vid)
            try:
                data = self.yt.extract_live(vid)
                if data.get('is_live') and data.get('hls_url'):
                    debug_log("频道页找到直播视频", {"video_id": vid, "hls_url": data['hls_url'][:80]})
                    return {'video_id': vid, 'hls_url': data['hls_url']}
            except Exception as e:
                debug_log("频道页 - extract_live失败", {"video_id": vid, "error": repr(e)})
                continue

        debug_log("频道页未找到直播视频", {"url": url})
        return None

    def _fetch_and_rewrite_m3u8(self, hls_url, channel_id):
        self._ensure_session()

        try:
            resp = self.session.get(hls_url, headers={
                'User-Agent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip',
                'Referer': 'https://www.youtube.com/',
            }, timeout=30)
            resp.raise_for_status()
            text = resp.text
        except Exception as e:
            debug_log("Failed to fetch master m3u8", {"url": hls_url, "error": repr(e)})
            return None

        if '#EXT-X-STREAM-INF' in text:
            variant_url = self._pick_best_variant(hls_url, text)
            if not variant_url:
                debug_log("No variant found", {"master": hls_url})
                return None
            try:
                resp = self.session.get(variant_url, headers={
                    'User-Agent': 'com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip',
                    'Referer': 'https://www.youtube.com/',
                }, timeout=30)
                resp.raise_for_status()
                text = resp.text
            except Exception as e:
                debug_log("Failed to fetch variant m3u8", {"url": variant_url, "error": repr(e)})
                return None

        rewritten = []
        for line in text.splitlines():
            if line.startswith('#'):
                rewritten.append(line)
            else:
                ts_url = urljoin(hls_url, line.strip())
                encoded = self._b64_encode(ts_url)
                proxy_ts = f"http://127.0.0.1:9978/proxy?do=py&type=ts&url={encoded}&channel={channel_id}"
                rewritten.append(proxy_ts)
        return '\n'.join(rewritten) + '\n'

    def _pick_best_variant(self, base_url, text):
        lines = text.splitlines()
        best_score = -1
        best_url = ''
        for i, line in enumerate(lines):
            if not line.startswith('#EXT-X-STREAM-INF'):
                continue
            bandwidth = re.search(r'BANDWIDTH=(\d+)', line)
            resolution = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            score = 0
            if bandwidth:
                score += int(bandwidth.group(1))
            if resolution:
                score += int(resolution.group(1)) * int(resolution.group(2))
            for j in range(i + 1, len(lines)):
                if not lines[j].strip() or lines[j].startswith('#'):
                    continue
                if score > best_score:
                    best_score = score
                    best_url = urljoin(base_url, lines[j].strip())
                break
        return best_url

    def _b64_encode(self, s):
        return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')

    def _b64_decode(self, s):
        padding = 4 - (len(s) % 4)
        if padding != 4:
            s += '=' * padding
        return base64.urlsafe_b64decode(s).decode()

    def _error_response(self, msg):
        error_m3u8 = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-TARGETDURATION:10
#EXTINF:10.0,
error.ts
#EXT-X-ENDLIST
# {msg}
"""
        return [500, "application/vnd.apple.mpegurl", error_m3u8]