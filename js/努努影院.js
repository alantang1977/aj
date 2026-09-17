const axios = require("axios");
const cheerio = require("cheerio");
const crypto = require("crypto");

// ========== 全局配置 ==========
const HOST = "https://nnyy.la";

const HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://nnyy.la/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
};

// ========== 解密工具 ==========
class CryptoUtil {
    // RC4 解密（改进版）
    static decryptRC4(encryptedHex, key = "i_love_you") {
        try {
            // 如果已经是解密后的URL，直接返回
            if (encryptedHex.startsWith('http')) {
                return encryptedHex;
            }
            
            // 确保是有效的hex字符串
            if (!/^[0-9a-fA-F]+$/.test(encryptedHex)) {
                console.log('不是有效的hex字符串:', encryptedHex);
                return encryptedHex;
            }
            
            const encryptedBytes = Buffer.from(encryptedHex, 'hex');
            const keyBytes = Buffer.from(key, 'utf8');
            
            // KSA
            const s = Array.from({ length: 256 }, (_, i) => i);
            let j = 0;
            for (let i = 0; i < 256; i++) {
                j = (j + s[i] + keyBytes[i % keyBytes.length]) % 256;
                [s[i], s[j]] = [s[j], s[i]];
            }
            
            // PRGA
            let i = 0;
            j = 0;
            const decryptedBytes = Buffer.alloc(encryptedBytes.length);
            
            for (let k = 0; k < encryptedBytes.length; k++) {
                i = (i + 1) % 256;
                j = (j + s[i]) % 256;
                [s[i], s[j]] = [s[j], s[i]];
                const keystreamByte = s[(s[i] + s[j]) % 256];
                decryptedBytes[k] = encryptedBytes[k] ^ keystreamByte;
            }
            
            const result = decryptedBytes.toString('utf8');
            console.log('解密结果:', result);
            return result;
        } catch (error) {
            console.error('RC4解密失败:', error.message, '加密数据:', encryptedHex);
            return encryptedHex;
        }
    }

    // 尝试多种可能的密钥
    static decryptWithMultipleKeys(encryptedHex) {
        const possibleKeys = ["i_love_you", "iloveyou", "nnyy", "nnyy.la", "www.nnyy.la"];
        
        for (const key of possibleKeys) {
            try {
                const result = this.decryptRC4(encryptedHex, key);
                if (result && result.includes('http')) {
                    console.log(`使用密钥 "${key}" 解密成功`);
                    return result;
                }
            } catch (error) {
                continue;
            }
        }
        
        return encryptedHex;
    }
}

// ========== 解析工具 ==========
class ParseUtil {
    // 解析URL字典（改进版）
    static parseUrlDictionary(responseText) {
        const urlDictionary = {};
        
        // 多种匹配模式
        const patterns = [
            /urlDictionary\s*\[\s*(\d+)\s*\]\s*\[\s*(\d+)\s*\]\s*=\s*"([^"]+)"/g,
            /urlDictionary\[(\d+)\]\[(\d+)\]="([^"]+)"/g,
            /urlDictionary\[(\d+)\]\[(\d+)\]\s*=\s*'([^']+)'/g,
            /urlDictionary\[(\d+)\]\[(\d+)\]\s*=\s*`([^`]+)`/g,
            /var\s+urlDictionary\s*=\s*\{[^}]*?\}/g
        ];
        
        for (const pattern of patterns) {
            let match;
            while ((match = pattern.exec(responseText)) !== null) {
                if (match[1] && match[2] && match[3]) {
                    const key1 = parseInt(match[1]);
                    const key2 = parseInt(match[2]);
                    const value = match[3].trim();
                    
                    if (!urlDictionary[key1]) {
                        urlDictionary[key1] = {};
                    }
                    urlDictionary[key1][key2] = value;
                }
            }
        }
        
        // 尝试解析JSON格式的字典
        const jsonMatch = responseText.match(/var\s+urlDictionary\s*=\s*(\{[\s\S]*?\});/);
        if (jsonMatch) {
            try {
                const jsonStr = jsonMatch[1].replace(/'/g, '"').replace(/(\w+):/g, '"$1":');
                const jsonDict = JSON.parse(jsonStr);
                Object.assign(urlDictionary, jsonDict);
            } catch (error) {
                console.log('JSON解析失败:', error.message);
            }
        }
        
        console.log('解析到的URL字典:', JSON.stringify(urlDictionary, null, 2));
        return urlDictionary;
    }

    // 从字典获取URL（改进版）
    static getUrlFromDictionary(urlDictionary, indices) {
        try {
            const [primary, secondary] = indices.map(i => parseInt(i.trim()));
            console.log('查找字典，索引:', primary, secondary);
            
            if (urlDictionary[primary] && urlDictionary[primary][secondary]) {
                const url = urlDictionary[primary][secondary];
                console.log('找到加密URL:', url);
                return url;
            }
            
            // 尝试查找替代位置
            for (const p in urlDictionary) {
                for (const s in urlDictionary[p]) {
                    if (parseInt(p) === primary && parseInt(s) === secondary) {
                        return urlDictionary[p][s];
                    }
                }
            }
            
            return null;
        } catch (error) {
            console.error('获取字典URL失败:', error);
            return null;
        }
    }

    // 提取中间文本（改进版）
    static extractMiddleText(text, startStr, endStr, mode = 0, pattern = '') {
        try {
            const startIndex = text.indexOf(startStr);
            if (startIndex === -1) return "";
            
            const endIndex = text.indexOf(endStr, startIndex + startStr.length);
            if (endIndex === -1) return "";
            
            const middleText = text.substring(startIndex + startStr.length, endIndex);
            
            if (mode === 0) {
                return middleText.replace(/\\/g, "").trim();
            } else if (mode === 1 && pattern) {
                const regex = new RegExp(pattern, 'g');
                const matches = [];
                let match;
                while ((match = regex.exec(middleText)) !== null) {
                    matches.push(match[1]);
                }
                return matches.join(' ');
            }
            
            return middleText.trim();
        } catch (error) {
            console.error('提取中间文本失败:', error);
            return "";
        }
    }

    // 提取播放集数信息（新增）
    static extractPlayNumbers(onclickText) {
        try {
            // 多种匹配模式
            const patterns = [
                /play\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)/,
                /play\('(\d+)','(\d+)'\)/,
                /play\("(\d+)","(\d+)"\)/,
                /(\d+)\s*,\s*(\d+)/,
                /\[(\d+)\]\[(\d+)\]/
            ];
            
            for (const pattern of patterns) {
                const match = onclickText.match(pattern);
                if (match && match[1] && match[2]) {
                    return [match[1], match[2]];
                }
            }
            
            return [0, 0];
        } catch (error) {
            console.error('提取播放数字失败:', error);
            return [0, 0];
        }
    }
}

// ========== 缓存管理器 ==========
class CacheManager {
    constructor(ttl = 300000) {
        this.cache = new Map();
        this.ttl = ttl;
    }

    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        
        if (Date.now() - item.timestamp > this.ttl) {
            this.cache.delete(key);
            return null;
        }
        
        return item.data;
    }

    set(key, data) {
        this.cache.set(key, { data, timestamp: Date.now() });
    }

    clear() {
        this.cache.clear();
    }
}

// ========== HTTP客户端 ==========
class HttpClient {
    constructor() {
        this.cache = new CacheManager();
        this.axiosInstance = axios.create({
            timeout: 30000,
            headers: HEADERS,
            maxRedirects: 5,
            validateStatus: function (status) {
                return status >= 200 && status < 400;
            }
        });
        
        // 添加请求拦截器
        this.axiosInstance.interceptors.request.use(
            config => {
                console.log(`请求: ${config.method.toUpperCase()} ${config.url}`);
                return config;
            },
            error => {
                console.error('请求错误:', error);
                return Promise.reject(error);
            }
        );
        
        // 添加响应拦截器
        this.axiosInstance.interceptors.response.use(
            response => {
                console.log(`响应: ${response.status} ${response.config.url}`);
                return response;
            },
            error => {
                console.error('响应错误:', error.message);
                return Promise.reject(error);
            }
        );
    }

    async get(url, useCache = true) {
        const cacheKey = `GET:${url}`;
        
        if (useCache) {
            const cached = this.cache.get(cacheKey);
            if (cached) {
                console.log('使用缓存:', url);
                return cached;
            }
        }
        
        try {
            console.log('发起请求:', url);
            const response = await this.axiosInstance.get(url);
            const data = response.data;
            
            if (useCache) {
                this.cache.set(cacheKey, data);
            }
            
            return data;
        } catch (error) {
            if (global.store && global.store.log) {
                global.store.log.error(`HTTP请求失败: ${url} - ${error.message}`);
            } else {
                console.error(`HTTP请求失败: ${url} - ${error.message}`);
            }
            throw error;
        }
    }

    async post(url, data, useCache = false) {
        try {
            const response = await this.axiosInstance.post(url, data);
            return response.data;
        } catch (error) {
            if (global.store && global.store.log) {
                global.store.log.error(`HTTP POST请求失败: ${url} - ${error.message}`);
            } else {
                console.error(`HTTP POST请求失败: ${url} - ${error.message}`);
            }
            throw error;
        }
    }
}

// ========== 主要功能类 ==========
class NunNY {
    constructor() {
        this.http = new HttpClient();
        this.host = HOST;
    }

    // 首页分类
    async getHomeCategories() {
        try {
            const html = await this.http.get(this.host);
            const $ = cheerio.load(html);
            const categories = [];
            
            $('div.nav a').each((index, element) => {
                const name = $(element).text().trim();
                if (name !== "首页") {
                    const href = $(element).attr('href');
                    const id = href.replace('/', '');
                    categories.push({
                        type_id: id,
                        type_name: name
                    });
                }
            });
            
            // 添加短剧分类
            categories.push({
                type_id: "duanju",
                type_name: "短剧"
            });
            
            return categories;
        } catch (error) {
            console.error('获取首页分类失败:', error);
            return [];
        }
    }

    // 首页推荐视频
    async getHomeVideos() {
        try {
            const html = await this.http.get(this.host);
            const $ = cheerio.load(html);
            const videos = [];
            
            $('div.bd li').each((index, element) => {
                const img = $(element).find('img');
                const name = img.attr('alt');
                const pic = img.attr('data-src') || img.attr('src');
                const link = $(element).find('a.thumbnail');
                const id = link.attr('href');
                const remark = $(element).find('div.note').text().trim();
                
                if (name && pic && id) {
                    videos.push({
                        vod_id: id,
                        vod_name: name,
                        vod_pic: pic,
                        vod_remarks: remark
                    });
                }
            });
            
            return videos;
        } catch (error) {
            console.error('获取首页视频失败:', error);
            return [];
        }
    }

    // 分类页视频
    async getCategoryVideos(cid, page = 1) {
        try {
            const url = `${this.host}/${cid}/?page=${page}`;
            const html = await this.http.get(url);
            const $ = cheerio.load(html);
            const videos = [];
            
            $('div.lists-content li').each((index, element) => {
                const img = $(element).find('img');
                const name = img.attr('alt');
                const pic = img.attr('data-src') || img.attr('src');
                const link = $(element).find('a.thumbnail');
                const id = link.attr('href');
                const remark = $(element).find('div.note').text().trim();
                
                if (name && pic && id) {
                    videos.push({
                        vod_id: id,
                        vod_name: name,
                        vod_pic: pic,
                        vod_remarks: remark
                    });
                }
            });
            
            // 尝试获取总页数
            let pagecount = 9999;
            const pageLinks = $('ul.pagination li a');
            if (pageLinks.length > 0) {
                const pageNumbers = [];
                pageLinks.each((index, element) => {
                    const pageNum = parseInt($(element).text());
                    if (!isNaN(pageNum)) {
                        pageNumbers.push(pageNum);
                    }
                });
                if (pageNumbers.length > 0) {
                    pagecount = Math.max(...pageNumbers);
                }
            }
            
            return {
                list: videos,
                page: page,
                pagecount: pagecount,
                limit: videos.length,
                total: 999999
            };
        } catch (error) {
            console.error(`获取分类${cid}第${page}页视频失败:`, error);
            return {
                list: [],
                page: page,
                pagecount: 0,
                limit: 0,
                total: 0
            };
        }
    }

    // 视频详情
    async getVideoDetail(id) {
        try {
            const url = id.includes('http') ? id : `${this.host}${id}`;
            console.log('获取视频详情:', url);
            const html = await this.http.get(url, false);
            
            const $ = cheerio.load(html);
            
            // 提取基本信息
            const content = ParseUtil.extractMiddleText(html, '剧情简介：<span>', '<', 0) || 
                           ParseUtil.extractMiddleText(html, '剧情简介：', '</div>', 0) ||
                           "暂无剧情介绍";
            
            const director = ParseUtil.extractMiddleText(html, '导演：', '</div>', 1, 'href=".*?">(.*?)</a>') || 
                            "暂无导演介绍";
            
            const actor = ParseUtil.extractMiddleText(html, '主演：', '</div>', 1, 'href=".*?">(.*?)</a>') || 
                          "暂无主演介绍";
            
            const remarks = ParseUtil.extractMiddleText(html, '类型：', '</div>', 1, 'href=".*?">(.*?)</a>') || 
                            ParseUtil.extractMiddleText(html, '年份：', '</div>', 1, 'href=".*?">(.*?)</a>') ||
                            "暂无类型介绍";
            
            const area = ParseUtil.extractMiddleText(html, '制片国家/地区：', '</div>', 1, 'href=".*?">(.*?)</a>') || 
                         "暂无国家/地区介绍";
            
            // 年份
            const yearElement = $('h1.product-title');
            let year = yearElement.text().trim();
            if (year.includes('打分：')) {
                year = year.split('打分：')[0].trim();
            }
            year = year || ParseUtil.extractMiddleText(html, '年份：', '</div>', 0) || '暂无年份介绍';
            
            // 视频名称
            const vod_name = $('h1.product-title').text().split('打分')[0].trim() || 
                            ParseUtil.extractMiddleText(html, '<title>', '</title>', 0).replace(' - 努努影院', '') ||
                            '未知影片';
            
            // 封面
            const vod_pic = $('div.thumbnail img').attr('src') || 
                           $('div.thumbnail img').attr('data-src') || 
                           '';
            
            // 播放线路
            const playSources = [];
            $('div.playlists dt').each((index, element) => {
                const sourceName = $(element).text().trim();
                if (sourceName) {
                    playSources.push(sourceName);
                }
            });
            
            // 如果没有找到线路，添加默认线路
            if (playSources.length === 0) {
                playSources.push('默认线路');
            }
            
            // 播放集数
            const playUrls = [];
            $('ul.sort-list').each((lineIndex, element) => {
                $(element).find('a').each((i, a) => {
                    const onclick = $(a).attr('onclick');
                    if (onclick) {
                        const numbers = ParseUtil.extractPlayNumbers(onclick);
                        if (numbers[0] && numbers[1]) {
                            // 使用线路索引作为第一个参数
                            const playId = `${numbers[0]},${numbers[1]}@${url}`;
                            const name = $(a).text().trim() || `第${i + 1}集`;
                            playUrls.push(`${name}$${playId}`);
                        }
                    }
                });
            });
            
            // 如果没有播放集数，尝试其他选择器
            if (playUrls.length === 0) {
                $('a[onclick*="play"]').each((index, element) => {
                    const onclick = $(element).attr('onclick');
                    const text = $(element).text().trim();
                    if (onclick && text) {
                        const numbers = ParseUtil.extractPlayNumbers(onclick);
                        if (numbers[0] && numbers[1]) {
                            const playId = `${numbers[0]},${numbers[1]}@${url}`;
                            playUrls.push(`${text}$${playId}`);
                        }
                    }
                });
            }
            
            // 如果还是没有播放集数，创建一个默认的
            if (playUrls.length === 0) {
                console.log('没有找到播放集数，创建默认播放地址');
                playUrls.push(`正片$${1},1@${url}`);
            }
            
            return [{
                vod_id: url,
                vod_name: vod_name,
                vod_pic: vod_pic,
                vod_director: director,
                vod_actor: actor,
                vod_remarks: remarks,
                vod_year: year,
                vod_area: area,
                vod_content: content.replace(/\n/g, ''),
                vod_play_from: playSources.join('$$$'),
                vod_play_url: playUrls.join('#')
            }];
        } catch (error) {
            console.error('获取视频详情失败:', error);
            return [{
                vod_id: id,
                vod_name: '获取失败',
                vod_content: '获取视频信息失败，请稍后重试'
            }];
        }
    }

    // 获取播放地址（关键修复）
    async getPlayUrl(flag, id) {
        try {
            console.log('获取播放地址，ID:', id);
            
            if (!id) {
                throw new Error('播放ID为空');
            }
            
            const parts = id.split('@');
            if (parts.length < 2) {
                throw new Error(`播放ID格式错误: ${id}`);
            }
            
            const numbersStr = parts[0];
            const videoUrl = parts.slice(1).join('@'); // 处理URL中可能包含@的情况
            
            console.log('数字部分:', numbersStr);
            console.log('视频URL:', videoUrl);
            
            const indices = numbersStr.split(',').map(i => i.trim());
            if (indices.length < 2) {
                throw new Error(`播放索引格式错误: ${numbersStr}`);
            }
            
            // 获取视频页面
            const html = await this.http.get(videoUrl, false);
            
            // 解析URL字典
            const urlDictionary = ParseUtil.parseUrlDictionary(html);
            if (Object.keys(urlDictionary).length === 0) {
                // 尝试直接查找播放地址
                console.log('URL字典为空，尝试其他方式');
                
                // 查找直接嵌入的播放地址
                const playUrlMatch = html.match(/var\s+playUrl\s*=\s*['"]([^'"]+)['"]/);
                if (playUrlMatch && playUrlMatch[1]) {
                    console.log('找到直接播放地址:', playUrlMatch[1]);
                    return {
                        parse: 0,
                        playUrl: '',
                        url: playUrlMatch[1],
                        header: HEADERS
                    };
                }
                
                // 查找iframe地址
                const iframeMatch = html.match(/<iframe[^>]*src=['"]([^'"]+)['"]/);
                if (iframeMatch && iframeMatch[1]) {
                    console.log('找到iframe地址:', iframeMatch[1]);
                    return {
                        parse: 0,
                        playUrl: '',
                        url: iframeMatch[1],
                        header: HEADERS
                    };
                }
                
                throw new Error('URL字典为空且未找到其他播放地址');
            }
            
            // 从字典获取加密URL
            const encryptedUrl = ParseUtil.getUrlFromDictionary(urlDictionary, indices);
            if (!encryptedUrl) {
                console.log('字典内容:', JSON.stringify(urlDictionary, null, 2));
                throw new Error(`URL字典中未找到对应的播放地址，索引: ${indices}`);
            }
            
            console.log('加密URL:', encryptedUrl);
            
            // 解密URL
            let decryptedUrl;
            
            // 先尝试多种密钥解密
            decryptedUrl = CryptoUtil.decryptWithMultipleKeys(encryptedUrl);
            
            // 如果还是没有解密出http，尝试直接使用
            if (!decryptedUrl.includes('http')) {
                console.log('解密失败或结果不是URL，尝试直接使用');
                decryptedUrl = encryptedUrl;
            }
            
            // 确保URL完整
            if (decryptedUrl.startsWith('//')) {
                decryptedUrl = 'https:' + decryptedUrl;
            } else if (decryptedUrl.startsWith('/')) {
                decryptedUrl = 'https://nnyy.la' + decryptedUrl;
            }
            
            console.log('最终播放地址:', decryptedUrl);
            
            return {
                parse: 0,
                playUrl: '',
                url: decryptedUrl,
                header: HEADERS
            };
        } catch (error) {
            console.error('获取播放地址失败:', error.message);
            console.error('错误堆栈:', error.stack);
            
            if (global.store && global.store.log) {
                global.store.log.error(`播放地址获取失败: ${error.message}`);
            }
            
            // 返回一个空播放地址而不是抛出错误
            return {
                parse: 0,
                playUrl: '',
                url: '',
                header: HEADERS
            };
        }
    }

    // 搜索视频
    async searchVideos(keyword, page = 1) {
        try {
            const url = `${this.host}/search?wd=${encodeURIComponent(keyword)}&page=${page}`;
            const html = await this.http.get(url);
            const $ = cheerio.load(html);
            const videos = [];
            
            $('div.lists-content li').each((index, element) => {
                const img = $(element).find('img');
                const name = img.attr('alt');
                const pic = img.attr('data-src') || img.attr('src');
                const link = $(element).find('a.thumbnail');
                const id = link.attr('href');
                const remark = $(element).find('div.note').text().trim();
                
                if (name && pic && id) {
                    videos.push({
                        vod_id: id,
                        vod_name: name,
                        vod_pic: pic,
                        vod_remarks: remark
                    });
                }
            });
            
            // 尝试获取总页数
            let pagecount = 1;
            const pageLinks = $('ul.pagination li a');
            if (pageLinks.length > 0) {
                const pageNumbers = [];
                pageLinks.each((index, element) => {
                    const pageNum = parseInt($(element).text());
                    if (!isNaN(pageNum)) {
                        pageNumbers.push(pageNum);
                    }
                });
                if (pageNumbers.length > 0) {
                    pagecount = Math.max(...pageNumbers);
                }
            }
            
            return {
                list: videos,
                page: page,
                pagecount: pagecount,
                limit: videos.length,
                total: 999999
            };
        } catch (error) {
            console.error(`搜索"${keyword}"失败:`, error);
            return {
                list: [],
                page: page,
                pagecount: 0,
                limit: 0,
                total: 0
            };
        }
    }
}

// ========== 站点元数据 ==========
const meta = {
    key: "NunNY",
    name: "努努影院",
    type: 4,
    api: "/video/NunNY"
};

// ========== 全局存储 ==========
const store = { init: false };

// ========== 初始化函数 ==========
const init = async (server) => {
    if (store.init) return;
    store.log = server.log;
    global.store = store;
    store.init = true;
    
    store.log.info(`努努影院初始化完成，Node.js版本: ${process.version}`);
};

// ========== 主要功能函数（适配TVBox接口） ==========
const _home = async ({ filter }) => {
    try {
        const instance = new NunNY();
        const categories = await instance.getHomeCategories();
        const videos = await instance.getHomeVideos();
        
        return { 
            class: categories,
            list: videos
        };
    } catch (error) {
        console.error('首页加载失败:', error);
        return { class: [], list: [] };
    }
};

const _category = async ({ id, page, filter, filters }) => {
    try {
        const instance = new NunNY();
        const pg = page || 1;
        return await instance.getCategoryVideos(id, pg);
    } catch (error) {
        console.error('分类加载失败:', error);
        return {
            list: [],
            page: page || 1,
            pagecount: 0,
            limit: 0,
            total: 0
        };
    }
};

const _detail = async ({ ids }) => {
    try {
        if (!ids || !Array.isArray(ids) || ids.length === 0) {
            return { list: [] };
        }
        
        const instance = new NunNY();
        const videos = await instance.getVideoDetail(ids[0]);
        return { list: videos };
    } catch (error) {
        console.error('详情加载失败:', error);
        return { list: [] };
    }
};

const _play = async ({ id, flags }) => {
    try {
        const instance = new NunNY();
        console.log('播放请求，ID:', id, 'Flags:', flags);
        const result = await instance.getPlayUrl(flags, id);
        console.log('播放结果:', result);
        return result;
    } catch (error) {
        console.error('播放地址获取失败:', error);
        if (global.store && global.store.log) {
            global.store.log.error(`播放地址获取失败: ${error.message}`);
        }
        return { 
            parse: 0, 
            url: '',
            header: HEADERS
        };
    }
};

const _search = async ({ wd, page }) => {
    try {
        if (!wd) {
            return { list: [], page: page || 1, pagecount: 0 };
        }
        
        const instance = new NunNY();
        const pg = page || 1;
        return await instance.searchVideos(wd, pg);
    } catch (error) {
        console.error('搜索失败:', error);
        return {
            list: [],
            page: page || 1,
            pagecount: 0,
            limit: 0,
            total: 0
        };
    }
};

// ========== 模块导出 ==========
module.exports = async (app, opt) => {
    app.get(meta.api, async (req, reply) => {
        if (!store.init) await init(req.server);
        
        const { extend, filter, t, ac, pg, ext, ids, play, wd, quick } = req.query;
        
        console.log('收到请求:', req.query);
        
        try {
            if (play) {
                return await _play({ id: play, flags: ext });
            } else if (wd) {
                return await _search({ wd: wd, page: parseInt(pg || "1") });
            } else if (!ac) {
                return await _home({ filter: filter ?? false });
            } else if (ac === "detail") {
                if (t) {
                    const filters = filter ? JSON.parse(filter) : {};
                    return await _category({ id: t, page: parseInt(pg || "1"), filters: filters });
                } else if (ids) {
                    return await _detail({ ids: Array.isArray(ids) ? ids : [ids] });
                }
            }
            return { code: 404, msg: "未知请求" };
        } catch (e) {
            if (global.store && global.store.log) {
                global.store.log.error(`请求处理失败: ${e.message}`);
                global.store.log.error(e.stack);
            }
            console.error('请求处理失败:', e);
            return { code: 500, msg: "服务器内部错误" };
        }
    });
    
    // 添加清除缓存路由
    app.get(`${meta.api}/clear-cache`, async (req, reply) => {
        const instance = new NunNY();
        instance.http.cache.clear();
        if (global.store && global.store.log) {
            global.store.log.info("努努影院缓存已清空");
        }
        return { code: 200, msg: "缓存已清空" };
    });
    
    // 添加状态检查路由
    app.get(`${meta.api}/status`, async (req, reply) => {
        const instance = new NunNY();
        try {
            await instance.http.get(HOST);
            return { code: 200, msg: "站点可达", host: HOST };
        } catch (error) {
            return { code: 500, msg: `站点不可达: ${error.message}`, host: HOST };
        }
    });
    
    // 添加站点到列表
    opt.sites.push(meta);
    
    console.log(`努努影院插件已加载，API地址: ${meta.api}`);
};