# coding=utf-8
"""
洛雪音乐服务器的 ys Type 3 单文件爬虫。

提供 HomeUI v4 CSS-like 音乐首页、榜单/歌单/歌手/专辑、收藏读取、音乐播放解析，
以及通过 Action 管理 lxserver 自定义 JS 音源的能力。

@author @ccfork
"""

import base64
import hashlib
import json
import os
import re
import time
from copy import deepcopy
from urllib.parse import quote

import requests
from requests import Session
from requests.exceptions import RequestException

from base.spider import Spider as BaseSpider


SOURCE_NAMES = {
    "kw": "酷我音乐",
    "kg": "酷狗音乐",
    "tx": "QQ音乐",
    "wy": "网易云音乐",
    "mg": "咪咕音乐",
}

QUALITY_NAMES = {
    "128k": "标准音质",
    "320k": "高品音质",
    "flac": "无损音质",
    "flac24bit": "Hi-Res",
}

SORT_IDS = {
    "kw": {"hot": "hot", "new": "new"},
    "kg": {"hot": "6", "new": "7", "recommend": "5"},
    "tx": {"hot": "5", "new": "2"},
    "wy": {"hot": "hot", "new": "hot"},
    "mg": {"hot": "15127315", "new": "15127315"},
}

DEFAULT_CONFIG = {
    "base_url": "http://127.0.0.1:9527",
    "username": "admin",
    "password": "password",
    "api_token": "",
    "admin_password": "123456",
    "source": "kw",
    "playlist_source": "wy",
    "album_source": "wy",
    "sources": ["kw", "kg", "tx", "wy", "mg"],
    "quality": "320k",
    "qualities": ["128k", "320k", "flac"],
    "timeout": 12,
    "max_pages": 5,
    "max_songs": 500,
    "home_ttl": 180,
    "download_folder": "",
    "download_quality": "320k",
    "auto_download": "否",
}


class LxClientError(Exception):
    """lxserver 请求失败。"""


class LxHttpClient:
    """负责 lxserver HTTP、登录令牌和各业务接口调用。"""

    def __init__(self, config):
        self.config = config
        self.base_url = str(config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
        self.timeout = self._positive_int(config.get("timeout"), 12, 3, 60)
        self.session = Session()
        self.session.headers.update({
            "User-Agent": "ys-LxClient/1.0",
            "Accept": "application/json, text/plain, */*",
        })
        self.token = str(config.get("api_token") or "")

    @staticmethod
    def _positive_int(value, fallback, minimum, maximum):
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError):
            return fallback

    @property
    def username(self):
        return str(self.config.get("username") or "").strip()

    def _url(self, path):
        return self.base_url + "/" + str(path or "").lstrip("/")

    def _login(self, force=False):
        if self.token and not force:
            return self.token
        username = self.username
        password = str(self.config.get("password") or "")
        if not username or not password:
            raise LxClientError("收藏和私有音源需要配置 lxserver 用户名与密码")
        result = self._request(
            "POST",
            "/api/user/login",
            json_body={"username": username, "password": password},
            use_auth=False,
        )
        if not isinstance(result, dict) or not result.get("success") or not result.get("token"):
            raise LxClientError("lxserver 用户登录失败")
        self.token = str(result["token"])
        return self.token

    def _headers(self, use_auth=False, use_admin=False):
        headers = {}
        if use_auth:
            headers["X-User-Token"] = self._login()
            headers["X-User-Name"] = self.username
        if use_admin:
            headers["X-Frontend-Auth"] = str(self.config.get("admin_password") or "")
        return headers

    def _request(self, method, path, params=None, json_body=None, use_auth=False,
                 use_admin=False, retry_auth=True):
        try:
            response = self.session.request(
                method,
                self._url(path),
                params=params,
                json=json_body,
                headers=self._headers(use_auth, use_admin),
                timeout=self.timeout,
            )
        except RequestException as error:
            raise LxClientError("无法连接 lxserver: %s" % error)

        if response.status_code == 401 and use_auth and retry_auth:
            self.token = ""
            self._login(force=True)
            return self._request(
                method,
                path,
                params=params,
                json_body=json_body,
                use_auth=use_auth,
                use_admin=use_admin,
                retry_auth=False,
            )

        if response.status_code >= 400:
            message = response.text.strip()
            try:
                data = response.json()
                message = data.get("error") or data.get("message") or message
            except (ValueError, AttributeError):
                pass
            raise LxClientError("lxserver 返回 %s: %s" % (response.status_code, message or "请求失败"))

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def ping(self):
        return self._request("GET", "/api/music/config")

    def search(self, source, keyword, search_type="song", page=1, limit=20):
        data = self._request("GET", "/api/music/search", params={
            "source": source,
            "type": search_type,
            "name": keyword,
            "page": page,
            "limit": limit,
        })
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("list", "data", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    def hot_search(self, source):
        return self._request("GET", "/api/music/hotSearch", params={"source": source})

    def leaderboard_boards(self, source):
        return self._request("GET", "/api/music/leaderboard/boards", params={"source": source})

    def leaderboard_list(self, source, board_id, page=1):
        return self._request("GET", "/api/music/leaderboard/list", params={
            "source": source,
            "bangid": board_id,
            "page": page,
        })

    def playlist_list(self, source, sort_id="hot", tag_id="", page=1):
        return self._request("GET", "/api/music/songList/list", params={
            "source": source,
            "sortId": sort_id,
            "tagId": tag_id,
            "page": page,
        })

    def playlist_detail(self, source, playlist_id, page=1):
        return self._request("GET", "/api/music/songList/detail", params={
            "source": source,
            "id": playlist_id,
            "page": page,
        })

    def playlist_search(self, source, keyword, page=1):
        return self._request("GET", "/api/music/songList/search", params={
            "source": source,
            "text": keyword,
            "page": page,
        })

    def artist_detail(self, source, artist_id):
        return self._request("GET", "/api/music/artistDetail", params={
            "source": source,
            "id": artist_id,
        })

    def artist_songs(self, source, artist_id, order="hot"):
        return self._request("GET", "/api/music/artistSongs", params={
            "source": source,
            "id": artist_id,
            "order": order,
        }) or []

    def artist_albums(self, source, artist_id, page=1):
        return self._request("GET", "/api/music/artistAlbums", params={
            "source": source,
            "id": artist_id,
            "page": page,
        })

    def album_songs(self, source, album_id):
        return self._request("GET", "/api/music/albumSongs", params={
            "source": source,
            "id": album_id,
        })

    def music_url(self, song, quality):
        username = self.username
        use_auth = bool(username and username not in ("default", "open", "_open"))
        return self._request(
            "POST",
            "/api/music/url",
            json_body={
                "songInfo": song,
                "quality": quality,
                "enableAutoSwitchApiSource": True,
            },
            use_auth=use_auth,
        )

    def lyric(self, song):
        return self._request(
            "GET",
            "/api/music/lyric",
            params={
                "source": song.get("source") or "",
                "songmid": song.get("songmid") or song.get("songId") or "",
                "songId": song.get("songId") or "",
                "name": song.get("name") or "",
                "singer": song.get("singer") or "",
                "hash": song.get("hash") or "",
                "interval": song.get("interval") or "",
                "copyrightId": song.get("copyrightId") or "",
                "albumId": song.get("albumId") or "",
                "lrcUrl": song.get("lrcUrl") or "",
                "mrcUrl": song.get("mrcUrl") or "",
                "trcUrl": song.get("trcUrl") or "",
            },
            use_auth=bool(self.username),
        )

    def user_data(self):
        data = self._request("GET", "/api/user/list", use_auth=True)
        return data if isinstance(data, dict) else {}

    def favorite_artists(self):
        data = self._request("GET", "/api/user/library/artists", use_auth=True)
        return data if isinstance(data, list) else []

    def favorite_albums(self):
        data = self._request("GET", "/api/user/library/albums", use_auth=True)
        return data if isinstance(data, list) else []

    def source_list(self):
        data = self._request(
            "GET",
            "/api/custom-source/list",
            params={"username": self.username or "default"},
            use_auth=bool(self.username),
            use_admin=True,
        )
        return data if isinstance(data, list) else []

    def source_validate(self, content, allow_unsafe=False):
        return self._request(
            "POST",
            "/api/custom-source/validate",
            json_body={
                "script": content,
                "username": self.username or "default",
                "allowUnsafeVM": bool(allow_unsafe),
            },
            use_auth=bool(self.username),
            use_admin=True,
        )

    def source_upload(self, filename, content, allow_unsafe=False):
        return self._request(
            "POST",
            "/api/custom-source/upload",
            json_body={
                "filename": filename,
                "content": content,
                "username": self.username or "default",
                "allowUnsafeVM": bool(allow_unsafe),
            },
            use_auth=bool(self.username),
            use_admin=True,
        )

    def source_toggle(self, source_id, owner, enabled, allow_unsafe=False):
        username = "default" if owner == "open" else owner
        return self._request(
            "POST",
            "/api/custom-source/toggle",
            json_body={
                "id": source_id,
                "username": username,
                "enabled": bool(enabled),
                "allowUnsafeVM": bool(allow_unsafe),
            },
            use_auth=bool(self.username),
            use_admin=True,
        )

    def source_delete(self, source_id, owner):
        username = "default" if owner == "open" else owner
        return self._request(
            "POST",
            "/api/custom-source/delete",
            json_body={"id": source_id, "username": username},
            use_auth=bool(self.username),
            use_admin=True,
        )

    def source_reorder(self, source_ids):
        return self._request(
            "POST",
            "/api/custom-source/reorder",
            json_body={"username": self.username or "default", "sourceIds": source_ids},
            use_auth=bool(self.username),
            use_admin=True,
        )


class LxMapper:
    """负责 lxserver 实体、Spider Vod 和自描述 ID 的相互转换。"""

    ID_PREFIX = "lxclient"

    @classmethod
    def pack(cls, kind, payload=None):
        raw = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        return "%s:%s:%s" % (cls.ID_PREFIX, kind, body)

    @classmethod
    def unpack(cls, value):
        text = str(value or "")
        parts = text.split(":", 2)
        if len(parts) != 3 or parts[0] != cls.ID_PREFIX:
            return None
        try:
            body = parts[2] + "=" * (-len(parts[2]) % 4)
            data = json.loads(base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8"))
            return {"kind": parts[1], "data": data if isinstance(data, dict) else {}}
        except (ValueError, TypeError, UnicodeError):
            return None

    @staticmethod
    def text(value, fallback=""):
        if value is None or value == "":
            return fallback
        if isinstance(value, list):
            names = [LxMapper.text(item) for item in value]
            return "、".join(item for item in names if item) or fallback
        if isinstance(value, dict):
            for key in ("name", "title", "nickname", "singerName", "artistName", "author"):
                if value.get(key) not in (None, ""):
                    return LxMapper.text(value.get(key), fallback)
            return fallback
        return str(value)

    @staticmethod
    def first(item, keys, fallback=None):
        for key in keys:
            target = item
            for part in key.split("."):
                if not isinstance(target, dict):
                    target = None
                    break
                target = target.get(part)
            if target not in (None, ""):
                return target
        return fallback

    @classmethod
    def song(cls, raw, fallback_source=""):
        item = dict(raw or {})
        meta = item.get("meta")
        if isinstance(meta, dict):
            for key, value in meta.items():
                if item.get(key) in (None, ""):
                    item[key] = value
        source = cls.text(cls.first(item, ["source"], fallback_source))
        songmid = cls.text(cls.first(item, ["songmid", "songId", "id", "copyrightId", "hash"]))
        result = {
            "source": source,
            "songmid": songmid,
            "songId": cls.first(item, ["songId", "id"]),
            "name": cls.text(cls.first(item, ["name", "songName", "title"]), "未知歌曲"),
            "singer": cls.text(cls.first(item, ["singer", "artist", "author"]), "未知歌手"),
            "albumName": cls.text(cls.first(item, ["albumName", "album.name", "album"])),
            "albumId": cls.first(item, ["albumId", "album.id"]),
            "albumMid": cls.first(item, ["albumMid", "album.mid"]),
            "interval": cls.text(cls.first(item, ["interval", "duration"])),
            "img": cls.text(cls.first(item, ["img", "pic", "picUrl", "cover", "coverUrl"])),
            "hash": cls.first(item, ["hash"]),
            "strMediaMid": cls.first(item, ["strMediaMid"]),
            "copyrightId": cls.first(item, ["copyrightId"]),
            "lrcUrl": cls.first(item, ["lrcUrl"]),
            "mrcUrl": cls.first(item, ["mrcUrl"]),
            "trcUrl": cls.first(item, ["trcUrl"]),
            "types": item.get("types") if isinstance(item.get("types"), list) else [],
            "_types": item.get("_types") if isinstance(item.get("_types"), dict) else {},
            "typeUrl": item.get("typeUrl") if isinstance(item.get("typeUrl"), dict) else {},
        }
        if isinstance(meta, dict):
            result["meta"] = meta
        return result

    @classmethod
    def song_vod(cls, raw, fallback_source=""):
        song = cls.song(raw, fallback_source)
        remarks = " · ".join(item for item in (song["singer"], song["albumName"], song["interval"]) if item)
        return {
            "vod_id": cls.pack("song", song),
            "vod_name": song["name"],
            "vod_pic": song["img"],
            "vod_remarks": remarks,
            "vod_actor": song["singer"],
            "vod_content": remarks,
            "vod_player": "music",
            "style": {"type": "rect", "ratio": 1.0},
        }

    @classmethod
    def playlist_vod(cls, raw, fallback_source=""):
        item = dict(raw or {})
        source = cls.text(item.get("source"), fallback_source)
        playlist_id = cls.first(item, ["id", "sourceId", "playListId"])
        name = cls.text(cls.first(item, ["name", "title"]), "未命名歌单")
        pic = cls.text(cls.first(item, ["img", "pic", "picUrl", "cover", "coverUrl"]))
        author = cls.text(cls.first(item, ["author", "creator", "creator.nickname", "username", "userName"]))
        total = cls.first(item, ["total", "songCount", "trackCount", "count"], "")
        desc = cls.text(cls.first(item, ["desc", "description", "intro"]))
        payload = {
            "source": source,
            "id": playlist_id,
            "name": name,
            "pic": pic,
            "author": author,
            "desc": desc,
        }
        return {
            "vod_id": cls.pack("playlist", payload),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": " · ".join(item for item in (author, ("%s 首" % total) if total else "") if item),
            "vod_actor": author,
            "vod_content": desc,
            "vod_player": "music",
            "style": {"type": "rect", "ratio": 1.0},
        }

    @classmethod
    def board_vod(cls, raw, fallback_source=""):
        item = dict(raw or {})
        source = cls.text(item.get("source"), fallback_source)
        board_id = cls.first(item, ["bangid", "id", "sourceId"])
        if isinstance(board_id, str) and board_id.startswith(source + "__"):
            board_id = board_id[len(source) + 2:]
        name = cls.text(cls.first(item, ["name", "title"]), "未命名榜单")
        pic = cls.text(cls.first(item, ["img", "pic", "picUrl", "cover", "coverUrl"]))
        return cls.folder_vod("chart", {"source": source, "id": board_id, "name": name, "pic": pic}, name, pic, SOURCE_NAMES.get(source, source))

    @classmethod
    def album_vod(cls, raw, fallback_source=""):
        """增强的专辑转换，支持更多平台的数据格式"""
        item = dict(raw or {})
        source = cls.text(item.get("source"), fallback_source)
        
        # 更健壮的ID提取 - 支持多种字段名和嵌套结构
        album_id = (
            cls.first(item, ["id", "mid", "albumId", "album_id", "albumMid"]) or
            cls.first(item.get("album", {}), ["id", "mid", "albumId"]) or
            cls.first(item.get("info", {}), ["id", "albumId"]) or
            ""
        )
        
        # 处理腾讯音乐特殊前缀
        if source == "tx" and isinstance(album_id, str) and album_id.startswith("alb_tx_"):
            album_id = album_id[7:]
        
        # 更健壮的名称提取
        name = (
            cls.text(cls.first(item, ["name", "title", "album", "albumName"])) or
            cls.text(cls.first(item.get("album", {}), ["name", "title"])) or
            cls.text(cls.first(item.get("info", {}), ["name", "title"])) or
            cls.text(cls.first(item, ["songName"])) or
            "未命名专辑"
        )
        
        # 更健壮的封面提取
        pic = (
            cls.text(cls.first(item, ["img", "picUrl", "coverArt", "cover", "coverUrl", "pic"])) or
            cls.text(cls.first(item.get("album", {}), ["picUrl", "cover", "img"])) or
            cls.text(cls.first(item.get("info", {}), ["img", "picUrl"])) or
            cls.text(cls.first(item.get("cover", {}), ["url"])) or
            ""
        )
        
        # 更健壮的歌手提取
        singer = (
            cls.text(cls.first(item, ["singer", "artistName", "artist", "artists", "author"])) or
            cls.text(cls.first(item.get("album", {}), ["artistName", "artist", "singer"])) or
            cls.text(cls.first(item.get("info", {}), ["author", "singer"])) or
            ""
        )
        
        # 年份提取
        publish_time = (
            cls.first(item, ["publishTime", "created", "publish_date", "pubDate"]) or
            cls.first(item.get("info", {}), ["publishTime"])
        )
        year = ""
        try:
            if str(publish_time).isdigit() and len(str(publish_time)) >= 10:
                stamp = int(publish_time)
                if len(str(publish_time)) == 10:
                    stamp *= 1000
                year = time.strftime("%Y", time.localtime(stamp / 1000))
            elif publish_time:
                year = str(publish_time)[:4]
        except (ValueError, OSError, OverflowError):
            year = ""
        
        payload = {"source": source, "id": album_id, "name": name, "pic": pic, "singer": singer}
        
        return {
            "vod_id": cls.pack("album", payload),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": " · ".join(item for item in (singer, year) if item),
            "vod_actor": singer,
            "vod_year": year,
            "vod_player": "music",
            "style": {"type": "rect", "ratio": 1.0},
        }

    @classmethod
    def artist_vod(cls, raw, fallback_source=""):
        item = dict(raw or {})
        source = cls.text(item.get("source"), fallback_source)
        artist_id = cls.first(item, ["id", "mid", "artistId"])
        name = cls.text(cls.first(item, ["name", "artistName"]), "未知歌手")
        pic = cls.text(cls.first(item, ["picUrl", "img", "avatar", "pic"]))
        album_size = cls.first(item, ["albumSize", "albumNum"], "")
        remarks = ("%s 张专辑" % album_size) if album_size else SOURCE_NAMES.get(source, source)
        return cls.folder_vod("artist", {"source": source, "id": artist_id, "name": name, "pic": pic}, name, pic, remarks, circle=True)

    @classmethod
    def artist_from_song(cls, raw):
        song = cls.song(raw)
        return cls.folder_vod(
            "artist_query",
            {"name": song["singer"], "source": "wy", "pic": song["img"]},
            song["singer"],
            song["img"],
            "查看歌曲与专辑",
            circle=True,
        )

    @classmethod
    def folder_vod(cls, kind, payload, name, pic="", remarks="", circle=False):
        return {
            "vod_id": cls.pack(kind, payload),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_tag": "folder",
            "cate": {"land": 0 if circle else 1, "circle": 1 if circle else 0, "ratio": 1.0 if circle else 1.78},
        }

    @classmethod
    def action_vod(cls, name, config, remarks="", pic=""):
        return {
            "vod_id": json.dumps(config, ensure_ascii=False, separators=(",", ":")),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_tag": "action",
        }

    @staticmethod
    def clean_episode_name(value):
        return " ".join(str(value or "未知歌曲").replace("#", " ").replace("$", " ").split())

    @classmethod
    def music_detail(cls, entity, raw_songs, config):
        songs = []
        seen = set()
        for raw in raw_songs or []:
            song = cls.song(raw, entity.get("source", ""))
            key = "%s:%s" % (song.get("source"), song.get("songmid"))
            if not song.get("source") or not song.get("songmid") or key in seen:
                continue
            seen.add(key)
            songs.append(song)
        qualities = config.get("qualities") if isinstance(config.get("qualities"), list) else []
        qualities = [item for item in qualities if item in QUALITY_NAMES]
        preferred_quality = str(config.get("quality") or "320k")
        if preferred_quality in QUALITY_NAMES:
            qualities = [preferred_quality] + [item for item in qualities if item != preferred_quality]
        if not qualities:
            qualities = [preferred_quality if preferred_quality in QUALITY_NAMES else "320k"]

        play_from = []
        play_url = []
        for quality in qualities:
            episodes = []
            for song in songs:
                token = cls.pack("play", {"quality": quality, "song": song})
                episodes.append("%s$%s" % (cls.clean_episode_name(song["name"]), token))
            if episodes:
                play_from.append(QUALITY_NAMES.get(quality, quality))
                play_url.append("#".join(episodes))

        # 添加"下载"选项 - 使用 "download" 标记，音质由下载设置决定
        if songs:
            download_episodes = []
            for song in songs:
                token = cls.pack("play", {"quality": "download", "song": song})
                download_episodes.append("%s$%s" % (cls.clean_episode_name(song["name"]), token))
            if download_episodes:
                play_from.append("📥 下载")
                play_url.append("#".join(download_episodes))

        return {
            "vod_id": entity.get("id", ""),
            "vod_name": entity.get("name") or (songs[0]["name"] if songs else "洛雪音乐"),
            "vod_pic": entity.get("pic") or (songs[0]["img"] if songs else ""),
            "vod_remarks": entity.get("remarks") or ("%s 首歌曲" % len(songs)),
            "vod_actor": entity.get("singer") or (songs[0]["singer"] if songs else ""),
            "vod_content": entity.get("content") or entity.get("remarks") or "",
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
            "vod_player": "music",
        }


class LxHomeLayoutBuilder:
    """构建云雾白底与祖母绿点缀的 HomeUI v4 音乐主题。"""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/") + "/"

    @staticmethod
    def _node(node_id, node_type, classes=None, source="", title="", subtitle="",
              items=None, attributes=None, slot="", action="", children=None, icon=None,
              states=None):
        node = {"id": node_id, "type": node_type}
        if classes:
            node["classes"] = classes
        if source:
            node["source"] = source
        if title:
            node["title"] = title
        if subtitle:
            node["subtitle"] = subtitle
        if items is not None:
            node["list"] = list(items)[:60]
        if attributes:
            node["attributes"] = {str(key): str(value) for key, value in attributes.items()}
        if slot:
            node["slot"] = slot
        if action:
            node["action"] = action
        if children is not None:
            node["children"] = children
        if icon is not None:
            node["icon"] = icon
        if states:
            node["states"] = states
        return node

    @staticmethod
    def _navigation_items(prefix=""):
        """统一生成可自定义激活色/激活图标的点播底部或 TV 侧栏入口。"""
        values = [
            ("vod", "点播", "music", "lx-vod", True),
            ("live", "直播", "live", "lx-live", False),
            ("setting", "设置", "settings", "lx-settings", False),
        ]
        result = []
        for key, title, icon, action, selected in values:
            result.append({
                "id": "%s-%s" % (prefix, key) if prefix else key,
                "type": "action_button",
                "classes": ["lx-tab"],
                "text": title,
                "icon": {"name": icon, "active_name": icon,
                         "tint": "#FF6B7280", "active_tint": "#FF059669"},
                "action": action,
                "attributes": {"role": "tab", "selected": "true" if selected else "false"},
                "states": {
                    "selected": {"color": "#FF059669", "icon-color": "#FF059669",
                                  "background": "#1910B981"},
                    "focused": {"color": "#FF059669", "icon-color": "#FF059669"},
                },
            })
        return result

    def _shortcuts(self, data):
        web_action = LxMapper.action_vod("洛雪网页", {
            "actionId": "lx_open_web",
            "type": "webview",
            "title": "洛雪音乐",
            "url": self.base_url,
            "height": -80,
            "textZoom": 90,
        }, "打开本机 lxserver")
        import_action = LxMapper.action_vod("导入音源", {
            "actionId": "lx_import_source",
            "type": "multiInput",
            "title": "导入 JS 音源",
            "msg": "选择本地 JS 文件，校验后上传到 lxserver。",
            "input": [
                {"id": "file", "name": "JS 音源文件", "tip": "请选择 .js 文件", "value": "", "selectData": "[file]"},
                {"id": "unsafe", "name": "允许不安全 VM", "tip": "一般保持否", "value": "否", "selectData": "否:=否,是:=是"},
            ],
        }, "选择本地 JS 文件")
        settings_action = LxMapper.action_vod("连接设置", {
            "actionId": "lx_connection_settings",
            "type": "multiInput",
            "title": "lxserver 连接设置",
            "msg": "设置会保存到当前站点，重新打开后仍然生效。",
            "input": data.get("settings_inputs") or [],
        }, "服务器地址、用户与默认平台")
        return [
            web_action,
            LxMapper.folder_vod("shortcut", {"target": "charts"}, "排行榜", "", "多平台榜单"),
            LxMapper.folder_vod("shortcut", {"target": "playlists"}, "歌单广场", "", "发现新歌单"),
            LxMapper.folder_vod("shortcut", {"target": "favorites"}, "我的收藏", "", "歌曲、专辑、歌手"),
            LxMapper.folder_vod("shortcut", {"target": "sources"}, "音源管理", "", "启停、排序与删除"),
            import_action,
            settings_action,
        ]

    @staticmethod
    def _css():
        return """
:root{--accent:#FF10B981;--accent-strong:#FF047857;--page:#FFFCFDFC;--panel:#FFFFFFFF;--soft:#FFF1F9F6;--hover:#FFF5FAF8;--text:#FF173129;--muted:#FF64766E;--line:#FFE5EFEB}
page{display:flex;color:var(--text);background:transparent;font-family:sans;font-size:13sp}
.lx-header{color:var(--text);font-size:17sp;font-weight:700;background:transparent}
.lx-nav,.lx-player{background:#EFFFFFFF;background-blur:18dp;border-color:var(--line)}
.lx-feed{display:flex;flex-direction:column;padding:10dp 14dp 154dp}
.lx-status{margin-top:4dp;margin-bottom:6dp;padding-inline:18dp;padding-block:15dp;section-radius:22dp;section-background:linear-gradient(135deg,#FF10B981,#FF047857);section-border:0dp solid transparent;color:#FFFFFFFF;heading-color:#FFFFFFFF;heading-size:22sp;heading-weight:700;meta-color:#E6FFFFFF;meta-font-size:13sp;meta-weight:normal;box-shadow:0dp 12dp 30dp #2410B981;animation:lx-enter 420ms ease-out both}
.lx-section{margin-top:4dp;margin-bottom:4dp;padding-inline:0dp;padding-top:0dp;padding-bottom:0dp;section-background:transparent;section-border:0dp solid transparent;heading-color:var(--text);heading-size:18sp;heading-weight:700;color:var(--text);font-size:13sp;font-weight:600;meta-color:var(--muted);meta-font-size:11sp;meta-weight:normal;title-lines:1;meta-lines:1}
.lx-shortcuts{orientation:horizontal;viewport-count:2.65;gap:8dp;item-height:64dp;item-ratio:2.7;card-padding:7dp;card-radius:16dp;card-background:var(--panel);card-border:1dp solid var(--line);show-meta:false;font-size:12sp}
.lx-hero{item-ratio:1.78;card-radius:20dp;card-background:transparent;card-border:0dp solid transparent;color:#FFFFFFFF;heading-color:var(--text);font-size:14sp;meta-color:#E8FFFFFF;meta-font-size:11sp;background-dim:.76;box-shadow:0dp 12dp 28dp #2010B981}
.lx-hot{orientation:horizontal;viewport-count:3.05;gap:8dp;item-height:42dp;item-ratio:3.6;card-padding:9dp;card-radius:999dp;card-background:var(--soft);card-border:1dp solid #FFD5EEE5;color:#FF176B55;font-size:12sp;show-image:false;show-meta:false;title-lines:1}
.lx-hot:selected{color:#FFFFFFFF;card-background:var(--accent)}
.lx-albums{orientation:horizontal;viewport-count:2.75;gap:12dp;item-ratio:1;card-padding:0dp;card-radius:14dp;card-background:transparent;card-border:0dp solid transparent;font-size:12sp;meta-font-size:10sp}
.lx-songs{orientation:horizontal;rows:4;viewport-count:1;gap:7dp;item-height:66dp;item-ratio:5.2;card-padding:7dp;card-radius:14dp;card-background:var(--panel);card-border:1dp solid var(--line);font-size:13sp;meta-font-size:10sp}
.lx-artists{orientation:horizontal;viewport-count:4.15;gap:12dp;item-ratio:1;card-padding:0dp;card-radius:999dp;card-background:transparent;card-border:0dp solid transparent;clip-shape:circle;text-align:center;font-size:11sp;show-meta:false}
.lx-ranking{orientation:horizontal;rows:3;viewport-count:1;gap:7dp;item-height:66dp;item-ratio:5;card-padding:7dp;card-radius:14dp;card-background:var(--panel);card-border:1dp solid var(--line);rank-font-size:14sp;font-size:13sp;meta-font-size:10sp}
.lx-bento{display:grid;grid-columns:2;grid-rows:3;gap:12dp;item-ratio:1;card-radius:16dp;card-background:var(--panel);card-border:1dp solid var(--line);mosaic-spans:2x2,1x1,1x1,2x1}
.lx-tab{color:#FF6B7280;icon-color:#FF6B7280;font-size:11sp;border-radius:18dp;transition:background 180ms ease-out,color 180ms ease-out,scale 160ms ease-out}
.lx-tab:selected{color:var(--accent-strong);icon-color:var(--accent-strong);background:#1910B981;scale:1.03}
.lx-player{position:fixed;left:14dp;right:14dp;bottom:84dp;height:60dp;border-radius:18dp;color:var(--text);box-shadow:0dp 10dp 26dp #1F10B981;z-index:24}
.lx-player:playing{color:var(--accent);icon-color:var(--accent);animation:lx-breathe 1500ms ease-in-out infinite}
.card:pressed{scale:.97;opacity:.88}
@media (orientation:landscape) and (max-width:959dp){.lx-feed{padding-left:94dp;padding-right:22dp}.lx-nav{orientation:vertical;position:fixed;left:10dp;top:72dp;bottom:14dp;width:70dp;border-radius:22dp}.lx-player{left:94dp;bottom:16dp}.lx-shortcuts{viewport-count:4.2}.lx-albums{viewport-count:5.2}.lx-artists{viewport-count:7.2}}
@media (tv){.lx-feed{padding:34dp 68dp 118dp 180dp}.lx-section{heading-size:26sp;font-size:18sp;meta-font-size:14sp}.lx-nav{orientation:vertical;position:fixed;left:34dp;top:96dp;bottom:34dp;width:110dp;border-radius:28dp}.lx-hero{item-ratio:2.5}.lx-albums{viewport-count:6.2;gap:20dp}.lx-songs{rows:3;viewport-count:2;gap:12dp;item-height:88dp}.lx-ranking{rows:2;viewport-count:3;item-height:88dp}.lx-artists{viewport-count:8.2}.lx-bento{grid-columns:6;grid-rows:2;gap:20dp}.lx-player{left:180dp;right:68dp;bottom:28dp;height:76dp}.card:focused{scale:1.06;border:3dp solid var(--accent);elevation:14dp}}
@media (prefers-reduced-motion:reduce){.card,.lx-tab,.lx-status,.lx-player{animation:none;transition:none}}
""".strip()

    def build(self, data):
        songs = (data.get("songs") or [])[:24]
        playlists = (data.get("playlists") or [])[:18]
        albums = (data.get("albums") or [])[:16]
        artists = (data.get("artists") or [])[:16]
        boards = (data.get("boards") or [])[:14]
        hot = (data.get("hot") or [])[:18]
        favorite_songs = (data.get("favorite_songs") or [])[:18]
        favorite_albums = (data.get("favorite_albums") or [])[:14]
        favorite_artists = (data.get("favorite_artists") or [])[:14]
        shortcuts = self._shortcuts(data)
        server_text = "已连接 lxserver · 发现你的下一首歌" if data.get("server_ok") else "尚未连接 lxserver · 请检查连接设置"

        mobile_content = [
            self._node("lx-mobile-status", "headline", ["lx-status"], title="洛雪音乐",
                       subtitle=server_text),
            self._node("lx-mobile-shortcuts", "shortcuts", ["lx-section", "lx-shortcuts"], source="inline",
                       title="音乐控制台", items=shortcuts, attributes={"limit": 7, "show-meta": "false"}),
            self._node("lx-mobile-hero", "spotlight", ["lx-section", "lx-hero"], source="inline",
                       title="现在流行",
                       items=songs[:5], attributes={"limit": 5, "autoplay-ms": 6500,
                                                   "show-indicator": "true",
                                                   "wallpaper-source": "selected-media"}),
            self._node("lx-mobile-hot", "chip_cloud", ["lx-section", "lx-hot"], source="inline",
                       title="大家都在搜", items=hot,
                       attributes={"limit": 18, "show-meta": "false"}),
            self._node("lx-mobile-favorites", "song_list", ["lx-section", "lx-songs"], source="inline",
                       title="我喜欢的音乐", subtitle="直接读取 lxserver 收藏",
                       items=favorite_songs, attributes={"limit": 18, "empty-text": "收藏歌曲后会出现在这里"}),
            self._node("lx-mobile-playlists", "album_shelf", ["lx-section", "lx-albums"], source="inline",
                       title="精选歌单", items=playlists, attributes={"limit": 18, "show-meta": "true"}),
            self._node("lx-mobile-albums", "cover_flow", ["lx-section", "lx-albums"], source="inline",
                       title="专辑唱片架", items=favorite_albums + albums,
                       attributes={"limit": 18, "show-meta": "true"}),
            self._node("lx-mobile-artists", "artist_rail", ["lx-section", "lx-artists"], source="inline",
                       title="热门音乐人", items=favorite_artists + artists,
                       attributes={"limit": 16}),
            self._node("lx-mobile-songs", "song_list", ["lx-section", "lx-songs"], source="inline",
                       title="热歌速递", items=songs[5:] or songs,
                       attributes={"limit": 18, "show-badge": "true"}),
            self._node("lx-mobile-ranking", "ranking", ["lx-section", "lx-ranking"], source="inline",
                       title="在线排行榜", items=boards, attributes={"limit": 14})
        ]

        tv_content = [
            self._node("lx-tv-status", "headline", ["lx-status"], title="LX MUSIC SERVER",
                       subtitle=server_text),
            self._node("lx-tv-hero", "hero", ["lx-hero"], source="inline",
                       title="今晚播放", items=songs[:6],
                       attributes={"limit": 6, "wallpaper-source": "focused-media"}),
            self._node("lx-tv-bento", "bento_grid", ["lx-bento"], source="inline",
                       title="精选歌单", items=playlists[:10],
                       attributes={"limit": 10, "wallpaper-source": "focused-media"}),
            self._node("lx-tv-favorites", "song_list", ["lx-songs"], source="inline",
                       title="我喜欢的音乐", items=favorite_songs,
                       attributes={"limit": 18, "empty-text": "暂无收藏歌曲"}),
            self._node("lx-tv-albums", "album_shelf", ["lx-albums"], source="inline",
                       title="专辑唱片架", items=favorite_albums + albums,
                       attributes={"limit": 18}),
            self._node("lx-tv-ranking", "ranking", ["lx-ranking"], source="inline",
                       title="多平台榜单", items=boards, attributes={"limit": 14}),
            self._node("lx-tv-artists", "artist_rail", ["lx-artists"], source="inline",
                       title="音乐人", items=favorite_artists + artists, attributes={"limit": 16})
        ]

        actions = [
            {"id": "lx-vod", "command": "system.vod"},
            {"id": "lx-search", "command": "system.search"},
            {"id": "lx-settings", "command": "system.settings"},
            {"id": "lx-live", "command": "system.live"},
            {"id": "lx-site", "command": "system.site"},
            {"id": "lx-history", "command": "system.history"},
            {"id": "lx-favorite", "command": "system.favorite"},
            {"id": "lx-player-open", "command": "player.open"},
            {"id": "lx-player-toggle", "command": "player.play_pause"},
            {"id": "lx-player-prev", "command": "player.previous"},
            {"id": "lx-player-next", "command": "player.next"},
        ]

        theme = {
            "name": "lx-cloud-emerald", "mode": "light",
            "variables": {
                "--accent": "#FF10B981", "--accent-strong": "#FF059669",
                "--page": "#FFFCFDFC", "--panel": "#FFFFFFFF",
                "--mist": "#FFF1F9F6",
            },
            "properties": {"font-family": "rounded", "content-max-width": "1760dp"},
            "backgrounds": [
                {"type": "solid", "color": "#FFFCFDFC", "media": "light"},
                {"type": "gradient", "color": "#FFFFFFFF", "color_end": "#FFEEF7F4",
                 "angle": 145, "opacity": 0.48, "media": "light"},
                {"type": "gradient", "color": "#FFF4FBF9", "color_end": "#FFFFFFFF",
                 "angle": 28, "opacity": 0.38, "media": "light"},
                {"type": "gradient", "color": "#FFF3F6FC", "color_end": "#FFFFFFFF",
                 "angle": 315, "opacity": 0.28, "media": "light"},
            ],
        }

        return {
            "version": 4,
            "document": {
                "id": "lx-emerald-player",
                "default_profile": "mobile",
                "variables": {
                    "--accent": "#FF10B981", "--accent-strong": "#FF059669",
                    "--page": "#FFFCFDFC", "--panel": "#FFFFFFFF",
                    "--hover": "#FFF5FAF8", "--text": "#FF173129",
                    "--muted": "#FF64766E", "--line": "#FFE5EFEB",
                },
                "theme": theme,
                "shell": {
                    "edge_to_edge": True,
                    "status_bar": {"visible": True, "style": "auto", "color": "#00FFFFFF"},
                    "navigation_bar": {"visible": True, "style": "auto", "color": "#F8FFFFFF"},
                    "backgrounds": [],
                },
                "styles": {
                    "css": self._css(),
                    "keyframes": [
                        {"name": "lx-enter", "frames": [
                            {"offset": "from", "declarations": {
                                "opacity": "0", "translate-y": "14dp", "scale": ".98"}},
                            {"offset": "to", "declarations": {
                                "opacity": "1", "translate-y": "0dp", "scale": "1"}},
                        ]},
                        {"name": "lx-breathe", "frames": [
                            {"offset": "0%", "declarations": {"opacity": ".78", "scale": ".99"}},
                            {"offset": "50%", "declarations": {"opacity": "1", "scale": "1.03"}},
                            {"offset": "100%", "declarations": {"opacity": ".78", "scale": ".99"}},
                        ]},
                    ],
                },
                "motion": {
                    "enabled": True,
                    "transitions": [
                        {"selector": ".card", "property": "scale",
                         "duration_ms": 180, "easing": "ease-out"},
                        {"selector": ".lx-player", "property": "background",
                         "duration_ms": 420, "easing": "ease-in-out"},
                    ],
                },
                "actions": actions,
                "profiles": {
                    "mobile": {
                        "enabled": True,
                        "canvas": {
                            "edge_to_edge": True, "clip_to_bounds": False,
                            "safe_area": "system", "backgrounds": [],
                        },
                        "chrome": {
                            "top": {
                                "enabled": True, "height": 58, "position": "sticky",
                                "logo": {"name": "music", "tint": "#FF10B981",
                                         "active_tint": "#FF059669"},
                                "title": "洛雪音乐",
                                "items": [
                                    {"id": "lx-mobile-search-item", "title": "搜索",
                                     "icon": {"name": "search", "tint": "#FF4B5563"},
                                     "action": "lx-search"},
                                    {"id": "lx-mobile-settings-item", "title": "设置",
                                     "icon": {"name": "settings", "tint": "#FF4B5563"},
                                     "action": "lx-settings"},
                                ],
                                "backgrounds": [{"type": "solid", "color": "#EFFFFFFF",
                                                 "opacity": 0.94}],
                            },
                            "bottom": {
                                "enabled": True, "height": 72, "position": "fixed",
                                "backgrounds": [{"type": "solid", "color": "#EFFFFFFF",
                                                 "opacity": 0.94}],
                            },
                            "floating": {
                                "enabled": True, "height": 70, "position": "fixed",
                                "backgrounds": [],
                            },
                        },
                        "nodes": [
                            self._node("lx-mobile-page", "page", children=[
                                self._node("lx-mobile-header", "top_bar", ["lx-header"],
                                           slot="top"),
                                self._node("lx-mobile-feed", "container", ["lx-feed"],
                                           slot="content", children=mobile_content),
                                self._node("lx-mobile-player", "mini_player", ["lx-player"],
                                           slot="floating", action="lx-player-open",
                                           attributes={"wallpaper-source": "playing-media",
                                                       "empty-text": "选择一首歌开始播放"}),
                                self._node("lx-mobile-nav", "bottom_tabs", ["lx-nav", "lx-tab"],
                                           slot="bottom", attributes={"role": "tablist"},
                                           children=self._navigation_items()),
                            ])
                        ],
                    },
                    "tv": {
                        "enabled": True,
                        "canvas": {
                            "edge_to_edge": True, "clip_to_bounds": False,
                            "safe_area": "system", "backgrounds": [],
                        },
                        "chrome": {
                            "top": {
                                "enabled": True, "height": 76, "position": "sticky",
                                "logo": {"name": "music", "tint": "#FF10B981"},
                                "title": "洛雪音乐",
                                "items": [
                                    {"id": "lx-tv-search-item", "title": "搜索",
                                     "icon": {"name": "search", "tint": "#FF4B5563"},
                                     "action": "lx-search"},
                                    {"id": "lx-tv-settings-item", "title": "设置",
                                     "icon": {"name": "settings", "tint": "#FF4B5563"},
                                     "action": "lx-settings"},
                                ],
                                "backgrounds": [{"type": "solid", "color": "#EFFFFFFF",
                                                 "opacity": 0.94}],
                            },
                            "bottom": {"enabled": False},
                            "floating": {
                                "enabled": True, "height": 84, "position": "fixed",
                                "backgrounds": [],
                            },
                        },
                        "nodes": [
                            self._node("lx-tv-page", "page", children=[
                                self._node("lx-tv-header", "top_bar", ["lx-header"],
                                           slot="top"),
                                self._node("lx-tv-nav", "side_tabs", ["lx-nav", "lx-tab"],
                                           slot="bottom", attributes={"role": "tablist"},
                                           children=self._navigation_items("lx-tv")),
                                self._node("lx-tv-feed", "container", ["lx-feed"],
                                           slot="content", children=tv_content),
                                self._node("lx-tv-player", "mini_player", ["lx-player"],
                                           slot="floating", action="lx-player-open",
                                           attributes={"wallpaper-source": "playing-media",
                                                       "empty-text": "暂无播放"}),
                            ])
                        ],
                    },
                },
            },
        }


class Spider(BaseSpider):
    """ys Spider 入口。"""

    def __init__(self):
        super().__init__()
        self.config = deepcopy(DEFAULT_CONFIG)
        self.client = LxHttpClient(self.config)
        self.settings_path = ""
        self.home_cache = None
        self.home_cache_at = 0
        self.search_keyword = ""
        self.search_source = ""  # 搜索时选中的平台

    def getName(self):
        return "洛雪音乐"

    def init(self, extend=""):
        self.settings_path = self._settings_path()
        options = self._parse_options(extend)
        options.update(self._load_settings())
        self._apply_options(options)

    def _settings_path(self):
        """按站点隔离配置文件，Android 使用应用私有 filesDir。"""
        site_key = str(getattr(self, "siteKey", "") or self.getName() or "lxclient")
        digest = hashlib.sha256(site_key.encode("utf-8")).hexdigest()[:20]
        root = os.environ.get("YS_LXCLIENT_CONFIG_DIR", "").strip()
        if not root:
            try:
                from com.chaquo.python import Python
                root = str(Python.getPlatform().getApplication().getFilesDir().getAbsolutePath())
            except Exception:
                root = os.path.join(os.path.expanduser("~"), ".ys")
        return os.path.join(root, "lxclient", "config-%s.json" % digest)

    def _load_settings(self):
        if not self.settings_path or not os.path.isfile(self.settings_path):
            return {}
        try:
            if os.path.getsize(self.settings_path) > 256 * 1024:
                return {}
            with open(self.settings_path, "r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_settings(self):
        if not self.settings_path:
            return False
        directory = os.path.dirname(self.settings_path)
        temporary = self.settings_path + ".tmp"
        try:
            os.makedirs(directory, exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as settings_file:
                json.dump(self.config, settings_file, ensure_ascii=False, separators=(",", ":"))
                settings_file.flush()
                try:
                    os.fsync(settings_file.fileno())
                except OSError:
                    pass
            os.replace(temporary, self.settings_path)
            return True
        except (OSError, TypeError, ValueError):
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                pass
            return False

    @staticmethod
    def _parse_options(value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            data = json.loads(str(value))
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {"base_url": str(value)} if str(value).startswith("http") else {}

    @staticmethod
    def _list_value(value, fallback):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            result = [item.strip() for item in value.split(",") if item.strip()]
            return result or fallback
        return fallback

    def _apply_options(self, options):
        aliases = {"server": "base_url", "url": "base_url", "user": "username", "token": "api_token"}
        normalized = dict(options or {})
        for source_key, target_key in aliases.items():
            if source_key in normalized and target_key not in normalized:
                normalized[target_key] = normalized[source_key]
        for key in DEFAULT_CONFIG:
            if key in normalized:
                self.config[key] = normalized[key]
        self.config["sources"] = self._list_value(self.config.get("sources"), DEFAULT_CONFIG["sources"])
        self.config["qualities"] = self._list_value(self.config.get("qualities"), DEFAULT_CONFIG["qualities"])
        self.config["base_url"] = str(self.config.get("base_url") or DEFAULT_CONFIG["base_url"]).rstrip("/")
        self.client = LxHttpClient(self.config)
        self.home_cache = None
        self.home_cache_at = 0

    def _settings_inputs(self):
        return [
            {"id": "base_url", "name": "服务器地址", "tip": "例如 http://127.0.0.1:9527", "value": self.config["base_url"]},
            {"id": "username", "name": "用户名", "tip": "用于收藏和私有音源", "value": str(self.config.get("username") or "")},
            {"id": "password", "name": "用户密码", "tip": "用于换取临时 Token", "value": str(self.config.get("password") or ""), "inputType": 129},
            {"id": "api_token", "name": "已有 Token", "tip": "可选，填写后优先使用；留空则自动登录", "value": str(self.config.get("api_token") or ""), "inputType": 129},
            {"id": "admin_password", "name": "管理密码", "tip": "管理公开音源或 unsafe VM", "value": str(self.config.get("admin_password") or ""), "inputType": 129},
            {"id": "source", "name": "默认歌曲平台", "value": str(self.config.get("source") or "kw"), "selectData": "酷我:=kw,酷狗:=kg,QQ:=tx,网易:=wy,咪咕:=mg"},
            {"id": "playlist_source", "name": "首页歌单平台", "value": str(self.config.get("playlist_source") or "wy"), "selectData": "网易:=wy,QQ:=tx,酷我:=kw,酷狗:=kg,咪咕:=mg"},
            {"id": "quality", "name": "默认音质", "value": str(self.config.get("quality") or "320k"), "selectData": "标准:=128k,高品:=320k,无损:=flac,Hi-Res:=flac24bit"},
            {"id": "download_folder", "name": "下载文件夹", "tip": "选择歌曲下载保存位置", "value": str(self.config.get("download_folder") or ""), "selectData": "[folder]"},
            {"id": "download_quality", "name": "下载音质", "value": str(self.config.get("download_quality") or "320k"), "selectData": "标准:=128k,高品:=320k,无损:=flac,Hi-Res:=flac24bit"},
            {"id": "auto_download", "name": "自动下载", "value": str(self.config.get("auto_download") or "否"), "selectData": "否:=否,是:=是"},
        ]

    @staticmethod
    def _source_values():
        return [{"n": name, "v": source} for source, name in SOURCE_NAMES.items()]

    def _classes(self):
        return [
            {"type_id": "song_search", "type_name": "搜索歌曲", "type_flag": "1", "land": 1, "ratio": 1.78},
            {"type_id": "charts", "type_name": "排行榜", "type_flag": "1", "land": 1, "ratio": 1.78},
            {"type_id": "playlists", "type_name": "歌单广场", "land": 1, "ratio": 1.0},
            {"type_id": "local_songs", "type_name": "🎵 本地歌曲", "land": 1, "ratio": 1.0},
            {"type_id": "favorites", "type_name": "我的收藏", "type_flag": "1", "land": 1, "ratio": 1.0},
            {"type_id": "account", "type_name": "用户账号", "type_flag": "1", "land": 1, "ratio": 1.78},
            {"type_id": "sources", "type_name": "音源管理", "type_flag": "1", "land": 1, "ratio": 1.78},
        ]

    def _filters(self):
        """筛选器配置 - song_search 的筛选器必须配置正确"""
        return {
            "charts": [{
                "key": "source", "name": "平台", "init": str(self.config.get("source") or "kw"),
                "value": self._source_values(),
            }],
            "playlists": [
                {
                    "key": "source", "name": "平台", "init": str(self.config.get("source") or "kw"),
                    "value": self._source_values(),
                },
                {
                    "key": "sort", "name": "排序", "init": "hot",
                    "value": [{"n": "最热", "v": "hot"}, {"n": "最新", "v": "new"}, {"n": "推荐", "v": "recommend"}],
                },
                {
                    "key": "tag", "name": "标签", "init": "",
                    "value": [
                        {"n": "全部", "v": ""}, {"n": "华语", "v": "华语"}, {"n": "欧美", "v": "欧美"},
                        {"n": "流行", "v": "流行"}, {"n": "摇滚", "v": "摇滚"}, {"n": "民谣", "v": "民谣"},
                        {"n": "电子", "v": "电子"}, {"n": "轻音乐", "v": "轻音乐"}, {"n": "ACG", "v": "ACG"},
                    ],
                },
            ],
            "local_songs": [
                {
                    "key": "delete_mode", "name": "删除模式", "init": "off",
                    "value": [{"n": "🔒 关闭", "v": "off"}, {"n": "🗑️ 开启删除", "v": "on"}],
                }
            ],
            "song_search": [
                {
                    "key": "source", 
                    "name": "平台", 
                    "init": str(self.config.get("source") or "kw"),
                    "value": self._source_values(),
                }
            ],
        }

    @staticmethod
    def _extract_list(data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("list"), list):
            return data["list"]
        return []

    def _favorites(self):
        result = {"songs": [], "albums": [], "artists": [], "user_lists": [], "error": ""}
        try:
            user_data = self.client.user_data()
            result["songs"] = user_data.get("loveList") if isinstance(user_data.get("loveList"), list) else []
            result["user_lists"] = user_data.get("userList") if isinstance(user_data.get("userList"), list) else []
            result["albums"] = self.client.favorite_albums()
            result["artists"] = self.client.favorite_artists()
        except LxClientError as error:
            result["error"] = str(error)
        return result

    @staticmethod
    def _page_number(value):
        try:
            return max(int(value or 1), 1)
        except (TypeError, ValueError):
            return 1

    def _load_home(self, force=False):
        ttl = LxHttpClient._positive_int(self.config.get("home_ttl"), 180, 30, 3600)
        if not force and self.home_cache and time.time() - self.home_cache_at < ttl:
            return self.home_cache
        data = {
            "server_ok": False,
            "playlists": [],
            "songs": [],
            "albums": [],
            "artists": [],
            "boards": [],
            "hot": [],
            "favorite_songs": [],
            "favorite_albums": [],
            "favorite_artists": [],
            "favorite_user_lists": [],
            "settings_inputs": self._settings_inputs(),
            "error": "",
        }
        try:
            self.client.ping()
            data["server_ok"] = True
        except LxClientError as error:
            data["error"] = str(error)
            self.home_cache = data
            self.home_cache_at = time.time()
            return data

        errors = []
        playlist_source = str(self.config.get("playlist_source") or "wy")
        try:
            raw_playlists = self.client.playlist_list(
                playlist_source,
                SORT_IDS.get(playlist_source, {}).get("hot", "hot"),
                "",
                1,
            )
            data["playlists"] = [LxMapper.playlist_vod(item, playlist_source) for item in self._extract_list(raw_playlists)[:15]]
        except LxClientError as error:
            errors.append("歌单: %s" % error)

        board_source = str(self.config.get("source") or "kw")
        board_items = []
        try:
            raw_boards = self.client.leaderboard_boards(board_source)
            board_items = self._extract_list(raw_boards)
            data["boards"] = [LxMapper.board_vod(item, board_source) for item in board_items[:12]]
        except LxClientError as error:
            errors.append("榜单: %s" % error)

        if board_items:
            board_id = LxMapper.first(board_items[0], ["bangid", "id"])
            if isinstance(board_id, str) and board_id.startswith(board_source + "__"):
                board_id = board_id[len(board_source) + 2:]
            song_items = []
            try:
                raw_songs = self.client.leaderboard_list(board_source, board_id, 1)
                song_items = self._extract_list(raw_songs)[:24]
                data["songs"] = [LxMapper.song_vod(item, board_source) for item in song_items]
            except LxClientError as error:
                errors.append("榜单歌曲: %s" % error)

            seen_artists = set()
            artists = []
            for item in song_items:
                name = LxMapper.song(item, board_source).get("singer")
                if not name or name in seen_artists:
                    continue
                seen_artists.add(name)
                artists.append(LxMapper.artist_from_song(item))
                if len(artists) >= 12:
                    break
            data["artists"] = artists

            album_keyword = LxMapper.song(song_items[0], board_source).get("singer") if song_items else "周杰伦"
            album_source = str(self.config.get("album_source") or "wy")
            try:
                raw_albums = self.client.search(album_source, album_keyword, "album", 1, 12)
                data["albums"] = [LxMapper.album_vod(item, album_source) for item in raw_albums[:12]]
            except LxClientError as error:
                errors.append("专辑: %s" % error)

        try:
            raw_hot = self.client.hot_search(board_source)
            hot_items = raw_hot.get("list") if isinstance(raw_hot, dict) else raw_hot
            if isinstance(hot_items, list):
                for item in hot_items[:18]:
                    keyword = item if isinstance(item, str) else LxMapper.first(item, ["keyword", "searchWord", "word", "name"])
                    if keyword:
                        data["hot"].append(LxMapper.folder_vod("keyword", {"keyword": str(keyword)}, str(keyword), "", "热门搜索"))
        except LxClientError as error:
            errors.append("热搜: %s" % error)

        favorites = self._favorites()
        data["favorite_songs"] = [LxMapper.song_vod(item, str(self.config.get("source") or "kw")) for item in favorites["songs"][:15]]
        data["favorite_albums"] = [LxMapper.album_vod(item, str(self.config.get("album_source") or "wy")) for item in favorites["albums"][:12]]
        data["favorite_artists"] = [LxMapper.artist_vod(item, str(self.config.get("source") or "kw")) for item in favorites["artists"][:12]]
        data["favorite_user_lists"] = favorites["user_lists"]
        if favorites["error"]:
            errors.append("收藏: %s" % favorites["error"])
        data["error"] = "；".join(errors)
        self.home_cache = data
        self.home_cache_at = time.time()
        return data

    def homeContent(self, filter):
        """首页只显示分类，不显示推荐内容"""
        return {
            "class": self._classes(),
            "filters": self._filters(),
            "list": [],
        }

    def homeLayout(self):
        data = self._load_home()
        return LxHomeLayoutBuilder(self.config["base_url"]).build(data)

    def homeVideoContent(self):
        """首页推荐内容为空"""
        return {"list": []}

    def _page_result(self, items, page, limit=30, total=None):
        try:
            total = len(items) if total is None else max(int(total), 0)
        except (TypeError, ValueError):
            total = len(items)
        try:
            limit = max(int(limit), 1)
        except (TypeError, ValueError):
            limit = max(len(items), 1)
        pagecount = max(page, (total + limit - 1) // limit) if total else page
        return {"list": items, "page": page, "pagecount": pagecount, "limit": limit, "total": total}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容 - song_search 分支从筛选器获取平台"""
        page = self._page_number(pg)
        options = self._parse_options(extend)

        if tid == "song_search":
            # 从筛选器获取平台，如果没有则使用默认
            source = str(options.get("source") or self.config.get("source") or "kw")
            # 保存到实例变量供搜索使用
            self.search_source = source
            return self._search_root()

        if tid == "local_songs":
            delete_mode = str(options.get("delete_mode") or "off") == "on"
            return self._local_songs_root(delete_mode=delete_mode)

        ref = LxMapper.unpack(tid)
        if ref:
            return self._category_ref(ref["kind"], ref["data"], page)
        if tid == "charts":
            source = str(options.get("source") or self.config.get("source") or "kw")
            data = self.client.leaderboard_boards(source)
            items = [LxMapper.board_vod(item, source) for item in self._extract_list(data)]
            return self._page_result(items, 1, max(len(items), 1), len(items))
        if tid == "playlists":
            source = str(options.get("source") or self.config.get("source") or "kw")
            sort_name = str(options.get("sort") or "hot")
            sort_id = SORT_IDS.get(source, {}).get(sort_name, SORT_IDS.get(source, {}).get("hot", "hot"))
            tag_id = str(options.get("tag") or "") if source == "wy" else ""
            data = self.client.playlist_list(source, sort_id, tag_id, page)
            raw_items = self._extract_list(data)
            items = [LxMapper.playlist_vod(item, source) for item in raw_items]
            total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
            limit = data.get("limit", max(len(items), 1)) if isinstance(data, dict) else max(len(items), 1)
            return self._page_result(items, page, limit, total)
        if tid == "favorites":
            return self._favorite_root()
        if tid == "account":
            return self._account_root()
        if tid == "sources":
            return self._source_category()
        return self._page_result([], page)

    def _category_ref(self, kind, data, page):
        if kind == "shortcut":
            return self.categoryContent(data.get("target", ""), str(page), False, {})
        if kind == "chart":
            result = self.client.leaderboard_list(data.get("source"), data.get("id"), page)
            items = [LxMapper.song_vod(item, data.get("source")) for item in self._extract_list(result)]
            total = result.get("total", len(items)) if isinstance(result, dict) else len(items)
            limit = result.get("limit", max(len(items), 1)) if isinstance(result, dict) else max(len(items), 1)
            return self._page_result(items, page, limit, total)
        if kind == "keyword":
            self.search_keyword = data.get("keyword", "")
            source = data.get("source") or self.config.get("source") or "kw"
            self.search_source = source
            return self._search_root()
        if kind == "artist_query":
            keyword = data.get("name", "")
            source = data.get("source") or "wy"
            singers = self.client.search(source, keyword, "singer", 1, 10)
            if singers:
                return self._artist_root(LxMapper.artist_vod(singers[0], source))
            songs = self.client.search(str(self.config.get("source") or "kw"), keyword, "song", page, 30)
            return self._page_result([LxMapper.song_vod(item) for item in songs], page, 30)
        if kind == "artist":
            return self._artist_root(LxMapper.artist_vod(data, data.get("source", "wy")))
        if kind == "artist_songs":
            songs = self.client.artist_songs(data.get("source"), data.get("id"), data.get("order", "hot"))
            return self._page_result([LxMapper.song_vod(item, data.get("source")) for item in songs], 1, max(len(songs), 1), len(songs))
        if kind == "artist_albums":
            result = self.client.artist_albums(data.get("source"), data.get("id"), page)
            items = [LxMapper.album_vod(item, data.get("source")) for item in self._extract_list(result)]
            total = result.get("total", len(items)) if isinstance(result, dict) else len(items)
            return self._page_result(items, page, 50, total)
        if kind == "favorite_songs":
            favorites = self._favorites()
            items = [LxMapper.song_vod(item) for item in favorites["songs"]]
            return self._page_result(items, 1, max(len(items), 1), len(items))
        if kind == "favorite_albums":
            favorites = self._favorites()
            items = [LxMapper.album_vod(item) for item in favorites["albums"]]
            return self._page_result(items, 1, max(len(items), 1), len(items))
        if kind == "favorite_artists":
            favorites = self._favorites()
            items = [LxMapper.artist_vod(item) for item in favorites["artists"]]
            return self._page_result(items, 1, max(len(items), 1), len(items))
        if kind == "user_lists":
            favorites = self._favorites()
            items = []
            for playlist in favorites["user_lists"]:
                payload = {"id": playlist.get("id"), "name": playlist.get("name") or "自建歌单"}
                items.append({
                    "vod_id": LxMapper.pack("local_playlist", payload),
                    "vod_name": payload["name"],
                    "vod_pic": LxMapper.text(LxMapper.first(playlist, ["img", "pic", "cover"])),
                    "vod_remarks": "%s 首" % len(playlist.get("list") or []),
                    "vod_player": "music",
                })
            return self._page_result(items, 1, max(len(items), 1), len(items))
        return self._page_result([], page)

    def _favorite_root(self):
        favorites = self._favorites()
        items = [
            LxMapper.folder_vod("favorite_songs", {}, "收藏歌曲", "", "%s 首" % len(favorites["songs"])),
            LxMapper.folder_vod("favorite_albums", {}, "收藏专辑", "", "%s 张" % len(favorites["albums"])),
            LxMapper.folder_vod("favorite_artists", {}, "收藏歌手", "", "%s 位" % len(favorites["artists"]), circle=True),
            LxMapper.folder_vod("user_lists", {}, "自建歌单", "", "%s 个" % len(favorites["user_lists"])),
        ]
        if favorites["error"]:
            items.append(LxMapper.action_vod("收藏登录失败", {
                "actionId": "lx_connection_settings",
                "type": "multiInput",
                "title": "修正 lxserver 登录信息",
                "msg": favorites["error"],
                "input": self._settings_inputs(),
            }, "点击修改连接设置"))
        return self._page_result(items, 1, len(items), len(items))

    def _search_root(self):
        """搜索页面：搜索框在上面，结果在下面显示"""
        source = self.search_source or self.config.get("source") or "kw"
        source_name = SOURCE_NAMES.get(source, source)

        search_input = LxMapper.action_vod(
            f"🔍 输入关键词搜索 ({source_name})", 
            {
                "actionId": "lx_song_search",
                "type": "multiInput",
                "title": "搜索歌曲",
                "msg": f"当前平台：{source_name}，输入关键词搜索",
                "input": [
                    {
                        "id": "keyword",
                        "name": "关键词",
                        "tip": "例如：周杰伦、晴天、七里香",
                        "value": self.search_keyword or "",
                    }
                ],
            },
            f"当前平台：{source_name}，点击输入搜索词",
            ""
        )

        items = [search_input]

        if self.search_keyword:
            # 综合搜索：同时搜索歌曲、歌单、专辑、歌手
            result_items = self._do_comprehensive_search(self.search_keyword, source)
            if result_items:
                items.extend(result_items)
            else:
                items.append({
                    "vod_id": "lx_no_result",
                    "vod_name": f"😅 在 {source_name} 未找到相关结果",
                    "vod_remarks": "提示：可以切换平台重新搜索",
                    "vod_tag": "action",
                })
            items.extend(self._get_hot_search_items(source))
        else:
            items.extend(self._get_hot_search_items(source))

        return self._page_result(items, 1, max(len(items), 1), len(items))

    def _do_comprehensive_search(self, keyword, source):
        """综合搜索：同时搜索歌曲、歌单、专辑、歌手（增强专辑搜索）"""
        items = []
        
        # 1. 搜索歌曲
        try:
            result = self.client.search(source, keyword, "song", 1, 15)
            if result and isinstance(result, list):
                for item in result[:15]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.song_vod(item, source))
                if len(result) > 15:
                    # 添加"查看更多歌曲"入口
                    items.append(LxMapper.folder_vod(
                        "keyword", 
                        {"keyword": keyword, "source": source, "type": "song"}, 
                        f"🎵 查看更多歌曲...", 
                        "", 
                        f"共 {len(result)} 首"
                    ))
        except LxClientError:
            pass

        # 2. 搜索歌单
        try:
            result = self.client.playlist_search(source, keyword, 1)
            raw_items = self._extract_list(result)
            if raw_items:
                # 添加歌单分隔标题
                items.append({
                    "vod_id": "lx_playlist_sep",
                    "vod_name": "📋 相关歌单",
                    "vod_remarks": f"找到 {len(raw_items)} 个歌单",
                    "vod_tag": "folder",
                    "cate": {"land": 1, "ratio": 1.78},
                })
                for item in raw_items[:10]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.playlist_vod(item, source))
        except LxClientError:
            pass

        # 3. 搜索专辑 - 增强健壮性
        try:
            result = self.client.search(source, keyword, "album", 1, 8)
            if result and isinstance(result, list):
                valid_albums = []
                for item in result[:8]:
                    if isinstance(item, dict):
                        item["source"] = source
                    album_vod = LxMapper.album_vod(item, source)
                    # 验证专辑是否有有效数据
                    if album_vod.get("vod_name") and album_vod.get("vod_name") != "未命名专辑":
                        valid_albums.append(album_vod)
                    elif album_vod.get("vod_id") and album_vod.get("vod_name"):
                        valid_albums.append(album_vod)
                
                if valid_albums:
                    # 添加专辑分隔标题
                    items.append({
                        "vod_id": "lx_album_sep",
                        "vod_name": "💿 相关专辑",
                        "vod_remarks": f"找到 {len(valid_albums)} 张专辑",
                        "vod_tag": "folder",
                        "cate": {"land": 1, "ratio": 1.78},
                    })
                    items.extend(valid_albums)
        except LxClientError:
            pass

        # 4. 搜索歌手
        try:
            result = self.client.search(source, keyword, "singer", 1, 8)
            if result and isinstance(result, list):
                # 添加歌手分隔标题
                items.append({
                    "vod_id": "lx_singer_sep",
                    "vod_name": "🎤 相关歌手",
                    "vod_remarks": f"找到 {len(result)} 位歌手",
                    "vod_tag": "folder",
                    "cate": {"land": 1, "ratio": 1.78},
                })
                for item in result[:8]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.artist_vod(item, source))
        except LxClientError:
            pass

        return items

    def _get_hot_search_items(self, source):
        """获取热门搜索词列表"""
        items = []
        try:
            data = self.client.hot_search(source)
            hot_items = data.get("list") if isinstance(data, dict) else data
            if isinstance(hot_items, list):
                source_name = SOURCE_NAMES.get(source, source)
                items.append({
                    "vod_id": "lx_hot_title",
                    "vod_name": f"🔥 热门搜索 [{source_name}]",
                    "vod_remarks": "点击关键词快速搜索",
                    "vod_tag": "folder",
                    "cate": {"land": 1, "ratio": 1.78},
                })
                for item in hot_items[:30]:
                    keyword = item if isinstance(item, str) else LxMapper.first(item, ["keyword", "searchWord", "word", "name"])
                    if keyword:
                        items.append(LxMapper.folder_vod(
                            "keyword", {"keyword": str(keyword), "source": source}, 
                            str(keyword), "", f"在 {source_name} 搜索"
                        ))
        except LxClientError:
            pass
        return items

    def _account_root(self):
        username = self.client.username
        download_folder = str(self.config.get("download_folder") or "").strip()
        download_quality = str(self.config.get("download_quality") or "320k")
        quality_name = QUALITY_NAMES.get(download_quality, download_quality)
        items = [
            LxMapper.action_vod("当前用户：%s" % (username or "未登录"), {
                "actionId": "lx_account",
            }, "点击后可切换用户或退出当前用户"),
            LxMapper.action_vod("下载文件夹：%s" % (download_folder or "未设置"), {
                "actionId": "lx_connection_settings",
                "type": "multiInput",
                "title": "设置下载文件夹",
                "msg": "选择歌曲下载保存位置",
                "input": [
                    {"id": "download_folder", "name": "下载文件夹", "tip": "选择文件夹", "value": download_folder, "selectData": "[folder]"},
                ],
            }, "点击设置下载文件夹"),
            LxMapper.action_vod("下载音质：%s" % quality_name, {
                "actionId": "lx_connection_settings",
                "type": "multiInput",
                "title": "设置下载音质",
                "msg": "选择下载歌曲的音质",
                "input": [
                    {"id": "download_quality", "name": "下载音质", "value": download_quality, "selectData": "标准:=128k,高品:=320k,无损:=flac,Hi-Res:=flac24bit"},
                ],
            }, "点击设置下载音质"),
        ]
        if username:
            items.append(LxMapper.action_vod("退出当前用户", {
                "actionId": "lx_account",
                "value": {"menu": LxMapper.pack("account_command", {"op": "logout"})},
            }, "仅清除本脚本保存的登录信息"))
        else:
            items.append(LxMapper.action_vod("登录用户", {
                "actionId": "lx_connection_settings",
                "type": "multiInput",
                "title": "登录 lxserver 用户",
                "msg": "填写用户名和密码后保存。",
                "input": self._settings_inputs(),
            }, "登录后可读取个人收藏"))
        return self._page_result(items, 1, len(items), len(items))

    def _artist_root(self, artist_vod):
        ref = LxMapper.unpack(artist_vod.get("vod_id")) or {"data": {}}
        data = ref.get("data") or {}
        items = [
            LxMapper.folder_vod("artist_songs", dict(data, order="hot"), "热门歌曲", data.get("pic", ""), data.get("name", "")),
            LxMapper.folder_vod("artist_albums", data, "歌手专辑", data.get("pic", ""), data.get("name", "")),
        ]
        return self._page_result(items, 1, len(items), len(items))

    def _source_category(self):
        sources = self.client.source_list()
        items = []
        for source in sources:
            source_id = str(source.get("id") or "")
            owner = str(source.get("owner") or self.client.username or "open")
            enabled = bool(source.get("enabled"))
            status = str(source.get("status") or ("success" if enabled else "disabled"))
            supported = source.get("supportedSources") if isinstance(source.get("supportedSources"), list) else []
            command = lambda op, sid=source_id, own=owner: LxMapper.pack("source_command", {"op": op, "id": sid, "owner": own})
            config = {
                "actionId": "lx_source_operation",
                "type": "menu",
                "title": str(source.get("name") or source_id),
                "selectedIndex": 0,
                "option": [
                    {"name": "停用" if enabled else "启用", "action": command("disable" if enabled else "enable")},
                    {"name": "上移", "action": command("up")},
                    {"name": "下移", "action": command("down")},
                    {"name": "删除（不可恢复）", "action": command("delete")},
                ],
            }
            remarks = "%s · %s · %s" % (
                "已启用" if enabled else "已停用",
                status,
                "/".join(supported) if supported else "未识别平台",
            )
            items.append(LxMapper.action_vod(str(source.get("name") or source_id), config, remarks))
        items.insert(0, LxMapper.action_vod("导入新的 JS 音源", {
            "actionId": "lx_import_source",
            "type": "multiInput",
            "title": "导入 JS 音源",
            "msg": "选择文件后先校验，再上传到当前用户空间。",
            "input": [
                {"id": "file", "name": "JS 音源文件", "tip": "请选择 .js 文件", "value": "", "selectData": "[file]"},
                {"id": "unsafe", "name": "允许不安全 VM", "value": "否", "selectData": "否:=否,是:=是"},
            ],
        }, "支持文件选择器"))
        return self._page_result(items, 1, max(len(items), 1), len(items))

    # ========== 本地歌曲功能 ==========
    def _local_songs_root(self, delete_mode=False):
        """本地歌曲页面：只读取下载文件夹根目录中的音乐文件（不扫描子文件夹）"""
        download_folder = str(self.config.get("download_folder") or "").strip()
        
        if not download_folder:
            return self._page_result([{
                "vod_id": "lx_no_folder",
                "vod_name": "📁 请先设置下载文件夹",
                "vod_remarks": "点击下方「设置下载文件夹」",
                "vod_tag": "action",
            }, {
                "vod_id": json.dumps({
                    "actionId": "lx_connection_settings",
                    "type": "multiInput",
                    "title": "设置下载文件夹",
                    "msg": "选择歌曲下载保存位置",
                    "input": [
                        {"id": "download_folder", "name": "下载文件夹", "tip": "选择文件夹", "value": "", "selectData": "[folder]"},
                    ],
                }, ensure_ascii=False),
                "vod_name": "⚙️ 设置下载文件夹",
                "vod_remarks": "点击选择文件夹",
                "vod_tag": "action",
            }], 1, 2, 2)

        if not os.path.exists(download_folder):
            return self._page_result([{
                "vod_id": "lx_folder_not_exist",
                "vod_name": "❌ 文件夹不存在",
                "vod_remarks": f"请检查路径: {download_folder}",
                "vod_tag": "action",
            }], 1, 1, 1)

        music_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.wma', '.ape'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        lyric_extensions = {'.lrc', '.txt'}
        
        songs = []
        files_dict = {}
        
        try:
            for file in os.listdir(download_folder):
                file_path = os.path.join(download_folder, file)
                if os.path.isdir(file_path):
                    continue
                base_name = os.path.splitext(file)[0]
                ext = os.path.splitext(file)[1].lower()
                key = base_name
                
                if key not in files_dict:
                    files_dict[key] = {
                        "music": None, 
                        "cover": None, 
                        "lyric": None, 
                        "base_name": base_name,
                        "file_name": file
                    }
                
                if ext in music_extensions:
                    files_dict[key]["music"] = file_path
                    files_dict[key]["ext"] = ext
                elif ext in image_extensions:
                    files_dict[key]["cover"] = file_path
                elif ext in lyric_extensions:
                    files_dict[key]["lyric"] = file_path
            
            for key, info in files_dict.items():
                if info["music"]:
                    file_path = info["music"]
                    ext = info.get("ext", os.path.splitext(file_path)[1].lower())
                    base_name = info.get("base_name", os.path.splitext(os.path.basename(file_path))[0])
                    
                    name_parts = base_name.split(' - ')
                    if len(name_parts) >= 2:
                        song_name = name_parts[0].strip()
                        singer_name = name_parts[1].strip()
                    elif base_name.count(' - ') >= 1:
                        parts = base_name.split(' - ')
                        song_name = parts[0].strip()
                        singer_name = ' - '.join(parts[1:]).strip()
                    else:
                        song_name = base_name
                        singer_name = "本地歌曲"
                    
                    lyric_text = ""
                    if info["lyric"]:
                        try:
                            with open(info["lyric"], "r", encoding="utf-8") as f:
                                lyric_text = f.read()
                        except:
                            pass
                    
                    song = {
                        "source": "local",
                        "name": song_name,
                        "singer": singer_name,
                        "file_path": file_path,
                        "cover_path": info["cover"] or "",
                        "lyric_path": info["lyric"] or "",
                        "lyric_text": lyric_text,
                        "file_name": info.get("file_name", os.path.basename(file_path)),
                        "ext": ext,
                        "size": os.path.getsize(file_path),
                        "modified": os.path.getmtime(file_path),
                        "base_name": base_name,
                        "download_folder": download_folder,
                    }
                    songs.append(song)
                    
        except Exception as e:
            return self._page_result([{
                "vod_id": "lx_scan_error",
                "vod_name": "❌ 扫描文件夹失败",
                "vod_remarks": str(e),
                "vod_tag": "action",
            }], 1, 1, 1)

        songs.sort(key=lambda x: x.get("modified", 0), reverse=True)

        items = []
        for song in songs[:500]:
            cover_pic = song.get("cover_path", "")
            if cover_pic and os.path.exists(cover_pic):
                cover_pic = "file://" + cover_pic
            
            remarks = f"{song['singer']} · {song['ext'].upper()} · {self._format_size(song['size'])}"
            
            # 删除模式：使用 lx_delete_song_ 前缀
            if delete_mode:
                # 将文件路径编码到 vod_id 中
                encoded_path = base64.urlsafe_b64encode(song["file_path"].encode()).decode().rstrip("=")
                item = {
                    "vod_id": f"lx_delete_song_{encoded_path}",
                    "vod_name": f"🗑️ {song['name']}",
                    "vod_pic": cover_pic,
                    "vod_remarks": f"点击删除 · {remarks}",
                    "vod_actor": song["singer"],
                    "vod_content": f"文件路径: {song['file_path']}",
                    "vod_tag": "action",
                    "style": {"type": "rect", "ratio": 1.0},
                }
            else:
                # 浏览模式：正常播放
                item = {
                    "vod_id": LxMapper.pack("local_song", song),
                    "vod_name": song["name"],
                    "vod_pic": cover_pic,
                    "vod_remarks": remarks,
                    "vod_actor": song["singer"],
                    "vod_content": f"文件路径: {song['file_path']}",
                    "vod_player": "music",
                    "style": {"type": "rect", "ratio": 1.0},
                }
            
            items.append(item)

        if items:
            mode_text = "🗑️ 删除模式 (点击歌曲直接删除)" if delete_mode else "🎵 浏览模式 (点击歌曲播放)"
            items.insert(0, {
                "vod_id": "lx_local_stats",
                "vod_name": f"📁 共 {len(items)-1} 首本地歌曲",
                "vod_remarks": f"{mode_text} · {download_folder}",
                "vod_tag": "folder",
                "cate": {"land": 1, "ratio": 1.78},
            })

        return self._page_result(items, 1, max(len(items), 1), len(items))

    def _format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"

    # ========== 删除功能 ==========
    def _delete_local_song_by_path(self, file_path):
        """根据文件路径删除本地歌曲及其关联文件"""
        if not file_path or not os.path.exists(file_path):
            return {
                "action": {"actionId": "__refresh_list__"},
                "toast": "❌ 文件不存在",
            }
        
        # 获取关联文件
        dir_path = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        deleted_files = []
        failed_files = []
        
        # 1. 删除歌曲文件
        try:
            os.remove(file_path)
            deleted_files.append(os.path.basename(file_path))
        except Exception as e:
            failed_files.append(f"{os.path.basename(file_path)}: {str(e)}")
        
        # 2. 删除封面文件
        cover_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        for ext in cover_exts:
            cover_path = os.path.join(dir_path, base_name + ext)
            if os.path.exists(cover_path):
                try:
                    os.remove(cover_path)
                    deleted_files.append(os.path.basename(cover_path))
                except:
                    pass
            cover_path_upper = os.path.join(dir_path, base_name + ext.upper())
            if os.path.exists(cover_path_upper):
                try:
                    os.remove(cover_path_upper)
                    deleted_files.append(os.path.basename(cover_path_upper))
                except:
                    pass
        
        # 3. 删除歌词文件
        lyric_path = os.path.join(dir_path, base_name + '.lrc')
        if os.path.exists(lyric_path):
            try:
                os.remove(lyric_path)
                deleted_files.append(os.path.basename(lyric_path))
            except:
                pass
        lyric_path_upper = os.path.join(dir_path, base_name + '.LRC')
        if os.path.exists(lyric_path_upper):
            try:
                os.remove(lyric_path_upper)
                deleted_files.append(os.path.basename(lyric_path_upper))
            except:
                pass
        
        # 构建返回结果
        if deleted_files:
            msg = f"✅ 已删除: {', '.join(deleted_files)}"
        else:
            msg = f"❌ 删除失败: {', '.join(failed_files)}"
        
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": msg,
        }

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        item_id = str(ids or "").split(",", 1)[0]
        
        # 处理删除请求 - 兼容 detailContent 入口
        if item_id.startswith("lx_delete_song_"):
            return self._action_delete_local_song(item_id)
        
        ref = LxMapper.unpack(item_id)
        if not ref:
            return {"list": []}
        kind = ref["kind"]
        data = ref["data"]
        
        # ===== 本地歌曲 =====
        if kind == "local_song":
            song = data
            file_path = song.get("file_path", "")
            cover_path = song.get("cover_path", "")
            lyric_text = song.get("lyric_text", "")
            
            if not file_path or not os.path.exists(file_path):
                return {"list": [{
                    "vod_id": item_id,
                    "vod_name": "❌ 文件不存在",
                    "vod_remarks": "请检查文件是否已被删除或移动",
                    "vod_player": "music",
                }]}
            
            cover_pic = cover_path if cover_path else ""
            if cover_pic and os.path.exists(cover_pic):
                cover_pic = "file://" + cover_pic
            
            return {"list": [{
                "vod_id": item_id,
                "vod_name": song.get("name", "未知歌曲"),
                "vod_pic": cover_pic,
                "vod_remarks": f"{song.get('singer', '本地歌曲')} · {song.get('ext', '').upper()} · {self._format_size(song.get('size', 0))}",
                "vod_actor": song.get("singer", "本地歌曲"),
                "vod_content": f"文件路径: {file_path}",
                "vod_play_from": "本地播放",
                "vod_play_url": f"本地歌曲${item_id}",
                "vod_player": "music",
                "vod_lrc": lyric_text,
            }]}
        
        # ===== 原有的歌曲处理 =====
        if kind == "song":
            song = LxMapper.song(data)
            detail = LxMapper.music_detail({
                "id": item_id,
                "name": song["name"],
                "pic": song["img"],
                "singer": song["singer"],
                "remarks": " · ".join(item for item in (song["singer"], song["albumName"]) if item),
                "source": song["source"],
            }, [song], self.config)
            return {"list": [detail]}
        if kind == "playlist":
            songs = self._collect_playlist(data)
            detail = LxMapper.music_detail({
                "id": item_id,
                "name": data.get("name"),
                "pic": data.get("pic"),
                "singer": data.get("author"),
                "remarks": "%s 首歌曲" % len(songs),
                "content": data.get("desc"),
                "source": data.get("source"),
            }, songs, self.config)
            return {"list": [detail]}
        if kind == "album":
            songs = self._collect_album(data)
            detail = LxMapper.music_detail({
                "id": item_id,
                "name": data.get("name"),
                "pic": data.get("pic"),
                "singer": data.get("singer"),
                "remarks": "%s 首歌曲" % len(songs),
                "source": data.get("source"),
            }, songs, self.config)
            return {"list": [detail]}
        if kind == "local_playlist":
            favorites = self._favorites()
            playlist = next((item for item in favorites["user_lists"] if str(item.get("id")) == str(data.get("id"))), None)
            songs = []
            if isinstance(playlist, dict):
                for key in ("list", "songs", "songList", "tracks"):
                    if isinstance(playlist.get(key), list):
                        songs = playlist[key]
                        break
            detail = LxMapper.music_detail({
                "id": item_id,
                "name": data.get("name"),
                "remarks": "%s 首歌曲" % len(songs),
            }, songs, self.config)
            return {"list": [detail]}
        return {"list": []}

    def _collect_playlist(self, data):
        songs = []
        max_pages = LxHttpClient._positive_int(self.config.get("max_pages"), 5, 1, 20)
        max_songs = LxHttpClient._positive_int(self.config.get("max_songs"), 500, 1, 2000)
        source = data.get("source")
        for page in range(1, max_pages + 1):
            result = self.client.playlist_detail(source, data.get("id"), page)
            page_items = self._extract_list(result)
            songs.extend(page_items)
            total = result.get("total", 0) if isinstance(result, dict) else 0
            limit = result.get("limit", len(page_items)) if isinstance(result, dict) else len(page_items)
            if source == "tx" or not page_items or len(songs) >= max_songs:
                break
            if total and len(songs) >= int(total):
                break
            if limit and len(page_items) < int(limit):
                break
        return songs[:max_songs]

    def _collect_album(self, data):
        try:
            result = self.client.album_songs(data.get("source"), data.get("id"))
            songs = self._extract_list(result)
            if songs:
                return songs[:LxHttpClient._positive_int(self.config.get("max_songs"), 500, 1, 2000)]
        except LxClientError:
            pass
        keyword = " ".join(item for item in (str(data.get("name") or ""), str(data.get("singer") or "")) if item)
        fallback_source = data.get("source") if data.get("source") in SOURCE_NAMES else str(self.config.get("source") or "kw")
        songs = self.client.search(fallback_source, keyword, "song", 1, 20)
        album_name = str(data.get("name") or "")
        matched = [item for item in songs if LxMapper.song(item, fallback_source).get("albumName") == album_name]
        return matched or songs

    # ========== 搜索功能 ==========
    def searchContent(self, key, quick, pg="1"):
        """搜索方法 - 使用 search_source 平台优先，强制覆盖 source 字段"""
        page = self._page_number(pg)
        keyword = str(key or "").strip()
        if not keyword:
            return self._page_result([], page)

        # 解析搜索类型前缀
        search_type = "song"
        for prefix, target in (("歌曲:", "song"), ("歌曲：", "song"), ("歌手:", "singer"), ("歌手：", "singer"),
                               ("专辑:", "album"), ("专辑：", "album"), ("歌单:", "playlist"), ("歌单：", "playlist")):
            if keyword.startswith(prefix):
                keyword = keyword[len(prefix):].strip()
                search_type = target
                break

        quick_search = quick is True or str(quick).lower() in ("1", "true", "yes", "quick")
        
        # 使用 search_source（从筛选器选中的平台）
        search_source = self.search_source or self.config.get("source") or "kw"
        
        # 对于普通搜索（非快速搜索），使用综合搜索
        if not quick_search:
            return self._comprehensive_search_result(keyword, search_source, page)
        
        # 快速搜索：只搜索歌曲        if quick_search:
            sources = [search_source]
        else:
            sources = self.config.get("sources") or ["kw", "kg", "tx", "wy", "mg"]
            if search_source in sources:
                sources.remove(search_source)
                sources.insert(0, search_source)

        items = []

        if search_type == "singer":
            for source in sources:
                try:
                    result = self.client.search(source, keyword, "singer", page, 20)
                    if result:
                        for item in result:
                            if isinstance(item, dict):
                                item["source"] = source
                        items.extend(LxMapper.artist_vod(item, source) for item in result)
                except LxClientError:
                    continue
        elif search_type == "album":
            for source in sources:
                try:
                    result = self.client.search(source, keyword, "album", page, 20)
                    if result:
                        for item in result:
                            if isinstance(item, dict):
                                item["source"] = source
                        items.extend(LxMapper.album_vod(item, source) for item in result)
                except LxClientError:
                    continue
        elif search_type == "playlist":
            for source in sources:
                try:
                    result = self.client.playlist_search(source, keyword, page)
                    raw_items = self._extract_list(result)
                    if raw_items:
                        for item in raw_items:
                            if isinstance(item, dict):
                                item["source"] = source
                        items.extend(LxMapper.playlist_vod(item, source) for item in raw_items)
                except LxClientError:
                    continue
        else:
            # 歌曲搜索 - 使用 search_source 优先
            for source in sources:
                try:
                    result = self.client.search(source, keyword, "song", page, 30)
                    if result and isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict):
                                item["source"] = source
                        items.extend(LxMapper.song_vod(item, source) for item in result)
                except LxClientError:
                    continue

        return {"list": items, "page": page, "pagecount": page + 1 if items else page, "limit": 30, "total": len(items)}

    def _comprehensive_search_result(self, keyword, source, page):
        """综合搜索结果 - 用于 searchContent 的非快速搜索（增强专辑搜索）"""
        items = []
        
        # 1. 搜索歌曲
        try:
            result = self.client.search(source, keyword, "song", page, 20)
            if result and isinstance(result, list):
                for item in result[:20]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.song_vod(item, source))
        except LxClientError:
            pass

        # 2. 搜索歌单
        try:
            result = self.client.playlist_search(source, keyword, page)
            raw_items = self._extract_list(result)
            if raw_items:
                items.append({
                    "vod_id": "lx_playlist_sep",
                    "vod_name": "📋 相关歌单",
                    "vod_remarks": f"找到 {len(raw_items)} 个歌单",
                    "vod_tag": "folder",
                    "cate": {"land": 1, "ratio": 1.78},
                })
                for item in raw_items[:10]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.playlist_vod(item, source))
        except LxClientError:
            pass

        # 3. 搜索专辑 - 增强健壮性
        try:
            result = self.client.search(source, keyword, "album", page, 8)
            if result and isinstance(result, list):
                valid_albums = []
                for item in result[:8]:
                    if isinstance(item, dict):
                        item["source"] = source
                    album_vod = LxMapper.album_vod(item, source)
                    # 验证专辑是否有有效数据
                    if album_vod.get("vod_name") and album_vod.get("vod_name") != "未命名专辑":
                        valid_albums.append(album_vod)
                    elif album_vod.get("vod_id") and album_vod.get("vod_name"):
                        valid_albums.append(album_vod)
                
                if valid_albums:
                    items.append({
                        "vod_id": "lx_album_sep",
                        "vod_name": "💿 相关专辑",
                        "vod_remarks": f"找到 {len(valid_albums)} 张专辑",
                        "vod_tag": "folder",
                        "cate": {"land": 1, "ratio": 1.78},
                    })
                    items.extend(valid_albums)
        except LxClientError:
            pass

        # 4. 搜索歌手
        try:
            result = self.client.search(source, keyword, "singer", page, 8)
            if result and isinstance(result, list):
                items.append({
                    "vod_id": "lx_singer_sep",
                    "vod_name": "🎤 相关歌手",
                    "vod_remarks": f"找到 {len(result)} 位歌手",
                    "vod_tag": "folder",
                    "cate": {"land": 1, "ratio": 1.78},
                })
                for item in result[:8]:
                    if isinstance(item, dict):
                        item["source"] = source
                    items.append(LxMapper.artist_vod(item, source))
        except LxClientError:
            pass

        if not items:
            items.append({
                "vod_id": "lx_no_result",
                "vod_name": f"😅 在 {SOURCE_NAMES.get(source, source)} 未找到相关结果",
                "vod_remarks": "提示：可以切换平台重新搜索",
                "vod_tag": "action",
            })

        return {"list": items, "page": page, "pagecount": page + 1 if items else page, "limit": 30, "total": len(items)}

    def _download_file(self, url, path, headers=None):
        """下载文件到指定路径，支持自定义headers"""
        try:
            # 使用和播放一样的请求头
            download_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Referer": "http://www.kuwo.cn/",
                "Origin": "http://www.kuwo.cn",
            }
            if headers and isinstance(headers, dict):
                download_headers.update(headers)

            # 使用流式下载，跳过SSL验证
            response = requests.get(url, headers=download_headers, stream=True, timeout=60, verify=False)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            # 检查文件大小
            if total_size > 0 and downloaded < total_size:
                raise Exception("下载不完整")

            return True
        except Exception as e:
            raise Exception("下载失败: %s" % str(e))

    def _clean_filename(self, name):
        """清理文件名中的非法字符"""
        if not name:
            return "未知"
        return re.sub(r'[\\/*?:"<>|]', '', str(name).strip()) or "未知"

    def _download_song(self, song, quality=None):
        """下载歌曲、封面、歌词"""
        download_folder = str(self.config.get("download_folder") or "").strip()
        if not download_folder:
            return {"parse": 0, "url": "", "msg": "请先在「用户账号」中设置下载文件夹"}

        try:
            os.makedirs(download_folder, exist_ok=True)
        except Exception as e:
            return {"parse": 0, "url": "", "msg": "创建文件夹失败: %s" % str(e)}

        singer_name = self._clean_filename(song.get("singer", "未知歌手"))
        song_name = self._clean_filename(song.get("name", "未知歌曲"))
        base_name = f"{song_name} - {singer_name}"

        downloaded = []
        errors = []

        # 1. 下载歌曲 - 使用指定的音质
        if not quality:
            quality = str(self.config.get("download_quality") or "320k")

        audio_url = None
        audio_ext = "mp3"
        audio_headers = {}

        try:
            result = self.client.music_url(song, quality)
            if result and result.get("url"):
                audio_url = result.get("url")
                if audio_url:
                    url_path = audio_url.split('?')[0]
                    if '.flac' in url_path.lower():
                        audio_ext = "flac"
                    elif '.mp3' in url_path.lower():
                        audio_ext = "mp3"
                    elif '.m4a' in url_path.lower():
                        audio_ext = "m4a"
                    elif '.wav' in url_path.lower():
                        audio_ext = "wav"
                    else:
                        audio_ext = "mp3"
                    if result.get("header"):
                        audio_headers = result.get("header")
        except Exception:
            # 如果指定音质失败，降级到320k
            try:
                result = self.client.music_url(song, "320k")
                if result and result.get("url"):
                    audio_url = result.get("url")
                    audio_ext = "mp3"
                    if result.get("header"):
                        audio_headers = result.get("header")
            except Exception:
                pass

        if audio_url:
            try:
                audio_path = os.path.join(download_folder, f"{base_name}.{audio_ext}")
                self._download_file(audio_url, audio_path, audio_headers)
                downloaded.append("歌曲(%s)" % quality)
            except Exception as e:
                errors.append("歌曲下载失败: %s" % str(e))
                try:
                    audio_path = os.path.join(download_folder, f"{base_name}.{audio_ext}")
                    self._download_file(audio_url, audio_path, None)
                    downloaded.append("歌曲(%s)(重试成功)" % quality)
                except Exception as e2:
                    errors.append("歌曲下载重试失败: %s" % str(e2))
        else:
            errors.append("未找到可用的歌曲播放地址")

        # 2. 下载封面 (jpg)
        img_url = song.get("img") or song.get("picUrl") or ""
        if img_url:
            try:
                img_path = os.path.join(download_folder, f"{base_name}.jpg")
                self._download_file(img_url, img_path)
                downloaded.append("封面")
            except Exception as e:
                errors.append("封面下载失败: %s" % str(e))

        # 3. 下载歌词 (lrc)
        try:
            lyric_data = self.client.lyric(song)
            lyric_text = self._lyric_text(lyric_data)
            if lyric_text:
                lrc_path = os.path.join(download_folder, f"{base_name}.lrc")
                with open(lrc_path, "w", encoding="utf-8") as f:
                    f.write(lyric_text)
                downloaded.append("歌词")
        except Exception as e:
            errors.append("歌词下载失败: %s" % str(e))

        if downloaded:
            msg = "✅ 下载完成: %s" % "、".join(downloaded)
            msg += " → %s" % download_folder
        else:
            msg = "❌ 下载失败"

        if errors:
            msg += "；%s" % "; ".join(errors)

        return {
            "parse": 0,
            "url": audio_url or "",
            "msg": msg,
            "lrc": "下载完成" if downloaded else "下载失败",
            "artwork": song.get("img") or "",
            "flag": "📥 下载(%s)" % quality,
        }

    @staticmethod
    def _quality_for_song(song, requested, fallback):
        available = set()
        for item in song.get("types") or []:
            if isinstance(item, dict) and item.get("type"):
                available.add(str(item["type"]))
        available.update(str(item) for item in (song.get("_types") or {}).keys())
        preferred = [requested, fallback, "320k", "128k", "flac", "flac24bit"]
        if not available:
            return next((item for item in preferred if item), "320k")
        return next((item for item in preferred if item in available), next(iter(available)))

    @staticmethod
    def _lyric_text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("lyric", "lrc", "rawLrc"):
                if isinstance(value.get(key), str):
                    return value[key]
        return ""

    def playerContent(self, flag, id, vipFlags):
        if isinstance(id, (list, tuple)):
            id = id[0] if id else ""
        ref = LxMapper.unpack(id)
        if not ref:
            return {"parse": 0, "url": "", "msg": "无效的播放参数"}
        
        kind = ref["kind"]
        data = ref["data"]
        
        # ===== 本地歌曲播放 =====
        if kind == "local_song":
            file_path = data.get("file_path", "")
            lyric_text = data.get("lyric_text", "")
            cover_path = data.get("cover_path", "")
            
            if not file_path or not os.path.exists(file_path):
                return {"parse": 0, "url": "", "msg": "文件不存在: %s" % file_path}
            
            artwork = ""
            if cover_path and os.path.exists(cover_path):
                artwork = "file://" + cover_path
            
            return {
                "parse": 0,
                "url": "file://" + file_path,
                "msg": "播放本地歌曲",
                "flag": "🎵 本地",
                "lrc": lyric_text,
                "artwork": artwork,
            }
        
        # ===== 原有的播放逻辑 =====
        if ref["kind"] == "play":
            song = LxMapper.song(ref["data"].get("song") or {})
            requested = str(ref["data"].get("quality") or "")
        else:
            song = LxMapper.song(ref["data"])
            requested = ""

        if requested == "download" or str(flag or "").lower() == "download":
            download_quality = str(self.config.get("download_quality") or "320k")
            return self._download_song(song, download_quality)

        for quality, name in QUALITY_NAMES.items():
            if str(flag or "").lower() in (quality.lower(), name.lower()):
                requested = quality
                break
        quality = self._quality_for_song(song, requested, str(self.config.get("quality") or "320k"))
        try:
            result = self.client.music_url(song, quality)
            if not isinstance(result, dict) or not result.get("url"):
                raise LxClientError("自定义音源没有返回播放地址")
            audio_url = result.get("url")
            lyric = ""
            try:
                lyric = self._lyric_text(self.client.lyric(song))
            except LxClientError:
                pass
            headers = result.get("header") or result.get("headers") or {}
            return {
                "parse": 0,
                "url": audio_url,
                "header": headers if isinstance(headers, dict) else {},
                "lrc": lyric,
                "artwork": song.get("img") or "",
                "flag": QUALITY_NAMES.get(quality, quality),
            }
        except LxClientError as error:
            return {"parse": 0, "url": "", "msg": str(error)}

    def action(self, action_str):
        try:
            payload = json.loads(action_str) if isinstance(action_str, str) else action_str
            action_id = (payload.get("action") or payload.get("actionId") or "") if isinstance(payload, dict) else str(action_str)
            value = payload.get("value", {}) if isinstance(payload, dict) else {}
        except (ValueError, TypeError):
            action_id = str(action_str or "")
            value = {}
        try:
            # 处理本地歌曲删除 - 放在最前面
            if action_id.startswith("lx_delete_song_"):
                return self._action_delete_local_song(action_id)
            if action_id == "lx_import_source":
                return self._action_import_source(value)
            if action_id == "lx_source_operation":
                return self._action_source_operation(value)
            if action_id == "lx_connection_settings":
                return self._action_connection_settings(value)
            if action_id == "lx_account":
                return self._action_account(value)
            if action_id == "lx_song_search":
                return self._action_song_search(value)
            if action_id == "lx_open_web":
                return {"action": {
                    "actionId": "lx_open_web",
                    "type": "webview",
                    "title": "洛雪音乐",
                    "url": self.config["base_url"].rstrip("/") + "/",
                    "height": -80,
                    "textZoom": 90,
                }}
            if action_id == "lx_refresh":
                self.home_cache = None
                return {"action": {"actionId": "__refresh_list__"}, "toast": "已刷新洛雪数据"}
            return "未知的洛雪操作: %s" % action_id
        except (LxClientError, OSError, ValueError) as error:
            return {"action": {
                "actionId": "lx_error",
                "type": "msgbox",
                "title": "操作失败",
                "htmlMsg": str(error),
            }}

    def _action_delete_local_song(self, action_id):
        """处理本地歌曲删除"""
        encoded_path = action_id[len("lx_delete_song_"):]
        # 补齐 base64 padding
        padding = 4 - len(encoded_path) % 4
        if padding != 4:
            encoded_path += "=" * padding
        try:
            file_path = base64.urlsafe_b64decode(encoded_path).decode()
        except:
            return {"action": {"actionId": "__refresh_list__"}, "toast": "❌ 文件路径解析错误"}
        
        result = self._delete_local_song_by_path(file_path)
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": result.get("toast", "删除完成"),
        }

    def _action_import_source(self, value):
        values = value if isinstance(value, dict) else {}
        file_path = str(values.get("file") or "").strip()
        allow_unsafe = str(values.get("unsafe") or "否").strip() in ("是", "true", "1", "yes")
        if not file_path:
            raise ValueError("请选择 JS 音源文件")
        if not file_path.lower().endswith(".js"):
            raise ValueError("音源文件必须以 .js 结尾")
        with open(file_path, "r", encoding="utf-8-sig") as source_file:
            content = source_file.read()
        if not content.strip():
            raise ValueError("选择的 JS 文件为空")
        if len(content.encode("utf-8")) > 5 * 1024 * 1024:
            raise ValueError("JS 音源文件不能超过 5 MB")
        validation = self.client.source_validate(content, allow_unsafe)
        if not isinstance(validation, dict) or not validation.get("valid"):
            if isinstance(validation, dict) and validation.get("disabledVM"):
                raise ValueError("服务器已禁用不安全 VM，该音源当前无法导入")
            if isinstance(validation, dict) and validation.get("requireUnsafe") and not allow_unsafe:
                raise ValueError("该音源需要不安全 VM，请重新导入并选择\"是\"")
            raise ValueError((validation or {}).get("error") if isinstance(validation, dict) else "音源校验失败")
        upload = self.client.source_upload(os.path.basename(file_path), content, allow_unsafe)
        if not isinstance(upload, dict) or not upload.get("success"):
            message = "音源上传失败"
            if isinstance(upload, dict):
                message = upload.get("error") or upload.get("message") or message
            raise ValueError(message or "音源上传失败")
        self.home_cache = None
        platforms = upload.get("supportedSources") or validation.get("sources") or []
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": "音源已导入（默认停用），支持: %s" % ("/".join(platforms) if platforms else "待识别"),
        }

    def _action_source_operation(self, value):
        values = value if isinstance(value, dict) else {}
        command_ref = LxMapper.unpack(values.get("menu") or "")
        if not command_ref or command_ref["kind"] != "source_command":
            raise ValueError("无效的音源操作")
        command = command_ref["data"]
        source_id = command.get("id")
        owner = command.get("owner") or self.client.username or "open"
        operation = command.get("op")
        if not source_id:
            raise ValueError("音源 ID 为空")
        sources = self.client.source_list()
        target = next((item for item in sources if str(item.get("id")) == str(source_id)), None)
        if target is None and operation != "delete_cancel":
            raise ValueError("音源已不存在，请刷新列表")
        if operation in ("enable", "disable"):
            allow_unsafe = bool(target and target.get("allowUnsafeVM"))
            result = self.client.source_toggle(source_id, owner, operation == "enable", allow_unsafe)
            if isinstance(result, dict) and result.get("success") is False:
                raise ValueError(result.get("message") or result.get("error") or "音源状态切换失败")
            message = "已启用" if operation == "enable" else "已停用"
        elif operation == "delete":
            name = str((target or {}).get("name") or source_id)
            return {"action": {
                "actionId": "lx_source_operation",
                "type": "menu",
                "title": "确认删除音源",
                "msg": "删除后无法恢复：%s" % name,
                "option": [
                    {"name": "确认删除", "action": LxMapper.pack("source_command", {"op": "delete_confirm", "id": source_id, "owner": owner})},
                    {"name": "取消", "action": LxMapper.pack("source_command", {"op": "delete_cancel", "id": source_id, "owner": owner})},
                ],
            }}
        elif operation == "delete_confirm":
            self.client.source_delete(source_id, owner)
            message = "音源已删除"
        elif operation == "delete_cancel":
            return {"toast": "已取消删除"}
        elif operation in ("up", "down"):
            ids = [str(item.get("id")) for item in sources if item.get("id")]
            if source_id not in ids:
                raise ValueError("音源不在当前列表中")
            index = ids.index(source_id)
            target_index = index - 1 if operation == "up" else index + 1
            if target_index < 0 or target_index >= len(ids):
                message = "已经在最前" if operation == "up" else "已经在最后"
            else:
                ids[index], ids[target_index] = ids[target_index], ids[index]
                self.client.source_reorder(ids)
                message = "音源顺序已更新"
        else:
            raise ValueError("不支持的音源操作")
        self.home_cache = None
        return {"action": {"actionId": "__refresh_list__"}, "toast": message}

    def _action_connection_settings(self, value):
        values = value if isinstance(value, dict) else {}
        options = {}
        for key in ("base_url", "username", "password", "api_token", "admin_password", "source", "playlist_source", "quality", "download_folder", "download_quality", "auto_download"):
            if key in values:
                options[key] = str(values[key]).strip()
        self._apply_options(options)
        warnings = []
        saved = self._save_settings()
        if not saved:
            warnings.append("配置文件保存失败")
        try:
            self.client.ping()
        except LxClientError as error:
            warnings.append("服务器连接失败: %s" % error)
        try:
            if self.client.username:
                self.client._login(force=True)
        except LxClientError as error:
            warnings.append("用户登录失败: %s" % error)
        message = "连接设置已保存" if saved else "连接设置仅当前有效"
        if warnings:
            message += "；" + "；".join(warnings)
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": message,
        }

    def _action_song_search(self, value):
        """搜索Action：从输入中获取关键词，使用当前选中的平台"""
        values = value if isinstance(value, dict) else {}
        
        keyword = ""
        
        # 从 input 数组中提取关键词
        input_list = values.get("input")
        if isinstance(input_list, list):
            for item in input_list:
                if item.get("id") == "keyword":
                    keyword = str(item.get("value") or "").strip()
        
        # 如果从 input 没取到，尝试直接从 values 取
        if not keyword:
            keyword = str(values.get("keyword") or "").strip()
        
        if not keyword:
            raise ValueError("请输入要搜索的歌名、歌手或专辑")

        # 保存搜索关键词
        self.search_keyword = keyword
        
        # 使用当前选中的平台（从筛选器设置）
        source = self.search_source or self.config.get("source") or "kw"
        source_name = SOURCE_NAMES.get(source, source)
        
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": f"🔍 搜索: {keyword} ({source_name})",
        }

    def _action_account(self, value):
        """提供本地账号切换；不触碰 lxserver 上的收藏或音源数据。"""
        values = value if isinstance(value, dict) else {}
        command_ref = LxMapper.unpack(values.get("menu") or "")
        if not command_ref:
            return {"action": {
                "actionId": "lx_account",
                "type": "menu",
                "title": "用户账号",
                "msg": "当前用户：%s" % (self.client.username or "未登录"),
                "option": [
                    {"name": "切换用户", "action": LxMapper.pack("account_command", {"op": "switch"})},
                    {"name": "退出当前用户", "action": LxMapper.pack("account_command", {"op": "logout"})},
                ],
            }}
        if command_ref["kind"] != "account_command":
            raise ValueError("无效的账号操作")
        operation = command_ref["data"].get("op")
        if operation == "switch":
            return {"action": {
                "actionId": "lx_connection_settings",
                "type": "multiInput",
                "title": "切换 lxserver 用户",
                "msg": "填写新用户名和密码后保存即可切换。",
                "input": self._settings_inputs(),
            }}
        if operation == "logout":
            return {"action": {
                "actionId": "lx_account",
                "type": "menu",
                "title": "确认退出用户",
                "msg": "退出后仅清除此脚本保存的用户名、密码和 Token，不会删除服务器数据。",
                "option": [
                    {"name": "确认退出", "action": LxMapper.pack("account_command", {"op": "logout_confirm"})},
                    {"name": "取消", "action": LxMapper.pack("account_command", {"op": "logout_cancel"})},
                ],
            }}
        if operation == "logout_cancel":
            return {"toast": "已取消退出"}
        if operation != "logout_confirm":
            raise ValueError("不支持的账号操作")
        self._apply_options({"username": "", "password": "", "api_token": ""})
        saved = self._save_settings()
        return {
            "action": {"actionId": "__refresh_list__"},
            "toast": "已退出当前用户" if saved else "已退出当前用户（配置仅当前有效）",
        }

    def destroy(self):
        try:
            self.client.session.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None