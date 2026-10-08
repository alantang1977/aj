# coding=utf-8
"""
ysp-fongmi.py — 央视频(CCTV/卫视)直播 · FongMi(影视TV) Python 插件
================================================================
把 ysp-live 那套"JCE 时移协议 + bkliveinfo/cKey 兜底 + 滑动窗口清单刷新"的逻辑，
搬进 FongMi 的 py 引擎里跑，不依赖电脑、不依赖任何外部二进制。

两种用法(同一个文件，可只用一种)：

1) 直播(推荐, 最像看电视)
   live 配置里：
   {
     "name": "央视频直播",
     "api": "./ysp-fongmi.py",
     "url": "ysp://all",
     "ua": "<UA 见文件里的 UA 常量>"
   }
   -> App 调 liveContent(url)，本插件吐出 M3U，每个频道指到插件内嵌的本地 HLS 代理。

2) 点播站点(分类/搜索/播放)
   sites 里：
   { "key": "ysp", "name": "央视频", "type": 3, "api": "./ysp-fongmi.py",
     "searchable": 1, "quickSearch": 1, "ext": {"port": 8899} }

频道台标(LOGO)：
   63 路全部带台标。央视/卫视用公开台标库的图(四个镜像轮着试, 谁通用谁),
   库里没有的 5 路(风云/第一/怀旧剧场、CCTV-8K、国学频道)是内嵌自绘的, 不联网。
   插件会把取到的图缓存到本地, 第二次起直接读缓存, 不重复下载。
   可以关或者改成直连, ext 里加：
     "logo": "local"  默认, 走插件(多镜像兜底+缓存), 最不容易出现空白图
     "logo": "remote" 播放器直接连公开台标库, 不占插件资源
     "logo": "off"    不要台标
     "logo_prefetch": false   不要开机预取(省流量, 图改成滑到哪拉到哪)

原理(为什么必须在 App 里再起一个本地端口)：
央视这套源给的是"时移 m3u8"，是有寿命的窗口，分片地址还会过期；
播放器自己不会续窗口。所以插件在 App 内起一个 127.0.0.1 上的极简 HTTP 服务，
每 10 秒刷新一次源清单、只保留贴近直播沿的 15 个分片，播放器反复拉这个本地
m3u8 就等于一直在看直播。视频分片本身由播放器直连央视 CDN，本地服务只发清单，
不转发视频流量。

只依赖 Python 标准库；不启动任何外部进程。
协议部分整理自用户提供的 ysp-live.py(原版里的 4K Rust 后端在 Android 上无法运行, 已移除,
4K/高码率那几路一律走 1080p)。
"""

import base64
import gzip
import json
import os
import random
import re
import socket
import struct
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import deque

try:
    sys.path.append('..')
except Exception:
    pass

_BaseSpider = object
try:
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = object


def _log(msg):
    try:
        print('[ysp] %s' % msg, flush=True)
    except Exception:
        pass


# ================================================================ JCE 协议

class W:
    def __init__(self):
        self.b = bytearray()

    def head(self, typ, tag):
        if tag < 15:
            self.b.append(((tag & 0xf) << 4) | (typ & 0xf))
        else:
            self.b.append(0xf0 | (typ & 0xf))
            self.b.append(tag)

    def byte(self, v, tag):
        v = int(v)
        if v == 0:
            self.head(12, tag)
        else:
            self.head(0, tag)
            self.b += struct.pack('>b', v)

    def short(self, v, tag):
        v = int(v)
        if -128 <= v <= 127:
            self.byte(v, tag)
        else:
            self.head(1, tag)
            self.b += struct.pack('>h', v)

    def int(self, v, tag):
        v = int(v)
        if -32768 <= v <= 32767:
            self.short(v, tag)
        else:
            self.head(2, tag)
            self.b += struct.pack('>i', v)

    def long(self, v, tag):
        v = int(v)
        if -2147483648 <= v <= 2147483647:
            self.int(v, tag)
        else:
            self.head(3, tag)
            self.b += struct.pack('>q', v)

    def float(self, v, tag):
        self.head(4, tag)
        self.b += struct.pack('>f', float(v))

    def double(self, v, tag):
        self.head(5, tag)
        self.b += struct.pack('>d', float(v))

    def string(self, s, tag):
        if s is None:
            return
        data = str(s).encode('utf-8')
        if len(data) > 255:
            self.head(7, tag)
            self.b += struct.pack('>i', len(data))
            self.b += data
        else:
            self.head(6, tag)
            self.b.append(len(data))
            self.b += data

    def bytes(self, data, tag):
        data = bytes(data)
        self.head(13, tag)
        self.head(0, 0)
        self.int(len(data), 0)
        self.b += data

    def struct(self, fn, tag):
        self.head(10, tag)
        fn(self)
        self.head(11, 0)

    def list(self, items, tag, wf):
        self.head(9, tag)
        self.int(len(items), 0)

    def out(self):
        return bytes(self.b)


class R:
    def __init__(self, data):
        self.d = memoryview(data)
        self.p = 0

    def rem(self):
        return len(self.d) - self.p

    def get(self, n):
        if self.p + n > len(self.d):
            raise EOFError
        b = self.d[self.p:self.p + n].tobytes()
        self.p += n
        return b

    def u8(self):
        return self.get(1)[0]

    def head(self):
        b = self.u8()
        typ = b & 0xf
        tag = (b & 0xf0) >> 4
        if tag == 15:
            tag = self.u8()
        return typ, tag

    def value(self, typ):
        if typ == 0:
            return struct.unpack('>b', self.get(1))[0]
        if typ == 1:
            return struct.unpack('>h', self.get(2))[0]
        if typ == 2:
            return struct.unpack('>i', self.get(4))[0]
        if typ == 3:
            return struct.unpack('>q', self.get(8))[0]
        if typ == 4:
            return struct.unpack('>f', self.get(4))[0]
        if typ == 5:
            return struct.unpack('>d', self.get(8))[0]
        if typ == 6:
            n = self.u8()
            return self.get(n).decode('utf-8', 'replace')
        if typ == 7:
            n = struct.unpack('>i', self.get(4))[0]
            return self.get(n).decode('utf-8', 'replace')
        if typ == 8:
            n = self._int()
            return {self._fv(): self._fv() for _ in range(n)}
        if typ == 9:
            n = self._int()
            return [self._fv() for _ in range(n)]
        if typ == 10:
            return self.struct()
        if typ == 11:
            return None
        if typ == 12:
            return 0
        if typ == 13:
            self.head()
            n = self._int()
            return self.get(n)
        raise ValueError('type %d' % typ)

    def _fv(self):
        t, _ = self.head()
        return self.value(t)

    def _int(self):
        t, _ = self.head()
        return int(self.value(t))

    def struct(self):
        m = {}
        while self.rem() > 0:
            t, tag = self.head()
            if t == 11:
                break
            m[tag] = self.value(t)
        return m


VER_NAME, VER_CODE = '3.2.7.26212', '302070'
APP_ID, QMF_APP_ID, QMF_PLATFORM, BIZ_ID = '1200013', 10012, 1, 0
CHAN_ID = '10070'
GUID = ''.join(random.choice('0123456789abcdef') for _ in range(32))


def _qua(w):
    w.string(VER_NAME, 0)
    w.string(VER_CODE, 1)
    w.int(1080, 2)
    w.int(2400, 3)
    w.int(3, 4)
    w.string('12', 5)
    w.int(1, 6)
    w.int(1, 7)
    w.int(420, 8)
    w.string(CHAN_ID, 9)
    for i in range(10, 15):
        w.string('', i)
    w.struct(lambda ww: (ww.int(0, 0), ww.byte(0, 1), ww.string('', 2)), 15)
    w.string('', 16)
    w.string('', 17)
    w.string('', 18)
    w.struct(lambda ww: (ww.int(0, 0), ww.float(0, 1), ww.float(0, 2), ww.double(0, 3)), 19)
    w.string(GUID[:16], 20)
    w.string('Pixel 6', 21)
    w.int(1, 22)
    for i in range(23, 27):
        w.int(0, i)
    w.string('', 27)
    w.string('', 28)
    w.string(GUID, 29)


def _head(w, cmd, reqid):
    w.int(reqid, 0)
    w.int(cmd, 1)
    w.struct(lambda ww: _qua(ww), 2)
    w.string(APP_ID, 3)
    w.string(GUID, 4)
    w.list([], 5, None)
    w.struct(lambda ww: None, 6)
    w.list([], 7, None)
    w.int(0, 8)
    w.int(0, 9)
    w.int(0, 10)


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
    g = GUID.encode()[:32]
    out += g + b'\x00' * (32 - len(g))
    out += struct.pack('>b', QMF_PLATFORM) + struct.pack('>i', int(VER_CODE)) + b'\x00' * 6
    out += bytes([0]) + struct.pack('>H', 0) + struct.pack('>H', 0)
    out += struct.pack('>i', len(inner)) + comp + bytes([3])
    struct.pack_into('>i', out, 1, len(out))
    return bytes(out)


def _unwrap(data):
    if data[:1] != b'\x13' or len(data) < 90:
        return None
    flags = struct.unpack('>i', data[21:25])[0]
    payload = data[89:-1]
    if flags & 2:
        payload = gzip.decompress(payload)
    if payload[:1] != b'&' or payload[-1:] != b'(':
        return None
    rc = R(payload[16:-1]).struct()
    return rc.get(1) or b''


class DeadHostError(RuntimeError):
    pass


def jce_timeshift_url(pid, sid, start, end, stream='fhd'):
    w = W()
    w.string(pid, 0)
    w.string(sid, 1)
    w.long(start, 2)
    w.long(end, 3)
    w.string(stream, 4)
    body = w.out()
    CMD = 25312
    reqid = int(time.time() * 1000) & 0x7fffffff
    packet = _wrap(CMD, body, reqid)
    req = urllib.request.Request('https://jacc.ysp.cctv.cn', data=packet, method='POST')
    req.add_header('Content-Type', 'application/octet-stream')
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
    resp_body = _unwrap(raw)
    if not resp_body:
        raise RuntimeError('bad response')
    m = R(resp_body).struct()
    err = m.get(0, 0)
    if err != 0:
        raise RuntimeError(m.get(1, 'errCode=%s' % err))
    url = m.get(2, '')
    if not url:
        raise RuntimeError('empty m3u8')
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


def _u32(v):
    return v & 0xFFFFFFFF


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
    for b in buf:
        v = (0x83 * v + b) & 0x7fffffff
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
        t = str(v)
        return t[-5:] if len(t) >= 5 else ''

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
    b64 = _b64url(enc)
    return {'cKey': '--01' + b64, 'guid': guid, 'ts': ts,
            'flowId': '%s_%d' % (uuid.uuid4().hex.upper(), _CK_PLATFORM)}


def _b64url(raw):
    return base64.b64encode(raw).decode().replace('+', '_').replace('/', '-').rstrip('=')


_BK_H264 = _b64url(b'H(30:1080,60:1080|30:1080,60:1080)')


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
    req = urllib.request.Request('https://bkliveinfo.ysp.cctv.cn/?' + q,
                                 headers={'User-Agent': 'qqlive', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        p = json.loads(r.read().decode())
    if int(p.get('iretcode', -1)) != 0:
        raise RuntimeError('iretcode=%s %s' % (p.get('iretcode'), p.get('errinfo', '')))
    urls = []
    if p.get('playurl'):
        urls.append(p['playurl'])
    bu = p.get('backurl_list') or p.get('backurlList') or p.get('backurl')
    if isinstance(bu, list):
        for it in bu:
            urls.append(it if isinstance(it, str) else (it.get('url') or it.get('playurl') or ''))
    elif isinstance(bu, str):
        urls += [x for x in re.split(r'[;,]', bu) if x.strip()]
    urls = [u for u in dict.fromkeys(urls) if u and '.cctv.' in u]
    if not urls:
        raise RuntimeError('no playurl')
    urls.sort(key=lambda u: (0 if 'bklive-' in u else 1, u))
    return urls


def fetch_abs_playlist(url, depth=0):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'qqlive', 'Referer': 'https://live.cctv.cn/',
        'Accept': 'application/vnd.apple.mpegurl,application/json,*/*'})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode('utf-8', 'replace')
        final = r.geturl()
    if depth < 2:
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if ln.strip().startswith('#EXT-X-STREAM-INF'):
                for j in range(i + 1, len(lines)):
                    s = lines[j].strip()
                    if s and not s.startswith('#'):
                        return fetch_abs_playlist(urllib.parse.urljoin(final, s), depth + 1)
                break
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s and not s.startswith('#'):
            out.append(urllib.parse.urljoin(final, s))
        else:
            out.append(ln)
    return '\n'.join(out)


# ================================================================ 频道表

CHANNELS = [
    ('cctv1', 'CCTV-1', '2024078201', '600001859', 'fhd'),
    ('cctv2', 'CCTV-2', '2024075401', '600001800', 'fhd'),
    ('cctv3', 'CCTV-3', '2024068501', '600001801', 'fhd'),
    ('cctv4', 'CCTV-4', '2029797101', '600001814', 'fhd'),
    ('cctv5', 'CCTV-5', '2024078401', '600001818', 'fhd'),
    ('cctv5p', 'CCTV-5+', '2024078001', '600001817', 'fhd'),
    ('cctv6', 'CCTV-6', '2013693901', '600108442', 'fhd'),
    ('cctv7', 'CCTV-7', '2024072001', '600004092', 'fhd'),
    ('cctv8', 'CCTV-8', '2029793001', '600001803', 'fhd'),
    ('cctv9', 'CCTV-9', '2024078601', '600004078', 'fhd'),
    ('cctv10', 'CCTV-10', '2024078701', '600001805', 'fhd'),
    ('cctv11', 'CCTV-11', '2027248701', '600001806', 'fhd'),
    ('cctv12', 'CCTV-12', '2027248801', '600001807', 'fhd'),
    ('cctv13', 'CCTV-13', '2029797201', '600001811', 'fhd'),
    ('cctv14', 'CCTV-14', '2027248901', '600001809', 'fhd'),
    ('cctv15', 'CCTV-15', '2027249001', '600001815', 'fhd'),
    ('cctv16', 'CCTV-16', '2027249101', '600098637', 'fhd'),
    ('cctv164k', 'CCTV-16 4K', '2027249301', '600099502', 'fhd'),
    ('cctv17', 'CCTV-17', '2027249401', '600001810', 'fhd'),
    ('cctv4k', 'CCTV-4K', '2029810301', '600002264', 'fhd'),
    ('cctv8k', 'CCTV-8K', '2026774101', '600156816', 'fhd'),
    ('cgtn', 'CGTN', '2024181701', '600014550', 'fhd'),
    ('cgtnfr', 'CGTN法语', '2024181801', '600084704', 'fhd'),
    ('cgtnru', 'CGTN俄语', '2024181901', '600084758', 'fhd'),
    ('cgtnar', 'CGTN阿拉伯语', '2024182001', '600084782', 'fhd'),
    ('cgtnes', 'CGTN西班牙语', '2024182101', '600084744', 'fhd'),
    ('cgtndoc', 'CGTN 纪录', '2024182301', '600084781', 'fhd'),
    ('cctvfyjc', 'CCTV 风云剧场', '2025637103', '600099658', 'shd'),
    ('cctvdyjc', 'CCTV 第一剧场', '2026874203', '600099655', 'shd'),
    ('cctvhjjc', 'CCTV 怀旧剧场', '2026874303', '600099620', 'shd'),
    ('bjws', '北京卫视', '2024052703', '600002309', 'fhd'),
    ('jsws', '江苏卫视', '2024171103', '600002521', 'fhd'),
    ('dfws', '东方卫视', '2024054503', '600002483', 'fhd'),
    ('zjws', '浙江卫视', '2024054703', '600002520', 'fhd'),
    ('hnws', '湖南卫视', '2024054803', '600002475', 'fhd'),
    ('hbws', '湖北卫视', '2024171203', '600002508', 'fhd'),
    ('gdws', '广东卫视', '2024060903', '600002485', 'fhd'),
    ('gxws', '广西卫视', '2024060703', '600002509', 'fhd'),
    ('hljws', '黑龙江卫视', '2029797003', '600002498', 'fhd'),
    ('hainanws', '海南卫视', '2024055603', '600002506', 'fhd'),
    ('cqws', '重庆卫视', '2024061103', '600002531', 'fhd'),
    ('szws', '深圳卫视', '2024061303', '600002481', 'fhd'),
    ('scws', '四川卫视', '2024061403', '600002516', 'fhd'),
    ('henanws', '河南卫视', '2029797303', '600002525', 'fhd'),
    ('dnws', '东南卫视', '2024061503', '600002484', 'fhd'),
    ('gzws', '贵州卫视', '2024061603', '600002490', 'fhd'),
    ('jxws', '江西卫视', '2024061703', '600002503', 'fhd'),
    ('lnws', '辽宁卫视', '2024171303', '600002505', 'fhd'),
    ('ahws', '安徽卫视', '2024171403', '600002532', 'fhd'),
    ('hebws', '河北卫视', '2024171503', '600002493', 'fhd'),
    ('sdws', '山东卫视', '2029787903', '600002513', 'fhd'),
    ('tjws', '天津卫视', '2019927003', '600152137', 'fhd'),
    ('jlws', '吉林卫视', '2025561503', '600190405', 'fhd'),
    ('saxws', '陕西卫视', '2029795103', '600190400', 'fhd'),
    ('nxws', '宁夏卫视', '2025608503', '600190737', 'fhd'),
    ('nmgws', '内蒙古卫视', '2025561203', '600190401', 'fhd'),
    ('ynws', '云南卫视', '2025561303', '600190402', 'fhd'),
    ('shanxiws', '山西卫视', '2025560803', '600190407', 'fhd'),
    ('qhws', '青海卫视', '2025559103', '600190406', 'fhd'),
    ('xizangws', '西藏卫视', '2025558003', '600190403', 'fhd'),
    ('xjws', '新疆卫视', '2019927403', '600152138', 'fhd'),
    ('cetv1', 'CETV-1', '2022823801', '600171827', 'fhd'),
    ('guoxue', '国学频道', '2029360403', '600213139', 'fhd'),
]

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'

REFRESH_INTERVAL = 10   # 清单刷新间隔(秒)
IDLE_TIMEOUT = 120      # 没人看就停刷
WINDOW = 300            # 每次向时移接口要的窗口(秒)
MAX_SEGS = 60           # 内存里最多保留多少分片
LIVE_WINDOW = 15        # 下发给播放器的分片数(贴近直播沿)
BK_URL_TTL = 300        # bkliveinfo 地址缓存时长(秒)

# 时移接口对这几个频道返回坏域名, 直接走 bkliveinfo
FORCE_BK = {'cctv11', 'cctv12', 'cctv14', 'cctv15', 'cctv16', 'cctv164k',
            'cctv17', 'cctv4k', 'cctvfyjc', 'cctvdyjc', 'cctvhjjc'}

GROUP_DEFS = [('cctv', '央视'), ('jc', '央视剧场'), ('cgtn', 'CGTN'), ('ws', '卫视'), ('other', '其他'),
              ('gz', '广州台'), ('gd', '广东台'), ('gdcity', '广东地市台'),
              ('hk', '香港台'), ('fh', '凤凰卫视')]
GROUP_NAMES = dict(GROUP_DEFS)
_GROUP_ID_BY_NAME = dict((name, gid) for gid, name in GROUP_DEFS)


def _group_of(slug):
    if slug.startswith('cgtn'):
        return 'cgtn'
    if slug.startswith('cctv'):
        return 'jc' if slug.endswith('jc') else 'cctv'
    if slug in ('cetv1', 'guoxue'):
        return 'other'
    return 'ws'


class Channel:
    def __init__(self, slug, name, sid, pid, defn):
        self.slug, self.name, self.sid, self.pid, self.defn = slug, name, sid, pid, defn
        self.lock = threading.Lock()
        self.segments = {}
        self.order = deque()
        self.seq = 0
        self.last_access = 0.0
        self.thread = None
        self.last_error = ''
        self.last_ok = 0.0
        self.mode = 'bk' if slug in FORCE_BK else 'jce'
        self.bk_urls = []
        self.bk_urls_time = 0.0
        self.bk_playlist = ''
        self._starting = False


CHANNEL_MAP = dict((c[0], Channel(*c)) for c in CHANNELS)
CHANNEL_ORDER = [c[0] for c in CHANNELS]


# ================================================================ 外部频道(广东/广州/香港/凤凰)
# 这几路不走央视 JCE/bkliveinfo, 也不需要本地滑动窗口代理:
# 它们是普通直播 HLS, 播放器直连各台官方/聚合地址即可。与 CHANNELS 完全分开, 互不影响。

XG = 'https://xiongguoying.top'
GZCDN = 'http://tencentplaygzrb01.gztv.com/live'

# (slug, 名称, 分组名, [播放地址...])；多个地址用于播放器容错切换
EXTERNAL_CHANNELS = [
    # ---- 广州台（官方 gztv CDN）----
    ('gzzh', '广州综合', '广州台', [GZCDN + '/zonghes.m3u8']),
    ('gzxw', '广州新闻', '广州台', [GZCDN + '/xinwen.m3u8']),
    ('ngds', '南国都市4K', '广州台', [GZCDN + '/nanguodushi.m3u8']),
    # ---- 广东台（官方 gdtv CDN，经聚合签发）----
    ('dwqws', '大湾区卫视', '广东台', [XG + '/dwqws']),
    ('gdzj', '广东珠江', '广东台', [XG + '/gdzj']),
    ('gdxw', '广东新闻', '广东台', [XG + '/gdxw']),
    ('gdty', '广东体育', '广东台', [XG + '/gdty']),
    ('gdgg', '广东民生', '广东台', [XG + '/gdgg']),
    ('gdys', '广东影视', '广东台', [XG + '/gdys']),
    ('gdse', '广东少儿', '广东台', [XG + '/gdse']),
    ('jjkt', '嘉佳卡通', '广东台', [XG + '/jjkt']),
    ('gdzy', '广东4K综艺', '广东台', [XG + '/gdzy']),
    ('dwqhw', '大湾区海外', '广东台', [XG + '/dwqhw']),
    ('nfgw', '南方购物', '广东台', [XG + '/nfgw']),
    ('lnxq', '岭南戏曲', '广东台', [XG + '/lnxq']),
    ('gdjdj', '广东经典剧', '广东台', [XG + '/gdjdj']),
    ('jlp', '广东纪录片', '广东台', [XG + '/jlp']),
    ('jkpd', 'GRTN健康', '广东台', [XG + '/jkpd']),
    ('shpd', 'GRTN生活', '广东台', [XG + '/shpd']),
    ('gdyd', '广东移动', '广东台', [XG + '/gdyd']),
    # ---- 广东地市台 ----
    ('stzh', '汕头综合', '广东地市台', [XG + '/stzh']),
    ('swzh', '汕尾综合', '广东地市台', [XG + '/swzh']),
    ('jmzh', '江门综合', '广东地市台', [XG + '/jmzh']),
    # ---- 香港 ----
    ('rthk31', 'RTHK31 港台', '香港台',
     ['https://rthktv31-live.akamaized.net/hls/live/2036818/RTHKTV31/master.m3u8']),
    # ---- 凤凰卫视（多源容错）----
    ('fhzw', '凤凰中文', '凤凰卫视', [
        'http://zmgd.zyrnet.com:8888/hls/110/index.m3u8',
        'http://120.198.95.220:9901/tsfile/live/1036_1.m3u8?key=txiptv']),
    ('fhzx', '凤凰资讯', '凤凰卫视', [
        'http://zmgd.zyrnet.com:8888/hls/109/index.m3u8',
        'http://120.198.95.220:9901/tsfile/live/1037_1.m3u8?key=txiptv']),
    ('fhhk', '凤凰香港', '凤凰卫视', [
        'https://epg.pw/stream/8770e89223a086eb1b8a0c931e42296d772a8069ad3eb72540e0c434e7cb3e93.m3u8',
        'https://epg.pw/stream/5f16dc7fc8aaaed3205516c63e4a8c24bca9dbba1181684244729cf574505b0e.m3u8']),
]
EXTERNAL_MAP = dict((e[0], e) for e in EXTERNAL_CHANNELS)
EXTERNAL_ORDER = [e[0] for e in EXTERNAL_CHANNELS]


def _ext_group_id(group_name):
    """外部频道的中文分组名 -> 站点分类用的 group id。"""
    return _GROUP_ID_BY_NAME.get(group_name, 'gd')


# 外部频道台标: 尽力匹配公开台标库(best-effort)。库里没有就回退空白占位, 不影响播放。
# 与上面逐条核实过的 LOGO_REMOTE 分开维护, 避免污染原表。
LOGO_REMOTE_EXTRA = {
    'gzzh': '广州综合', 'gzxw': '广州新闻',
    'dwqws': '大湾区卫视', 'gdzj': '广东珠江', 'gdxw': '广东新闻',
    'gdty': '广东体育', 'gdgg': '广东民生', 'gdys': '广东影视',
    'gdse': '广东少儿', 'jjkt': '嘉佳卡通',
    'stzh': '汕头综合',
    'fhzw': '凤凰中文', 'fhzx': '凤凰资讯', 'fhhk': '凤凰香港',
}


# ================================================================ 台标

# 公开台标库里对应的文件名。63 路逐条核过, 名字对不上就是 404, 所以是一一写死的。
LOGO_REMOTE = {
    'cctv1': 'CCTV1', 'cctv2': 'CCTV2', 'cctv3': 'CCTV3', 'cctv4': 'CCTV4',
    'cctv5': 'CCTV5', 'cctv5p': 'CCTV5+', 'cctv6': 'CCTV6', 'cctv7': 'CCTV7',
    'cctv8': 'CCTV8', 'cctv9': 'CCTV9', 'cctv10': 'CCTV10', 'cctv11': 'CCTV11',
    'cctv12': 'CCTV12', 'cctv13': 'CCTV13', 'cctv14': 'CCTV14', 'cctv15': 'CCTV15',
    'cctv16': 'CCTV16', 'cctv164k': 'CCTV16', 'cctv17': 'CCTV17', 'cctv4k': 'CCTV4K',
    'cgtn': 'CGTN', 'cgtnfr': 'CGTN法语', 'cgtnru': 'CGTN俄语', 'cgtnar': 'CGTN阿语',
    'cgtnes': 'CGTN西语', 'cgtndoc': 'CGTN纪录',
    'bjws': '北京卫视', 'jsws': '江苏卫视', 'dfws': '东方卫视', 'zjws': '浙江卫视',
    'hnws': '湖南卫视', 'hbws': '湖北卫视', 'gdws': '广东卫视', 'gxws': '广西卫视',
    'hljws': '黑龙江卫视', 'hainanws': '海南卫视', 'cqws': '重庆卫视', 'szws': '深圳卫视',
    'scws': '四川卫视', 'henanws': '河南卫视', 'dnws': '东南卫视', 'gzws': '贵州卫视',
    'jxws': '江西卫视', 'lnws': '辽宁卫视', 'ahws': '安徽卫视', 'hebws': '河北卫视',
    'sdws': '山东卫视', 'tjws': '天津卫视', 'jlws': '吉林卫视', 'saxws': '陕西卫视',
    'nxws': '宁夏卫视', 'nmgws': '内蒙古卫视', 'ynws': '云南卫视', 'shanxiws': '山西卫视',
    'qhws': '青海卫视', 'xizangws': '西藏卫视', 'xjws': '新疆卫视', 'cetv1': '中国教育1台',
}

# 库里没有的 5 路: 央视三个付费剧场 + 8K + 国学频道, 自绘内嵌, 零联网
LOGO_LOCAL = {
    'cctv8k': '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',
    'cctvfyjc': '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',
    'cctvdyjc': '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',
    'cctvhjjc': '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',
    'guoxue': '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',
}

# 四个镜像轮着试, 第一个通的就用; 国内网络对这几个的连通性随时会变, 多备几个
LOGO_MIRRORS = [
    'https://live.fanmingming.cn/tv/%s.png',
    'https://cdn.jsdelivr.net/gh/fanmingming/live@main/tv/%s.png',
    'https://live.fanmingming.com/tv/%s.png',
    'https://raw.githubusercontent.com/fanmingming/live/main/tv/%s.png',
]

LOGO_MODE = 'local'     # local / remote / off
LOGO_TIMEOUT = 4        # 单个镜像超时(秒)
LOGO_PREFETCH = True    # 开机后台把台标抓到缓存里
_LOGO_MEM = {}
_LOGO_FAIL = {}
_LOGO_LOCK = threading.Lock()
_LOGO_DIR = None
_LOGO_PREFETCHED = False
_BLANK_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


def _logo_cache_dir():
    """找一个能写的目录放台标缓存; 找不到就只用内存缓存。"""
    global _LOGO_DIR
    if _LOGO_DIR is not None:
        return _LOGO_DIR or None
    cands = [os.path.join(tempfile.gettempdir(), 'ysp_logo'),
             os.path.join(os.path.expanduser('~'), '.ysp_logo'),
             '/data/local/tmp/ysp_logo']
    for d in cands:
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
            probe = os.path.join(d, '.probe')
            with open(probe, 'wb') as fp:
                fp.write(b'1')
            os.remove(probe)
            _LOGO_DIR = d
            return d
        except Exception:
            continue
    _LOGO_DIR = ''
    return None


def _logo_disk_get(slug):
    d = _logo_cache_dir()
    if not d:
        return None
    try:
        p = os.path.join(d, slug + '.png')
        if os.path.isfile(p) and os.path.getsize(p) > 400:
            with open(p, 'rb') as fp:
                return fp.read()
    except Exception:
        pass
    return None


def _logo_disk_put(slug, data):
    d = _logo_cache_dir()
    if not d:
        return
    try:
        p = os.path.join(d, slug + '.png')
        with open(p, 'wb') as fp:
            fp.write(data)
    except Exception:
        pass


def _logo_fetch(slug):
    """从镜像列表里逐个试, 拿到 PNG 就返回。"""
    fn = LOGO_REMOTE.get(slug) or LOGO_REMOTE_EXTRA.get(slug)
    if not fn:
        return None
    q = urllib.parse.quote(fn)
    for tpl in LOGO_MIRRORS:
        try:
            req = urllib.request.Request(tpl % q, headers={
                'User-Agent': UA, 'Accept': 'image/png,image/*;q=0.8,*/*;q=0.5'})
            r = urllib.request.urlopen(req, timeout=LOGO_TIMEOUT)
            data = r.read(600 * 1024)
            try:
                r.close()
            except Exception:
                pass
            if len(data) > 400 and data[:4] == b'\x89PNG':
                return data
        except Exception:
            continue
    return None


def _logo_bytes(slug):
    """返回该频道台标的 PNG 字节; 拿不到返回 None。"""
    b64 = LOGO_LOCAL.get(slug)
    if b64:
        try:
            return base64.b64decode(b64)
        except Exception:
            return None
    now = time.time()
    with _LOGO_LOCK:
        if slug in _LOGO_MEM:
            return _LOGO_MEM[slug]
        if now - _LOGO_FAIL.get(slug, 0) < 60:   # 刚失败过, 一分钟内不再硬试
            return None
    data = _logo_disk_get(slug)
    if data is None:
        data = _logo_fetch(slug)
        if data:
            _logo_disk_put(slug, data)
    if data:
        with _LOGO_LOCK:
            _LOGO_MEM[slug] = data
        return data
    with _LOGO_LOCK:
        _LOGO_FAIL[slug] = time.time()
    return None


def _logo_url(slug, port=None):
    """按当前模式给出图标地址; off 返回 None。"""
    if LOGO_MODE == 'off':
        return None
    fn = LOGO_REMOTE.get(slug) or LOGO_REMOTE_EXTRA.get(slug)
    if LOGO_MODE == 'remote' and fn:
        return LOGO_MIRRORS[0] % urllib.parse.quote(fn)
    if not port:
        if _SERVER is not None and _SERVER.alive:
            port = _SERVER_PORT
        else:
            port = _ensure_server()
    if not port:
        return None
    return 'http://127.0.0.1:%d/logo/%s.png' % (port, slug)


def _logo_prefetch_start():
    """后台把 63 路台标抓进缓存, 用户滑列表时就是秒开。"""
    global _LOGO_PREFETCHED
    if not LOGO_PREFETCH:
        return
    with _LOGO_LOCK:
        if _LOGO_PREFETCHED:
            return
        _LOGO_PREFETCHED = True
    t = threading.Thread(target=_logo_prefetch_run)
    t.daemon = True
    t.start()


def _logo_prefetch_run():
    ok = 0
    logo_slugs = CHANNEL_ORDER + [s for s in EXTERNAL_ORDER if s in LOGO_REMOTE_EXTRA]
    for slug in logo_slugs:
        try:
            if _logo_bytes(slug):
                ok += 1
        except Exception:
            pass
        time.sleep(0.05)
    _log('台标就绪 %d/%d' % (ok, len(logo_slugs)))


def _seg_key(url, pdt):
    if pdt:
        return 'pdt:' + pdt
    p = urllib.parse.urlsplit(url)
    return p.scheme + '://' + p.netloc + p.path


def jce_fetch(ch):
    now = int(time.time())
    m3u8_url = jce_timeshift_url(ch.pid, ch.sid, now - WINDOW, now, ch.defn)
    req = urllib.request.Request(m3u8_url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode('utf-8', 'replace')
    segs, dur, pdt = [], 6.0, ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            try:
                dur = float(line[len('#EXTINF:'):].split(',')[0])
            except ValueError:
                dur = 6.0
        elif line.startswith('#EXT-X-PROGRAM-DATE-TIME:'):
            pdt = line[len('#EXT-X-PROGRAM-DATE-TIME:'):]
        elif line and not line.startswith('#'):
            segs.append((dur, pdt, urllib.parse.urljoin(m3u8_url, line)))
            pdt = ''
    if not segs:
        raise RuntimeError('empty playlist')
    return segs


def jce_refresh(ch):
    segs = jce_fetch(ch)
    added = 0
    with ch.lock:
        for dur, pdt, url in segs:
            key = _seg_key(url, pdt)
            if key in ch.segments:
                ch.segments[key][3] = url
                continue
            ch.seq += 1
            ch.segments[key] = [ch.seq, dur, pdt, url]
            ch.order.append(key)
            added += 1
        while len(ch.order) > MAX_SEGS:
            ch.segments.pop(ch.order.popleft(), None)
        ch.last_error = ''
    if added:
        _log('%s +%d 片' % (ch.slug, added))
    return True


def bk_refresh(ch):
    now = time.time()
    if now - ch.bk_urls_time > BK_URL_TTL or not ch.bk_urls:
        ch.bk_urls = bk_playurls(ch.sid, ch.pid, ch.defn)
        ch.bk_urls_time = now
        _log('%s bkliveinfo 拿到 %d 个地址' % (ch.slug, len(ch.bk_urls)))
    last_err = ''
    for attempt in range(2):
        for u in ch.bk_urls:
            try:
                pl = fetch_abs_playlist(u)
                if '#EXTM3U' not in pl:
                    continue
                with ch.lock:
                    ch.bk_playlist = pl
                    ch.last_error = ''
                return True
            except urllib.error.HTTPError as e:
                last_err = 'HTTPError: HTTP %s' % e.code
                if e.code == 403:
                    time.sleep(2)
                continue
            except Exception as e:
                last_err = '%s: %s' % (type(e).__name__, e)
        if attempt == 0:
            try:
                ch.bk_urls = bk_playurls(ch.sid, ch.pid, ch.defn)
                ch.bk_urls_time = time.time()
            except Exception:
                pass
    ch.bk_urls_time = 0
    raise RuntimeError(last_err[:120] or 'bk playlist failed')


def refresh_once(ch):
    try:
        if ch.mode == 'bk':
            ok = bk_refresh(ch)
        else:
            try:
                ok = jce_refresh(ch)
            except DeadHostError:
                ch.mode = 'bk'
                _log('%s JCE 坏域名, 切 bkliveinfo' % ch.slug)
                ok = bk_refresh(ch)
        if ok:
            ch.last_ok = time.time()
        return ok
    except Exception as e:
        ch.last_error = ('%s: %s' % (type(e).__name__, e))[:120]
        _log('%s 刷新失败: %s' % (ch.slug, ch.last_error))
        return False


def refresh_loop(ch):
    fails = 0
    while time.time() - ch.last_access < IDLE_TIMEOUT:
        ok = refresh_once(ch)
        fails = 0 if ok else fails + 1
        time.sleep(REFRESH_INTERVAL if fails < 3 else 30)
    _log('%s 无人观看, 停刷' % ch.slug)


def ensure_channel(ch):
    ch.last_access = time.time()
    need_fetch = False
    need_thread = False
    with ch.lock:
        if ch._starting:
            return
        need_fetch = not ch.segments and not ch.bk_playlist
        need_thread = ch.thread is None or not ch.thread.is_alive()
        if need_fetch or need_thread:
            ch._starting = True
    try:
        if need_fetch:
            refresh_once(ch)
        if need_thread:
            ch.thread = threading.Thread(target=refresh_loop, args=(ch,))
            ch.thread.daemon = True
            ch.thread.start()
    finally:
        with ch.lock:
            ch._starting = False


def build_playlist(ch):
    with ch.lock:
        if ch.mode == 'bk':
            return ch.bk_playlist or None
        keys = list(ch.order)[-LIVE_WINDOW:]
        segs = [ch.segments[k] for k in keys if k in ch.segments]
    if not segs:
        return None
    target = max(6, max(int(s[1] + 0.5) for s in segs))
    out = ['#EXTM3U', '#EXT-X-VERSION:3',
           '#EXT-X-TARGETDURATION:%d' % target,
           '#EXT-X-MEDIA-SEQUENCE:%d' % segs[0][0]]
    for _, dur, pdt, url in segs:
        if pdt:
            out.append('#EXT-X-PROGRAM-DATE-TIME:' + pdt)
        out.append('#EXTINF:%.3f,' % dur)
        out.append(url)
    return '\n'.join(out) + '\n'


# ================================================================ 本地极简 HTTP 服务
# 只发清单, 不转发视频流量; 用裸 socket 实现, 避免额外依赖。

DEFAULT_PORT = 8899
_SERVER = None
_SERVER_PORT = DEFAULT_PORT
_SERVER_LOCK = threading.Lock()


def _index_html():
    def _li(slug, name):
        return ('<li style="margin:6px 0"><img src="/logo/%s.png" width="30" height="30" '
                'style="vertical-align:middle;margin-right:8px;border-radius:5px">'
                '<a href="/%s.m3u8">%s</a> <span>/%s.m3u8</span></li>'
                % (slug, slug, name, slug))
    cctv = '<ul>%s</ul>' % ''.join(_li(c[0], c[1]) for c in CHANNELS)
    groups = {}
    for slug, name, gname, urls in EXTERNAL_CHANNELS:
        groups.setdefault(gname, []).append(_li(slug, name))
    ext = ''.join('<h4 style="margin:14px 0 4px">%s</h4><ul>%s</ul>'
                  % (g, ''.join(groups[g])) for g in groups)
    total = len(CHANNELS) + len(EXTERNAL_CHANNELS)
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>央视频直播</title></head><body>'
            '<h3>央视频 · 央视/广东/广州/香港/凤凰 直播 · %d 路</h3>'
            '<p>本页由插件内嵌代理提供，/diag 看状态。</p>'
            '<h4 style="margin:10px 0 4px">央视 / 卫视</h4>%s%s'
            '</body></html>' % (total, cctv, ext))


def _diag():
    now = time.time()
    d = _logo_cache_dir()
    with _LOGO_LOCK:
        cached, failed = len(_LOGO_MEM), len(_LOGO_FAIL)
    lines = ['port=%d' % _SERVER_PORT,
             'logo mode=%s total=%d builtin=%d cached=%d failed=%d dir=%s' % (
                 LOGO_MODE, len(CHANNEL_ORDER), len(LOGO_LOCAL), cached, failed, d or '-')]
    for slug in CHANNEL_ORDER:
        ch = CHANNEL_MAP[slug]
        age = ('%ds' % int(now - ch.last_ok)) if ch.last_ok else 'never'
        lines.append('%s mode=%s last_ok=%s err=%s' % (slug, ch.mode, age, ch.last_error))
    lines.append('---- external=%d ----' % len(EXTERNAL_CHANNELS))
    for slug, name, gname, urls in EXTERNAL_CHANNELS:
        lines.append('%s [%s] urls=%d' % (slug, gname, len(urls)))
    return '\n'.join(lines) + '\n'


def _extinf(slug, name, port=None):
    logo = _logo_url(slug, port)
    return ('#EXTINF:-1 tvg-id="%s" tvg-name="%s" group-title="%s"%s,%s'
            % (slug, name, GROUP_NAMES[_group_of(slug)],
               (' tvg-logo="%s"' % logo) if logo else '', name))


def _append_external_m3u(out, port):
    """把外部频道追加进 M3U: 直连官方/聚合地址; 每个地址一条, 供播放器容错。"""
    for slug, name, gname, urls in EXTERNAL_CHANNELS:
        logo = _logo_url(slug, port)
        head = ('#EXTINF:-1 tvg-id="%s" tvg-name="%s" group-title="%s"%s,%s'
                % (slug, name, gname,
                   (' tvg-logo="%s"' % logo) if logo else '', name))
        for u in urls:
            out.append(head)
            out.append(u)


def _m3u_all():
    base = 'http://127.0.0.1:%d' % _SERVER_PORT
    out = ['#EXTM3U']
    for slug, name, _s, _p, _d in CHANNELS:
        out.append(_extinf(slug, name, _SERVER_PORT))
        out.append('%s/%s.m3u8' % (base, slug))
    _append_external_m3u(out, _SERVER_PORT)
    return '\n'.join(out) + '\n'


def _route(path):
    if path in ('/', '/index.html'):
        return 200, 'text/html; charset=utf-8', _index_html().encode('utf-8')
    if path == '/health':
        return 200, 'text/plain; charset=utf-8', b'ok'
    if path == '/diag':
        return 200, 'text/plain; charset=utf-8', _diag().encode('utf-8')
    if path == '/all.m3u':
        return 200, 'application/vnd.apple.mpegurl', _m3u_all().encode('utf-8')
    m = re.match(r'^/logo/([A-Za-z0-9_]+)\.png$', path)
    if m:
        data = _logo_bytes(m.group(1))
        if not data:
            return 200, 'image/png', _BLANK_PNG, {'cache': 'no-cache'}
        return 200, 'image/png', data, {'cache': 'max-age=604800'}
    m = re.match(r'^/([A-Za-z0-9_]+)\.m3u8$', path)
    if m:
        slug = m.group(1)
        ch = CHANNEL_MAP.get(slug)
        if ch is None:
            ext = EXTERNAL_MAP.get(slug)
            if ext is not None:
                # 外部频道: 让播放器直接跳转去官方/聚合地址, 本地不转发
                return 302, 'text/plain; charset=utf-8', b'', {'location': ext[3][0]}
            return 404, 'text/plain; charset=utf-8', ('未知频道 %s' % slug).encode('utf-8')
        ensure_channel(ch)
        pl = build_playlist(ch)
        if not pl:
            return 503, 'text/plain; charset=utf-8', \
                ('频道 %s 拉取中/失败: %s' % (ch.name, ch.last_error or '请稍后')).encode('utf-8')
        return 200, 'application/vnd.apple.mpegurl', pl.encode('utf-8')
    return 404, 'text/plain; charset=utf-8', b'not found'


class _MiniServer(threading.Thread):
    daemon = True

    def __init__(self, host, port):
        threading.Thread.__init__(self)
        self.alive = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen(64)
        self.alive = True

    def run(self):
        while self.alive:
            try:
                cs, _addr = self.sock.accept()
            except Exception:
                break
            t = threading.Thread(target=self._serve, args=(cs,))
            t.daemon = True
            t.start()

    def _serve(self, cs):
        try:
            cs.settimeout(20)
            data = b''
            while b'\r\n\r\n' not in data and len(data) < 8192:
                chunk = cs.recv(2048)
                if not chunk:
                    break
                data += chunk
            if not data:
                return
            first = data.split(b'\r\n', 1)[0].decode('latin-1', 'replace')
            parts = first.split(' ')
            if len(parts) < 2:
                return
            path = urllib.parse.urlparse(parts[1]).path
            r = _route(path)
            extra = {}
            if len(r) == 4:
                code, ctype, body, extra = r
            else:
                code, ctype, body = r
            head = ('HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
                    'Access-Control-Allow-Origin: *\r\nCache-Control: %s\r\n'
                    % (code, 'OK' if code == 200 else 'ERR', ctype, len(body),
                       extra.get('cache', 'no-cache')))
            if extra.get('location'):
                head += 'Location: %s\r\n' % extra['location']
            head += 'Connection: close\r\n\r\n'
            cs.sendall(head.encode('latin-1') + body)
        except Exception:
            pass
        finally:
            try:
                cs.close()
            except Exception:
                pass

    def stop(self):
        self.alive = False
        try:
            self.sock.close()
        except Exception:
            pass


def _ensure_server(prefer=None):
    """返回可用端口; 起不来返回 None。"""
    global _SERVER, _SERVER_PORT
    with _SERVER_LOCK:
        if _SERVER is not None and _SERVER.alive:
            return _SERVER_PORT
        start = int(prefer or DEFAULT_PORT)
        for p in range(start, start + 12):
            try:
                srv = _MiniServer('127.0.0.1', p)
            except Exception:
                continue
            srv.start()
            _SERVER = srv
            _SERVER_PORT = p
            _log('本地 HLS 代理: http://127.0.0.1:%d/' % p)
            return p
        _log('本地 HLS 代理启动失败')
        return None


def _slug_of(v):
    s = str(v or '').strip()
    if '://' in s:
        s = s.split('://', 1)[1]
    s = s.split('?', 1)[0]
    if '/' in s:
        s = s.split('/', 1)[0]
    if '.' in s:
        s = s.split('.', 1)[0]
    return s


def _ext_json(extend):
    if isinstance(extend, dict):
        return extend
    try:
        d = json.loads(extend or '{}')
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _vod(ch):
    item = {'vod_id': ch.slug, 'vod_name': ch.name, 'vod_remarks': '直播',
            'type_name': GROUP_NAMES[_group_of(ch.slug)]}
    logo = _logo_url(ch.slug)
    if logo:
        item['vod_pic'] = logo
    return item


def _vod_ext(slug, name, group_name):
    item = {'vod_id': slug, 'vod_name': name, 'vod_remarks': '直播',
            'type_name': group_name}
    logo = _logo_url(slug)
    if logo:
        item['vod_pic'] = logo
    return item


# ================================================================ Spider

class Spider(_BaseSpider):

    def __init__(self):
        self._port = DEFAULT_PORT
        self._live_fmt = 'm3u'

    def init(self, extend=''):
        global LOGO_MODE, LOGO_PREFETCH
        ext = _ext_json(extend)
        if ext.get('port'):
            try:
                self._port = int(ext['port'])
            except Exception:
                self._port = DEFAULT_PORT
        if str(ext.get('live', '')).lower() in ('txt', 'm3u'):
            self._live_fmt = str(ext['live']).lower()
        mode = str(ext.get('logo', '')).lower()
        if mode in ('local', 'remote', 'off'):
            LOGO_MODE = mode
        if ext.get('logo_prefetch') is not None:
            LOGO_PREFETCH = bool(ext.get('logo_prefetch'))
        _ensure_server(self._port)
        _logo_prefetch_start()
        return None

    def getName(self):
        return '央视频直播'

    def homeContent(self, filter):
        classes = [{'type_id': tid, 'type_name': name} for tid, name in GROUP_DEFS]
        lst = [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if _group_of(s) == 'cctv']
        return {'class': classes, 'list': lst}

    def homeVideoContent(self):
        return {'list': [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if _group_of(s) == 'cctv']}

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or '')
        lst = [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER if _group_of(s) == tid]
        for slug, name, gname, urls in EXTERNAL_CHANNELS:
            if _ext_group_id(gname) == tid:
                lst.append(_vod_ext(slug, name, gname))
        return {'list': lst, 'page': 1, 'pagecount': 1, 'limit': len(lst), 'total': len(lst)}

    def detailContent(self, ids):
        slug = _slug_of(ids[0] if isinstance(ids, (list, tuple)) and ids else ids)
        ch = CHANNEL_MAP.get(slug)
        if ch is None:
            ext = EXTERNAL_MAP.get(slug)
            if ext is None:
                return {'list': []}
            _slug, name, gname, urls = ext
            item = _vod_ext(slug, name, gname)
            item['vod_content'] = '%s · 直连官方/聚合直播源（本地不转发视频流量）' % name
            item['vod_play_from'] = gname
            item['vod_play_url'] = '直播$ysp://%s' % slug
            return {'list': [item]}
        item = _vod(ch)
        item['vod_content'] = '%s · 央视频直播（插件内嵌代理，播放器直连央视 CDN）' % ch.name
        item['vod_play_from'] = '央视频'
        item['vod_play_url'] = '直播$ysp://%s' % slug
        return {'list': [item]}

    def searchContent(self, key, quick, pg='1'):
        key = str(key or '').strip()
        lst = [_vod(CHANNEL_MAP[s]) for s in CHANNEL_ORDER
               if key and (key in CHANNEL_MAP[s].name or key.lower() in s)]
        for slug, name, gname, urls in EXTERNAL_CHANNELS:
            if key and (key in name or key.lower() in slug):
                lst.append(_vod_ext(slug, name, gname))
        return {'list': lst, 'page': 1, 'pagecount': 1}

    def playerContent(self, flag, id, vipFlags=None):
        slug = _slug_of(id)
        ch = CHANNEL_MAP.get(slug)
        port = _ensure_server(self._port)
        if ch is None:
            ext = EXTERNAL_MAP.get(slug)
            if ext is not None:
                # 外部频道: 播放器直连官方/聚合地址, 无需本地代理
                return {'parse': 0, 'jx': 0, 'url': ext[3][0],
                        'format': 'application/x-mpegURL',
                        'header': {'User-Agent': UA}}
            return {'parse': 0, 'jx': 0, 'url': slug}
        ensure_channel(ch)
        if port:
            return {'parse': 0, 'jx': 0,
                    'url': 'http://127.0.0.1:%d/%s.m3u8' % (port, slug),
                    'format': 'application/x-mpegURL',
                    'header': {'User-Agent': UA}}
        # 兜底: 本地服务起不来, 直接给时移地址(能播, 但窗口走完会断, 播放器需重新点)
        try:
            now = int(time.time())
            return {'parse': 0, 'jx': 0,
                    'url': jce_timeshift_url(ch.pid, ch.sid, now - WINDOW, now + 3600 * 3, ch.defn),
                    'format': 'application/x-mpegURL',
                    'header': {'User-Agent': UA}}
        except Exception as e:
            return {'parse': 0, 'jx': 0, 'url': slug, 'desc': str(e)[:60]}

    def liveContent(self, url):
        """直播配置: groups 为空 + api 指向本文件时, App 会调这里取列表文字。"""
        port = _ensure_server(self._port) or self._port
        if self._live_fmt == 'txt':
            out = []
            last = None
            for slug, name, _s, _p, _d in CHANNELS:
                g = GROUP_NAMES[_group_of(slug)]
                if g != last:
                    out.append('%s,#genre#' % g)
                    last = g
                out.append('%s,http://127.0.0.1:%d/%s.m3u8' % (name, port, slug))
            for slug, name, gname, urls in EXTERNAL_CHANNELS:
                if gname != last:
                    out.append('%s,#genre#' % gname)
                    last = gname
                for u in urls:
                    out.append('%s,%s' % (name, u))
            return '\n'.join(out) + '\n'
        out = ['#EXTM3U']
        for slug, name, _s, _p, _d in CHANNELS:
            out.append(_extinf(slug, name, port))
            out.append('http://127.0.0.1:%d/%s.m3u8' % (port, slug))
        _append_external_m3u(out, port)
        return '\n'.join(out) + '\n'

    def destroy(self):
        # 不主动关本地服务, 下次 init 复用同一个端口
        return None
