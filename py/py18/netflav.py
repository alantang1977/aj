# coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import urllib.parse
import re
from lxml import etree

class Spider(Spider):
    def getName(self):
        return "https://www.netflav.com/"
    
    def init(self, extend):
        pass
        
    def homeContent(self, filter):
        cateManual = {
            "有码": "26",
            "无码": "27", 
            "中文": "28",
            "女伏": "29",
            "类别": "30"
        }
        classes = [{'type_name': k, 'type_id': v} for k, v in cateManual.items()]
        return {'class': classes}

    def homeVideoContent(self):
        try:
            rsp = self.fetch('https://www.netflav.com/')
            root = etree.HTML(rsp.text)
            videos = root.xpath('//ul[@class="fed-list-info fed-part-rows"]/li[contains(@class,"fed-list-item")]')[:12]
            
            videoList = []
            for video in videos:
                name = self.getText(video, './/a[@class="fed-list-title"]/@title')
                img = self.getText(video, './/a[@class="fed-list-pics"]/@data-original')
                remarks = self.getText(video, './/span[@class="fed-list-remarks"]/text()')
                href = self.getText(video, './/a[@class="fed-list-pics"]/@href')
                
                if name and href:
                    videoList.append({
                        "vod_id": href,
                        "vod_name": name,
                        "vod_pic": self.fixUrl(img),
                        "vod_remarks": remarks
                    })
            
            return {'list': videoList}
        except:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            rsp = self.fetch(f'https://www.djjch.com/wuba/{tid}-{pg}.html')
            root = etree.HTML(rsp.text)
            videos = root.xpath('//ul[contains(@class,"fed-list-info")]/li[contains(@class,"fed-list-item")]')
            
            videoList = []
            for video in videos:
                name = self.getText(video, './/a[contains(@class,"fed-list-title")]/@title')
                img = self.getText(video, './/a[contains(@class,"fed-list-pics")]/@data-original')
                remarks = self.getText(video, './/span[contains(@class,"fed-list-remarks")]/text()')
                href = self.getText(video, './/a[contains(@class,"fed-list-pics")]/@href')
                
                if href:
                    videoList.append({
                        "vod_id": href,
                        "vod_name": name,
                        "vod_pic": self.fixUrl(img),
                        "vod_remarks": remarks
                    })
            
            return {
                'list': videoList,
                'page': pg,
                'pagecount': 999,
                'limit': len(videoList),
                'total': 999999
            }
        except:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 90, 'total': 0}

    def detailContent(self, array):
        try:
            tid = array[0]
            url = self.fixUrl(tid, True)
            rsp = self.fetch(url)
            root = etree.HTML(rsp.text)
            
            title = self.getText(root, '//h1/text()') or self.getText(root, '//title/text()')
            img = self.fixUrl(self.getText(root, '//img[@data-original]/@data-original'))
            
            # 获取描述信息
            info_text = ' '.join([x.strip() for x in root.xpath('//div[contains(@class,"fed-part-layout")]//text()') if x.strip()])
            detail_text = ' '.join([x.strip() for x in root.xpath('//div[contains(@class,"fed-deta-info")]//text()') if x.strip()])
            desc = ' '.join([info_text, detail_text]).strip() or '暂无简介'
            
            # 解析播放源 - 重点保留中文名称
            playFrom, playList = self.parsePlaySources(root)
            
            vod = {
                "vod_id": tid,
                "vod_name": title,
                "vod_pic": img,
                "vod_content": desc,
                "vod_play_from": '$$$'.join(playFrom) if playFrom else '',
                "vod_play_url": '$$$'.join(playList) if playList else ''
            }
            
            return {'list': [vod]}
        except Exception as e:
            print(f"detailContent error: {e}")
            return {'list': []}

    def searchContent(self, key, quick):
        try:
            # 使用百度搜索API进行搜索
            search_url = f'https://sp0.baidu.com/9_Q4simg2RQJ8t7jm9iCKT-xh_/s.gif?r=https%3A%2F%2Fwww.djjch.com%2Fsearch.php%3Fsearchword%3D{urllib.parse.quote(key)}&l=https://www.djjch.com/wuba/30.html'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Referer': 'https://www.djjch.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh-Hans;q=0.9'
            }
            
            # 发送搜索请求
            rsp = self.fetch(search_url, headers=headers)
            
            # 解析百度返回的JSON数据
            if rsp.status_code == 200:
                try:
                    data = rsp.json()
                    videoList = []
                    
                    # 解析搜索结果
                    for item in data.get('result', [])[:20]:
                        try:
                            name = item.get('title', '').replace('<em>', '').replace('</em>', '')
                            href = item.get('url', '')
                            img = item.get('img', '')
                            desc = item.get('abstract', '')
                            
                            if name and href and ('/play/' in href or '/detail/' in href):
                                videoList.append({
                                    "vod_id": href,
                                    "vod_name": name,
                                    "vod_pic": self.fixUrl(img),
                                    "vod_remarks": desc[:50] if desc else ""
                                })
                        except:
                            continue
                    
                    return {'list': videoList}
                except:
                    # 如果JSON解析失败，尝试备用方案
                    return self.fallbackSearch(key)
            else:
                return self.fallbackSearch(key)
                
        except Exception as e:
            print(f"搜索出错: {e}")
            return self.fallbackSearch(key)

    def fallbackSearch(self, key):
        """备用搜索方案"""
        try:
            # 方案1: 尝试使用首页内容过滤
            home_result = self.homeVideoContent()
            filtered_list = []
            for item in home_result.get('list', []):
                if key.lower() in item['vod_name'].lower():
                    filtered_list.append(item)
            if filtered_list:
                return {'list': filtered_list[:10]}
            
            # 方案2: 尝试分类页面搜索
            for tid in ["26", "27", "28", "29", "30"]:
                try:
                    cat_result = self.categoryContent(tid, 1, {}, {})
                    for item in cat_result.get('list', []):
                        if key.lower() in item['vod_name'].lower():
                            filtered_list.append(item)
                    if len(filtered_list) >= 5:
                        break
                except:
                    continue
            
            return {'list': filtered_list[:10]}
        except:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = self.fixUrl(id, True)
            rsp = self.fetch(url)
            
            # 尝试多种方式提取视频地址
            patterns = [
                r'var now\s*=\s*["\'](.*?)["\']',
                r'player\.url\s*=\s*["\'](.*?)["\']',
                r'src\s*:\s*["\'](.*?)["\']',
                r'file\s*:\s*["\'](.*?)["\']',
                r'url\s*=\s*["\'](.*?)["\']',
                r'video_url\s*=\s*["\'](.*?)["\']',
                r'<source\s+src=["\'](.*?)["\']',
                r'iframe\.src\s*=\s*["\'](.*?)["\']'
            ]
            
            play_url = None
            for pattern in patterns:
                matches = re.findall(pattern, rsp.text, re.IGNORECASE)
                for match in matches:
                    if match and self.isVideoFormat(match):
                        play_url = match
                        break
                if play_url:
                    break
            
            if not play_url:
                iframe_match = re.search(r'<iframe[^>]*src=["\'](.*?)["\']', rsp.text)
                if iframe_match:
                    play_url = iframe_match.group(1)
            
            if play_url:
                play_url = self.fixUrl(play_url)
            
            return {
                "parse": 0,
                "playUrl": "",
                "url": play_url or url,
                "header": {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
                    "Referer": "https://www.djjch.com/"
                }
            }
        except:
            return {"parse": 0, "playUrl": "", "url": id, "header": {}}

    def isVideoFormat(self, url):
        formats = ['.m3u8', '.mp4', '.avi', '.mkv', '.flv', '.ts', '.mpeg', '.mov']
        return any(fmt in url.lower() for fmt in formats)

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    # 辅助方法
    def getText(self, element, xpath):
        result = element.xpath(xpath)
        return result[0] if result else ''

    def fixUrl(self, url, is_content_url=False):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if is_content_url:
            return 'https://www.djjch.com' + url
        return 'https://www.djjch.com' + url

    def parsePlaySources(self, root):
        playFrom, playList = [], []
        
        # 从选项卡获取播放源
        tab_elements = root.xpath('//ul[contains(@class,"nav-tabs")]/li/a')
        play_containers = root.xpath('//div[contains(@class,"tab-pane")]')
        
        for i, tab in enumerate(tab_elements):
            if i >= len(play_containers):
                break
                
            name_parts = tab.xpath('.//text()')
            name = ''.join(name_parts).strip()
            
            if not name or '排序' in name or '↑↓' in name:
                continue
                
            name = re.sub(r'\s+', ' ', name)
            name = name.replace('&nbsp;', ' ').strip()
            
            episodes = play_containers[i].xpath('.//a[contains(@class,"btn")]')
            episode_list = []
            
            for ep in episodes:
                ep_name = ''.join(ep.xpath('.//text()')).strip()
                ep_url = self.getText(ep, './@href')
                if ep_name and ep_url:
                    episode_list.append(f"{ep_name}${self.fixUrl(ep_url, True)}")
            
            if episode_list:
                playFrom.append(name)
                playList.append('#'.join(episode_list))
        
        return playFrom, playList
