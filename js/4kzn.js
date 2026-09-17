const cheerio = require("cheerio"); // 对应模板中可用的 cheerio
const axios = require("axios");   // 对应模板中可用的 axios

// 配置信息
let host = 'https://4kzn.com'; [1]
const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Referer': host + '/'
}; [1]

// 模拟 source 1 中的辅助函数
async function req(url) {
    const res = await axios.get(url, { headers });
    return { content: res.data };
}

const _home = async ({ filter }) => {
    return {
        class: [
            { type_id: 'zuixin', type_name: '最新' },
            { type_id: 'top250', type_name: 'TOP250' },
            { type_id: 'dianying', type_name: '电影' },
            { type_id: 'juji', type_name: '剧集' }
        ],
        filters: {
            "dianying": [{ key: "type", name: "类型", value: [{ "n": "全部", "v": "" }, { "n": "电影", "v": "dianying" }, { "n": "喜剧", "v": "xiju" }, { "n": "爱情", "v": "aiqing" }, { "n": "剧情", "v": "juqing" }, { "n": "悬疑", "v": "xuanyi" }, { "n": "传记", "v": "zhuanji" }, { "n": "动作", "v": "dongzuo" }, { "n": "科幻", "v": "kehuan" }, { "n": "犯罪", "v": "fanzui" }, { "n": "奇幻", "v": "qihuan" }, { "n": "冒险", "v": "maoxian" }, { "n": "家庭", "v": "jiating" }, { "n": "运动", "v": "yundong" }, { "n": "歌舞", "v": "gewu" }, { "n": "战争", "v": "zhanzheng" }, { "n": "惊悚", "v": "jingsong" }, { "n": "西部", "v": "xibu" }, { "n": "动画", "v": "donghua" }, { "n": "灾难", "v": "zainan" }, { "n": "恐怖", "v": "kongbu" }, { "n": "历史", "v": "lishi" }, { "n": "音乐", "v": "yinyue" }, { "n": "同性", "v": "tongxing" }, { "n": "纪录片", "v": "jilupian" }, { "n": "古装", "v": "guzhuang" }, { "n": "儿童", "v": "ertong" }, { "n": "武侠", "v": "武侠" }] }],
            "juji": [{ key: "type", name: "类型", value: [{ "n": "全部", "v": "" }, { "n": "剧集", "v": "juji" }, { "n": "剧情", "v": "juq" }, { "n": "惊悚", "v": "jings" }, { "n": "犯罪", "v": "fanzuii" }, { "n": "动作", "v": "jjdongzuo" }, { "n": "历史", "v": "jjlishi" }, { "n": "战争", "v": "jjzhanzheng" }, { "n": "冒险", "v": "jjmaoxian" }, { "n": "古装", "v": "古装" }, { "n": "爱情", "v": "爱情" }, { "n": "喜剧", "v": "喜剧" }, { "n": "最新", "v": "zuixin-juji" }, { "n": "科幻", "v": "科幻" }, { "n": "悬疑", "v": "悬疑" }, { "n": "奇幻", "v": "奇幻" }, { "n": "家庭", "v": "家庭" }, { "n": "恐怖", "v": "恐怖" }, { "n": "西部", "v": "西部" }, { "n": "动画", "v": "动画" }] }]
        }
    }; [1]
};

const _category = async ({ id, page, filter, filters }) => {
    const pg = page || 1;
    const type = filters.type || id;
    const url = `${host}/books/${type}/page/${pg}`; [1]
    const { content } = await req(url);
    const $ = cheerio.load(content);
    const list = $('.posts-row .posts-item').map((i, el) => {
        const item = $(el);
        return {
            vod_id: item.find('a.item-image').attr('href'),
            vod_name: item.find('.item-title').text().trim(),
            vod_pic: item.find('.lazy').attr('data-src'),
            vod_remarks: item.find('.text-muted').text().trim()
        };
    }).get(); [1]
    return { list, page: parseInt(pg), pagecount: 999 };
};

const _detail = async ({ id }) => {
    const result = { list: [] };
    for (const docId of id) {
        const url = docId.startsWith('http') ? docId : host + docId; [1]
        const { content } = await req(url);
        const $ = cheerio.load(content);
        const txt = $('.panel-body p').text();
        const getInfo = (k) => (txt.match(new RegExp(`${k}:\\s*(.*?)(?=\\s*(导演|主演|类型|制片|语言|上映|片长|又名|IMDb|$))`)) || ['', ''])[1].replace(/\//g, ',');
        
        const playList = $('.site-go a').map((i, el) => {
            const a = $(el);
            return a.text().trim() + '$push://' + a.attr('href');
        }).get(); [1]

        result.list.push({
            vod_id: docId,
            vod_name: $('.site-name').text().trim(),
            vod_pic: $('.lazy').attr('data-src'),
            type_name: getInfo('类型'),
            vod_year: (getInfo('上映日期').match(/\d{4}/) || [''])[0],
            vod_area: getInfo('制片国家/地区'),
            vod_actor: getInfo('主演'),
            vod_director: getInfo('导演'),
            vod_content: txt.split('IMDb:').pop().trim(),
            vod_play_from: playList.length ? playList.map(u => u.split('$')[0]).join('$$$') : '无资源',
            vod_play_url: playList.length ? playList.join('$$$') : ''
        });
    }
    return result; [1][2]
};

const _search = async ({ page, quick, wd }) => {
    const pg = page || 1;
    const url = `${host}/?post_type=book&s=${encodeURIComponent(wd)}&page=${pg}`; [1]
    const { content } = await req(url);
    const $ = cheerio.load(content);
    const list = $('.posts-row .posts-item').map((i, el) => {
        const item = $(el);
        return {
            vod_id: item.find('a.item-image').attr('href'),
            vod_name: item.find('.item-title').text().trim(),
            vod_pic: item.find('.lazy').attr('data-src'),
            vod_remarks: item.find('.text-muted').text().trim()
        };
    }).get();
    return { list, page: parseInt(pg) }; [1]
};

const _play = async ({ flag, flags, id }) => {
    return {
        parse: 0,
        jx: 0,
        url: id,
        header: headers
    }; [1][2]
};

const meta = {
    key: "4kzn",
    name: "4K指南[盘]",
    type: 4,
    api: "/video/4kzn",
    searchable: 1,
    quickSearch: 1,
    changeable: 0,
}; [2]

module.exports = async (app, opt) => {
    app.get(meta.api, async (req, reply) => {
        const { filter, t, ac, pg, ext, ids, play, wd, quick } = req.query; [2]
        
        if (play) {
            return await _play({ id: play });
        } else if (wd) {
            return await _search({ page: pg, quick, wd });
        } else if (!ac) {
            return await _home({ filter: filter ?? false });
        } else if (ac === "detail") {
            if (t) {
                let filters = {};
                if (ext) {
                    try {
                        const CryptoJS = require("crypto-js");
                        filters = JSON.parse(CryptoJS.enc.Base64.parse(ext).toString(CryptoJS.enc.Utf8));
                    } catch {}
                }
                return await _category({ id: t, page: pg, filters });
            } else if (ids) {
                return await _detail({ id: ids.split(",").map(v => v.trim()) });
            }
        }
        return req.query;
    });
    opt.sites.push(meta); [2]
};