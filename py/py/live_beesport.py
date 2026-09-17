# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/5/19 21:19

import sys
import requests
import base64
import os
import time
import re
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "BeeSport"

    def init(self, extend):
        self.ext_time = 120
        self.cache_path = '/storage/emulated/0/TV/cache_BeeSport'
        if not os.path.exists(self.cache_path):
            os.mkdir(self.cache_path, 0o755)
        pass

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def liveContent(self, url):
        data_list = [
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/TNT_SPORTS_1.png', 'group-title': 'BeeSport', 'name': 'TNT SPORTS 1', 'fun': 'beesport', 'pid': 'TNT_Sports_1'},
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/TNT_SPORTS_2.png', 'group-title': 'BeeSport', 'name': 'TNT SPORTS 2', 'fun': 'beesport', 'pid': 'TNT_Sports_2'},
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/TNT_SPORTS_3.png', 'group-title': 'BeeSport', 'name': 'TNT SPORTS 3', 'fun': 'beesport', 'pid': 'TNT_Sports_3'},
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/TNT_SPORTS_4.png', 'group-title': 'BeeSport', 'name': 'TNT SPORTS 4', 'fun': 'beesport', 'pid': 'TNT_Sports_4'},
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/SKY_SPORTS_FOOTBALL.png', 'group-title': 'BeeSport', 'name': 'SKY SPORTS FOOTBALL', 'fun': 'beesport', 'pid': 'Sky_Sports_Football_Live_TV'},
            {'tvg-id': '', 'tvg-name': '', 'tvg-logo': 'https://logo.doube.eu.org/beesport/SKY_SPORTS_MAIN_EVENT.png', 'group-title': 'BeeSport', 'name': 'SKY SPORTS MAIN EVENT', 'fun': 'beesport', 'pid': 'Sky_Sports_Main_Event'},
            # ... 其他频道数据保持不变
        ]

        tv_list = ['#EXTM3U']
        for i in data_list:
            tvg_id = i['tvg-id']
            tvg_name = i['tvg-name']
            tvg_logo = i['tvg-logo']
            group_name = i['group-title']
            name = i['name']
            fun = i['fun']
            pid = i['pid']
            tv_list.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{tvg_name}" tvg-logo="{tvg_logo}" group-title="{group_name}",{name}')
            tv_list.append(f'{self.getProxyUrl()}&fun={fun}&pid={pid}&Author=Doubebly&TG=t.me/doubebly001')

        return '\n'.join(tv_list)

    def homeContent(self, filter):
        return {}

    def homeVideoContent(self):
        return {}

    def categoryContent(self, cid, page, filter, ext):
        return {}

    def detailContent(self, did):
        return {}

    def searchContent(self, key, quick, page='1'):
        return {}

    def searchContentPage(self, keywords, quick, page):
        return {}

    def playerContent(self, flag, pid, vipFlags):
        return {}

    def localProxy(self, params):
        _fun = params.get('fun', None)
        _type = params.get('type', None)
        if _fun is not None:
            fun = getattr(self, f'fun_{_fun}')
            return fun(params)
        return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]

    def fun_beesport(self, params):
        pid = params['pid']
        cache_play_url = self.cache_get(pid)
        if cache_play_url != 'False':
            return [302, "text/plain", None, {'Location': cache_play_url}]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://beesports.net',
            'referer': 'https://beesports.net/live-tv',
        }

        json_data = {
            'channel': f'https://live_tv.starcdnup.com/{pid}/index.m3u8',
        }
        
        try:
            response = requests.post('https://beesports.net/authorize-channel', headers=headers, json=json_data, timeout=10)
            response_data = response.json()
            
            # 修复获取播放地址的逻辑
            if 'channels' in response_data and len(response_data['channels']) > 0:
                url = response_data['channels'][0]
                # 验证URL格式
                if url and (url.startswith('http') or url.startswith('//')):
                    if url.startswith('//'):
                        url = 'https:' + url
                    self.cache_set(pid, url)
                    return [302, "text/plain", None, {'Location': url}]
            
            # 如果获取失败，尝试备用方法
            return self.get_backup_stream(pid)
            
        except Exception as e:
            print(f"获取播放地址失败: {e}")
            # 返回备用流
            return self.get_backup_stream(pid)

    def get_backup_stream(self, pid):
        """获取备用流地址"""
        try:
            # 尝试直接访问可能的m3u8地址
            backup_urls = [
                f'https://live_tv.starcdnup.com/{pid}/index.m3u8',
                f'https://live-tv.starcdnup.com/{pid}/index.m3u8',
                f'https://cdn.starcdnup.com/{pid}/index.m3u8',
            ]
            
            for backup_url in backup_urls:
                try:
                    test_response = requests.head(backup_url, timeout=5)
                    if test_response.status_code == 200:
                        self.cache_set(pid, backup_url)
                        return [302, "text/plain", None, {'Location': backup_url}]
                except:
                    continue
                    
        except Exception as e:
            print(f"备用流获取失败: {e}")
        
        # 最终返回默认视频
        return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]

    def destroy(self):
        files_and_dirs = os.listdir(self.cache_path)
        if len(files_and_dirs) > 0:
            for file in files_and_dirs:
                os.remove(os.path.join(self.cache_path, file))
        return '正在Destroy'

    def b64encode(self, data):
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    def b64decode(self, data):
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')

    def cache_get(self, key):
        t = time.time()
        path = self.cache_getkey(key)
        if not os.path.exists(path):
            return 'False'
        if t - os.path.getmtime(path) > self.ext_time:
            return 'False'
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
        return data

    def cache_set(self, key, data):
        path = self.cache_getkey(key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        return True

    def cache_getkey(self, key):
        return self.cache_path + '/' + key + '.txt'

if __name__ == '__main__':
    pass