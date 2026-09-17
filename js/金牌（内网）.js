const CryptoJS = require("crypto-js");
const axios = require("axios");

// 可用依赖：async-mutex、axios、cheerio、crypto-js、dayjs、hls-parser、json-bigint、xmlbuilder2
let HOST = 'https://www.hkybqufgh.com';
let siteKey = "", siteType = "", sourceKey = "", ext = "";
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.61 Chrome/126.0.6478.61 Not/A)Brand/8 Safari/537.36';

// 替换原cat.js的Crypto工具
const Crypto = {
  MD5: (str) => CryptoJS.MD5(str),
  SHA1: (str) => CryptoJS.SHA1(str)
};

/**
 * 网络请求封装（替换原req方法）
 * @param {string} reqUrl - 请求地址
 * @param {object} headers - 请求头
 * @returns {Promise<object>} 响应数据
 */
async function request(reqUrl, headers = {}) {
  try {
    const response = await axios.get(reqUrl, { headers });
    
    if (response.status !== 200) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const content = response.data;
    if (!content || (typeof content === 'string' && content.trim() === '')) {
      throw new Error('响应内容为空');
    }
    
    return typeof content === 'object' ? content : JSON.parse(content);
  } catch (error) {
    console.error('请求失败:', error.message);
    throw error;
  }
}

/**
 * 生成UUID
 * @returns {string} UUID字符串
 */
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * 获取请求头（含签名）
 * @param {object} params - 请求参数
 * @returns {object} 完整请求头
 */
function getHeaders(params = {}) {
  const t = Date.now().toString();
  const signParams = { ...params, key: 'cb808529bae6b6be45ecfab29a4889bc', t };
  
  const queryString = Object.keys(signParams)
    .map(key => `${key}=${signParams[key]}`)
    .join('&');
  
  const md5Result = Crypto.MD5(queryString).toString();
  const sign = Crypto.SHA1(md5Result).toString();
  const deviceid = generateUUID();
  
  return {
    'User-Agent': UA,
    'Accept': 'application/json, text/plain, */*',
    'sign': sign,
    't': t,
    'deviceid': deviceid
  };
}

/**
 * 字段名转换（适配示例格式）
 * @param {string} field - 原始字段名
 * @returns {string} 转换后字段名
 */
function convertFieldName(field) {
  field = field.toLowerCase();
  if (field.startsWith('vod') && field.length > 3) {
    field = field.replace('vod', 'vod_');
  }
  if (field.startsWith('type') && field.length > 4) {
    field = field.replace('type', 'type_');
  }
  return field;
}

/**
 * 视频数据格式转换
 * @param {array} array - 原始视频数据数组
 * @returns {array} 转换后的数据数组
 */
function getVod(array) {
  return array.map(item => {
    const newItem = {};
    for (const [key, value] of Object.entries(item)) {
      newItem[convertFieldName(key)] = value;
    }
    return newItem;
  });
}

// 核心业务方法（适配example.js格式）
const _home = async ({ filter }) => {
  try {
    const cdata = await request(`${HOST}/api/mw-movie/anonymous/get/filer/type`, getHeaders());
    const fdata = await request(`${HOST}/api/mw-movie/anonymous/v1/get/filer/list`, getHeaders());
    
    const classes = cdata.data.map(k => ({
      type_name: k.typeName,
      type_id: k.typeId.toString()
    }));
    
    const sortValues = [
      { n: "最近更新", v: "2" },
      { n: "人气高低", v: "3" },
      { n: "评分高低", v: "4" }
    ];
    
    const filters = {};
    for (const [tid, d] of Object.entries(fdata.data)) {
      const currentSortValues = [...sortValues];
      if (tid === '1') currentSortValues.shift();
      
      const filteredTypeList = d.typeList.filter(i => i.itemText !== "伦理");
      filters[tid] = [
        {
          key: "type",
          name: "类型",
          value: filteredTypeList.map(i => ({ n: i.itemText, v: i.itemValue }))
        },
        ...(d.plotList && d.plotList.length ? [{
          key: "v_class",
          name: "剧情",
          value: d.plotList.map(i => ({ n: i.itemText, v: i.itemText }))
        }] : []),
        { key: "area", name: "地区", value: d.districtList.map(i => ({ n: i.itemText, v: i.itemText })) },
        { key: "year", name: "年份", value: d.yearList.map(i => ({ n: i.itemText, v: i.itemText })) },
        { key: "lang", name: "语言", value: d.languageList.map(i => ({ n: i.itemText, v: i.itemText })) },
        { key: "sort", name: "排序", value: currentSortValues }
      ];
    }
    
    // 同时获取首页视频数据
    const homeVodData = await request(`${HOST}/api/mw-movie/anonymous/v1/home/all/list`, getHeaders());
    const hotSearchData = await request(`${HOST}/api/mw-movie/anonymous/home/hotSearch`, getHeaders());
    
    let vodList = [];
    for (const i of Object.values(homeVodData.data)) {
      vodList = vodList.concat(i.list);
    }
    vodList = vodList.concat(hotSearchData.data);
    
    return {
      class: classes,
      filters: filters,
      list: getVod(vodList)
    };
  } catch (error) {
    return { class: [], filters: {}, list: [] };
  }
};

const _category = async ({ id, page, filter, filters }) => {
  try {
    const extend = filters || {};
    const params = {
      area: extend.area || '',
      filterStatus: "1",
      lang: extend.lang || '',
      pageNum: page,
      pageSize: "30",
      sort: extend.sort || '1',
      sortBy: "1",
      type: extend.type || '',
      type1: id,
      v_class: extend.v_class || '',
      year: extend.year || ''
    };
    
    const headers = getHeaders(params);
    const queryString = Object.keys(params).map(key => `${key}=${params[key]}`).join('&');
    const data = await request(`${HOST}/api/mw-movie/anonymous/video/list?${queryString}`, headers);
    
    return {
      list: getVod(data.data.list),
      page: parseInt(page),
      pagecount: 9999,
      total: 999999
    };
  } catch (error) {
    return { list: [], page: parseInt(page), pagecount: 0, total: 0 };
  }
};

const _detail = async ({ id }) => {
  try {
    const result = { list: [] };
    for (const vodId of id) {
      const headers = getHeaders({ id: vodId });
      const data = await request(`${HOST}/api/mw-movie/anonymous/video/detail?id=${vodId}`, headers);
      
      let vod = getVod([data.data])[0];
      vod.vod_play_from = '金牌';
      
      const playUrls = [];
      if (vod.episodelist && vod.episodelist.length > 0) {
        for (const episode of vod.episodelist) {
          const episodeName = vod.episodelist.length > 1 ? episode.name : vod.vod_name;
          playUrls.push(`${episodeName}$${vodId}@@${episode.nid}`);
        }
      }
      
      vod.vod_play_url = playUrls.join('#');
      delete vod.episodelist;
      result.list.push(vod);
    }
    return result;
  } catch (error) {
    return { list: [] };
  }
};

const _search = async ({ page, quick, wd }) => {
  try {
    const params = {
      keyword: wd,
      pageNum: page,
      pageSize: "8",
      sourceCode: "1"
    };
    
    const headers = getHeaders(params);
    const queryString = Object.keys(params).map(key => `${key}=${params[key]}`).join('&');
    const data = await request(`${HOST}/api/mw-movie/anonymous/video/searchByWord?${queryString}`, headers);
    
    return {
      list: getVod(data.data.result.list),
      page: parseInt(page),
      pagecount: Math.ceil(data.data.result.total / 8) || 1,
      total: data.data.result.total || 0
    };
  } catch (error) {
    return { list: [], page: parseInt(page), pagecount: 0, total: 0 };
  }
};

const _play = async ({ flag, flags, id }) => {
  try {
    const [videoId, nid] = id.split('@@');
    const headers = getHeaders({ clientType: '1', id: videoId, nid });
    
    const pdata = await request(
      `${HOST}/api/mw-movie/anonymous/v2/video/episode/url?clientType=1&id=${videoId}&nid=${nid}`,
      headers
    );
    
    const vlist = [];
    if (pdata.data && pdata.data.list) {
      for (const item of pdata.data.list) {
        vlist.push(item.resolutionName, item.url);
      }
    }
    
    const header = {
      'User-Agent': UA,
      'sec-ch-ua-platform': '"Windows"',
      'DNT': '1',
      'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
      'sec-ch-ua-mobile': '?0',
      'Origin': HOST,
      'Referer': `${HOST}/`
    };
    
    return {
      parse: 0,
      jx: 0,
      url: vlist,
      header: header
    };
  } catch (error) {
    return { parse: 0, jx: 0, url: [], header: {} };
  }
};

const _proxy = async (req, reply) => {
  return Object.assign({}, req.query, req.params);
};

// 元数据配置（与example.js格式一致）
const meta = {
  key: "golden",
  name: "金牌（内网）",
  type: 4,
  api: "/video/golden", // 相对地址，服务自动处理
  searchable: 1,
  quickSearch: 1,
  changeable: 0
};

// 导出模块（遵循example.js规范）
module.exports = async (app, opt) => {
  app.get(meta.api, async (req, reply) => {
    const { extend, filter, t, ac, pg, ext, ids, flag, play, wd, quick } = req.query;
    
    if (play) {
      return await _play({ flag: flag || "", flags: [], id: play });
    } else if (wd) {
      return await _search({
        page: parseInt(pg || "1"),
        quick: quick || false,
        wd
      });
    } else if (!ac) {
      return await _home({ filter: filter ?? false });
    } else if (ac === "detail") {
      if (t) {
        const body = {
          id: t,
          page: parseInt(pg || "1"),
          filter: filter || false,
          filters: {}
        };
        
        if (ext) {
          try {
            body.filters = JSON.parse(
              CryptoJS.enc.Base64.parse(ext).toString(CryptoJS.enc.Utf8)
            );
          } catch (e) {
            console.error('解析ext失败:', e);
          }
        }
        
        return await _category(body);
      } else if (ids) {
        return await _detail({
          id: ids
            .split(",")
            .map((_id) => _id.trim())
            .filter(Boolean)
        });
      }
    }
    
    return req.query;
  });
  
  app.get(`${meta.api}/proxy`, _proxy);
  opt.sites.push(meta);
};
