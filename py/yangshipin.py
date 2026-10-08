#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
央视频直播 - 单源多模式版 (JCE 25312 / bkliveinfo)，TVBox / FongMi / VodPlus 爬虫版

用法一：当直播源（live 里填）
{
"api": "./yangshipin.py",
"ext": {},
"name": "央视频"
}

用法二：当点播站（site 里填）
{
"key": "yangshipin_vod", "name": "央视频",
"type": 3,
"api": "./yangshipin.py", "ext": {}
}

ext 可选：
  epg_xml         直播源 M3U 的节目单地址，默认 https://epg.112114.xyz/pp.xml，留空则不写
  epg_ids         覆盖 tvg-id 映射，如 {"CCTV-1 综合": "CCTV1"}
  logo_mode       direct(默认) 台标走 CDN 直连；proxy 则全部走本地代理
  direct          true = 全部请求走 urllib，不借容器的 self.fetch()，排错时用
  wait            打开频道时等待首帧就绪的秒数，默认 12
  live_mode       proxy(默认) 走代理滚动缓冲；redirect 直接 302 到官方 m3u8，省掉握手等待

排错：浏览器打开 代理地址?type=diag
      加 &slug=cctv1 会当场拉一次流（&mode=redirect 则测直连取址）

多模式兼容说明：
- 出网：所有请求统一走 _http()，GET 优先借容器 self.fetch()，失败或 POST 回落 urllib，
  SSL 校验失败自动降级重试一次；ext direct=true 可只用 urllib
- 取流：单源双通道互备 —— bk(bkliveinfo) 取不到自动回落 JCE，
  JCE 撞到死链 CDN(liverecord.video.cloud.cctv.com) 自动切 bk
- 播放：localProxy 取代 ThreadingHTTPServer，不占端口；live_mode 可在
  代理滚动缓冲(proxy) 与 官方直连 302(redirect) 之间切换
- 入口：live(直播 M3U) / site(点播分类+详情) / diag 三种模式共用同一份频道表
"""

import base64, gzip, hashlib, json, os, random, re, struct, threading, time
import ssl
import urllib.error, urllib.parse, urllib.request, uuid
from collections import deque

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"


# ================================================================ 日志 (已禁用文件写入)
# 只 print 到 stdout, 不写文件. TVBox 一般看不到 stdout, 等于静默.

def _log(msg):
    try:
        print('[ysp] ' + msg, flush=True)
    except Exception:
        pass


def format_remarks(brand="央视频", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    return ("%s | %s" % (brand, clean_meta)) if clean_meta else brand


UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
WINDOW = 300
REFRESH_INTERVAL = 2
IDLE_TIMEOUT = 300
MAX_SEGS = 400
PLAYLIST_WINDOW = 8
HTTP_TIMEOUT = 12


# ================================================================ JCE 协议

class W:
    def __init__(self): self.b = bytearray()
    def head(self, typ, tag):
        if tag < 15: self.b.append(((tag & 0xf) << 4) | (typ & 0xf))
        else: self.b.append(0xf0 | (typ & 0xf)); self.b.append(tag)
    def byte(self, v, tag):
        v = int(v)
        if v == 0: self.head(12, tag)
        else: self.head(0, tag); self.b += struct.pack('>b', v)
    def short(self, v, tag):
        v = int(v)
        if -128 <= v <= 127: self.byte(v, tag)
        else: self.head(1, tag); self.b += struct.pack('>h', v)
    def int(self, v, tag):
        v = int(v)
        if -32768 <= v <= 32767: self.short(v, tag)
        else: self.head(2, tag); self.b += struct.pack('>i', v)
    def long(self, v, tag):
        v = int(v)
        if -2147483648 <= v <= 2147483647: self.int(v, tag)
        else: self.head(3, tag); self.b += struct.pack('>q', v)
    def float(self, v, tag):
        self.head(4, tag); self.b += struct.pack('>f', float(v))
    def double(self, v, tag):
        self.head(5, tag); self.b += struct.pack('>d', float(v))
    def string(self, s, tag):
        if s is None: return
        data = str(s).encode('utf-8')
        if len(data) > 255: self.head(7, tag); self.b += struct.pack('>i', len(data)); self.b += data
        else: self.head(6, tag); self.b.append(len(data)); self.b += data
    def bytes(self, data, tag):
        data = bytes(data); self.head(13, tag); self.head(0, 0); self.int(len(data), 0); self.b += data
    def struct(self, fn, tag): self.head(10, tag); fn(self); self.head(11, 0)
    def list(self, items, tag, wf=None): self.head(9, tag); self.int(len(items), 0)
    def out(self): return bytes(self.b)


class R:
    def __init__(self, data): self.d = memoryview(data); self.p = 0
    def rem(self): return len(self.d) - self.p
    def get(self, n):
        if self.p + n > len(self.d): raise EOFError
        b = self.d[self.p:self.p + n].tobytes(); self.p += n; return b
    def u8(self): return self.get(1)[0]
    def head(self):
        b = self.u8(); typ = b & 0xf; tag = (b & 0xf0) >> 4
        if tag == 15: tag = self.u8()
        return typ, tag
    def value(self, typ):
        if typ == 0: return struct.unpack('>b', self.get(1))[0]
        if typ == 1: return struct.unpack('>h', self.get(2))[0]
        if typ == 2: return struct.unpack('>i', self.get(4))[0]
        if typ == 3: return struct.unpack('>q', self.get(8))[0]
        if typ == 4: return struct.unpack('>f', self.get(4))[0]
        if typ == 5: return struct.unpack('>d', self.get(8))[0]
        if typ == 6: n = self.u8(); return self.get(n).decode('utf-8', 'replace')
        if typ == 7: n = struct.unpack('>i', self.get(4))[0]; return self.get(n).decode('utf-8', 'replace')
        if typ == 8: n = self._int(); return {self._fv(): self._fv() for _ in range(n)}
        if typ == 9: n = self._int(); return [self._fv() for _ in range(n)]
        if typ == 10: return self.struct()
        if typ == 11: return None
        if typ == 12: return 0
        if typ == 13: t, _ = self.head(); n = self._int(); return self.get(n)
        raise ValueError('type %d' % typ)
    def _fv(self): t, _ = self.head(); return self.value(t)
    def _int(self): t, _ = self.head(); return int(self.value(t))
    def struct(self):
        m = {}
        while self.rem() > 0:
            t, tag = self.head()
            if t == 11: break
            m[tag] = self.value(t)
        return m


VER_NAME, VER_CODE = '3.2.7.26212', '302070'
APP_ID, QMF_APP_ID, QMF_PLATFORM, BIZ_ID = '1200013', 10012, 1, 0
CHAN_ID = '10070'
GUID = ''.join(random.choice('0123456789abcdef') for _ in range(32))


def _qua(w):
    w.string(VER_NAME, 0); w.string(VER_CODE, 1)
    w.int(1080, 2); w.int(2400, 3); w.int(3, 4); w.string('12', 5)
    w.int(1, 6); w.int(1, 7); w.int(420, 8); w.string(CHAN_ID, 9)
    for i in range(10, 15): w.string('', i)
    w.struct(lambda ww: (ww.int(0, 0), ww.byte(0, 1), ww.string('', 2)), 15)
    w.string('', 16); w.string('', 17); w.string('', 18)
    w.struct(lambda ww: (ww.int(0, 0), ww.float(0, 1), ww.float(0, 2), ww.double(0, 3)), 19)
    w.string(GUID[:16], 20); w.string('Pixel 6', 21)
    w.int(1, 22)
    for i in range(23, 27): w.int(0, i)
    w.string('', 27); w.string('', 28); w.string(GUID, 29)


def _head(w, cmd, reqid):
    w.int(reqid, 0); w.int(cmd, 1)
    w.struct(lambda ww: _qua(ww), 2)
    w.string(APP_ID, 3); w.string(GUID, 4)
    w.list([], 5); w.struct(lambda ww: None, 6)
    w.list([], 7)
    w.int(0, 8); w.int(0, 9); w.int(0, 10)


def _wrap(cmd, body, reqid):
    w = W()
    w.struct(lambda ww: _head(ww, cmd, reqid), 0)
    w.bytes(body, 1)
    reqcmd = w.out()
    inner = bytearray([38]) + struct.pack('>i', len(reqcmd) + 17) + bytes([1]) + b'\x00' * 10 + reqcmd + bytes([40])
    comp = gzip.compress(bytes(inner))
    out = bytearray([19]) + struct.pack('>i', 0) + struct.pack('>H', 2) + struct.pack('>H', 65281)
    out += struct.pack('>H', cmd) + struct.pack('>H', 0) + struct.pack('>q', reqid)
    out += struct.pack('>i', 531) + struct.pack('>i', QMF_APP_ID) + struct.pack('>q', BIZ_ID)
    g = GUID.encode()[:32]; out += g + b'\x00' * (32 - len(g))
    out += struct.pack('>b', QMF_PLATFORM) + struct.pack('>i', int(VER_CODE)) + b'\x00' * 6
    out += bytes([0]) + struct.pack('>H', 0) + struct.pack('>H', 0)
    out += struct.pack('>i', len(inner)) + comp + bytes([3])
    struct.pack_into('>i', out, 1, len(out))
    return bytes(out)


def _unwrap(data):
    if data[:1] != b'\x13' or len(data) < 90: return None
    flags = struct.unpack('>i', data[21:25])[0]
    payload = data[89:-1]
    if flags & 2: payload = gzip.decompress(payload)
    if payload[:1] != b'&' or payload[-1:] != b'(': return None
    rc = R(payload[16:-1]).struct()
    return rc.get(1) or b''


class DeadHostError(RuntimeError):
    pass


def jce_timeshift_url(pid, sid, start, end, stream='fhd'):
    w = W()
    w.string(pid, 0); w.string(sid, 1); w.long(start, 2); w.long(end, 3); w.string(stream, 4)
    body = w.out()
    CMD = 25312
    reqid = int(time.time() * 1000) & 0x7fffffff
    packet = _wrap(CMD, body, reqid)
    st, raw, _ = _http('POST', 'https://jacc.ysp.cctv.cn',
                      {'Content-Type': 'application/octet-stream'}, packet, HTTP_TIMEOUT)
    if st < 200 or st >= 300:
        raise RuntimeError('jce HTTP %d' % st)
    resp_body = _unwrap(raw)
    if not resp_body: raise RuntimeError('bad response')
    m = R(resp_body).struct()
    err = m.get(0, 0)
    if err != 0: raise RuntimeError(m.get(1, 'errCode=%s' % err))
    url = m.get(2, '')
    if not url: raise RuntimeError('empty m3u8')
    if 'liverecord.video.cloud.cctv.com' in url:
        raise DeadHostError('dead cdn host')
    return url


# ================================================================ cKey + bkliveinfo

_CK_PLATFORM = 4330403
_CK_APPVER = 'V8.22.1035.3031'
_CK_TEA = bytes.fromhex('59b2f7cf725ef43c34fdd7c123411ed3')
_CK_GTEA = bytes.fromhex('110DBEC10C23E7D2E56A1CAD6914EF1B')
_CK_XOR = bytes([0x84, 0x2e, 0xed, 0x08, 0xf0, 0x66, 0xe6, 0xea, 0x48, 0xb4, 0xca, 0xa9, 0x91, 0xed, 0x6f, 0xf3])
_CK_GXOR = bytes([0xb3, 0xc9, 0x53, 0xa0, 0x69, 0x13, 0xad, 0x4d])


def _u32(v): return v & 0xFFFFFFFF


def _tea_blk(blk, key):
    y, z = struct.unpack('>2I', blk)
    k = struct.unpack('>4I', key)
    s = 0
    for _ in range(16):
        s = _u32(s + 0x9e3779b9)
        y = _u32(y + _u32(_u32(_u32(z << 4) + k[0]) ^ _u32(z + s) ^ _u32((z >> 5) + k[1])))
        z = _u32(z + _u32(_u32(_u32(y << 4) + k[2]) ^ _u32(y + s) ^ _u32((y >> 5) + k[3])))
    return struct.pack('>2I', y, z)


def _cksum(buf):
    v = 0
    for b in buf: v = (0x83 * v + b) & 0x7fffffff
    return v


def _tea_pkt(data, key):
    pad = (8 - ((len(data) + 10) % 8)) % 8
    plain = bytes([(os.urandom(1)[0] & 0xf8) | pad]) + os.urandom(pad) + os.urandom(2) + data + bytes(7)
    out, pp, pc = b'', bytes(8), bytes(8)
    for off in range(0, len(plain), 8):
        mixed = bytes(a ^ b for a, b in zip(plain[off:off + 8], pc))
        enc = _tea_blk(mixed, key)
        cipher = bytes(a ^ b for a, b in zip(enc, pp))
        out += cipher
        pp, pc = mixed, cipher
    return out


def _lp(s):
    d = s.encode() if isinstance(s, str) else s
    return struct.pack('>H', len(d)) + d


def _ck_guard(ts, guid):
    def tail(v):
        t = str(v); return t[-5:] if len(t) >= 5 else ''
    body = struct.pack('>I', ts) + _lp(tail(guid)) + _lp(tail('null')) + _lp(tail('null')) + _lp('-1')
    plain = _lp(body)
    enc = _tea_pkt(plain, _CK_GTEA) + struct.pack('>I', _cksum(plain))
    enc = bytes(a ^ _CK_GXOR[i & 7] for i, a in enumerate(enc))
    return enc.hex().upper()


def _ckey(channel_id):
    ts = int(time.time())
    guid = os.urandom(16).hex()
    guard = _ck_guard(ts, guid)
    uid = os.urandom(4).hex().upper()
    body = (bytes.fromhex('0000004200000004000004d2') + struct.pack('>I', _CK_PLATFORM)
            + struct.pack('>I', 0) + struct.pack('>I', ts) + _lp('dcgh')
            + _lp('_zj1A5Gh6QYcxWjIUGos2w==') + _lp(_CK_APPVER) + _lp(str(channel_id))
            + _lp(guid) + struct.pack('>I', 1) + struct.pack('>I', 1) + _lp(uid) + _lp('nil')
            + _lp('57eab0c4-2c58-44c6-8ae9-dd2757525dc5') + _lp('nil') + _lp('v0.1.000')
            + _lp('com.cctv.yangshipin.app.iphone') + _lp(str(_CK_PLATFORM))
            + _lp('ex_json_bus') + _lp('ex_json_vs') + _lp(guard))
    pkt = bytearray(struct.pack('>H', len(body)) + body)
    pkt[18:22] = struct.pack('>I', _cksum(bytes(pkt)))
    pkt = bytes(pkt)
    enc = _tea_pkt(pkt, _CK_TEA) + struct.pack('>I', _cksum(pkt))
    enc = bytes(a ^ _CK_XOR[i & 15] for i, a in enumerate(enc))
    b64 = base64.b64encode(enc).decode().replace('+', '_').replace('/', '-').rstrip('=')
    return {'cKey': '--01' + b64, 'guid': guid, 'ts': ts,
            'flowId': '%s_%d' % (uuid.uuid4().hex.upper(), _CK_PLATFORM)}


_BK_H264 = base64.b64encode(b'H(30:1080,60:1080|30:1080,60:1080)').decode()


def bk_playurls(channel_id, live_pid, defn='fhd'):
    t = _ckey(channel_id)
    q = urllib.parse.urlencode({
        'atime': '120', 'livepid': live_pid, 'cnlid': channel_id,
        'appVer': _CK_APPVER, 'app_version': '300090', 'caplv': '1', 'cmd': '2',
        'defn': defn, 'device': 'iPhone', 'encryptVer': '4.2', 'getpreviewinfo': '0',
        'hevclv': '0', 'lang': 'zh-Hans_CN', 'livequeue': '0', 'logintype': '1',
        'nettype': '1', 'newnettype': '1', 'newplatform': str(_CK_PLATFORM),
        'platform': str(_CK_PLATFORM), 'sdtfrom': 'v3021', 'spacode': '23',
        'spaudio': '1', 'spdemuxer': '6', 'spdrm': '2', 'spdynamicrange': '1',
        'spflv': '1', 'spflvaudio': '1', 'sphdrfps': '60', 'sphttps': '1',
        'spvcode': _BK_H264, 'spvideo': '4', 'stream': '1', 'system': '1',
        'sysver': 'ios18.2.1', 'uhd_flag': '0', 'cKey': t['cKey'], 'guid': t['guid'],
        'fntick': str(t['ts']), 'flowid': t['flowId'], 'playbacktime': '0',
    })
    st, body, _ = _http('GET', 'https://bkliveinfo.ysp.cctv.cn/?' + q,
                        {'User-Agent': 'qqlive', 'Accept': 'application/json'}, None, HTTP_TIMEOUT)
    if st < 200 or st >= 300:
        raise RuntimeError('bk HTTP %d' % st)
    p = json.loads(body.decode('utf-8', 'replace'))
    if int(p.get('iretcode', -1)) != 0:
        raise RuntimeError('iretcode=%s %s' % (p.get('iretcode'), p.get('errinfo', '')))
    urls = []
    if p.get('playurl'): urls.append(p['playurl'])
    bu = p.get('backurl_list') or p.get('backurlList') or p.get('backurl')
    if isinstance(bu, list):
        for it in bu: urls.append(it if isinstance(it, str) else (it.get('url') or it.get('playurl') or ''))
    elif isinstance(bu, str):
        urls += [x for x in re.split(r'[;,]', bu) if x.strip()]
    urls = [u for u in dict.fromkeys(urls) if u and '.cctv.' in u]
    if not urls: raise RuntimeError('no playurl')
    urls.sort(key=lambda u: (0 if 'bklive-' in u else 1, u))
    return urls


# ================================================================ 频道表

CHANNELS = [
    ('cctv1',     'CCTV-1 综合',         '2024078201', '600001859', 'fhd'),
    ('cctv2',     'CCTV-2 财经',         '2024075401', '600001800', 'fhd'),
    ('cctv3',     'CCTV-3 综艺',         '2024068501', '600001801', 'fhd'),
    ('cctv4',     'CCTV-4 中文国际',       '2029797101', '600001814', 'fhd'),
    ('cctv5',     'CCTV-5 体育',         '2024078401', '600001818', 'fhd'),
    ('cctv5p',    'CCTV-5+ 体育赛事',      '2024078001', '600001817', 'fhd'),
    ('cctv6',     'CCTV-6 电影',         '2013693901', '600108442', 'fhd'),
    ('cctv7',     'CCTV-7 国防军事',       '2024072001', '600004092', 'fhd'),
    ('cctv8',     'CCTV-8 电视剧',        '2029793001', '600001803', 'fhd'),
    ('cctv9',     'CCTV-9 纪录',         '2024078601', '600004078', 'fhd'),
    ('cctv10',    'CCTV-10 科教',        '2024078701', '600001805', 'fhd'),
    ('cctv11',    'CCTV-11 戏曲',        '2027248701', '600001806', 'fhd'),
    ('cctv12',    'CCTV-12 社会与法',      '2027248801', '600001807', 'fhd'),
    ('cctv13',    'CCTV-13 新闻',        '2029797201', '600001811', 'fhd'),
    ('cctv14',    'CCTV-14 少儿',        '2027248901', '600001809', 'fhd'),
    ('cctv15',    'CCTV-15 音乐',        '2027249001', '600001815', 'fhd'),
    ('cctv16',    'CCTV-16 奥林匹克',      '2027249101', '600098637', 'fhd'),
    ('cctv17',    'CCTV-17 农业农村',      '2027249401', '600001810', 'fhd'),
    ('cctv4k',    'CCTV-4K 超高清',       '2029810301', '600002264', 'fhd'),
    ('cctv8k',    'CCTV-8K 超高清',       '2026774101', '600156816', 'fhd'),
    ('cctv164k',  'CCTV-16 4K',        '2027249301', '600099502', 'fhd'),
    ('cgtn',      'CGTN 英语',           '2024181701', '600014550', 'fhd'),
    ('cgtnfr',    'CGTN 法语',           '2024181801', '600084704', 'fhd'),
    ('cgtnru',    'CGTN 俄语',           '2024181901', '600084758', 'fhd'),
    ('cgtnar',    'CGTN 阿拉伯语',         '2024182001', '600084782', 'fhd'),
    ('cgtnes',    'CGTN 西班牙语',         '2024182101', '600084744', 'fhd'),
    ('cgtndoc',   'CGTN 纪录',           '2024182301', '600084781', 'fhd'),
    ('cctvfyjc',  'CCTV 风云剧场',         '2025637103', '600099658', 'shd'),
    ('cctvdyjc',  'CCTV 第一剧场',         '2026874203', '600099655', 'shd'),
    ('cctvhjjc',  'CCTV 怀旧剧场',         '2026874303', '600099620', 'shd'),
    ('bjws',      '北京卫视',              '2024052703', '600002309', 'fhd'),
    ('jsws',      '江苏卫视',              '2024171103', '600002521', 'fhd'),
    ('dfws',      '东方卫视',              '2024054503', '600002483', 'fhd'),
    ('zjws',      '浙江卫视',              '2024054703', '600002520', 'fhd'),
    ('hnws',      '湖南卫视',              '2024054803', '600002475', 'fhd'),
    ('hbws',      '湖北卫视',              '2024171203', '600002508', 'fhd'),
    ('gdws',      '广东卫视',              '2024060903', '600002485', 'fhd'),
    ('gxws',      '广西卫视',              '2024060703', '600002509', 'fhd'),
    ('hljws',     '黑龙江卫视',             '2029797003', '600002498', 'fhd'),
    ('hainanws',  '海南卫视',              '2024055603', '600002506', 'fhd'),
    ('cqws',      '重庆卫视',              '2024061103', '600002531', 'fhd'),
    ('szws',      '深圳卫视',              '2024061303', '600002481', 'fhd'),
    ('scws',      '四川卫视',              '2024061403', '600002516', 'fhd'),
    ('henanws',   '河南卫视',              '2029797303', '600002525', 'fhd'),
    ('dnws',      '东南卫视',              '2024061503', '600002484', 'fhd'),
    ('gzws',      '贵州卫视',              '2024061603', '600002490', 'fhd'),
    ('jxws',      '江西卫视',              '2024061703', '600002503', 'fhd'),
    ('lnws',      '辽宁卫视',              '2024171303', '600002505', 'fhd'),
    ('ahws',      '安徽卫视',              '2024171403', '600002532', 'fhd'),
    ('hebws',     '河北卫视',              '2024171503', '600002493', 'fhd'),
    ('sdws',      '山东卫视',              '2029787903', '600002513', 'fhd'),
    ('tjws',      '天津卫视',              '2019927003', '600152137', 'fhd'),
    ('jlws',      '吉林卫视',              '2025561503', '600190405', 'fhd'),
    ('saxws',     '陕西卫视',              '2029795103', '600190400', 'fhd'),
    ('nxws',      '宁夏卫视',              '2025608503', '600190737', 'fhd'),
    ('nmgws',     '内蒙古卫视',             '2025561203', '600190401', 'fhd'),
    ('ynws',      '云南卫视',              '2025561303', '600190402', 'fhd'),
    ('shanxiws',  '山西卫视',              '2025560803', '600190407', 'fhd'),
    ('qhws',      '青海卫视',              '2025559103', '600190406', 'fhd'),
    ('xizangws',  '西藏卫视',              '2025558003', '600190403', 'fhd'),
    ('xjws',      '新疆卫视',              '2019927403', '600152138', 'fhd'),
    ('cetv1',     'CETV-1',            '2022823801', '600171827', 'fhd'),
    ('guoxue',    '国学频道',              '2029360403', '600213139', 'fhd'),
]

CHANNEL_MAP = {c[0]: {'slug': c[0], 'name': c[1], 'sid': c[2], 'pid': c[3], 'defn': c[4]} for c in CHANNELS}

FORCE_BK = {'cctv11', 'cctv12', 'cctv14', 'cctv15', 'cctv16', 'cctv164k',
            'cctv17', 'cctv4k', 'cctvfyjc', 'cctvdyjc', 'cctvhjjc'}

BACKEND_CHANNELS = {
    'cctv1', 'cctv2', 'cctv3', 'cctv4', 'cctv5', 'cctv5p',
    'cctv7', 'cctv8', 'cctv9', 'cctv10', 'cctv11', 'cctv12',
    'cctv13', 'cctv14', 'cctv15', 'cctv16', 'cctv17',
    'cctv4k', 'cctv8k', 'cctv164k',
    'cgtn', 'cgtnfr', 'cgtnru', 'cgtnar', 'cgtnes', 'cgtndoc',
}

TRUE_4K_CHANNELS = {'cctv4k', 'cctv8k', 'cctv164k'}


def _has_native(slug):
    info = CHANNEL_MAP.get(slug, {})
    return bool(info.get('sid')) and bool(info.get('pid'))


# ================================================================ 台标

LOGO_MIRRORS = [
    'https://cdn.jsdmirror.com/gh/fanmingming/live@main/tv/',
    'https://jsd.onmicrosoft.cn/gh/fanmingming/live@main/tv/',
    'https://gcore.jsdelivr.net/gh/fanmingming/live@main/tv/',
    'https://cdn.jsdelivr.net/gh/fanmingming/live@main/tv/',
    'https://ghproxy.net/https://raw.githubusercontent.com/fanmingming/live/main/tv/',
    'https://live.fanmingming.com/tv/',
]
LOGO_PROBE_FILE = 'CCTV1.png'
LOGO_TIMEOUT = 8
LOGO_MODE = 'auto'

_LOGO_BASE = LOGO_MIRRORS[0]
_LOGO_DONE = threading.Event()
_LOGO_START_LOCK = threading.Lock()
_LOGO_STARTED = False
_LOGO_CACHE = {}
_LOGO_CACHE_LOCK = threading.Lock()

_LOGO_PLACEHOLDER = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
)

_LOGO_OVERRIDE = {
    'cctv5p': 'CCTV5+.png', 'cctv4k': 'CCTV4K.png', 'cctv8k': 'CCTV8K.png',
    'cctv164k': 'CCTV16.png',
    'cgtn': 'CGTN.png',
    'cgtnfr': 'CGTN法语.png', 'cgtnru': 'CGTN俄语.png',
    'cgtnar': 'CGTN阿语.png', 'cgtnes': 'CGTN西语.png', 'cgtndoc': 'CGTN纪录.png',
    'cctvfyjc': '风云剧场.png', 'cctvdyjc': '第一剧场.png', 'cctvhjjc': '怀旧剧场.png',
    'cetv1': 'CETV1.png', 'guoxue': '国学.png',
}


def _logo_file(slug, name=''):
    if slug in _LOGO_OVERRIDE: return _LOGO_OVERRIDE[slug]
    m = re.match(r'^cctv(\d+)$', slug)
    if m: return 'CCTV%s.png' % m.group(1)
    if name and slug.endswith('ws'): return name + '.png'
    return ''


def _probe_logo_source():
    global _LOGO_BASE
    try:
        for base in LOGO_MIRRORS:
            try:
                st, head, _ = _http('GET', base + LOGO_PROBE_FILE,
                                    {'User-Agent': UA, 'Referer': 'https://live.cctv.cn/'}, None, LOGO_TIMEOUT)
                if st >= 200 and st < 300 and head[:4] == b'\x89PNG':
                    _LOGO_BASE = base; return
            except Exception: continue
        _LOGO_BASE = ''
    finally: _LOGO_DONE.set()


def _ensure_logo_source(wait=3.0):
    global _LOGO_STARTED
    with _LOGO_START_LOCK:
        if not _LOGO_STARTED:
            _LOGO_STARTED = True
            threading.Thread(target=_probe_logo_source, daemon=True).start()
    _LOGO_DONE.wait(wait)
    return _LOGO_BASE


def _logo_url(slug, name=''):
    # 台标只给 CDN 直连地址；拿不到就返回空，由 Spider._logo 决定要不要走代理兜底
    _ensure_logo_source(wait=0)
    fname = _logo_file(slug, name)
    base = _LOGO_BASE
    if not (base and fname):
        return ''
    return base + urllib.parse.quote(fname)


def _fetch_logo_bytes(slug, name):
    fname = _logo_file(slug, name)
    if fname:
        bases = ([_LOGO_BASE] if _LOGO_BASE else []) + [b for b in LOGO_MIRRORS if b != _LOGO_BASE]
        q = urllib.parse.quote(fname)
        for base in bases:
            try:
                st, data, _ = _http('GET', base + q,
                                    {'User-Agent': UA, 'Referer': 'https://live.cctv.cn/'}, None, LOGO_TIMEOUT)
                if st >= 200 and st < 300 and data[:4] == b'\x89PNG': return data
            except Exception: continue
    return _LOGO_PLACEHOLDER


# ================================================================ 活流状态

class _ChannelState:
    def __init__(self, slug, name, sid, pid, defn, mode):
        self.slug = slug; self.name = name
        self.sid = sid; self.pid = pid; self.defn = defn
        self.lock = threading.Lock()
        self.segments = {}; self.order = deque(); self.seq = 0
        self.headers = {'User-Agent': UA}
        self.last_access = 0.0; self.thread = None
        self.last_error = ''
        self.mode = mode
        self._starting = False


CHANNEL_STATE = {}

for c in CHANNELS:
    slug, name, sid, pid, defn = c[0], c[1], c[2], c[3], c[4]
    if sid and pid:
        native_mode = 'bk' if slug in FORCE_BK else 'jce'
        CHANNEL_STATE[slug] = _ChannelState(slug, name, sid, pid, defn, native_mode)


def _seg_key(url, pdt):
    if pdt: return 'pdt:' + pdt
    p = urllib.parse.urlsplit(url)
    return p.scheme + '://' + p.netloc + p.path


def _append_segments(ch, segs):
    with ch.lock:
        for dur, pdt, url in segs:
            key = _seg_key(url, pdt)
            if key in ch.segments:
                ch.segments[key][3] = url
                continue
            ch.seq += 1
            ch.segments[key] = [ch.seq, dur, pdt, url]
            ch.order.append(key)
        while len(ch.order) > MAX_SEGS:
            ch.segments.pop(ch.order.popleft(), None)
        ch.last_error = ''


def _parse_m3u8(text, base_url):
    segs, dur, pdt = [], 6.0, ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            try: dur = float(line[len('#EXTINF:'):].split(',')[0])
            except ValueError: dur = 6.0
        elif line.startswith('#EXT-X-PROGRAM-DATE-TIME:'):
            pdt = line[len('#EXT-X-PROGRAM-DATE-TIME:'):]
        elif line and not line.startswith('#'):
            segs.append((dur, pdt, urllib.parse.urljoin(base_url, line)))
            pdt = ''
    return segs


def _jce_refresh(ch):
    ch.headers = {'User-Agent': UA}
    now = int(time.time())
    m3u8_url = jce_timeshift_url(ch.pid, ch.sid, now - WINDOW, now, ch.defn)
    st, body, _ = _http('GET', m3u8_url, {'User-Agent': UA}, None, HTTP_TIMEOUT)
    if st < 200 or st >= 300:
        raise RuntimeError('jce playlist HTTP %d' % st)
    text = body.decode('utf-8', 'replace')
    segs = _parse_m3u8(text, m3u8_url)
    if not segs: raise RuntimeError('empty playlist')
    _append_segments(ch, segs)
    return True


def _bk_refresh(ch):
    ch.headers = {'User-Agent': UA, 'Referer': 'https://live.cctv.cn/'}
    urls = bk_playurls(ch.sid, ch.pid, ch.defn)
    last_err = ''
    for u in urls:
        try:
            hb = {'User-Agent': UA, 'Referer': 'https://live.cctv.cn/',
                  'Accept': 'application/vnd.apple.mpegurl,application/json,*/*'}
            st, body, _ = _http('GET', u, hb, None, HTTP_TIMEOUT)
            if st < 200 or st >= 300:
                raise RuntimeError('bk playlist HTTP %d' % st)
            text = body.decode('utf-8', 'replace'); final = u
            lines = text.splitlines()
            for i, ln in enumerate(lines):
                if ln.strip().startswith('#EXT-X-STREAM-INF'):
                    for j in range(i + 1, len(lines)):
                        s = lines[j].strip()
                        if s and not s.startswith('#'):
                            sub = urllib.parse.urljoin(final, s)
                            st2, body2, _ = _http('GET', sub, {'User-Agent': UA}, None, HTTP_TIMEOUT)
                            if st2 < 200 or st2 >= 300:
                                raise RuntimeError('bk variant HTTP %d' % st2)
                            text = body2.decode('utf-8', 'replace'); final = sub
                            break
                    break
            segs = _parse_m3u8(text, final)
            if segs:
                _append_segments(ch, segs)
                return True
        except Exception as e:
            last_err = '%s: %s' % (type(e).__name__, e); continue
    raise RuntimeError(last_err or 'bk playlist failed')


def _refresh_native(ch):
    if ch.mode == 'bk':
        try: return _bk_refresh(ch)
        except Exception as e:
            _log('%s bk failed (%s), fallback jce' % (ch.slug, e))
            ch.mode = 'jce'
            return _jce_refresh(ch)
    try:
        return _jce_refresh(ch)
    except DeadHostError:
        ch.mode = 'bk'
        return _bk_refresh(ch)


def _refresh_once(ch):
    t0 = time.time()
    try:
        ok = _refresh_native(ch)
        _log('refresh %s: ok=%s %.2fs segs=%d'
             % (ch.slug, ok, time.time() - t0, len(ch.order)))
        return ok
    except Exception as e:
        ch.last_error = ('%s: %s' % (type(e).__name__, e))[:120]
        _log('refresh %s: FAIL %.2fs %s'
             % (ch.slug, time.time() - t0, ch.last_error))
        return False


def _refresh_loop(ch):
    fails = 0
    while time.time() - ch.last_access < IDLE_TIMEOUT:
        ok = _refresh_once(ch)
        fails = 0 if ok else fails + 1
        time.sleep(REFRESH_INTERVAL if fails < 3 else 15)


def _ensure_channel(ch):
    ch.last_access = time.time()
    with ch.lock:
        if ch._starting: return
        need_fetch = not ch.segments
        need_thread = ch.thread is None or not ch.thread.is_alive()
        if need_fetch or need_thread: ch._starting = True
        else: return
    try:
        if need_fetch: _refresh_once(ch)
        if need_thread:
            ch.thread = threading.Thread(target=_refresh_loop, args=(ch,), daemon=True)
            ch.thread.start()
    finally:
        with ch.lock: ch._starting = False


class _Resp(object):

    __slots__ = ("status", "content", "headers")

    def __init__(self, status, content, headers):
        self.status = status
        self.content = content
        self.headers = headers


def _gunzip(content, headers):
    if not content:
        return content
    encoding = ""
    for key, value in (headers or {}).items():
        if str(key).lower() == "content-encoding":
            encoding = str(value).lower()
    if content[:2] == b"\x1f\x8b" or "gzip" in encoding:
        try:
            return gzip.decompress(content)
        except (OSError, ValueError, EOFError):
            return content
    return content


class _Net(object):
    """容器无关的网络层。

    GET 优先借容器的 self.fetch()，POST 和一切失败情形回落到 urllib；
    内置 Python 常缺 CA 证书，SSL 校验失败时自动降级重试一次。
    """

    def __init__(self):
        self.spider = None
        self.fetch_broken = False

    def bind(self, spider):
        self.spider = spider

    # ---- 容器 fetch ----
    def _via_fetch(self, url, headers, timeout):
        if self.spider is None or self.fetch_broken or DIRECT:
            return None
        fn = getattr(self.spider, "fetch", None)
        if not callable(fn):
            return None
        try:
            response = fn(url, headers=headers, timeout=timeout)
        except TypeError:
            try:
                response = fn(url, headers=headers)
            except Exception:
                return None
        except Exception:
            return None
        if response is None:
            return None
        if isinstance(response, str):
            return _Resp(200, response.encode("utf-8"), {})
        if isinstance(response, dict):
            body = response.get("content")
            if body is None:
                body = response.get("body")
            if body is None:
                body = response.get("text") or ""
            if isinstance(body, str):
                body = body.encode("utf-8")
            return _Resp(int(response.get("code") or response.get("status") or 200),
                         bytes(body), response.get("headers") or {})
        status = getattr(response, "status_code", None)
        if status is None:
            status = getattr(response, "status", None)
        if status is None:
            self.fetch_broken = True
            return None
        content = getattr(response, "content", None)
        if content is None:
            content = (getattr(response, "text", "") or "").encode("utf-8")
        raw = getattr(response, "headers", None) or {}
        try:
            raw = dict(raw)
        except (TypeError, ValueError):
            raw = {}
        return _Resp(int(status), bytes(content), raw)

    # ---- urllib ----
    def _via_urllib(self, method, url, headers, body, timeout, unverified):
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        context = ssl.create_default_context()
        if unverified:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(request, timeout=timeout, context=context) as stream:
            return _Resp(stream.status, stream.read(), dict(stream.headers))

    @staticmethod
    def _http_error(error):
        body = b""
        try:
            body = error.read()
        except Exception:
            pass
        headers = {}
        try:
            headers = dict(error.headers or {})
        except (TypeError, ValueError):
            headers = {}
        return error.code, _gunzip(body, headers), headers

    def request(self, method, url, headers=None, body=None, timeout=15):
        headers = dict(headers or {})
        headers.setdefault("User-Agent", UA)
        if "Accept-Encoding" not in headers:
            headers["Accept-Encoding"] = "identity"
        if method == "GET" and body is None:
            try:
                response = self._via_fetch(url, headers, timeout)
            except Exception:
                response = None
            if response is not None:
                return response.status, _gunzip(response.content, response.headers), response.headers
        try:
            response = self._via_urllib(method, url, headers, body, timeout, False)
            return response.status, _gunzip(response.content, response.headers), response.headers
        except urllib.error.HTTPError as error:
            return self._http_error(error)
        except ssl.SSLError:
            try:
                response = self._via_urllib(method, url, headers, body, timeout, True)
                return response.status, _gunzip(response.content, response.headers), response.headers
            except urllib.error.HTTPError as error:
                return self._http_error(error)
            except Exception as error:
                return 599, ("%s(SSL降级): %s" % (type(error).__name__, error)).encode("utf-8"), {}
        except Exception as error:
            return 599, ("%s: %s" % (type(error).__name__, error)).encode("utf-8"), {}


DIRECT = False
_NET = _Net()


def _http(method, url, headers=None, body=None, timeout=15):
    """统一 HTTP 出口，返回 (status, bytes, headers)。"""
    return _NET.request(method, url, headers, body, timeout)


def _one(value):
    """localProxy 的参数值可能是 str 或 list，统一取第一个。"""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return "" if value is None else str(value)


def _safe(value):
    """M3U 属性里不能出现双引号。"""
    return str(value).replace('"', "'")


# ================================================================ 分类 / EPG

GROUP_NAMES = {
    "cctv": "央视频道", "satellite": "卫视频道", "cgtn": "CGTN",
    "4k": "4K超清", "premium": "付费剧场", "other": "其他",
}

EPG_XML_URL = "https://epg.112114.xyz/pp.xml"

# tvg-id 默认按主流 XMLTV 源（fanmingming / 112114）的习惯命名
EPG_IDS = {
    "cctv5p": "CCTV5+", "cctv4k": "CCTV4K", "cctv8k": "CCTV8K",
    "cctv164k": "CCTV16",
    "cgtn": "CGTN",
    "cgtnfr": "CGTN法语", "cgtnru": "CGTN俄语",
    "cgtnar": "CGTN阿语", "cgtnes": "CGTN西语", "cgtndoc": "CGTN纪录",
    "cctvfyjc": "风云剧场", "cctvdyjc": "第一剧场", "cctvhjjc": "怀旧剧场",
    "cetv1": "CETV1", "guoxue": "国学",
}


def _epg_id(slug, name=""):
    if slug in EPG_IDS:
        return EPG_IDS[slug]
    matched = re.match(r"^cctv(\d+)$", slug)
    if matched:
        return "CCTV%s" % matched.group(1)
    return name or slug


def _classify(slug):
    cats = []
    if (re.match(r"^cctv\d+$", slug) or slug == "cctv5p") and slug not in TRUE_4K_CHANNELS:
        cats.append("cctv")
    if slug in TRUE_4K_CHANNELS:
        cats.append("4k")
    if slug in ("cctvfyjc", "cctvdyjc", "cctvhjjc"):
        cats.append("premium")
    if slug.endswith("ws") or slug == "cetv1":
        cats.append("satellite")
    if slug.startswith("cgtn"):
        cats.append("cgtn")
    if slug == "guoxue":
        cats.append("other")
    return cats


def _group_name(slug):
    cats = _classify(slug)
    return GROUP_NAMES.get(cats[0], "其他") if cats else "其他"


def _upstream_url(ch):
    """拿到官方可直接播放的 m3u8 地址（不改切片、不经过代理）。

    bk 优先取回源列表第一条，取不到再试 JCE；两个都失败返回空，由调用方退回代理滚动缓冲。
    """
    if not (ch.sid and ch.pid):
        return ''
    now = int(time.time())
    for mode in (('bk', 'jce') if ch.mode == 'bk' else ('jce', 'bk')):
        try:
            if mode == 'bk':
                urls = bk_playurls(ch.sid, ch.pid, ch.defn)
                for u in urls:
                    if u:
                        return u
            else:
                return jce_timeshift_url(ch.pid, ch.sid, now - WINDOW, now, ch.defn)
        except Exception as error:
            _log('%s upstream %s failed: %s' % (ch.slug, mode, error))
    return ''


def _start_channel(ch):
    """后台起刷新线程，立刻返回，不阻塞当前请求。"""
    ch.last_access = time.time()
    thread = threading.Thread(target=_ensure_channel, args=(ch,), daemon=True)
    thread.start()
    return thread


# ================================================================ Spider

class Spider(SpiderBase):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.brandActor = "📺 央视频直播"
        self.brandDirector = "ysp-live-multi"
        self.epg_xml = EPG_XML_URL
        self.epg_ids = {}
        self.logo_mode = "direct"
        self.wait = 12.0
        self.live_mode = "proxy"

    # ---------------- 生命周期 ----------------
    def getName(self):
        return "央视频"

    def getDependence(self):
        # 单源版只用标准库（urllib / struct / gzip），不依赖 pycryptodome、cryptography
        return []

    def init(self, extend=""):
        global DIRECT
        opts = {}
        if isinstance(extend, dict):
            opts = extend
        elif isinstance(extend, str) and extend.strip().startswith("{"):
            try:
                opts = json.loads(extend)
            except ValueError:
                opts = {}
        self.epg_xml = str(opts.get("epg_xml", EPG_XML_URL) or "")
        if isinstance(opts.get("epg_ids"), dict):
            self.epg_ids = {str(k): str(v) for k, v in opts["epg_ids"].items()}
        self.logo_mode = str(opts.get("logo_mode") or "direct").lower()
        self.live_mode = str(opts.get("live_mode") or "proxy").lower()
        DIRECT = bool(opts.get("direct", False))
        try:
            self.wait = max(3.0, float(opts.get("wait") or 12))
        except (TypeError, ValueError):
            self.wait = 12.0
        _NET.bind(self)
        try:
            _ensure_logo_source(wait=0)
        except Exception:
            pass
        return True

    def destroy(self):
        for ch in CHANNEL_STATE.values():
            ch.last_access = 0.0

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    # ---------------- 入口 ----------------
    def homeContent(self, filter):
        classes = [{"type_id": "all", "type_name": "全部频道"}]
        for key, name in (("cctv", "央视频道"), ("satellite", "卫视频道"),
                          ("cgtn", "CGTN"), ("4k", "4K超清"),
                          ("premium", "付费剧场"), ("other", "其他")):
            classes.append({"type_id": key, "type_name": name})
        return {"class": classes, "filters": {}, "list": self._cards("all")}

    def homeVideoContent(self):
        return {"list": self._cards("all")}

    def categoryContent(self, tid, pg, filter, extend):
        cards = self._cards(tid or "all")
        return {"page": 1, "pagecount": 1, "limit": len(cards), "total": len(cards), "list": cards}

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        slug = _one(raw).strip()
        base = slug
        info = CHANNEL_MAP.get(base)
        if not info:
            return {"list": []}
        self._warm(base)
        lines_1 = ["超清$%s" % base]
        parts_from, parts_url = [], []
        if lines_1:
            parts_from.append("央视频源1")
            parts_url.append("#".join(lines_1))
        desc = "【📺 央视频直播】\n频道: %s\n源1: JCE/bk" % info["name"]
        desc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return {"list": [{
            "vod_id": slug, "vod_name": info["name"],
            "vod_pic": self._logo(base, info["name"]),
            "vod_actor": self.brandActor, "vod_director": self.brandDirector,
            "vod_remarks": "央视频 | 直播",
            "vod_content": desc,
            "vod_play_from": "$$$".join(parts_from),
            "vod_play_url": "$$$".join(parts_url),
        }]}

    def searchContent(self, key, quick, pg="1"):
        keyword = (key or "").strip().lower()
        cards = []
        if keyword:
            for slug, name, _s, _p, _d in CHANNELS:
                if keyword in name.lower() or keyword in slug.lower():
                    cards.append(self._card(slug, name))
        return {"page": 1, "pagecount": 1, "limit": len(cards), "total": len(cards), "list": cards}

    def playerContent(self, flag, id, vipFlags):
        slug = _one(id).strip()
        if slug.startswith("http://") or slug.startswith("https://"):
            return {"parse": 0, "playUrl": "", "url": slug,
                    "header": {"User-Agent": UA, "Referer": "https://live.cctv.cn/"}}
        ch = CHANNEL_STATE.get(slug)
        if ch is None:
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        self._warm(slug)
        return {
            "parse": 0, "playUrl": "",
            "url": self._purl(slug=slug),
            "header": {"User-Agent": UA, "Referer": "https://live.cctv.cn/"},
        }

    # ---------------- 直播源 M3U ----------------
    def liveContent(self, url=""):
        if self.epg_xml:
            lines = ['#EXTM3U tvg-url="%s" x-tvg-url="%s"' % (self.epg_xml, self.epg_xml)]
        else:
            lines = ["#EXTM3U"]
        for slug, name, _sid, _pid, _defn in CHANNELS:
            lines.append(self._m3u_entry(slug, name))
            lines.append(self._play_url(slug))
        return "\n".join(lines) + "\n"

    def _play_url(self, slug):
        if self.live_mode == "redirect":
            return self._purl(slug=slug, mode="redirect")
        return self._purl(slug=slug)

    def _m3u_entry(self, slug, name, epg_slug=""):
        source = epg_slug or slug
        tvg = _safe(self.epg_ids.get(source) or _epg_id(source, name))
        return '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s' % (
            tvg, tvg, self._logo(slug, name), _safe(_group_name(slug)), _safe(name))

    # ---------------- 本地代理（取代本地 HTTP 服务） ----------------
    def localProxy(self, param):
        try:
            query = {}
            for key, value in (param or {}).items():
                query[str(key)] = _one(value)
            kind = query.get("type", "")
            if kind == "diag":
                return [200, "text/plain; charset=utf-8",
                        self._diag(query.get("slug"), query.get("mode"))]
            if kind == "logo":
                return self._logo_bytes(query.get("slug", ""))
            slug = query.get("slug") or query.get("id") or ""
            ch = CHANNEL_STATE.get(slug)
            if ch is None:
                return [404, "text/plain; charset=utf-8", "央视频: 未知频道 " + slug]
            if query.get("seq"):
                return self._chunk(ch, query["seq"])
            want_redirect = self.live_mode == "redirect"
            if query.get("mode") == "redirect":
                want_redirect = True
            elif query.get("mode") == "proxy":
                want_redirect = False
            if want_redirect:
                direct = _upstream_url(ch)
                if direct:
                    return [302, "text/plain", "",
                            {"Location": direct, "Cache-Control": "no-store"}]
            return self._playlist(ch)
        except Exception as error:
            return [502, "text/plain; charset=utf-8",
                    "央视频: %s: %s" % (type(error).__name__, error)]

    def _playlist(self, ch):
        """返回滚动播放列表。

        直播没有详情页可以预热，所以这里不再同步等握手：后台起刷新线程，
        最多等 self.wait 秒拿到首帧后就吐出滚动窗口（取不到就等代理线程补上）。
        """
        ch.last_access = time.time()
        candidates = [ch]
        with ch.lock:
            ready = bool(ch.order)
        if not ready:
            _start_channel(ch)
        owner = self._first_ready(candidates, self.wait)
        if owner is None:
            detail = " | ".join("%s:%s" % (c.slug, c.last_error or "超时")
                                for c in candidates)
            return [503, "text/plain; charset=utf-8", "央视频: 暂无数据 " + detail]
        return self._render(owner)

    def _first_ready(self, channels, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for ch in channels:
                with ch.lock:
                    if ch.order:
                        return ch
            time.sleep(0.15)
        for ch in channels:
            with ch.lock:
                if ch.order:
                    return ch
        return None

    def _render(self, ch):
        with ch.lock:
            keys = list(ch.order)
            segs = [ch.segments[k] for k in keys if k in ch.segments]
            window = segs[-PLAYLIST_WINDOW:] if segs else []
        if not window:
            return [503, "text/plain; charset=utf-8",
                    "央视频: 暂无数据 %s" % (ch.last_error or "抓取中")]
        ch.last_access = time.time()
        target = max(6, int(max(seg[1] for seg in window) + 0.5))
        out = ["#EXTM3U", "#EXT-X-VERSION:3",
               "#EXT-X-TARGETDURATION:%d" % target,
               "#EXT-X-MEDIA-SEQUENCE:%d" % window[0][0],
               "#EXT-X-DISCONTINUITY-SEQUENCE:0",
               "#EXT-X-START:TIME-OFFSET=-15.0"]
        for seq, dur, pdt, _url in window:
            if pdt:
                out.append("#EXT-X-PROGRAM-DATE-TIME:" + pdt)
            out.append("#EXTINF:%.3f," % dur)
            out.append(self._purl(slug=ch.slug, seq=seq))
        return [200, "application/vnd.apple.mpegurl", "\n".join(out) + "\n",
                {"Cache-Control": "no-cache, no-store"}]

    def _chunk(self, ch, raw_seq):
        try:
            seq = int(raw_seq)
        except (TypeError, ValueError):
            return [400, "text/plain; charset=utf-8", "央视频: bad seq"]
        ch.last_access = time.time()
        with ch.lock:
            url = None
            for key in ch.order:
                seg = ch.segments.get(key)
                if seg and seg[0] == seq:
                    url = seg[3]
                    break
        if not url:
            return [404, "text/plain; charset=utf-8", "央视频: 切片已过期"]
        status, body, _ = _http("GET", url, ch.headers or {"User-Agent": UA}, None, 20)
        if status < 200 or status >= 300 or not body:
            return [502, "text/plain; charset=utf-8", "央视频: 切片 HTTP %d" % status]
        return [200, "video/mp2t", body, {"Cache-Control": "no-cache, no-store"}]

    def _logo_bytes(self, slug):
        info = CHANNEL_MAP.get(slug) or {}
        with _LOGO_CACHE_LOCK:
            data = _LOGO_CACHE.get(slug)
        if data is None:
            data = _fetch_logo_bytes(slug, info.get("name", ""))
            with _LOGO_CACHE_LOCK:
                _LOGO_CACHE[slug] = data
        return [200, "image/png", data, {"Cache-Control": "public, max-age=86400"}]

    def _probe(self, slug, mode=""):
        """?type=diag&slug=cctv1 —— 当场拉一次，看看卡在哪个源。"""
        ch = CHANNEL_STATE.get(slug)
        if ch is None:
            return "未知频道: %s\n" % slug
        out = ["频道: %s  模式: %s" % (ch.slug, ch.mode)]
        if mode == "redirect" or (self.live_mode == "redirect" and mode != "proxy"):
            started = time.time()
            url = _upstream_url(ch)
            out.append("直连取址: %.2fs -> %s" % (time.time() - started, url or "(失败)"))
            if url:
                st, body, _ = _http("GET", url, {"User-Agent": UA}, None, HTTP_TIMEOUT)
                out.append("直连拉取: HTTP %d, %d 字节" % (st, len(body or b"")))
                out.append((body or b"").decode("utf-8", "replace")[:200].replace("\n", " | "))
        started = time.time()
        ok = _refresh_once(ch)
        with ch.lock:
            count = len(ch.order)
        out.append("代理取流: ok=%s %.2fs segs=%d err=%s"
                   % (ok, time.time() - started, count, ch.last_error))
        return "\n".join(out) + "\n"

    def _diag(self, slug="", mode=""):
        if slug:
            return self._probe(slug, mode)
        lines = ["net: %s" % ("urllib(直连)" if DIRECT else "容器fetch优先/urllib兜底"),
                 "logo源: %s" % (_LOGO_BASE or "(未探测到)"),
                 "频道总数: %d" % len(CHANNEL_STATE), ""]
        for slug in sorted(CHANNEL_STATE):
            ch = CHANNEL_STATE[slug]
            with ch.lock:
                count = len(ch.order)
            lines.append("%-14s mode=%-6s segs=%-4d err=%s" % (slug, ch.mode, count, ch.last_error))
        return "\n".join(lines) + "\n"

    # ---------------- 小工具 ----------------
    def _purl(self, **kw):
        # 容器不一定提供 getProxyUrl（本地直跑 / 老版本壳子），拿不到就退化成空串，
        # 由调用方走直连兜底，避免整站直接抛异常。
        try:
            base = (self.getProxyUrl() or "").strip()
        except Exception:
            base = ""
        if not base:
            return ""
        sep = "&" if "?" in base else "?"
        return base + sep + "&".join(
            "%s=%s" % (k, urllib.parse.quote(str(v), safe="")) for k, v in kw.items())

    def _warm(self, slug):
        """后台预热，真正等数据在代理返回播放列表时才做。"""
        ch = CHANNEL_STATE.get(slug)
        if ch is None:
            return
        ch.last_access = time.time()
        threading.Thread(target=_ensure_channel, args=(ch,), daemon=True).start()

    def _logo(self, slug, name=""):
        direct = _logo_url(slug, name)
        if self.logo_mode != "proxy":
            if direct:
                return direct
        proxied = self._purl(type="logo", slug=slug)
        return proxied or direct or ""

    def _card(self, slug, name=""):
        tag = ""
        if slug in TRUE_4K_CHANNELS:
            tag = "真4K"
        elif slug in BACKEND_CHANNELS:
            tag = "高码率"
        return {"vod_id": slug, "vod_name": name,
                "vod_pic": self._logo(slug, name),
                "vod_remarks": ("央视频 | %s" % tag) if tag else "央视频",
                "style": {"type": "rect", "ratio": 1.78}}

    def _cards(self, tid):
        out = []
        for slug, name, _s, _p, _d in CHANNELS:
            if tid in ("", "all") or tid in _classify(slug):
                out.append(self._card(slug, name))
        return out
