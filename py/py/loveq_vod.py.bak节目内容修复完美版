# -*- coding: utf-8 -*-
# by @木凡的天空

import re
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from base.spider import Spider as BaseSpider
import datetime 

class Spider(BaseSpider):
    def init(self, extend=""):
        self.base_url = "https://www.loveq.cn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base_url + "/",
        }
        # 设置图片链接
        self.default_pic = "http://anru.8518898.xyz:10086/down/JRcxcn0PDrO4.jpg"  # 全部分类默认图片链接
        self.dexian_pic = "http://anru.8518898.xyz:10086/down/Pcm6Olh20rH3.jpg"  # 得闲小叙专用图片链接
        
        # 定义需要过滤掉的分类名称
        self.filter_categories = ["盛世乾坤","一些事一些情","一些事一些情精华剪辑"]

    # ========== 通用请求 ==========
    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
        except Exception as e:
            print("请求失败:", e)
        return ""

    # ========== 首页分类 (已添加年份和月份筛选) ==========
    def homeContent(self, filter):
        html = self.get(f"{self.base_url}/program.html")
        if not html:
            return {"class": []}

        soup = BeautifulSoup(html, "lxml")
        categories = []
        for a in soup.find_all("a", href=re.compile(r"program-cat\d+-p1\.html")):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title or "program-cat" not in href:
                continue
            m = re.search(r"program-cat(\d+)-p1\.html", href)
            if m:
                cat_id = m.group(1)
                # 过滤不需要的分类
                if title not in self.filter_categories:
                    categories.append({"type_name": title, "type_id": cat_id})

        categories = sorted(categories, key=lambda x: int(x["type_id"]))
        categories = [c for c in categories if c["type_id"] != "0"]
        
        # --- 添加年份和月份筛选器 ---
        filter_data = {}
        
        # 生成年份筛选器 (从当前年份到2003年)
        current_year = datetime.date.today().year
        years = [{"n": "全部年份", "v": ""}]
        years.extend([{"n": str(y), "v": str(y)} for y in range(current_year + 1, 2002, -1)])
        
        # 生成月份筛选器
        months = [{"n": "全部月份", "v": ""}]
        months.extend([{"n": f"{m}月", "v": f"{m:02d}"} for m in range(1, 13)])
        
        # 将年份和月份筛选器绑定到分类ID "1" (全部/粤语节目)
        if any(c["type_id"] == "1" for c in categories):
            filter_data["1"] = [
                {
                    "key": "year",
                    "name": "年份",
                    "value": years
                },
                {
                    "key": "month", 
                    "name": "月份",
                    "value": months
                }
            ]
            
        # 为其他分类也添加筛选器（可选）
        for cat in categories:
            if cat["type_id"] != "1" and cat["type_id"] not in filter_data:
                filter_data[cat["type_id"]] = [
                    {
                        "key": "year",
                        "name": "年份", 
                        "value": years
                    },
                    {
                        "key": "month",
                        "name": "月份",
                        "value": months
                    }
                ]
        # --------------------

        return {"class": categories, "filters": filter_data}

    def homeVideoContent(self):
        # 默认返回粤语分类/全部节目第一页
        return self.categoryContent("1", "1", False, {})

    # ========== 分类节目 (已修复 URL 和滚动循环问题，支持年份月份筛选) ==========
    def categoryContent(self, tid, pg, filter, extend):
        pg_int = int(pg)
        limit = 30 # TVBox 默认每页限制
        
        # --- 提取年份和月份参数 ---
        year = extend.get("year", "")
        month = extend.get("month", "")
        
        # --- 构建 URL (使用正确的查询参数格式) ---
        url_params = f"cat_id={tid}&page={pg}"
        if year:
            url_params += f"&year={year}"
        if month:
            url_params += f"&month={month}"
            
        url = f"{self.base_url}/program.html?{url_params}"
            
        # print(f"请求URL: {url}") # 调试信息

        html = self.get(url)
        if not html:
            # 如果请求失败，返回空列表
            return {"list": []}

        soup = BeautifulSoup(html, "lxml")
        videos = []
        # 查找所有节目链接
        for a in soup.find_all("a", href=re.compile("program_download")):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title:
                continue
            vid_match = re.search(r'program_download-?(\d+)\.html', href)
            vid = vid_match.group(1) if vid_match else href

            # 设置节目图片链接
            vod_pic = self.default_pic 

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": vod_pic,
                "vod_remarks": ""
            })

        
        # --- 最终翻页逻辑 ---
        # 强制将总页数设置为一个大数 999 
        page_count = 999 

        # 如果当前页获取到的列表是空的，则将 pagecount 设置为当前页前一页，停止翻页
        if not videos and pg_int > 1:
            page_count = pg_int - 1 

        return {
            "list": videos,
            "page": pg_int,
            "pagecount": page_count, # <-- 修复后的值
            "limit": limit,
            "total": len(videos) # 保持 total 为当前页视频数
        }

    # ========== 搜索 (支持年份月份筛选) ==========
    def searchContent(self, key, quick, pg="1"):
        # 对关键词进行URL编码
        encoded_key = quote(key.encode('utf-8'))
        url = f"{self.base_url}/so-{pg}-{encoded_key}.html"

        html = self.get(url)
        if not html:
            # 如果第一种方式失败，尝试备用搜索URL
            url = f"{self.base_url}/so.html?wd={encoded_key}&page={pg}"
            html = self.get(url)
            if not html:
                return {"list": []}

        soup = BeautifulSoup(html, "lxml")
        results = []

        # 多种选择器尝试匹配搜索结果
        selectors = [
            "a[href*='program_download']",
            ".search-result a",
            ".result-item a", 
            "li a[href*='program_download']"
        ]

        for selector in selectors:
            for a in soup.select(selector):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title or not href:
                    continue

                # 匹配节目ID
                vid_match = re.search(r'program_download-?(\d+)\.html', href)
                if vid_match:
                    vid = vid_match.group(1)
                    # 检查标题是否包含搜索关键词
                    if key.lower() in title.lower():
                        # 去重，避免多重选择器重复添加
                        if vid not in [r["vod_id"] for r in results]:
                            results.append({
                                "vod_id": vid,
                                "vod_name": title,
                                "vod_pic": self.default_pic,  # 搜索结果也使用全部分类图片链接
                                "vod_remarks": "搜索结果"
                            })

        # 如果没有找到结果，尝试从页面中提取所有节目链接 (作为最后的兜底)
        if not results:
            for a in soup.find_all("a", href=re.compile("program_download")):
                href = a.get("href", "")
                title = a.get_text(strip=True)
                if not title:
                    continue
                vid_match = re.search(r'program_download-?(\d+)\.html', href)
                if vid_match:
                    vid = vid_match.group(1)
                    if vid not in [r["vod_id"] for r in results]:
                        results.append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": self.default_pic,  # 搜索结果也使用全部分类图片链接
                            "vod_remarks": "搜索结果"
                        })

        return {"list": results}

    # ========== 节目详情（提取音频） ==========
    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.base_url}/program_download-{vid}.html"
        html = self.get(url)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(strip=True).replace("-LoveQ", "").strip() if soup.title else f"节目{vid}"

        # 重新设计内容提取逻辑 - 从pdl1列表中提取
        pub_date = ""
        content = ""
        
        # 方法1: 从ul class="pdl1" 列表中提取信息
        pdl1_list = soup.find("ul", class_="pdl1")
        if pdl1_list:
            for li in pdl1_list.find_all("li"):
                li_text = li.get_text(strip=True)
                
                # 提取发布日期
                if "发布日期：" in li_text:
                    # 提取日期部分，去掉时间
                    date_match = re.search(r'发布日期：(\d{4}-\d{2}-\d{2})', li_text)
                    if date_match:
                        pub_date = date_match.group(1)
                    else:
                        pub_date = li_text.replace("发布日期：", "").split()[0]  # 只取日期部分
                
                # 提取节目内容
                elif "节目内容：" in li_text:
                    content = li_text.replace("节目内容：", "").strip()
        
        # 方法2: 如果没找到pdl1列表，尝试其他位置
        if not content:
            # 从搜索表单的input中获取节目名称作为备选内容
            search_input = soup.find("input", {"name": "q"})
            if search_input and search_input.get("value"):
                content = search_input.get("value")
        
        # 方法3: 如果还是没找到内容，尝试从标题中提取
        if not content and title:
            # 从标题中排除常见后缀
            exclude_from_title = ["-LoveQ", "一些事一些情", "节目下载"]
            temp_title = title
            for exclude in exclude_from_title:
                temp_title = temp_title.replace(exclude, "")
            content = temp_title.strip()

        # 检查内容是否只包含日期时间格式，如果是则替换为默认内容
        if content:
            # 匹配常见的日期时间格式
            date_time_patterns = [
                r'^\d{4}-\d{2}-\d{2}$',  # 2025-10-31
                r'^\d{4}\.\d{2}\.\d{2}$',  # 2025.10.30
                r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$',  # 2025-10-31 10:47:47
                r'^\d{4}/\d{2}/\d{2}$',  # 2025/10/31
                r'^\d{2}:\d{2}:\d{2}$',  # 10:47:47
                r'^\d{2}:\d{2}$',  # 10:47
            ]
            
            for pattern in date_time_patterns:
                if re.match(pattern, content.strip()):
                    content = "Hugo,阿智很懒，忙得没时间写."
                    break
        
        # 如果没有节目内容，设置默认内容
        if not content:
            content = "Hugo,阿智很懒，忙得没时间写."

        # 格式化描述 - 在日期前加上"发布日期"字样
        if pub_date and content:
            desc = f"发布日期 {pub_date} | {content}"
        elif pub_date:
            desc = f"发布日期 {pub_date}"
        else:
            desc = content

        # 精确提取正确的音频链接 - 只提取 dl2.loveq.cn:8090 的链接
        audio_links = []

        # 方法1: 从audio标签中精确提取 dl2.loveq.cn:8090 链接
        for tag in soup.find_all("audio"):
            src = tag.get("src")
            if src and "dl2.loveq.cn:8090" in src:
                audio_links.append(src)

        # 方法2: 正则精确匹配 dl2.loveq.cn:8090 的MP3链接
        if not audio_links:
            matches = re.findall(
                r'https://dl2\.loveq\.cn:8090/live/program/\d+/\d+\.\d+\.\d+\.mp3\?sign=[a-f0-9]+&timestamp=\d+',
                html
            )
            audio_links.extend(matches)

        # 方法3: 更宽泛的 dl2.loveq.cn:8090 链接匹配
        if not audio_links:
            matches = re.findall(
                r'https://dl2\.loveq\.cn:8090/live/program/[^\s"\']+\.mp3\?sign=[a-f0-9]+&timestamp=\d+',
                html
            )
            audio_links.extend(matches)

        # 方法4: 从JavaScript中提取
        if not audio_links:
            script_patterns = [
                r'audio\.src\s*=\s*["\'](https://dl2\.loveq\.cn:8090[^"\']+\.mp3\?sign=[a-f0-9]+&timestamp=\d+)["\']',
                r'window\.open\(["\'](https://dl2\.loveq\.cn:8090[^"\']+\.mp3\?sign=[a-f0-9]+&timestamp=\d+)["\']',
            ]
            for pattern in script_patterns:
                matches = re.findall(pattern, html, re.I)
                audio_links.extend(matches)
                
        # 移除重复链接
        audio_links = list(set(audio_links))

        # 只取第一个有效的音频链接
        if audio_links:
            play_url = f"木凡的天空${audio_links[0]}"
        else:
            play_url = "暂无音频"

        # 判断是否为得闲小叙分类的节目，设置对应的图片链接
        vod_pic = self.default_pic  # 默认使用全部分类图片链接
        if "得闲小叙" in title or "得闲" in title:
            vod_pic = self.dexian_pic

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": vod_pic,
            "vod_content": desc,
            "vod_play_from": "LoveQ音频",
            "vod_play_url": play_url
        }]}

    # ========== 播放器接口 ==========
    def playerContent(self, flag, id, vipFlags):
        """TVBox 直接播放 mp3 链接"""
        play_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.loveq.cn/",
            "Origin": "https://www.loveq.cn",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Range": "bytes=0-",
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": play_headers
        }

    def isVideoFormat(self, url):
        return any(ext in url.lower() for ext in [".mp3", ".wma"])

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass