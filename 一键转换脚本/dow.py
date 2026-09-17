# -*- coding: utf-8 -*-
# @version v2.2 - Windows独立版 + TVBox插件二合一 | 修复饭太硬(www.饭太硬.cc/tv)等站点"图片内嵌JSON"下载本地失败问题
# @author 陆小凤 (修改适配整合)
# 说明：
# 1. Windows 环境：完全兼容原 dow.txt 所有命令行参数、配置格式与功能（强制域名、强制覆盖等）
# 2. TVBox/OKTV 环境：自动启用完整 UI 管理、批量操作、接口切换、持久化配置等 v5.4 功能
# 3. 核心能力增强：循环多层解密、HEAD 请求容错、spider/jar 强制下载、遗漏文件补下、智能路径检测
# 4. 本次更新(v2.2)：针对饭太硬等站点 —— 接口返回"伪装图片(JPEG)"、图片末尾以 ** 拼接 base64 编码的完整 box JSON，
#    且 JSON 内含有 JS 注释(// 行注释)导致 json.loads 失败。新增：
#      - _extract_json_from_image_bytes()  二进制层面稳健提取图片内嵌 JSON（不依赖文字解码）
#      - strip_js_comments()               剥离 JSON 中的 JS 行注释（保留字符串内 //）
#      - _safe_json_loads()                统一安全 JSON 解析入口（自动剥注释 + 片段提取兜底）
#      - spider/jar 字段本地文件统一强制 .jar 扩展名，保证本地 box 引用正确
# 5. 兼容：保留 v2.1 全量 GitHub 代理识别 / 归一化逻辑，多代理场景下解密正常
import base64
import copy
import hashlib
import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ===================== 可选依赖检测 =====================
# AES 解密库
_HAS_AES = False
_AES_MODE = None
try:
    from Crypto.Cipher import AES as _AES_IMPL
    _AES_MODE = 'pycryptodome'
    _HAS_AES = True
except ImportError:
    try:
        import pyaes as _AES_IMPL
        _AES_MODE = 'pyaes'
        _HAS_AES = True
    except ImportError:
        pass

# TVBox 基类与 Android 环境
_HAS_BASE_SPIDER = False
_HAS_ANDROID = False
BaseSpider = object
jclass = None
dynamic_proxy = None
try:
    from base.spider import Spider as BaseSpider
    _HAS_BASE_SPIDER = True
    try:
        from java import jclass, dynamic_proxy
        _HAS_ANDROID = True
    except ImportError:
        pass
except ImportError:
    pass

# ===================== 全局常量 =====================
DEFAULT_USER_AGENT = 'okhttp/4.12.0'
DEFAULT_EXTERNAL_API_URL = "https://xn--v4q818bf34b.cc/helper/api.php"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
CACHE_DIR = os.path.join(SCRIPT_DIR, 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# 持久化配置路径（Android 环境自动切换）
PERSISTENT_CONFIG_PATH = os.path.join(CACHE_DIR, "persistent_config.json")
if _HAS_ANDROID:
    def _get_app_cache_dir():
        try:
            ActivityThread = jclass("android.app.ActivityThread")
            at = ActivityThread.currentActivityThread()
            context = at.getApplication()
            return context.getCacheDir().getAbsolutePath()
        except Exception:
            return "/storage/emulated/0/.local_source_manager"
    _cache_root = _get_app_cache_dir()
    os.makedirs(_cache_root, exist_ok=True)
    PERSISTENT_CONFIG_PATH = os.path.join(_cache_root, "persistent_config.json")

GITHUB_PROXY = "https://gh.jasonzeng.dev/"

# 全量GitHub代理模式列表（移植自dow.py，覆盖所有主流公共加速站）
GITHUB_PROXY_PATTERNS = [
    r"https?://gh-proxy\.com/",
    r"https?://ghproxy\.net/",
    r"https?://ghfast\.top/",
    r"https?://ghproxy\.cc/",
    r"https?://mirror\.ghproxy\.com/",
    r"https?://gh\.jasonzeng\.dev/",
    r"https?://fastgit\.cc/",
    r"https?://raw\.githubusercontent\.com/",
    # v2.2：饭太硬等站点常用的 GitHub 加速前缀，识别后剥离并归一化为统一代理，
    # 避免默认代理叠加形成"双重代理"导致下载失败（HTTP 000 / 挑战页）
    r"https?://git\.yylx\.win/",
    r"https?://gh\.927223\.xyz/",
    r"https?://gh\.xxooo\.cf/",
]

DOWNLOAD_EXTS = {
    '.js', '.py', '.jar', '.json', '.txt', '.m3u', '.m3u8',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.css', '.html', '.htm', '.xml', '.zip', '.mp4', '.ts',
    '.woff', '.woff2', '.ttf', '.eot', '.svg',
}

SKIP_EXTS = {'.php', '.asp', '.aspx', '.jsp', '.cgi', '.exe', '.dll', '.sh', '.bat'}

SKIP_PATTERNS = [
    r'/api\.php/provide/vod', r'/api\.php/app/', r'provide/vod',
    r'\?url=', r'\{name\}', r'\{date\}', r'\{episode\}', r'proxy://',
]

BOOL_MAP = {'是': True, '否': False, '下载': True, '不下载': False,
            'true': True, 'false': False, '1': True, '0': False, True: True, False: False}

_COMMON_USER_DIRS = [
    '/storage/emulated/0', '/sdcard', '/storage/sdcard0',
    '/storage/emulated/0/TVBox', '/storage/emulated/0/影视仓',
    '/storage/emulated/0/影视TV', '/storage/emulated/0/Download',
    '/storage/emulated/0/Documents', '/data/data', '/storage',
]

_FS_SEARCH_ROOTS = ['/storage/emulated/0', '/sdcard', '/storage/sdcard0', '/storage']
_FS_SKIP_DIRS = {
    'Android', 'DCIM', 'Pictures', 'Music', 'Movies', 'WhatsApp',
    'tencent', 'Telegram', '.cache', 'cache', 'Download', 'Documents',
    'Ringtones', 'Alarms', 'Notifications', 'Podcasts', 'Audiobooks',
}

# ========================= 解密模块（v5.4 增强版 + 兼容dow.py逻辑） =========================
def _strip_pkcs7(d):
    if d:
        p = d[-1]
        if 0 < p <= 16 and d[-p:] == bytes([p]) * p:
            return d[:-p]
    return d

def _contains_special_strings(response):
    if not isinstance(response, str):
        return False
    return bool(re.search(r'sites|genre|EXTINF', response))

def _extract_text(response_no_spaces):
    trimmed = response_no_spaces.rstrip('*')
    pos = trimmed.rfind('**')
    if pos != -1:
        return trimmed[pos + 2:]
    return trimmed

def _extract_encryption_params(s):
    prefix = "2423"
    suffix = "2324"
    suffix_pos = s.find(suffix)
    if suffix_pos == -1:
        return None
    pwd_mix = s[:suffix_pos + len(suffix)]
    if len(s) < 26:
        return None
    roundtime_in_hax = s[-26:]
    encrypted_text = s[len(pwd_mix):-26]
    pwd_in_hax = pwd_mix[len(prefix):-len(suffix)]
    return {
        'pwdInHax': pwd_in_hax,
        'roundtimeInHax': roundtime_in_hax,
        'encryptedText': encrypted_text
    }

def _decrypt_aes(encrypted_text_hex, pwd_in_hax, roundtime_in_hax):
    if not _HAS_AES:
        return None
    try:
        round_time = bytes.fromhex(roundtime_in_hax)
        pwd = bytes.fromhex(pwd_in_hax)
    except Exception:
        return None
    iv = round_time.ljust(16, b'0')
    key = pwd.ljust(16, b'0')
    try:
        cipher_bytes = bytes.fromhex(encrypted_text_hex)
    except Exception:
        return None
    decrypted = None
    if _AES_MODE == 'pycryptodome':
        try:
            decrypted = _AES_IMPL.new(key, _AES_IMPL.MODE_CBC, iv).decrypt(cipher_bytes)
        except Exception:
            return None
    elif _AES_MODE == 'pyaes':
        try:
            aes = _AES_IMPL.AESModeOfOperationCBC(key, iv=iv)
            d = _AES_IMPL.Decrypter(aes)
            decrypted = d.feed(cipher_bytes)
            decrypted += d.feed()
        except Exception:
            return None
    if decrypted:
        return _strip_pkcs7(decrypted)
    return None

def _extract_content(response, depth=0, max_depth=20):
    if not response or depth > max_depth:
        return None
    current = response.strip()
    has_double_star = '**' in current
    starts_with_2423 = current.startswith('2423')
    if not has_double_star and not starts_with_2423:
        return current
    if has_double_star:
        response_no_spaces = re.sub(r'\s+', '', current)
        cleaned_text = _extract_text(response_no_spaces)
        try:
            decoded = base64.b64decode(cleaned_text).decode('utf-8', errors='replace')
            if _contains_special_strings(decoded):
                return decoded
            return _extract_content(decoded, depth + 1, max_depth)
        except Exception:
            return None
    if starts_with_2423:
        params = _extract_encryption_params(current)
        if not params:
            return None
        decrypted = _decrypt_aes(params['encryptedText'], params['pwdInHax'], params['roundtimeInHax'])
        if decrypted is None:
            return None
        try:
            decrypted_str = decrypted.decode('utf-8', errors='replace')
            if _contains_special_strings(decrypted_str):
                return decrypted_str
            return _extract_content(decrypted_str, depth + 1, max_depth)
        except Exception:
            return None
    return current

def try_decrypt_content(content, url='', external_api_url=DEFAULT_EXTERNAL_API_URL, session=None, max_rounds=5):
    if isinstance(content, str):
        content = content.lstrip('\ufeff')
    if not content:
        return None
    if _contains_special_strings(content) or (content.strip().startswith('{') or content.strip().startswith('[')):
        return content
    current = content
    for i in range(max_rounds):
        result = _extract_content(current)
        if result and result != current:
            current = result
            if _contains_special_strings(current) or (current.strip().startswith('{') or current.strip().startswith('[')):
                return current
        else:
            break
    if current != content:
        return current
    if external_api_url and session:
        try:
            if '?url=' in external_api_url:
                resp = session.get(external_api_url + url, timeout=(5, 10))
            else:
                resp = session.post(external_api_url,
                    json={"action": "fetch_content", "params": {"url": url}, "ts": int(time.time())},
                    timeout=(5, 10))
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'success':
                    r = data.get('formattedContent') or data.get('data', '')
                    if r:
                        return r
        except Exception:
            pass
    return None

# ========================= v2.2 新增：图片内嵌JSON / JS注释剥离 / 安全JSON解析 =========================
def strip_js_comments(text):
    """
    去除 JSON 文本中的 JS 风格行注释（// 到行尾），但保留字符串字面量内的 //。
    饭太硬等接口返回的 box JSON 中会用 // 注释掉整条站点配置，导致 json.loads 失败。
    :param text: 原始文本
    :return: 剥离注释后的文本
    """
    if not text:
        return text
    if not isinstance(text, str):
        try:
            text = _decode_bytes(text)
        except Exception:
            text = str(text)
    out = []
    i = 0
    n = len(text)
    in_str = False
    in_line_comment = False
    while i < n:
        c = text[i]
        if in_line_comment:
            if c == '\n':
                in_line_comment = False
                out.append(c)
            i += 1
            continue
        if in_str:
            out.append(c)
            if c == '\\':
                if i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            in_line_comment = True
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def _extract_json_from_image_bytes(raw):
    """
    针对饭太硬等站点：接口返回"伪装图片"(JPEG/BMP/GIF)，真实 box JSON 以 base64 形式
    拼接在图片数据末尾（以 ** 为分隔符）。在二进制层面直接提取，不依赖文字解码。
    :param raw: 原始响应字节
    :return: 成功返回 dict/list，失败返回 None
    """
    if not raw or not isinstance(raw, (bytes, bytearray)):
        return None
    raw = bytes(raw)
    # 仅处理图片魔数：JPEG(FF D8 FF) / BMP(BM) / GIF(GIF8)
    is_image = (raw[:3] == b'\xff\xd8\xff' or raw[:2] == b'BM'
                or raw[:6] in (b'GIF87a', b'GIF89a'))
    if not is_image:
        return None
    # 图片结束标记（JPEG EOI）
    eoi = raw.rfind(b'\xff\xd9')
    tail = raw[eoi + 2:] if eoi != -1 else raw
    candidates = []
    # 优先找 ** 分隔符，取其后内容
    idx = tail.find(b'**')
    if idx != -1:
        candidates.append(tail[idx + 2:].strip())
        # 部分站点可能在 ** 前还有随机前缀，整段尝试
        candidates.append(tail.strip())
    else:
        candidates.append(tail.strip())
    for b64 in candidates:
        if not b64:
            continue
        try:
            decoded = base64.b64decode(b64)
        except Exception:
            continue
        text = _decode_bytes(decoded)
        data = _safe_json_loads(text)
        if data is not None:
            return data
    return None

def _safe_json_loads(text):
    """
    统一安全 JSON 解析入口：
      1. 尝试直接 json.loads
      2. 失败则剥离 JS 注释后重试
      3. 仍失败则用正则提取 { } / [ ] 片段逐一尝试（片段同样先剥注释）
    :param text: 文本或字节
    :return: 解析成功返回 dict/list，失败返回 None
    """
    if not text:
        return None
    if isinstance(text, (bytes, bytearray)):
        text = _decode_bytes(text)
    text = str(text).lstrip('\ufeff')
    if not text.strip():
        return None
    # 1) 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) 剥离 JS 注释后解析
    cleaned = strip_js_comments(text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # 3) 正则提取片段（贪心匹配最外层 { } 或 [ ]），逐段剥注释解析
    for pat in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        for m in re.finditer(pat, cleaned):
            cand = m.group()
            try:
                return json.loads(strip_js_comments(cand))
            except Exception:
                continue
    # 4) 兼容部分站点 JSON 片段被 // 整行注释包裹的情况
    for line in cleaned.splitlines():
        s = line.strip()
        if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
            try:
                return json.loads(strip_js_comments(s))
            except Exception:
                continue
    return None

# ========================= 通用辅助函数 =========================
# ===== 新增：站点自定义反爬请求头适配表，仅针对特定域名追加头，不影响其他站点 =====
SITE_CUSTOM_HEADERS = {
    "www.xn--sss604efuw.cc": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "http://www.xn--sss604efuw.cc/",
        "Origin": "http://www.xn--sss604efuw.cc",
        "Cookie": "Hm_lvt_xxx=1720000000; Hm_lpvt_xxx=1720000000",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    },
    "www.饭太硬.cc": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "http://www.饭太硬.cc/",
        "Origin": "http://www.饭太硬.cc",
        "Cookie": "Hm_lvt_xxx=1720000000; Hm_lpvt_xxx=1720000000",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
}


def get_custom_site_headers(url):
    """
    根据URL域名获取站点自定义头；无匹配返回空dict
    :param url: 完整请求url
    :return dict: 需要合并追加的请求头
    """
    if not url:
        return {}
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc in SITE_CUSTOM_HEADERS:
            return SITE_CUSTOM_HEADERS[netloc].copy()
    except Exception:
        pass
    return {}
# ===== 新增结束 =====

def _decode_bytes(raw):
    if not raw:
        return ''
    if raw[:3] == b'\xef\xbb\xbf':
        return raw.decode('utf-8-sig', errors='replace')
    for enc in ('utf-8', 'gb18030', 'big5'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')

def _read_text_file(path):
    with open(path, 'rb') as f:
        return _decode_bytes(f.read())

def clean_preroll_m3u8(content: str) -> str:
    lines = content.splitlines(keepends=True)
    out = []
    start_output = False
    for line in lines:
        s = line.strip()
        if s == "#EXT-X-DISCONTINUITY":
            start_output = True
            continue
        if start_output:
            out.append(line)
    if not start_output:
        return content
    return "".join(out)

def parse_curl_command(curl_str: str):
    import shlex
    url = ""
    headers = {}
    try:
        parts = shlex.split(curl_str)
        for i, p in enumerate(parts):
            if p.startswith("http://") or p.startswith("https://"):
                url = p
            elif p in ("-H", "--header") and i + 1 < len(parts):
                header_str = parts[i + 1]
                if ":" in header_str:
                    k, v = header_str.split(":", 1)
                    headers[k.strip()] = v.strip()
    except Exception:
        pass
    return url, headers

def _encode_url(url):
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.encode('idna').decode('ascii') if parsed.netloc else ''
        path = urllib.parse.quote(parsed.path, safe='/') if parsed.path else ''
        query = urllib.parse.quote(parsed.query, safe='=&?') if parsed.query else ''
        encoded = urllib.parse.urlunparse((parsed.scheme, netloc, path, parsed.params, query, parsed.fragment))
        return encoded
    except Exception:
        return url

# ========================= 文件下载器（全功能整合版 + 代理逻辑修复） =========================
class FileDownloader:
    SKIP_EXTS = SKIP_EXTS
    BINARY_EXTS = {'.jar', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.m3u', '.m3u8', '.mp4', '.ts'}
    DOWNLOAD_EXTS = DOWNLOAD_EXTS

    # 原 dow.txt 核心特性：强制可下载域名（无视扩展名与跳过规则）
    FORCE_DOWNLOAD_DOMAINS = [
        "9280.kstore.vip",
        "kstore.vip",
    ]

    def __init__(self, output_dir, config=None, log_callback=None, progress_callback=None, cancel_event=None):
        self.output_dir = output_dir
        self.config = config or {}
        self.log_callback = log_callback or (lambda msg: None)
        self.progress_callback = progress_callback or (lambda msg: None)
        self.cancel_event = cancel_event
        self.downloaded = {}
        self.failed = []
        self.skipped = []
        self._lock = threading.Lock()
        self._processed = set()

        cfg_download = self.config.get('download', self.config) if 'download' in self.config else self.config
        self.overwrite = cfg_download.get('overwrite', False)
        self.timeout = (cfg_download.get('timeout_connect', 10), cfg_download.get('timeout_read', 60))
        self.chunk_size = cfg_download.get('chunk_size', 8192)
        self.max_size = self.config.get('max_file_size_mb', 100) * 1024 * 1024
        self.skip_exts = set(self.config.get('skip_extensions', []))
        self.skip_exts.update(self.SKIP_EXTS)
        self.skip_patterns = self.config.get('skip_patterns', [])
        self.decrypt_enabled = cfg_download.get('decrypt', {}).get('enabled', True)
        self.external_api = cfg_download.get('decrypt', {}).get('external_api_url', '')
        self.proxy = self.config.get('proxy', '')
        self.github_proxy = self.config.get('github_proxy', GITHUB_PROXY)
        self.user_agent = self.config.get('user_agent', DEFAULT_USER_AGENT)

        # 全量GitHub代理模式列表（移植自dow.py）
        self.github_proxy_patterns = self.config.get('github_proxy_patterns', GITHUB_PROXY_PATTERNS)

        self.category_map = cfg_download.get('category_map', {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
        self.skip_patterns_core = cfg_download.get('skip_patterns_core', SKIP_PATTERNS)
        self.max_workers = cfg_download.get('max_workers', 8)
        self.retry_total = cfg_download.get('retry_total', 2)
        self.retry_backoff = cfg_download.get('retry_backoff', 0.3)
        self.pool_connections = cfg_download.get('pool_connections', 10)
        self.pool_maxsize = cfg_download.get('pool_maxsize', 20)

        self.session = requests.Session()
        retry = Retry(total=self.retry_total, backoff_factor=self.retry_backoff, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=self.pool_connections, pool_maxsize=self.pool_maxsize)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'identity'
        })
        self.session.verify = False
        if self.proxy:
            self.session.proxies = {'http': self.proxy, 'https': self.proxy}

        os.makedirs(self.output_dir, exist_ok=True)

    def _log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _is_github_file_url(self, url):
        if not url:
            return False
        github_domains = (
            'raw.githubusercontent.com', 'github.com', 'gist.github.com',
            'gist.githubusercontent.com', 'githubusercontent.com'
        )
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            for d in github_domains:
                if d in netloc:
                    return True
        except Exception:
            pass
        return False

    # 【关键修复】移植dow.py代理归一化逻辑 + 保留d.py地址规范化
    def normalize_github_url(self, url):
        if not url:
            return url
        original = url

        # 第一步：识别所有已知GitHub代理前缀，剥离得到原始地址（dow.py核心逻辑）
        for pat in self.github_proxy_patterns:
            if re.match(pat, url):
                original = re.sub(pat, "", url, count=1)
                if original.startswith("raw.githubusercontent.com"):
                    original = "https://" + original
                break

        # 第二步：GitHub地址规范化（d.py原有增强：blob转raw、gist处理）
        if self._is_github_file_url(original):
            parsed = urllib.parse.urlparse(original)
            path = parsed.path.lstrip('/')
            if 'github.com' in parsed.netloc:
                parts = path.split('/')
                if len(parts) >= 4:
                    user, repo = parts[0], parts[1]
                    if parts[2] in ('blob', 'raw'):
                        branch = parts[3]
                        file_path = '/'.join(parts[4:])
                        original = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{file_path}"
                    else:
                        original = f"https://raw.githubusercontent.com/{user}/{repo}/master/{'/'.join(parts[3:])}"
            elif 'gist.github.com' in parsed.netloc:
                gist_id = path.split('/')[0]
                original = f"https://gist.githubusercontent.com/raw/{gist_id}/"

        # 第三步：统一加上配置的代理前缀
        if self.github_proxy and ("github.com" in original or "githubusercontent.com" in original):
            proxy = self.github_proxy.rstrip('/') + '/'
            if not original.startswith(proxy):
                return proxy + original.lstrip('/')
        return original

    def split_url_and_suffix(self, url):
        if not url:
            return url, ""
        if ';md5;' in url:
            idx = url.index(';md5;')
            return url[:idx], url[idx:]
        parsed = urllib.parse.urlparse(url)
        if parsed.query and ('md5=' in parsed.query or 'MD5=' in parsed.query):
            base = url.split('?')[0]
            return base, '?' + parsed.query
        return url, ""

    # 三层判定逻辑：强制域名 > spider/jar字段 > 常规扩展名
    def is_downloadable(self, url, field_key=None):
        if not url or not isinstance(url, str):
            return False
        url_clean = url.strip()
        if not url_clean or url_clean.startswith("proxy://"):
            return False
        # 优先级1：强制可下载域名（原 dow.txt 特性，无视所有规则）
        for domain in self.FORCE_DOWNLOAD_DOMAINS:
            if domain in url_clean:
                return True
        # 优先级2：spider/jar 字段强制判定（v5.4 特性）
        if field_key in ('spider', 'jar'):
            for pat in self.skip_patterns_core:
                if re.search(pat, url_clean):
                    return False
            return True
        # 优先级3：常规扩展名与规则判断
        for pat in self.skip_patterns_core:
            if re.search(pat, url_clean):
                return False
        path_part = url_clean.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        if ext in self.SKIP_EXTS:
            return False
        if ext in self.DOWNLOAD_EXTS:
            return True
        return False

    # 原 dow.txt 特性：强制域名跳过解密
    def _should_skip_decrypt(self, url):
        for domain in self.FORCE_DOWNLOAD_DOMAINS:
            if domain in url:
                return True
        return False

    def resolve_url(self, rel_path, base_url):
        if not rel_path:
            return None
        if rel_path.startswith(('http://', 'https://')):
            return self.normalize_github_url(rel_path)
        if rel_path.startswith("//"):
            return self.normalize_github_url("https:" + rel_path)
        if rel_path.startswith("./") or rel_path.startswith("../"):
            return self.normalize_github_url(urllib.parse.urljoin(base_url, rel_path))
        if rel_path.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            return self.normalize_github_url(f"{parsed.scheme}://{parsed.netloc}{rel_path}")
        return self.normalize_github_url(urllib.parse.urljoin(base_url, rel_path))

    # 【修复】使用全量代理模式清理URL，确保同资源不同代理生成相同本地路径
    def get_target_path(self, url, category, field_key=None):
        if not url:
            return os.path.join(category, 'unknown')
        clean_url = url
        # 遍历所有已知代理前缀，彻底清理
        for pat in self.github_proxy_patterns:
            clean_url = re.sub(pat, "", clean_url)
        path_part = clean_url.split('?')[0].split(';')[0].rstrip('/')
        path_part = urllib.parse.unquote(path_part)
        filename = os.path.basename(path_part)
        if not filename:
            filename = hashlib.md5(url.encode()).hexdigest()[:8]
            filename += self.category_map.get(category, '.bin')
        ext = os.path.splitext(filename)[1].lower()
        if field_key in ('spider', 'jar'):
            # v2.2：spider/jar 字段本地文件统一强制 .jar 扩展名，
            # 兼容饭太硬等站点用 .jpg 等扩展名伪装 jar 的情况，保证本地 box 引用正确
            base_name = os.path.splitext(filename)[0] if ext else filename
            if not base_name:
                base_name = hashlib.md5(url.encode()).hexdigest()[:8]
            return os.path.join('jar', base_name + '.jar')
        if not ext:
            filename += self.category_map.get(category, '.bin')
        return os.path.join(category, filename)

    def should_skip(self, url):
        if not url or not isinstance(url, str):
            return True, "空URL"
        for pattern in self.skip_patterns:
            if pattern in url:
                return True, f"命中跳过模式: {pattern}"
        return False, ""

    def download_file(self, url, base_url, category='lib', field_key=None):
        if self.cancel_event and self.cancel_event.is_set():
            self._log("下载任务已取消")
            return None
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = self.split_url_and_suffix(url)
        if not self.is_downloadable(url_part, field_key):
            return None
        should_skip, reason = self.should_skip(url_part)
        if should_skip:
            with self._lock:
                self.skipped.append((url, reason))
            self._log(f"跳过文件: {url} ({reason})")
            return None
        abs_url = self.resolve_url(url_part, base_url)
        if not abs_url:
            with self._lock:
                self.failed.append((url, "无法解析URL"))
            return None
        target_rel = self.get_target_path(abs_url, category, field_key)
        target_abs = os.path.join(self.output_dir, target_rel)
        with self._lock:
            if target_rel in self._processed:
                self.downloaded[url_part] = target_rel
                return target_rel
            self._processed.add(target_rel)
        if not self.overwrite and os.path.exists(target_abs):
            with self._lock:
                self.downloaded[url_part] = target_rel
            self._log(f"文件已存在，跳过: {target_rel}")
            return target_rel
        self._log(f"下载文件: {abs_url}")
        try:
            # v5.4 增强：HEAD 请求容错，失败直接走 GET
            try:
                head_resp = self.session.head(abs_url, timeout=self.timeout, allow_redirects=True)
                total_size = int(head_resp.headers.get('content-length', 0))
                support_range = head_resp.headers.get('accept-ranges') == 'bytes'
            except Exception as head_err:
                self._log(f"HEAD请求失败 {abs_url}: {head_err}，尝试直接GET")
                total_size = 0
                support_range = False

            downloaded_size = 0
            req_headers = dict(self.session.headers)
            mode = "wb"
            if os.path.exists(target_abs) and total_size > 0:
                downloaded_size = os.path.getsize(target_abs)
                if downloaded_size == total_size:
                    with self._lock:
                        self.downloaded[url_part] = target_rel
                    self._log(f"✅ 本地已存在完整文件，跳过: {target_rel}")
                    return target_rel
                elif downloaded_size < total_size and support_range:
                    self._log(f"🔄 断点续传 {target_rel} (已下载 {downloaded_size/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB)")
                    req_headers["Range"] = f"bytes={downloaded_size}-"
                    mode = "ab"

            os.makedirs(os.path.dirname(target_abs), exist_ok=True)
            resp = self.session.get(abs_url, headers=req_headers, timeout=self.timeout, stream=True)
            self._log(f"响应状态: {resp.status_code}")
            if resp.status_code not in (200, 206):
                with self._lock:
                    self.failed.append((url, f"HTTP {resp.status_code}"))
                return None
            if total_size > 20 * 1024 * 1024 and support_range and mode == "wb":
                return self._download_file_multithread(abs_url, req_headers, target_abs, target_rel, url_part, total_size, field_key)

            last_log_time = time.time()
            downloaded_len = downloaded_size
            with open(target_abs, mode) as f_local:
                for chunk in resp.iter_content(chunk_size=self.chunk_size):
                    if self.cancel_event and self.cancel_event.is_set():
                        self._log("下载被取消")
                        return None
                    if chunk:
                        f_local.write(chunk)
                        downloaded_len += len(chunk)
                        now = time.time()
                        if now - last_log_time > 1.5:
                            if total_size > 0:
                                pct = (downloaded_len / total_size) * 100
                                self.progress_callback(f"⏳ {target_rel} {pct:.1f}% ({downloaded_len/1024/1024:.1f}MB)")
                            else:
                                self.progress_callback(f"⏳ {target_rel} ({downloaded_len/1024/1024:.1f}MB)")
                            last_log_time = now
            with self._lock:
                self.downloaded[url_part] = target_rel
            self._log(f"下载成功: {target_rel}")
            return target_rel
        except Exception as e:
            with self._lock:
                self.failed.append((url, str(e)))
                self._processed.discard(target_rel)
            self._log(f"下载失败: {e}")
            return None

    def _download_file_multithread(self, url, headers, path, target_rel, url_part, total_size, field_key=None):
        self._log(f"⚡ 启用多线程分块下载: {target_rel}")
        num_threads = min(8, max(2, self.max_workers))
        chunk_size = total_size // num_threads
        ranges = []
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else total_size - 1
            ranges.append((start, end))
        temp_files = []
        lock = threading.Lock()
        completed = [0]
        errors = []
        def download_chunk(idx, start, end):
            if self.cancel_event and self.cancel_event.is_set():
                return
            temp_path = f"{path}.part{idx}"
            temp_files.append(temp_path)
            try:
                h = dict(headers)
                h["Range"] = f"bytes={start}-{end}"
                r = self.session.get(url, headers=h, stream=True, timeout=self.timeout)
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if self.cancel_event and self.cancel_event.is_set():
                            return
                        if chunk:
                            f.write(chunk)
                with lock:
                    completed[0] += 1
                    self.progress_callback(f"⏳ {target_rel} 分块 {completed[0]}/{num_threads} 完成")
            except Exception as e:
                with lock:
                    errors.append(str(e))
        with ThreadPoolExecutor(max_workers=num_threads) as ex:
            futures = [ex.submit(download_chunk, idx, s, e) for idx, (s, e) in enumerate(ranges)]
            for fut in as_completed(futures):
                pass
        if errors:
            self._log(f"❌ 分块下载出错: {errors[0]}")
            with self._lock:
                self.failed.append((url, f"分块下载失败: {errors[0]}"))
            return None
        with open(path, 'wb') as outfile:
            for i in range(num_threads):
                part_path = f"{path}.part{i}"
                if os.path.exists(part_path):
                    with open(part_path, 'rb') as infile:
                        outfile.write(infile.read())
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass
        with self._lock:
            self.downloaded[url_part] = target_rel
        self._log(f"🎉 多线程下载完成: {target_rel}")
        return target_rel

    def download_text(self, url, base_url, force_decrypt=None):
        if self.cancel_event and self.cancel_event.is_set():
            return None
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = self.split_url_and_suffix(url)
        full_url = self.resolve_url(url_part, base_url)
        if not full_url:
            return None
        self._log(f"请求文本: {full_url}")
        try:
            req_headers = dict(self.session.headers)
            parsed = urllib.parse.urlparse(full_url)
            # v5.4 增强：自动添加 cnb.cool 站点请求头
            if 'cnb.cool' in parsed.netloc:
                req_headers['Referer'] = 'https://cnb.cool'
                req_headers['Origin'] = 'https://cnb.cool'
                self._log("自动添加 cnb.cool 请求头")
            resp = self.session.get(full_url, headers=req_headers, timeout=self.timeout)
            self._log(f"响应状态: {resp.status_code}, 内容长度: {len(resp.content)}")
            if resp.status_code != 200:
                self._log(f"下载文本失败，状态码: {resp.status_code}")
                return None
            # v2.2 增强：饭太硬等站点返回"伪装图片"，图片末尾内嵌 base64 的 box JSON，
            # 在二进制层面直接提取（不依赖文字解码，避免乱码丢失数据）
            raw = resp.content
            embedded = _extract_json_from_image_bytes(raw)
            if embedded is not None:
                self._log("识别到图片内嵌 JSON，已提取")
                return json.dumps(embedded, ensure_ascii=False)
            try:
                content = raw.decode('utf-8')
            except UnicodeDecodeError:
                content = resp.text
            content = content.lstrip('\ufeff')
            preview = content[:200].replace('\n', ' ').replace('\r', '')
            self._log(f"内容预览: {preview}...")
            path = urllib.parse.unquote(parsed.path)
            ext = os.path.splitext(path)[1].lower()
            if ext in self.BINARY_EXTS:
                self._log("二进制文件，不进行解密")
                return content
            do_decrypt = force_decrypt if force_decrypt is not None else self.decrypt_enabled
            # 原 dow.txt 特性：强制域名跳过解密
            if self._should_skip_decrypt(full_url):
                self._log("强制域名，跳过解密步骤")
                do_decrypt = False
            if do_decrypt:
                self._log("尝试解密内容...")
                decrypted = try_decrypt_content(content, full_url, self.external_api, self.session, max_rounds=5)
                if decrypted:
                    self._log("解密成功")
                    return decrypted
                else:
                    self._log("解密失败，返回原始内容")
            return content
        except Exception as e:
            self._log(f"下载文本异常: {e}")
            return None

# ========================= JSON 路径提取器 =========================
class PathExtractor:
    PATH_FIELDS = {'api', 'ext', 'url', 'wallpaper', 'spider', 'logo', 'jar', 'playerType',
                   'header', 'headers', 'ua', 'ref', 'referer'}
    def __init__(self, config=None):
        self.config = config or {}
        self.recursive_depth = self.config.get('recursive_depth', 2)
        self.extracted = set()
        self._json_files = set()
    def extract(self, obj, depth=0):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith('./'):
                    self.extracted.add(v)
                    if v.endswith('.json') and depth < self.recursive_depth:
                        self._json_files.add(v)
                elif isinstance(v, (dict, list)):
                    self.extract(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self.extract(item, depth + 1)
    def get_all_paths(self):
        return self.extracted
    def get_json_files(self):
        return self._json_files

# ========================= 主 Spider 类（双平台兼容） =========================
class Spider(BaseSpider):
    VERSION = "v2.1 - 双平台兼容 | 全量代理修复 | 解密能力对齐dow.py"
    ACTION_DOWNLOAD_PACKAGE = "local_source_download_package"
    ACTION_SHOW_STATUS = "local_source_show_status"

    def __init__(self):
        if _HAS_BASE_SPIDER:
            super().__init__()
        self.lock = threading.RLock()
        self.inited = False
        self._initial_extend = None
        self.config = {}
        self.package_download_sites = []
        self.download_output_dir = ""
        self.download_config = {}
        self._package_download_state = "idle"
        self._package_download_message = ""
        self._package_download_thread = None
        self._package_download_lock = threading.Lock()
        self._package_cancel_event = None
        self._dialog_refs = []
        self._notification_refs = []
        self._destroyed = False
        self._session = None
        self._site_states = {}
        self._site_op_threads = {}
        self._site_op_lock = threading.Lock()
        self._site_cancel_events = {}
        self.session = None
        self.external_api_url = DEFAULT_EXTERNAL_API_URL
        self.log_enabled = True
        self.log_level = 'info'
        self.log_dir = os.path.join(SCRIPT_DIR, 'logs')
        self.user_agent = DEFAULT_USER_AGENT
        self.category_map = {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'}
        self.skip_patterns_core = SKIP_PATTERNS
        self.max_workers = 8
        self.retry_total = 2
        self.retry_backoff = 0.3
        self.pool_connections = 10
        self.pool_maxsize = 20
        self._base_dir = None
        self._resource_dirs = []
        self._config_file_path = None
        self.log_queue = queue.Queue()
        self._persisted_runnable = None
        self._ui_listeners = []
        self._active_views = {}
        self._is_downloading = False
        self._log_dialog_open = False
        self.localized_interfaces = []
        self._load_localized_interfaces()
        self.root_dirs = []
        self._load_root_dirs()
        self.decrypt_filename_template = "{name}_m.json"
        self.localized_filename_template = "{name}.json"
        self.inject_manager_site = True
        self.oktv_switch_timeout = 2
        self._load_additional_config()
        self._ui_busy = False
        self._original_oktv_url = None
        # 原 dow.txt 核心特性：强制覆盖标记
        self.force_overwrite = False
        # 全量GitHub代理模式列表
        self.github_proxy_patterns = GITHUB_PROXY_PATTERNS

    # ===================== 配置与路径工具 =====================
    def _load_additional_config(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.decrypt_filename_template = data.get("decrypt_filename_template", "{name}_m.json")
                self.localized_filename_template = data.get("localized_filename_template", "{name}.json")
                self.inject_manager_site = data.get("inject_manager_site", True)
                self.oktv_switch_timeout = data.get("oktv_switch_timeout", 2)
        except Exception:
            pass

    def _save_additional_config(self):
        try:
            data = {}
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["decrypt_filename_template"] = self.decrypt_filename_template
            data["localized_filename_template"] = self.localized_filename_template
            data["inject_manager_site"] = self.inject_manager_site
            data["oktv_switch_timeout"] = self.oktv_switch_timeout
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_root_dirs(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.root_dirs = data.get("root_dirs", [])
            if not self.root_dirs:
                default_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
                if default_dir not in self.root_dirs:
                    self.root_dirs.append(default_dir)
        except Exception:
            default_dir = self.download_output_dir or os.path.join(SCRIPT_DIR, "本地包")
            self.root_dirs = [default_dir]
        for d in self.root_dirs:
            if d:
                os.makedirs(d, exist_ok=True)

    def _save_root_dirs(self):
        try:
            data = {}
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data["root_dirs"] = self.root_dirs
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _is_remote_path(self, path):
        if not path:
            return False
        return str(path).lower().startswith(('http://', 'https://', 'ftp://'))

    def _get_base_dir(self):
        return self._base_dir or SCRIPT_DIR

    def _detect_base_dir(self, ext):
        if self._base_dir:
            return self._base_dir
        clues = []
        if isinstance(ext, dict):
            config_file = ext.get('config_file', '')
            if config_file and not self._is_remote_path(config_file):
                clues.append(config_file)
            lives = ext.get('lives', [])
            if isinstance(lives, list):
                for item in lives:
                    if isinstance(item, str) and not self._is_remote_path(item):
                        clues.append(item)
                    elif isinstance(item, dict):
                        for k in ('api', 'url'):
                            v = item.get(k, '')
                            if v and not self._is_remote_path(v):
                                clues.append(v)
        if not clues:
            self._base_dir = SCRIPT_DIR
            return self._base_dir
        candidate_bases = []
        candidate_bases.extend(self._resource_dirs)
        candidate_bases.append(SCRIPT_DIR)
        parent = os.path.dirname(SCRIPT_DIR)
        if parent:
            candidate_bases.append(parent)
            pp = os.path.dirname(parent)
            if pp:
                candidate_bases.append(pp)
        candidate_bases.append(os.getcwd())
        for p in _COMMON_USER_DIRS:
            candidate_bases.append(p)
        seen = set()
        unique_bases = []
        for b in candidate_bases:
            if b and b not in seen and os.path.isdir(b):
                seen.add(b)
                unique_bases.append(b)
        for clue in clues:
            strip = clue.lstrip('./').lstrip('.\\').strip()
            basename = os.path.basename(clue)
            clue_dir = os.path.dirname(strip)
            for base in unique_bases:
                test_paths = [
                    os.path.join(base, strip),
                    os.path.join(base, basename),
                ]
                if clue_dir:
                    test_paths.extend([
                        os.path.join(base, 'json', basename),
                        os.path.join(base, 'py', basename),
                    ])
                for tp in test_paths:
                    if tp and os.path.exists(tp):
                        self._base_dir = base
                        self._remember_resource_dir(tp)
                        return self._base_dir
        for base in unique_bases:
            if os.path.isdir(os.path.join(base, 'json')) or os.path.isdir(os.path.join(base, 'py')):
                self._base_dir = base
                return self._base_dir
        self._base_dir = SCRIPT_DIR
        return self._base_dir

    def _resolve_file_path(self, path, base_dirs=None):
        if not path or self._is_remote_path(path):
            return None, None
        if os.path.isabs(path) and os.path.exists(path):
            return path, os.path.dirname(path)
        basename = os.path.basename(path)
        strip = path.lstrip('./').lstrip('.\\')
        strip_parent = os.path.dirname(strip)
        candidates = []
        base = self._get_base_dir()
        for b in [base, SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates.append(os.path.join(b, strip))
                candidates.append(os.path.join(b, basename))
                if strip_parent:
                    candidates.append(os.path.join(b, strip_parent, basename))
        for rd in getattr(self, '_resource_dirs', []) or []:
            if rd:
                candidates.append(os.path.join(rd, strip))
                candidates.append(os.path.join(rd, basename))
        p = SCRIPT_DIR
        for _ in range(3):
            p = os.path.dirname(p)
            if p and os.path.isdir(p):
                candidates.append(os.path.join(p, strip))
                candidates.append(os.path.join(p, basename))
        if base_dirs is None:
            base_dirs = _COMMON_USER_DIRS
        for b in base_dirs:
            candidates.append(os.path.join(b, strip))
            candidates.append(os.path.join(b, basename))
        seen = set()
        for cand in candidates:
            if not cand or cand in seen:
                continue
            seen.add(cand)
            if os.path.exists(cand):
                self._remember_resource_dir(cand)
                cand_dir = os.path.dirname(cand)
                inferred_base = cand_dir if not strip_parent or strip_parent == '.' else cand_dir[:-len(strip_parent)].rstrip('/\\') or '/'
                return cand, inferred_base
        return None, None

    def _resolve_resource_path(self, source):
        if not source:
            return None, None
        source = source.strip()
        if self._is_remote_path(source):
            return 'remote', source
        if os.path.isabs(source) and os.path.exists(source):
            return 'local', source
        found, _ = self._resolve_file_path(source)
        if found:
            return 'local', found
        base = self._get_base_dir()
        if source.startswith('./') or source.startswith('.\\'):
            return 'local', os.path.join(base, source[2:])
        elif not os.path.isabs(source):
            return 'local', os.path.join(base, source)
        else:
            return 'local', source

    def _remember_resource_dir(self, file_path):
        try:
            d = os.path.dirname(os.path.abspath(file_path))
            if d and d not in self._resource_dirs:
                self._resource_dirs.insert(0, d)
                parent = os.path.dirname(d)
                if parent and parent not in self._resource_dirs:
                    self._resource_dirs.append(parent)
        except Exception:
            pass

    def _load_json_resource(self, source, allow_decrypt=False):
        if not source:
            return None
        source = source.strip()
        if self._is_remote_path(source):
            try:
                if self.session is None:
                    self._init_session()
                resp = self.session.get(source, timeout=(10, 30), verify=False)
                if resp.status_code != 200:
                    return None
                text = _decode_bytes(resp.content)
                # v2.2：安全解析（自动剥离 JS 注释）
                data = _safe_json_loads(text)
                if data is not None:
                    return data
                if allow_decrypt:
                    dec = try_decrypt_content(text, source, self.external_api_url, self.session, max_rounds=5)
                    if dec:
                        data = _safe_json_loads(dec)
                        if data is not None:
                            return data
                        m2 = re.search(r'"(?:lives)"\s*:\s*(\[[\s\S]*?\])', dec)
                        if m2:
                            try:
                                return {"lives": _safe_json_loads(m2.group(1))}
                            except Exception:
                                pass
                return None
            except Exception:
                return None
        candidates_to_try = []
        if os.path.isabs(source) and os.path.exists(source):
            candidates_to_try.append(source)
        found, found_base = self._resolve_file_path(source)
        if found:
            candidates_to_try.append(found)
        base = self._get_base_dir()
        strip = source.lstrip('./').lstrip('.\\')
        for b in [base, SCRIPT_DIR, os.getcwd()]:
            if b:
                candidates_to_try.append(os.path.join(b, strip))
                candidates_to_try.append(os.path.join(b, os.path.basename(source)))
        last_err = None
        for cand in candidates_to_try:
            if not os.path.exists(cand):
                continue
            try:
                data = _safe_json_loads(_read_text_file(cand))
                if data is None:
                    raise ValueError("无法解析")
                self._remember_resource_dir(cand)
                return data
            except Exception as e:
                last_err = e
        return None

    def _init_session(self):
        if self._session is None:
            self._session = requests.Session()
            retry = Retry(total=2, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
            self._session.mount('http://', adapter)
            self._session.mount('https://', adapter)
            self._session.headers.update({
                'User-Agent': DEFAULT_USER_AGENT,
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Connection': 'keep-alive',
                'Accept-Encoding': 'identity'
            })
            self._session.verify = False
            self.session = self._session

    def _log(self, msg, level='info'):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] {msg}"
        print(line)
        self._push_log(msg)
        if not getattr(self, 'log_enabled', True):
            return
        try:
            log_dir = getattr(self, 'log_dir', None) or os.path.join(self.download_output_dir or SCRIPT_DIR, 'log')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'download.log')
            with open(log_file, 'a', encoding='utf-8') as f_local:
                f_local.write(line + '\n')
        except Exception:
            pass

    def _push_log(self, msg):
        time_str = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{time_str}] {msg}")

    # ===================== 默认配置与加载 =====================
    def _load_default_config(self):
        default_output = os.path.join(SCRIPT_DIR, "本地包")
        return {
            "sources": [],
            "download_output_dir": default_output,
            "download": {
                "skip_extensions": [".php", ".asp", ".jsp", ".cgi", ".exe", ".dll", ".sh", ".bat"],
                "skip_patterns": [],
                "max_file_size_mb": 100,
                "recursive_depth": 2,
                "decrypt": {"enabled": True, "external_api_url": DEFAULT_EXTERNAL_API_URL},
                "overwrite": True,
                "timeout_connect": 10,
                "timeout_read": 60,
                "chunk_size": 8192,
                "max_workers": 8,
                "retry_total": 2,
                "retry_backoff": 0.3,
                "pool_connections": 10,
                "pool_maxsize": 20,
                "category_map": {"js": ".js", "lib": ".json", "py": ".py", "jar": ".jar"},
                "skip_patterns_core": SKIP_PATTERNS
            },
            "proxy": "",
            "github_proxy": GITHUB_PROXY,
            "github_proxy_patterns": GITHUB_PROXY_PATTERNS,
            "concurrent": 3,
            "user_agent": DEFAULT_USER_AGENT,
            "external_api_url": DEFAULT_EXTERNAL_API_URL,
            "log": {
                "enabled": True,
                "level": "info",
                "dir": os.path.join(default_output, "log")
            }
        }

    def _normalize_config_keys(self, obj):
        if isinstance(obj, dict):
            new_obj = {}
            key_map = {
                '下载目录': 'download_output_dir', '全局代理': 'proxy', '并发数': 'concurrent',
                '跳过扩展名': 'skip_extensions', '跳过模式': 'skip_patterns',
                '最大文件大小MB': 'max_file_size_mb', '递归深度': 'recursive_depth',
                '覆盖': 'overwrite', '连接超时': 'timeout_connect', '读取超时': 'timeout_read',
                '块大小': 'chunk_size', '解密': 'decrypt', '启用': 'enabled',
                '外部API地址': 'external_api_url', '源列表': 'sources', '站点': 'sources',
                '接口': 'sources', 'github代理': 'github_proxy',
                '启用日志': 'log_enabled', '日志级别': 'log_level', '日志目录': 'log_dir',
            }
            for k, v in obj.items():
                new_key = key_map.get(k, k)
                new_obj[new_key] = self._normalize_config_keys(v)
            return new_obj
        elif isinstance(obj, list):
            return [self._normalize_config_keys(item) for item in obj]
        else:
            return obj

    def _load_config_from_ext(self, extend):
        if not extend:
            return None
        extend_str = str(extend).strip()
        if extend_str.startswith('{') or extend_str.startswith('['):
            try:
                return json.loads(extend_str)
            except Exception:
                return None
        else:
            return self._load_json_resource(extend_str, allow_decrypt=False)

    def _apply_config(self, config):
        config = self._normalize_config_keys(config)
        self.config = config
        raw_sources = config.get('sources') or config.get('urls', [])
        self.package_download_sites = []
        for item in raw_sources:
            if isinstance(item, dict) and item.get('url'):
                site = {
                    "id": self._package_download_site_id(item.get('name', '未命名'), item['url']),
                    "name": item.get('name', '未命名'),
                    "url": item['url'],
                    "enabled": item.get('enabled', True),
                    "type": "json"
                }
                self.package_download_sites.append(site)
            elif isinstance(item, str):
                site = {
                    "id": self._package_download_site_id(item, item),
                    "name": item,
                    "url": item,
                    "enabled": True,
                    "type": "json"
                }
                self.package_download_sites.append(site)

        self.download_output_dir = config.get('download_output_dir') or config.get('下载目录', '')
        if not self.download_output_dir:
            self.download_output_dir = os.path.join(SCRIPT_DIR, "本地包")
        os.makedirs(self.download_output_dir, exist_ok=True)

        default_download = self._load_default_config()['download']
        user_download = config.get('download', {})
        self.download_config = copy.deepcopy(default_download)
        for k, v in user_download.items():
            if isinstance(v, dict) and k in self.download_config and isinstance(self.download_config[k], dict):
                self.download_config[k].update(v)
            else:
                self.download_config[k] = v

        if config.get('proxy'):
            self.download_config['proxy'] = config['proxy']
        if config.get('github_proxy'):
            self.download_config['github_proxy'] = config['github_proxy']
        if config.get('github_proxy_patterns'):
            self.download_config['github_proxy_patterns'] = config['github_proxy_patterns']
        if config.get('concurrent'):
            self.download_config['concurrent'] = config['concurrent']

        # 强制覆盖优先级最高
        if self.force_overwrite:
            self.download_config['overwrite'] = True

        for site in self.package_download_sites:
            self._init_site_state(site['id'])

        self.user_agent = config.get('user_agent', DEFAULT_USER_AGENT)
        self.github_proxy_patterns = config.get('github_proxy_patterns', GITHUB_PROXY_PATTERNS)
        # v2.2：合并全局默认代理模式（只增不减），
        # 避免旧的持久化配置(cache/persistent_config.json)缺少新增代理前缀导致识别失败
        try:
            _merged_patterns = list(self.github_proxy_patterns)
            for _p in GITHUB_PROXY_PATTERNS:
                if _p not in _merged_patterns:
                    _merged_patterns.append(_p)
            self.github_proxy_patterns = _merged_patterns
        except Exception:
            pass
        self.category_map = self.download_config.get('category_map', {'js': '.js', 'lib': '.json', 'py': '.py', 'jar': '.jar'})
        self.skip_patterns_core = self.download_config.get('skip_patterns_core', SKIP_PATTERNS)
        self.max_workers = self.download_config.get('max_workers', 8)
        self.retry_total = self.download_config.get('retry_total', 2)
        self.retry_backoff = self.download_config.get('retry_backoff', 0.3)
        self.pool_connections = self.download_config.get('pool_connections', 10)
        self.pool_maxsize = self.download_config.get('pool_maxsize', 20)

        self.external_api_url = (
            self.config.get('external_api_url')
            or self.config.get('decrypt', {}).get('external_api_url')
            or self.download_config.get('decrypt', {}).get('external_api_url', DEFAULT_EXTERNAL_API_URL)
        )

        log_cfg = self.config.get('log', {})
        self.log_enabled = log_cfg.get('enabled', self.config.get('log_enabled', True))
        self.log_level = log_cfg.get('level', self.config.get('log_level', 'info'))
        self.log_dir = log_cfg.get('dir', self.config.get('log_dir', os.path.join(self.download_output_dir, 'log')))
        self.config['log'] = {'enabled': self.log_enabled, 'level': self.log_level, 'dir': self.log_dir}

        if self._session is not None:
            self.session = self._session

        self._load_root_dirs()
        self._load_additional_config()
        self._load_localized_interfaces()

    def _save_config_to_file(self, path=None):
        if path is None:
            path = os.path.join(SCRIPT_DIR, 'config.json')
        config = {
            "sources": [
                {"name": site['name'], "url": site['url'], "enabled": site.get('enabled', True)}
                for site in self.package_download_sites
            ],
            "download_output_dir": self.download_output_dir,
            "download": self.download_config,
            "proxy": self.download_config.get('proxy', ''),
            "github_proxy": self.download_config.get('github_proxy', GITHUB_PROXY),
            "github_proxy_patterns": self.github_proxy_patterns,
            "concurrent": self.download_config.get('concurrent', 3),
            "user_agent": getattr(self, 'user_agent', DEFAULT_USER_AGENT),
            "external_api_url": getattr(self, 'external_api_url', DEFAULT_EXTERNAL_API_URL),
            "log": {
                "enabled": getattr(self, 'log_enabled', True),
                "level": getattr(self, 'log_level', 'info'),
                "dir": getattr(self, 'log_dir', os.path.join(self.download_output_dir, 'log'))
            },
            "localized_interfaces": self.localized_interfaces,
            "root_dirs": self.root_dirs,
            "decrypt_filename_template": self.decrypt_filename_template,
            "localized_filename_template": self.localized_filename_template,
            "inject_manager_site": self.inject_manager_site,
            "oktv_switch_timeout": self.oktv_switch_timeout,
        }
        temp = path + ".tmp"
        os.makedirs(os.path.dirname(temp), exist_ok=True)
        with open(temp, 'w', encoding='utf-8') as f_local:
            json.dump(config, f_local, ensure_ascii=False, indent=2)
        os.replace(temp, path)
        self._save_persistent_config()

    def _save_persistent_config(self):
        try:
            os.makedirs(os.path.dirname(PERSISTENT_CONFIG_PATH), exist_ok=True)
            config = {
                "sources": [{"name": s['name'], "url": s['url'], "enabled": s.get('enabled', True)} for s in self.package_download_sites],
                "download_output_dir": self.download_output_dir,
                "download": self.download_config,
                "proxy": self.download_config.get('proxy', ''),
                "github_proxy": self.download_config.get('github_proxy', GITHUB_PROXY),
                "github_proxy_patterns": self.github_proxy_patterns,
                "concurrent": self.download_config.get('concurrent', 3),
                "user_agent": self.user_agent,
                "external_api_url": self.external_api_url,
                "log": {"enabled": self.log_enabled, "level": self.log_level, "dir": self.log_dir},
                "localized_interfaces": self.localized_interfaces,
                "root_dirs": self.root_dirs,
                "decrypt_filename_template": self.decrypt_filename_template,
                "localized_filename_template": self.localized_filename_template,
                "inject_manager_site": self.inject_manager_site,
                "oktv_switch_timeout": self.oktv_switch_timeout,
                "original_oktv_url": self._original_oktv_url,
            }
            with open(PERSISTENT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_persistent_config(self):
        if not os.path.exists(PERSISTENT_CONFIG_PATH):
            return None
        try:
            with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    # ===================== 站点管理 =====================
    def _init_site_state(self, site_id):
        if site_id not in self._site_states:
            self._site_states[site_id] = {
                'decrypt_status': 'idle', 'decrypt_msg': '未执行',
                'localize_status': 'idle', 'localize_msg': '未执行',
                'decrypt_result': None, 'localize_result': None,
            }

    def _get_site_status_icon(self, status):
        icons = {'idle': '⚪', 'processing': '🔄', 'success': '✅', 'error': '❌', 'partial': '⚠️'}
        return icons.get(status, '⚪')

    def _get_decrypt_status_text(self, site):
        state = self._site_states.get(site['id'], {})
        status = state.get('decrypt_status', 'idle')
        msg = state.get('decrypt_msg', '未执行')
        icon = self._get_site_status_icon(status)
        if status == 'processing':
            return f"{icon} 解密中..."
        elif status == 'success':
            return f"{icon} 已解密"
        elif status == 'error':
            return f"{icon} 解密失败"
        else:
            return f"{icon} 未执行"

    def _get_localize_status_text(self, site):
        state = self._site_states.get(site['id'], {})
        status = state.get('localize_status', 'idle')
        msg = state.get('localize_msg', '未执行')
        icon = self._get_site_status_icon(status)
        if status == 'processing':
            return f"{icon} 本地化中..."
        elif status == 'success':
            return f"{icon} 已本地化"
        elif status == 'error':
            return f"{icon} 本地化失败"
        else:
            return f"{icon} 未执行"

    def _package_download_site_id(self, name, url):
        payload = "{}\0{}".format(str(name or ""), str(url or ""))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _enabled_package_download_sites(self):
        return [s for s in self.package_download_sites if s.get("enabled", True)]

    def _normalize_package_download_name(self, name):
        name = re.sub(r'[\x00-\x1f]+', " ", str(name or "")).strip()
        name = re.sub(r'\s+', " ", name)
        if not name:
            raise ValueError("备注名不能为空")
        if name in (".", "..") or re.search(r'[\\/:*?"<>|]', name):
            raise ValueError("备注名包含非法字符")
        if len(name) > 40:
            raise ValueError("备注名不能超过40个字符")
        return name

    def _normalize_package_download_url(self, url):
        url = str(url or "").strip().strip('"').strip("'")
        if not url:
            raise ValueError("下载地址不能为空")
        if len(url) > 2048:
            raise ValueError("下载地址过长")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("下载地址必须是 http 或 https URL")
        return url

    def _add_or_update_package_download_site(self, name, url):
        clean_name = self._normalize_package_download_name(name)
        clean_url = self._normalize_package_download_url(url)
        name_match = url_match = None
        for item in self.package_download_sites:
            if str(item.get("name", "")).casefold() == clean_name.casefold():
                name_match = item
            if str(item.get("url", "")).casefold() == clean_url.casefold():
                url_match = item
        if name_match is not None and url_match is not None and name_match is not url_match:
            raise ValueError("备注名和网址分别属于已有站点")
        target = name_match or url_match
        created = target is None
        if created:
            if len(self.package_download_sites) >= 50:
                raise ValueError("下载站点最多保存50个")
            target = {
                "id": self._package_download_site_id(clean_name, clean_url),
                "name": clean_name, "url": clean_url,
                "enabled": True, "type": "json",
            }
            self.package_download_sites.append(target)
        else:
            target["name"] = clean_name
            target["url"] = clean_url
            target["type"] = "json"
        self._save_config_to_file()
        return dict(target), created

    def _delete_package_download_sites(self, site_ids):
        selected = {str(s).strip() for s in site_ids if str(s).strip()}
        if not selected:
            raise ValueError("请选择要删除的下载接口")
        existing = {str(item.get("id", "")).strip() for item in self.package_download_sites}
        matched = selected & existing
        if not matched:
            raise ValueError("选择的下载接口已不存在")
        if len(self.package_download_sites) - len(matched) < 1:
            raise ValueError("至少保留一个下载接口")
        self.package_download_sites = [item for item in self.package_download_sites if str(item.get("id", "")).strip() not in matched]
        self._save_config_to_file()
        return True

    # ===================== 核心下载与解析 =====================
    def _absolutize_urls(self, obj, base_url):
        if isinstance(obj, dict):
            return {k: self._absolutize_urls(v, base_url) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_urls(item, base_url) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith(('http://', 'https://')):
                return obj
            if obj.startswith(('./', '../', '/')):
                return urllib.parse.urljoin(base_url, obj)
            return obj
        else:
            return obj

    def _absolutize_local_paths(self, obj, base_dir):
        if isinstance(obj, dict):
            return {k: self._absolutize_local_paths(v, base_dir) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._absolutize_local_paths(item, base_dir) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith(('./', '../')):
                abs_path = os.path.abspath(os.path.join(base_dir, obj))
                return 'file://' + abs_path
            return obj
        else:
            return obj

    def _guess_category(self, url, field_key=None):
        if field_key in ('spider', 'jar'):
            return 'jar'
        path_part = url.split('?')[0].split(';')[0].rstrip('/')
        ext = os.path.splitext(path_part)[1].lower()
        if ext == '.jar': return 'jar'
        elif ext == '.py': return 'py'
        elif ext == '.js': return 'js'
        else: return 'lib'

    def _walk_and_collect(self, obj, base_url, result, field_key=None):
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_field = k if k in ('spider', 'jar') else field_key
                if isinstance(v, str):
                    stripped = v.strip()
                    if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                        parsed = _safe_json_loads(stripped)
                        if parsed is not None:
                            self._walk_and_collect(parsed, base_url, result, new_field)
                            continue
                    parts = [p.strip() for p in v.split('$$')]
                    for part in parts:
                        result.add((part, base_url, new_field))
                elif isinstance(v, (dict, list)):
                    self._walk_and_collect(v, base_url, result, new_field)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_and_collect(item, base_url, result, field_key)

    def _collect_files(self, data, base_url, downloader):
        all_items = set()
        self._walk_and_collect(data, base_url, all_items)
        max_depth = self.download_config.get('recursive_depth', 2)
        current_depth = 0
        processed_jsons = set()
        while current_depth < max_depth:
            json_items = [(u, b, fk) for u, b, fk in all_items
                          if u.split('?')[0].split(';')[0].lower().endswith('.json')]
            new_items = set()
            for url, url_base, field_key in json_items:
                if url in processed_jsons:
                    continue
                if not downloader.is_downloadable(url, field_key):
                    continue
                processed_jsons.add(url)
                content = downloader.download_text(url, url_base, force_decrypt=False)
                if content:
                    # v2.2：安全解析（自动剥离 JS 注释）
                    sub_data = _safe_json_loads(content)
                    if sub_data is not None:
                        if url.startswith(('http://', 'https://')):
                            parsed = urllib.parse.urlparse(url)
                            sub_base = f"{parsed.scheme}://{parsed.netloc}{os.path.dirname(parsed.path)}/"
                        else:
                            sub_base = url_base
                        self._walk_and_collect(sub_data, sub_base, new_items)
            if not new_items:
                break
            all_items.update(new_items)
            current_depth += 1
        unique = []
        seen = set()
        for url, url_base, field_key in all_items:
            if url in seen:
                continue
            seen.add(url)
            if downloader.is_downloadable(url, field_key):
                cat = self._guess_category(url, field_key)
                unique.append((url, cat, url_base, field_key))
        return unique

    def _parse_box_json(self, url, downloader):
        base_url = self._get_base_url(url)
        self._log(f"开始下载并解析接口: {url}")
        content = downloader.download_text(url, base_url, force_decrypt=True)
        if not content:
            self._log("下载内容为空")
            return None, None, "下载失败或内容为空"
        # v2.2：统一安全解析（自动剥离 JS 注释 + 片段提取兜底）
        data = _safe_json_loads(content)
        if data is not None:
            self._log("成功解析 JSON")
            return data, base_url, None
        decrypted = try_decrypt_content(content, url, self.external_api_url, self._session, max_rounds=5)
        if decrypted:
            self._log("解密成功，尝试解析")
            data = _safe_json_loads(decrypted)
            if data is not None:
                return data, base_url, None
        self._log("所有解析尝试均失败")
        return None, None, "无法解析为 JSON"

    def _download_all(self, paths, downloader):
        total = len(paths)
        if total == 0:
            return
        completed = [0]
        lock = threading.Lock()
        last_progress_time = [time.time()]
        def progress_wrapper(url, cat, base_url, field_key=None):
            if downloader.cancel_event and downloader.cancel_event.is_set():
                return None
            result = downloader.download_file(url, base_url, cat, field_key)
            with lock:
                completed[0] += 1
                now = time.time()
                if now - last_progress_time[0] > 1.0 or completed[0] == total:
                    pct = (completed[0] / total) * 100
                    self._push_log(f"⏳ 总进度 {completed[0]}/{total} ({pct:.1f}%) | 当前: {os.path.basename(url)[:30]}")
                    last_progress_time[0] = now
            return result
        max_workers = min(self.max_workers, max(1, len(paths)))
        self._push_log(f"🚀 启动 {max_workers} 线程并发下载，共 {total} 个文件...")
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(progress_wrapper, url, cat, base_url, field_key): (url, cat)
                       for url, cat, base_url, field_key in paths}
            for fut in as_completed(futures):
                if downloader.cancel_event and downloader.cancel_event.is_set():
                    ex.shutdown(wait=False)
                    break
        self._push_log(f"✅ 批量下载完成 {completed[0]}/{total}")

    def _find_local_path(self, url, downloader, keep_md5=False):
        if not url or not isinstance(url, str):
            return None
        url_part, suffix = downloader.split_url_and_suffix(url)
        # v2.2.2：仅 spider 字段的本地化引用保留 ;md5; 校验后缀（如 "./jar/xxx.jar;md5;xxx"），
        # 其他字段（api/url/ext 等）一律不带 md5 后缀；本地文件本身始终以无后缀名存储
        def _local_ref(rel):
            p = './' + rel.replace('\\', '/')
            if suffix and keep_md5:
                p += suffix
            return p
        if url_part in downloader.downloaded:
            return _local_ref(downloader.downloaded[url_part])
        variants = set()
        normalized = downloader.normalize_github_url(url_part)
        variants.add(normalized)
        if downloader.github_proxy:
            proxy = downloader.github_proxy.rstrip('/') + '/'
            if url_part.startswith(proxy):
                raw = url_part[len(proxy):]
                variants.add(raw)
                if raw.startswith('raw.githubusercontent.com/'):
                    variants.add('https://' + raw)
        for variant in variants:
            if variant != url_part and variant in downloader.downloaded:
                return _local_ref(downloader.downloaded[variant])
        return None

    def _collect_missing_files(self, data, downloader):
        all_items = set()
        self._walk_and_collect(data, "", all_items)
        missing = []
        seen = set()
        for url, _, field_key in all_items:
            if url in seen:
                continue
            seen.add(url)
            if not downloader.is_downloadable(url, field_key):
                continue
            url_part, _ = downloader.split_url_and_suffix(url)
            if url_part in downloader.downloaded:
                continue
            found = False
            variants = [downloader.normalize_github_url(url_part)]
            if downloader.github_proxy:
                proxy = downloader.github_proxy.rstrip('/') + '/'
                if url_part.startswith(proxy):
                    variants.append(url_part[len(proxy):])
            for v in variants:
                if v in downloader.downloaded:
                    found = True
                    break
            if found:
                continue
            cat = self._guess_category(url, field_key)
            missing.append((url, cat, "", field_key))
        return missing

    def _generate_local_box(self, data, source_name, output_dir, downloader):
        def localize(obj, field_key=None):
            if isinstance(obj, dict):
                return {k: localize(v, k) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [localize(item, field_key) for item in obj]
            elif isinstance(obj, str):
                stripped = obj.strip()
                if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                    parsed = _safe_json_loads(stripped)
                    if parsed is not None:
                        replaced = localize(parsed)
                        return json.dumps(replaced, ensure_ascii=False, separators=(',', ':'))
                # v2.2.2：仅 spider 字段保留 ;md5; 校验后缀，其他字段不带
                keep_md5 = (field_key == 'spider')
                local_path = self._find_local_path(obj, downloader, keep_md5=keep_md5)
                if local_path:
                    return local_path
                return obj
            else:
                return obj
        local_data = localize(data)
        local_data['warningText'] = f"本地包生成于 {time.strftime('%Y-%m-%d %H:%M:%S')} | 源: {source_name}"
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', source_name)
        box_filename = self.localized_filename_template.format(name=safe_name)
        box_path = os.path.join(output_dir, box_filename)
        with open(box_path, 'w', encoding='utf-8') as f_local:
            json.dump(local_data, f_local, ensure_ascii=False, indent=2)
        return box_path

    def _process_json_source(self, site, cancel_event=None):
        name = site.get("name", "未命名")
        url = site.get("url", "")
        if not url:
            raise ValueError("接口URL为空")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
        output_dir = os.path.join(self.download_output_dir, safe_name)
        os.makedirs(output_dir, exist_ok=True)
        download_cfg = copy.deepcopy(self.download_config)
        download_cfg['base_url'] = self._get_base_url(url)
        download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
        download_cfg['github_proxy_patterns'] = self.github_proxy_patterns
        download_cfg['user_agent'] = self.user_agent
        if self.force_overwrite:
            download_cfg['overwrite'] = True
        downloader = FileDownloader(output_dir, download_cfg, log_callback=self._log, progress_callback=self._push_log,
                                    cancel_event=cancel_event)
        self._package_download_message = f"正在解析 {name} ..."
        self._push_log(f"🎯 开始处理接口: {name}")
        data, base_url, error = self._parse_box_json(url, downloader)
        if error:
            raise Exception(f"解析失败: {error}")
        paths = self._collect_files(data, base_url, downloader)
        self._package_download_message = f"正在下载 {len(paths)} 个文件 ..."
        self._push_log(f"📦 收集到 {len(paths)} 个可下载文件，开始并发下载...")
        self._download_all(paths, downloader)
        # v5.4 增强：遗漏文件补充下载
        missing = self._collect_missing_files(data, downloader)
        if missing:
            self._push_log(f"🔄 发现 {len(missing)} 个遗漏文件，补充下载...")
            self._download_all(missing, downloader)
        self._push_log(f"🧩 正在生成本地化 box.json...")
        local_box_path = self._generate_local_box(data, name, output_dir, downloader)
        self._push_log(f"🎉 接口 {name} 处理完成！输出: {local_box_path}")
        stats = {
            "downloaded": len(downloader.downloaded),
            "failed": len(downloader.failed),
            "skipped": len(downloader.skipped),
            "output_dir": output_dir,
            "box_path": local_box_path,
        }
        self._add_or_update_localized_interface(name, url, local_box_path)
        return stats

    def _get_base_url(self, url):
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{os.path.dirname(parsed.path)}/"
        if not base.endswith('/'):
            base += '/'
        return base

    # ===================== 单站点操作 =====================
    def _decrypt_single_site(self, site_id):
        site = next((s for s in self.package_download_sites if s['id'] == site_id), None)
        if not site:
            return "站点不存在"
        with self._site_op_lock:
            if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                return "该站点正在处理中"
            self._init_site_state(site_id)
            self._site_states[site_id]['decrypt_status'] = 'processing'
            self._site_states[site_id]['decrypt_msg'] = '正在解密...'
            cancel_event = threading.Event()
            self._site_cancel_events[site_id] = cancel_event
        def _worker():
            try:
                name, url = site['name'], site['url']
                self._log(f"【解密】开始处理 {name} ({url})")
                download_cfg = copy.deepcopy(self.download_config)
                download_cfg['base_url'] = self._get_base_url(url)
                download_cfg['github_proxy'] = self.config.get('github_proxy', GITHUB_PROXY)
                download_cfg['github_proxy_patterns'] = self.github_proxy_patterns
                downloader = FileDownloader(self.download_output_dir, download_cfg, log_callback=self._log,
                                            cancel_event=cancel_event)
                content = downloader.download_text(url, self._get_base_url(url), force_decrypt=True)
                if cancel_event.is_set():
                    self._site_states[site_id]['decrypt_status'] = 'idle'
                    self._site_states[site_id]['decrypt_msg'] = '已取消'
                    return
                if not content:
                    self._site_states[site_id]['decrypt_status'] = 'error'
                    self._site_states[site_id]['decrypt_msg'] = '下载失败'
                    return
                data = _safe_json_loads(content)
                if data is not None:
                    is_json = True
                else:
                    is_json = False
                base_url = self._get_base_url(url)
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', name)
                output_dir = os.path.join(self.download_output_dir, safe_name)
                os.makedirs(output_dir, exist_ok=True)
                decrypt_name = self.decrypt_filename_template.format(name=safe_name)
                dec_path = os.path.join(output_dir, decrypt_name)
                if is_json:
                    data = self._absolutize_urls(data, base_url)
                    with open(dec_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self._site_states[site_id]['decrypt_status'] = 'success'
                    self._site_states[site_id]['decrypt_msg'] = '明文JSON已保存'
                    self._site_states[site_id]['decrypt_result'] = dec_path
                else:
                    dec = try_decrypt_content(content, url, self.external_api_url, self._session, max_rounds=5)
                    if dec:
                        data = _safe_json_loads(dec)
                        if data is not None:
                            data = self._absolutize_urls(data, base_url)
                            with open(dec_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            self._site_states[site_id]['decrypt_status'] = 'success'
                            self._site_states[site_id]['decrypt_msg'] = '解密成功'
                            self._site_states[site_id]['decrypt_result'] = dec_path
                        else:
                            with open(dec_path, 'w', encoding='utf-8') as f:
                                f.write(dec)
                            self._site_states[site_id]['decrypt_status'] = 'success'
                            self._site_states[site_id]['decrypt_msg'] = '解密成功(非JSON)'
                            self._site_states[site_id]['decrypt_result'] = dec_path
                    else:
                        self._site_states[site_id]['decrypt_status'] = 'error'
                        self._site_states[site_id]['decrypt_msg'] = '解密失败'
            except Exception as e:
                self._site_states[site_id]['decrypt_status'] = 'error'
                self._site_states[site_id]['decrypt_msg'] = f'异常: {str(e)[:30]}'
                self._log(f"【解密】异常: {e}")
            finally:
                with self._site_op_lock:
                    self._site_op_threads.pop(site_id, None)
                    if site_id in self._site_cancel_events:
                        del self._site_cancel_events[site_id]
        t = threading.Thread(target=_worker, daemon=True)
        with self._site_op_lock:
            self._site_op_threads[site_id] = t
        t.start()
        return "已开始解密任务"

    def _localize_single_site(self, site_id):
        site = next((s for s in self.package_download_sites if s['id'] == site_id), None)
        if not site:
            return "接口不存在"
        with self._site_op_lock:
            if site_id in self._site_op_threads and self._site_op_threads[site_id].is_alive():
                return "该接口正在处理中"
            self._init_site_state(site_id)
            self._site_states[site_id]['localize_status'] = 'processing'
            self._site_states[site_id]['localize_msg'] = '正在转换...'
            cancel_event = threading.Event()
            self._site_cancel_events[site_id] = cancel_event
        def _worker():
            try:
                stats = self._process_json_source(site, cancel_event)
                if cancel_event.is_set():
                    self._site_states[site_id]['localize_status'] = 'idle'
                    self._site_states[site_id]['localize_msg'] = '已取消'
                    return
                self._site_states[site_id]['localize_status'] = 'success'
                self._site_states[site_id]['localize_msg'] = f"下载{stats['downloaded']}个文件"
                self._site_states[site_id]['localize_result'] = stats.get('box_path')
            except Exception as e:
                self._site_states[site_id]['localize_status'] = 'error'
                self._site_states[site_id]['localize_msg'] = f'失败: {str(e)[:30]}'
                self._log(f"【本地化】{site['name']} 失败: {e}")
            finally:
                with self._site_op_lock:
                    self._site_op_threads.pop(site_id, None)
                    if site_id in self._site_cancel_events:
                        del self._site_cancel_events[site_id]
        t = threading.Thread(target=_worker, daemon=True)
        with self._site_op_lock:
            self._site_op_threads[site_id] = t
        t.start()
        return "已开始本地化任务"

    def _decrypt_all_sites(self):
        enabled = self._enabled_package_download_sites()
        if not enabled:
            return "没有已开启的站点"
        for site in enabled:
            self._decrypt_single_site(site['id'])
        return f"已开始解密 {len(enabled)} 个站点"

    def _start_package_download(self, sites=None):
        if sites is None:
            sites = self._enabled_package_download_sites()
        if not sites:
            return False, "没有选择任何接口"
        with self._package_download_lock:
            if self._package_download_thread and self._package_download_thread.is_alive():
                return False, "正在下载中"
            names = "、".join(s.get("name", "本地包") for s in sites)
            self._package_download_state = "queued"
            self._package_download_message = "已加入批量任务：{}".format(names)
            self._package_cancel_event = threading.Event()
            worker = threading.Thread(target=self._package_download_worker, args=(sites, self._package_cancel_event), daemon=True)
            self._package_download_thread = worker
            worker.start()
        return True, "开始下载 {} 个已选接口".format(len(sites))

    def _package_download_worker(self, sites, cancel_event):
        successes = []
        failures = []
        used_names = set()
        try:
            total = len(sites)
            for idx, site in enumerate(sites, 1):
                if cancel_event.is_set():
                    self._log("批量下载已取消")
                    break
                name = site.get("name", "本地包")
                url = site.get("url", "")
                try:
                    self._package_download_state = "processing"
                    self._package_download_message = "正在转换 {}/{}：{}".format(idx, total, name)
                    self._push_log(f"🚀 [{idx}/{total}] 开始处理接口: {name}")
                    package_name = self._normalize_package_download_name(name)
                    if package_name.casefold() in used_names:
                        raise ValueError("下载接口备注名重复: {}".format(name))
                    used_names.add(package_name.casefold())
                    stats = self._process_json_source(site, cancel_event)
                    if cancel_event.is_set():
                        break
                    successes.append({"name": name, "url": url, "result": stats})
                except Exception as e:
                    failures.append({"name": name, "error": str(e)})
            if cancel_event.is_set():
                self._package_download_state = "idle"
                self._package_download_message = "批量下载已被取消"
                return
            if not successes:
                raise ValueError("没有接口处理成功")
            total_files = sum(item["result"].get("downloaded", 0) for item in successes)
            fail_detail = "；".join("{}: {}".format(f["name"], f["error"]) for f in failures)
            msg = "批量处理完成：成功 {}/{}，共 {} 个文件；{}".format(
                len(successes), len(sites), total_files,
                "失败 {} 个（{}）；".format(len(failures), fail_detail) if failures else ""
            )
            self._package_download_state = "partial" if failures else "success"
            self._package_download_message = msg
            self._log(msg)
        except Exception as e:
            msg = "批量处理失败: {}".format(e)
            self._package_download_state = "error"
            self._package_download_message = msg
            self._log(msg)
        finally:
            with self._package_download_lock:
                self._package_download_thread = None
                self._package_cancel_event = None

    # ===================== 本地化接口管理 =====================
    def _load_localized_interfaces(self):
        try:
            if os.path.exists(PERSISTENT_CONFIG_PATH):
                with open(PERSISTENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.localized_interfaces = data.get("localized_interfaces", [])
            else:
                self.localized_interfaces = []
        except Exception:
            self.localized_interfaces = []

    def _add_or_update_localized_interface(self, name, url, box_path):
        abs_path = os.path.abspath(box_path)
        parent_dir = os.path.dirname(abs_path)
        dir_name = os.path.basename(parent_dir)
        for item in self.localized_interfaces:
            if item.get("parent_dir") == parent_dir and item.get("dir_name") == dir_name:
                if abs_path not in item.get("json_files", []):
                    item["json_files"].append(abs_path)
                if not item.get("selected"):
                    item["selected"] = abs_path
                self._save_config_to_file()
                return
        self.localized_interfaces.append({
            "parent_dir": parent_dir, "dir_name": dir_name,
            "json_files": [abs_path], "selected": abs_path, "hidden": False
        })
        self._save_config_to_file()

    # ===================== 初始化入口 =====================
    def init(self, extend=""):
        with self.lock:
            if self.inited:
                return
            self._initial_extend = extend
            self._init_session()
            config = self._load_default_config()
            ext = {}
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                elif isinstance(extend, str):
                    extend_str = extend.strip()
                    if extend_str.startswith('{') or extend_str.startswith('['):
                        try:
                            ext = json.loads(extend_str)
                        except Exception:
                            ext = {}
                    elif extend_str.startswith(('http://', 'https://', 'ftp://')) or os.path.exists(extend_str):
                        loaded = self._load_config_from_ext(extend_str)
                        if loaded and isinstance(loaded, dict):
                            ext = loaded
                    else:
                        ext = {'urls': [extend_str]} if extend_str else {}
                else:
                    ext = {}
            self._detect_base_dir(ext)
            if ext:
                ext = self._normalize_config_keys(ext)
                config_file = ext.get('config_file', '')
                if config_file:
                    cf_config = self._load_json_resource(config_file)
                    if cf_config:
                        cf_config = self._normalize_config_keys(cf_config)
                        for k, v in cf_config.items():
                            if k not in ext:
                                ext[k] = v
                for k, v in ext.items():
                    if k == 'config_file':
                        continue
                    if isinstance(v, dict) and k in config and isinstance(config[k], dict):
                        config[k].update(v)
                    else:
                        config[k] = v
            self._apply_config(config)
            persistent = self._load_persistent_config()
            if persistent and isinstance(persistent, dict):
                persistent = self._normalize_config_keys(persistent)
                for k, v in persistent.items():
                    if k == 'config_file':
                        continue
                    if isinstance(v, dict) and k in self.config and isinstance(self.config[k], dict):
                        self.config[k].update(v)
                    else:
                        self.config[k] = v
                self._apply_config(self.config)
                self._original_oktv_url = persistent.get("original_oktv_url")
            self.inited = True
            self._log("初始化完成（双平台兼容版 v2.1）")

    # ===================== Windows 命令行专用方法 =====================
    def _ensure_initialized(self):
        if not self.inited:
            try:
                self.init("")
            except Exception:
                self.inited = True

    def run_download_all(self):
        """一键下载所有已启用站点（Windows 命令行入口）"""
        self._ensure_initialized()
        started, msg = self._start_package_download()
        print(msg)
        while self._package_download_thread and self._package_download_thread.is_alive():
            time.sleep(1)
        print("所有下载任务已完成。")

    def run_decrypt_all(self):
        self._ensure_initialized()
        msg = self._decrypt_all_sites()
        print(msg)
        # v2.2：等待后台解密线程完成，避免 CLI 进程退出时 daemon 线程被杀死
        for site_id in list(self._site_op_threads.keys()):
            t = self._site_op_threads.get(site_id)
            while t and t.is_alive():
                time.sleep(1)
        print("所有解密任务已完成。")

    def run_decrypt_site(self, site_id):
        self._ensure_initialized()
        msg = self._decrypt_single_site(site_id)
        print(msg)
        # v2.2：等待该站点后台线程完成
        t = self._site_op_threads.get(site_id)
        while t and t.is_alive():
            time.sleep(1)
        state = self._site_states.get(site_id, {})
        print("解密结果: {} - {}".format(state.get('decrypt_status'), state.get('decrypt_msg')))

    def run_localize_site(self, site_id):
        self._ensure_initialized()
        msg = self._localize_single_site(site_id)
        print(msg)
        # v2.2：等待该站点后台线程完成
        t = self._site_op_threads.get(site_id)
        while t and t.is_alive():
            time.sleep(1)
        state = self._site_states.get(site_id, {})
        print("本地化结果: {} - {}".format(state.get('localize_status'), state.get('localize_msg')))

    # ===================== TVBox 标准接口（完整保留） =====================
    def getName(self):
        return "本地包管理器 {}".format(self.VERSION)

    def homeContent(self, filter):
        self._ensure_initialized()
        if not _HAS_BASE_SPIDER:
            return {"class": [], "filters": {}}
        classes = [
            {"type_id": "center", "type_name": "🎮管理中心"},
            {"type_id": "decrypt", "type_name": "🔐解密"},
            {"type_id": "localize", "type_name": "🥁本地"},
            {"type_id": "settings", "type_name": "🛠设置"},
        ]
        return {"class": classes, "filters": {}}

    def homeVod(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, ext):
        self._ensure_initialized()
        if not _HAS_BASE_SPIDER:
            return {"page": 1, "pagecount": 1, "limit": 10, "total": 0, "list": []}
        return {"page": 1, "pagecount": 1, "limit": 10, "total": 0, "list": []}

    def detailContent(self, array):
        self._ensure_initialized()
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        return {"page": 1, "pagecount": 1, "limit": 10, "total": 0, "list": []}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": "", "header": {}, "msg": "该条目为配置管理"}

    def localProxy(self, params):
        return [404, "application/json", json.dumps({"error": "not found"})]

    def action(self, action):
        self._ensure_initialized()
        return {"code": 0, "msg": ""}

    def destroy(self):
        self._destroyed = True
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        for ev in self._site_cancel_events.values():
            ev.set()
        if self._package_cancel_event:
            self._package_cancel_event.set()
        return "destroy"

# ========================= Windows 命令行主入口（完全兼容原 dow.txt） =========================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="在线转本地工具 - 双平台增强版 v2.1（解密能力对齐dow.py）")
    parser.add_argument("-c", "--config", help="指定配置文件路径（如 download.json）")
    parser.add_argument("--overwrite", action="store_true", help="强制覆盖已有文件（即使配置中未开启）")
    parser.add_argument("--decrypt-all", action="store_true", help="解密所有已开启站点")
    parser.add_argument("--decrypt-site", help="解密指定站点（通过备注名或ID）")
    parser.add_argument("--localize-site", help="本地化指定站点（通过备注名或ID）")
    parser.add_argument("--download-all", action="store_true", help="一键下载所有已开启站点（默认行为）")
    args = parser.parse_args()

    spider = Spider()
    if args.overwrite:
        spider.force_overwrite = True
        print("⚠️ 已启用强制覆盖模式，所有已存在的文件将被重新下载。")

    # 加载配置
    if args.config:
        spider.init(args.config)
    else:
        default_cfg = os.path.join(SCRIPT_DIR, "config.json")
        if os.path.exists(default_cfg):
            spider.init(default_cfg)
        else:
            spider.init("")

    # 执行命令
    if args.decrypt_all:
        spider.run_decrypt_all()
    elif args.decrypt_site:
        site_id = args.decrypt_site
        found = False
        for site in spider.package_download_sites:
            if site['id'] == site_id or site['name'] == site_id:
                spider.run_decrypt_site(site['id'])
                found = True
                break
        if not found:
            print(f"未找到站点: {site_id}")
    elif args.localize_site:
        site_id = args.localize_site
        found = False
        for site in spider.package_download_sites:
            if site['id'] == site_id or site['name'] == site_id:
                spider.run_localize_site(site['id'])
                found = True
                break
        if not found:
            print(f"未找到站点: {site_id}")
    else:
        spider.run_download_all()
