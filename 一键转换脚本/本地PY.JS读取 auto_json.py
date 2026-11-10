# -*- coding: utf-8 -*-
"""
PY.JS 云端仓库自动加载（cnb.cool）
==================================
- 扫描 cnb.cool 仓库根目录下的 py/js 文件夹（自动递归子目录）
- 站点 api 全部指向仓库 raw 地址，py/js 文件本体不下载、不占手机内存
- 手机本地仅生成一个很小的 /sdcard/auto_config.json（站点清单，百KB 内）
- 仓库增删文件后自动检查更新（默认缓存 6 小时），也可在「⚙ 扫描」里手动刷新
- 本脚本放在仓库根目录，与 X.json 同级，X.json 里 api 写 "./本地PY.JS读取 auto_json.py"
"""
import os
import sys
import json
import time
import threading
import hashlib
import urllib.parse
import urllib.request
import ssl

# ============================================================
# base 模块导入（兼容 TVBox / OK影视 各版本加载方式）
# ============================================================
try:
    from base.spider import Spider as BaseSpider
except Exception:
    try:
        from base import Spider as BaseSpider
    except Exception:
        class BaseSpider:
            def __init__(self): pass
            def getName(self): return "RemoteAutoLoader"
            def init(self, extend=""): pass
            def isVideoFormat(self, url): pass
            def manualVideoCheck(self): pass
            def homeContent(self, filter): return {'class': [], 'list': []}
            def homeVideoContent(self): return {'list': []}
            def categoryContent(self, tid, pg, filter, extend): return {'list': []}
            def detailContent(self, array): return {'list': []}
            def searchContent(self, key, quick): return {'list': []}
            def playerContent(self, flag, id, vipFlags): return {}
            def localProxy(self, param): return None
            def action(self, action): return {'code': 0, 'msg': ''}


_ICON_SCAN = "https://t9.baidu.com/it/u=59951231,564237437&fm=193"
_ICON_SEARCH = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f50d.png"


class Spider(BaseSpider):
    # 频道 TID
    TOOLS_TID = "__tools__"
    ALL_TID = "__all__"
    PY_TID = "__py_sources__"
    JS_TID = "__js_sources__"

    # ============================================================
    # ★★★ 用户配置区（按你的仓库改这里即可）★★★
    # ============================================================
    # 仓库地址（不带 .git 后缀，格式：组织名/仓库名）
    REPO = "junchao.tang/jtv"
    # 分支名
    BRANCH = "main"
    # 仓库根目录下需要扫描的一级目录（py/js 直接放仓库根目录，不需要 bh）
    SCAN_DIRS = ["py", "js"]
    # 网页目录解析失败时的兜底清单（仓库里可选放一个该文件，内容为路径数组，如 ["py/xx.py"]）
    MANIFEST_PATH = "pyjs_manifest.json"
    # 自动检查更新的缓存有效期（秒），默认 6 小时
    REFRESH_TTL = 6 * 3600

    # 点播源显示名
    SOURCE_NAME = "【PY.JS云端自动加载】"
    # 本地生成的小清单文件（只有这个 JSON 在手机上，py/js 本体都在云端）
    AUTO_CONFIG = "/sdcard/auto_config.json"
    # 本地缓存元数据（文件清单签名 + 更新时间）
    CACHE_META = "/sdcard/auto_remote_cache.json"

    def __init__(self):
        super().__init__()

        # ★ 排除文件（不加载为站点）
        self.EXCLUDE_FILES = {
            'AutoJsonGenerator.py', 'AutoJsonGenerator.js',
            'auto_loader.py', 'auto_json.py', 'auto_json.js',
            'loader.py', 'loader.js', 'main.py', 'main.js',
        }
        # ★ 屏蔽的子目录名
        self.EXCLUDE_DIRS = {
            'test', 'backup', 'temp', 'bak', '老文件', '优化',
        }

        self.lock = threading.RLock()
        self.py_count = 0
        self.js_count = 0
        self.total_count = 0
        self.out_file_path = ""
        self.err_msg = ""
        self.last_msg = ""
        self.last_update_ts = 0
        self.sources = []
        self.category_map = {}
        self.inited = False
        self._refreshing = False

        # 首次进入/每次执行逻辑：
        # 1. 先读本地已有的 auto_config.json（秒开，不阻塞界面）
        # 2. 本地没有清单（第一次用）→ 联网扫描仓库并生成清单
        # 3. 本地已有清单 → 后台线程检查仓库是否有增删（过了缓存有效期才联网），不阻塞
        try:
            self._load_existing_json()
            if not self.sources:
                self._scan_and_cache(force=True)
            else:
                self._start_background_refresh(force=False)
        except Exception as e:
            self.err_msg = "初始化异常: {}".format(e)

    def getName(self):
        return "PY.JS云端自动加载"

    def init(self, extend=""):
        if self.inited:
            return
        self.inited = True
        with self.lock:
            try:
                self._load_existing_json()
                if not self.sources:
                    self._scan_and_cache(force=True)
                else:
                    self._start_background_refresh(force=False)
            except Exception as e:
                self.err_msg = "init 异常: {}".format(e)

    # ============================================================
    # 网络请求（纯标准库，证书失败时降级兼容）
    # ============================================================
    def _tree_url(self, path):
        base = "https://cnb.cool/{}/-/tree/{}".format(self.REPO, self.BRANCH)
        if path:
            return base + "/" + self._quote_path(path)
        return base

    @property
    def _raw_base(self):
        return "https://cnb.cool/{}/-/git/raw/{}".format(self.REPO, self.BRANCH)

    @staticmethod
    def _quote_path(path):
        return "/".join(urllib.parse.quote(seg, safe='') for seg in str(path).split('/'))

    def _raw_url(self, rel_path):
        return self._raw_base + "/" + self._quote_path(rel_path)

    def _http_get(self, url, timeout=25):
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 TVBoxAutoLoader",
            "Accept": "text/html,application/json,*/*",
        }

        def _open(ctx):
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read()

        try:
            data = _open(ssl.create_default_context())
        except Exception:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            data = _open(ctx)
        return data.decode('utf-8', 'replace')

    # ============================================================
    # cnb.cool 目录页解析（页面内嵌 entries JSON，无需登录/Token）
    # ============================================================
    @staticmethod
    def _parse_entries(html, path):
        """从仓库目录页 HTML 提取该目录的 entries 数组（括号配对，兼容中文/特殊字符）"""
        anchor = '"path":"{}","name":"{}","entries":['.format(path, path)
        idx = html.find(anchor)
        if idx < 0:
            return None
        start = idx + len(anchor) - 1  # 指向 '['
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(html)):
            ch = html[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        return json.loads(html[start:i + 1])
        return None

    def _list_remote_dir(self, path):
        """返回某个仓库目录的条目列表 [{type, path, name, sha}]"""
        html = self._http_get(self._tree_url(path))
        entries = self._parse_entries(html, path)
        if entries is None:
            raise RuntimeError("目录页解析失败: {}".format(path or "/"))
        return entries

    def _fetch_manifest(self):
        """可选兜底：读取仓库根目录的 MANIFEST_PATH（JSON 数组），失败返回 None"""
        try:
            text = self._http_get(self._raw_url(self.MANIFEST_PATH), timeout=15)
            data = json.loads(text)
            if isinstance(data, list):
                return [str(p).replace('\\', '/').lstrip('/') for p in data if p]
        except Exception:
            return None
        return None

    # ============================================================
    # 递归收集仓库 py/js 文件
    # ============================================================
    def _is_excluded_file(self, name):
        return (name.startswith('__') or name in self.EXCLUDE_FILES
                or name.startswith('自动加载'))

    def _collect_remote_files(self):
        files = []
        seen = set()
        errors = []

        def walk(path):
            try:
                items = self._list_remote_dir(path)
            except Exception as e:
                errors.append("{}: {}".format(path or "/", e))
                return
            for it in items:
                p = str(it.get('path', '')).replace('\\', '/')
                t = it.get('type')
                name = it.get('name', p.rsplit('/', 1)[-1])
                if t == 'dir':
                    if name in self.EXCLUDE_DIRS:
                        continue
                    walk(p)
                elif t == 'file' and p.lower().endswith(('.py', '.js')):
                    base_name = p.rsplit('/', 1)[-1]
                    if self._is_excluded_file(base_name):
                        continue
                    if p not in seen:
                        seen.add(p)
                        files.append((p, str(it.get('sha', ''))))

        for top in self.SCAN_DIRS:
            walk(top)

        # 兜底：目录页解析全部失败时，尝试读取仓库内的手工清单
        if not files:
            manifest = self._fetch_manifest()
            if manifest:
                for p in manifest:
                    if p.lower().endswith(('.py', '.js')) and p not in seen:
                        if not self._is_excluded_file(p.rsplit('/', 1)[-1]):
                            seen.add(p)
                            files.append((p, ''))
        return files, errors

    @staticmethod
    def _category_of(rel_path):
        """py/xx.py → py；py/子目录/xx.py → 子目录（与本地版分类规则一致）"""
        parts = rel_path.split('/')
        if len(parts) <= 2:
            return parts[0]
        return parts[1]

    def _build_sources(self, files):
        sources = []
        seen_mods = set()
        for rel, sha in sorted(files):
            ext = os.path.splitext(rel)[1].lower()
            mod_name = os.path.splitext(rel)[0].rsplit('/', 1)[-1]
            typ = "JS" if ext == '.js' else "PY"
            dedup_key = (typ, mod_name)
            if dedup_key in seen_mods:
                continue
            seen_mods.add(dedup_key)

            sources.append({
                "id": ("js_" if ext == '.js' else "py_") + mod_name,
                "name": mod_name + ("[JS]" if ext == '.js' else ""),
                "path": rel,
                "relative_path": rel,
                "api": self._raw_url(rel),
                "type": typ,
                "category": self._category_of(rel),
                "sha": sha,
            })
        return sources

    def _signature(self, files):
        raw = "\n".join("{}:{}".format(sha, p) for p, sha in sorted(files))
        return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    # ============================================================
    # 本地缓存（清单 + 元数据）
    # ============================================================
    def _script_dir(self):
        try:
            return os.path.dirname(os.path.abspath(__file__))
        except Exception:
            return os.getcwd()

    def _config_targets(self):
        return [
            self.AUTO_CONFIG,
            '/storage/emulated/0/auto_config.json',
            os.path.join(self._script_dir(), 'auto_config.json'),
        ]

    def _meta_targets(self):
        return [
            self.CACHE_META,
            '/storage/emulated/0/auto_remote_cache.json',
            os.path.join(self._script_dir(), 'auto_remote_cache.json'),
        ]

    def _write_first_writable(self, targets, content, binary=False):
        for out_path in targets:
            try:
                out_dir = os.path.dirname(out_path)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                if os.path.exists(out_dir) and not os.access(out_dir, os.W_OK):
                    continue
                tmp = out_path + '.tmp'
                mode = 'wb' if binary else 'w'
                with open(tmp, mode, **({} if binary else {"encoding": "utf-8"})) as f:
                    f.write(content)
                    if not binary:
                        f.flush()
                        os.fsync(f.fileno())
                os.replace(tmp, out_path)
                return out_path
            except Exception:
                try:
                    if os.path.exists(out_path + '.tmp'):
                        os.remove(out_path + '.tmp')
                except Exception:
                    pass
                continue
        return ""

    def _load_meta(self):
        for path in self._meta_targets():
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    continue
        return None

    def _load_existing_json(self):
        for path in self._config_targets():
            if not os.path.isfile(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                continue
            if not config or not isinstance(config.get('sites'), list):
                continue

            sources = []
            category_map = {}
            for site in config['sites']:
                if not isinstance(site, dict):
                    continue
                api = str(site.get('api', ''))
                name = str(site.get('name', ''))
                key = str(site.get('key', ''))
                is_js = api.lower().split('?')[0].endswith('.js')
                rel = self._api_to_rel(api)
                src = {
                    "id": key,
                    "name": name,
                    "path": rel,
                    "relative_path": rel,
                    "api": api,
                    "type": "JS" if is_js else "PY",
                    "category": self._category_of(rel) if rel else "其它",
                }
                sources.append(src)
                category_map.setdefault(src["category"], []).append(src)

            self.sources = sources
            self.category_map = category_map
            self.total_count = len(sources)
            self.js_count = sum(1 for s in sources if s["type"] == "JS")
            self.py_count = self.total_count - self.js_count
            self.out_file_path = path
            meta = self._load_meta()
            if meta:
                self.last_update_ts = int(meta.get('ts', 0))
            return

    def _api_to_rel(self, api):
        """raw URL 反解出仓库相对路径（解 URL 编码）"""
        marker = "/-/git/raw/{}/".format(self.BRANCH)
        idx = api.find(marker)
        if idx >= 0:
            tail = api[idx + len(marker):].split('?')[0]
            return urllib.parse.unquote(tail)
        # 非本仓库地址（手工配置等），原样返回
        return urllib.parse.unquote(api)

    # ============================================================
    # 扫描仓库 → 生成 auto_config.json
    # ============================================================
    def _scan_and_cache(self, force=False):
        """返回 (是否有变化, 说明)"""
        with self.lock:
            files, errors = self._collect_remote_files()
            if not files:
                self.err_msg = "仓库扫描失败或没有任何 py/js 文件；{}".format(
                    "；".join(errors[:3]) if errors else "请检查仓库/分支配置")
                return False, self.err_msg

            sig = self._signature(files)
            meta = self._load_meta()
            if not force and meta and meta.get('signature') == sig and self.sources:
                self._save_meta(sig, meta.get('ts', int(time.time())))
                return False, "仓库无变化"

            sources = self._build_sources(files)
            config_data = {"sites": [{
                "key": s["id"],
                "name": s["name"],
                "type": 3,
                "api": s["api"],
                "searchable": 1,
                "quickSearch": 1,
                "filterable": 1,
                "changeable": 1,
                "playerType": 2,
            } for s in sources]}

            cfg_text = json.dumps(config_data, ensure_ascii=False, indent=4)
            cfg_path = self._write_first_writable(self._config_targets(), cfg_text)
            if not cfg_path:
                self.err_msg = "本地 auto_config.json 写入失败（/sdcard 不可写）"
                return False, self.err_msg

            now = int(time.time())
            self._save_meta(sig, now)
            self.out_file_path = cfg_path

            self.sources = sources
            self.category_map = {}
            for s in sources:
                self.category_map.setdefault(s["category"], []).append(s)
            self.total_count = len(sources)
            self.js_count = sum(1 for s in sources if s["type"] == "JS")
            self.py_count = self.total_count - self.js_count
            self.last_update_ts = now
            self.err_msg = ""

            self._try_reload_app()
            self.last_msg = "云端扫描完成：共 {} 个（PY:{} JS:{}）".format(
                self.total_count, self.py_count, self.js_count)
            if errors:
                self.last_msg += "；部分目录读取失败"
            return True, self.last_msg

    def _save_meta(self, signature, ts):
        meta = {
            "repo": self.REPO,
            "branch": self.BRANCH,
            "signature": signature,
            "ts": int(ts),
            "count": self.total_count,
        }
        path = self._write_first_writable(
            self._meta_targets(),
            json.dumps(meta, ensure_ascii=False, indent=2))
        return path

    def _start_background_refresh(self, force=False):
        """后台线程检查仓库更新，不阻塞界面"""
        if self._refreshing:
            return
        if not force:
            meta = self._load_meta()
            if meta and int(time.time()) - int(meta.get('ts', 0)) < self.REFRESH_TTL:
                return

        def worker():
            if self._refreshing:
                return
            self._refreshing = True
            try:
                self._scan_and_cache(force=force)
            except Exception as e:
                self.err_msg = "后台更新异常: {}".format(e)
            finally:
                self._refreshing = False

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ============================================================
    # OK影视 自动重载（与本地版同一套机制）
    # ============================================================
    def _get_current_app_port(self):
        try:
            from java import jclass
            port = int(jclass("com.github.catvod.Proxy").getPort())
            if port > 0:
                return port
        except Exception:
            pass
        return 0

    def _file_url(self, path):
        absolute = os.path.realpath(os.path.abspath(os.path.expanduser(str(path))))
        if absolute.startswith('/storage/emulated/0/'):
            return "file://storage/emulated/0/" + absolute[len('/storage/emulated/0/'):]
        if absolute.startswith('/sdcard/'):
            return "file://storage/emulated/0/" + absolute[len('/sdcard/'):]
        if absolute.startswith('/storage/'):
            return "file://storage/" + absolute[len('/storage/'):]
        return "file://" + absolute.lstrip('/')

    def _try_reload_app(self):
        try:
            port = self._get_current_app_port()
            if port < 1:
                return False, "本机服务端口未获取"
            target = self._file_url(self.AUTO_CONFIG)
            config_body = json.dumps({
                "type": 0,
                "url": target,
                "name": self.SOURCE_NAME,
            }, ensure_ascii=False, separators=(',', ':'))
            body = urllib.parse.urlencode({
                "config": config_body,
                "targets": "[]",
                "force": "true",
            }).encode('utf-8')
            url = "http://127.0.0.1:{}/action?do=sync&mode=1&type=history".format(port)
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                         "Connection": "close"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=2.5) as resp:
                status = int(getattr(resp, 'status', resp.getcode()))
                if status != 200:
                    return False, "HTTP {}".format(status)
            return True, "OK影视 已自动切换点播源"
        except Exception as e:
            return False, "自动切换失败: {}".format(e)

    # ============================================================
    # 界面
    # ============================================================
    def homeContent(self, filter):
        classes = [
            {"type_id": self.TOOLS_TID, "type_name": "⚙ 扫描"},
            {"type_id": self.ALL_TID, "type_name": "全部 ({})".format(self.total_count)},
            {"type_id": self.PY_TID, "type_name": "PY源 ({})".format(self.py_count)},
            {"type_id": self.JS_TID, "type_name": "JS源 ({})".format(self.js_count)},
        ]
        for cat_name in sorted(self.category_map.keys(), key=lambda x: x.casefold()):
            count = len(self.category_map[cat_name])
            classes.append({
                "type_id": "cat:" + cat_name,
                "type_name": "{} ({})".format(cat_name, count),
            })
        return {"class": classes, "list": self._sources_to_vods(self.sources)}

    def homeVideoContent(self):
        return {"list": self._sources_to_vods(self.sources)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        page_size = 60

        if tid == self.TOOLS_TID:
            items = self._tools_items()
            return {"page": 1, "pagecount": 1, "limit": page_size,
                    "total": len(items), "list": items}
        if tid == self.PY_TID:
            items = [s for s in self.sources if s["type"] == "PY"]
        elif tid == self.JS_TID:
            items = [s for s in self.sources if s["type"] == "JS"]
        elif str(tid).startswith("cat:"):
            items = list(self.category_map.get(str(tid)[4:], []))
        else:
            items = list(self.sources)

        total = len(items)
        page_count = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        return {"page": page, "pagecount": page_count, "limit": page_size,
                "total": total,
                "list": self._sources_to_vods(items[start:start + page_size])}

    def _tools_items(self):
        return [
            {"vod_id": "__rescan__", "vod_name": "刷新云端仓库",
             "vod_pic": _ICON_SCAN,
             "vod_remarks": "重新扫描仓库 py/js 并生成清单",
             "action": "rescan"},
            {"vod_id": "__status__", "vod_name": "状态信息",
             "vod_pic": _ICON_SCAN,
             "vod_remarks": "仓库 / 数量 / 更新时间"},
        ]

    def _status_text(self):
        t = time.strftime("%Y-%m-%d %H:%M:%S",
                          time.localtime(self.last_update_ts)) if self.last_update_ts else "未更新"
        return (
            "仓库: {}\n分支: {}\n扫描目录: {}\n"
            "PY源: {} 个\nJS源: {} 个\n合计: {} 个\n"
            "最近更新: {}\n"
            "清单文件: {}\n\n"
            "说明: py/js 源文件全部在云端仓库，手机本地仅保存站点清单；"
            "使用某个源时 App 才会临时下载运行。\n"
            "{}"
        ).format(self.REPO, self.BRANCH, "/".join(self.SCAN_DIRS),
                 self.py_count, self.js_count, self.total_count,
                 t, self.out_file_path or "（尚未生成）",
                 ("错误信息: " + self.err_msg) if self.err_msg else "")

    def detailContent(self, array):
        vid = str(array[0]) if isinstance(array, (list, tuple)) and array else str(array)

        if vid == "__rescan__":
            content = "点击播放按钮可立即重新扫描云端仓库"
            return {"list": [{"vod_id": vid, "vod_name": "刷新云端仓库",
                              "vod_pic": _ICON_SCAN, "vod_play_from": "提示",
                              "vod_play_url": "查看:$" + content, "vod_content": content}]}
        if vid == "__status__":
            content = self._status_text()
            return {"list": [{"vod_id": vid, "vod_name": "状态信息",
                              "vod_pic": _ICON_SCAN, "vod_play_from": "提示",
                              "vod_play_url": "查看:$" + content, "vod_content": content}]}

        for src in self.sources:
            if src["id"] == vid:
                content = (
                    "名称: {}\n分类: {}\n仓库路径: {}\nAPI: {}\n\n"
                    "重要提示：请切换到点播点击[{}]"
                ).format(src["name"], src["category"], src["relative_path"],
                         src["api"], self.SOURCE_NAME)
                return {"list": [{"vod_id": vid, "vod_name": src["name"],
                                  "vod_pic": "", "vod_play_from": "提示",
                                  "vod_play_url": "查看:$" + content,
                                  "vod_content": content}]}
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        keyword = str(key or "").strip().lower()
        if not keyword:
            return {"list": []}
        result = [s for s in self.sources if keyword in s["name"].lower()]
        return {"list": self._sources_to_vods(result, icon=_ICON_SEARCH)}

    def playerContent(self, flag, id, vipFlags):
        return {}

    def localProxy(self, param):
        return None

    def action(self, action):
        action = str(action)
        if action == "rescan":
            with self.lock:
                try:
                    changed, detail = self._scan_and_cache(force=True)
                    msg = ("{}\nPY:{} 个 / JS:{} 个".format(
                        detail, self.py_count, self.js_count))
                except Exception as e:
                    msg = "刷新失败：{}".format(e)
            return {"code": 0, "msg": msg}
        return {"code": 0, "msg": ""}

    def _sources_to_vods(self, items, icon=""):
        return [{
            "vod_id": src["id"],
            "vod_name": src["name"],
            "vod_pic": icon,
            "vod_remarks": src["relative_path"],
        } for src in items]
#（注：内容由AI生成）
