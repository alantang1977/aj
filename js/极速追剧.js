// import Crypto from 'assets://js/lib/crypto-js.js';
// import { backErr, getMylog } from '../lib/utils.js';
import cheerio from 'assets://js/lib/cheerio.min.js';

const baseUrl = 'https://jisuzhuiju.com';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36';

function backErr(err) {
    console.log('backErr', err);
    return JSON.stringify({ msg: err?.message || err });
}

function getMylog(Tag) {
    return function (...args) {
        console.log(`【${Tag}】`, ...args);
    };
}

function safeJsonParse(s = '') {
    try {
        s = s?.trim();
        return s.startsWith('{') ? JSON.parse(s) : s;
    } catch (e) {
        return s;
    }
}

async function getHtml(url) {
    let res = await req(url);
    return res.content;
}

const mylog = getMylog('极速追剧');

const currentYear = new Date().getFullYear();
const yearValues = [{ n: '全部', v: '' }];
for (let i = 0; i < 9; i++) {
    let y = String(currentYear - i);
    yearValues.push({ n: y, v: y });
}
yearValues.push({ n: '其他', v: '-1' });

const commonFilters = [
    { key: 'area', name: '地区', value: [{ n: '全部', v: '' }, { n: '大陆', v: '大陆' }, { n: '香港', v: '香港' }, { n: '台湾', v: '台湾' }, { n: '韩国', v: '韩国' }, { n: '日本', v: '日本' }, { n: '美国', v: '美国' }, { n: '其他', v: '其他' }] },
    { key: 'year', name: '年份', value: yearValues },
    { key: 'sort', name: '排序', value: [{ n: '按热度', v: 'hot' }, { n: '按最新', v: 'new' }, { n: '按推荐', v: 'score' }] }
];

const typeFilters = {
    '1': [{ key: 'type', name: '类型', value: [{ n: '全部', v: '' }, { n: '剧情', v: '7' }, { n: '古装', v: '9' }, { n: '爱情', v: '12' }, { n: '悬疑', v: '14' }, { n: '都市', v: '18' }, { n: '科幻', v: '28' }] }, ...commonFilters],
    '2': [{ key: 'type', name: '类型', value: [{ n: '全部', v: '' }, { n: '动作', v: '40' }, { n: '喜剧', v: '17' }, { n: '爱情', v: '12' }, { n: '科幻', v: '28' }, { n: '悬疑', v: '14' }, { n: '犯罪', v: '34' }] }, ...commonFilters],
    '3': [{ key: 'type', name: '类型', value: [{ n: '全部', v: '' }, { n: '热血', v: 'rexue' }, { n: '科幻', v: 'kehuan' }, { n: '奇幻', v: 'qihuan' }, { n: '冒险', v: 'maoxian' }] }, ...commonFilters],
    '4': [{ key: 'type', name: '类型', value: [{ n: '全部', v: '' }, { n: '真人秀', v: 'zhenrenxiu' }, { n: '音乐', v: 'yinyue' }, { n: '访谈', v: 'fangtan' }] }, ...commonFilters],
    '5': [{ key: 'type', name: '类型', value: [{ n: '全部', v: '' }, { n: '逆袭', v: 'nixi' }, { n: '甜宠', v: 'tianchong' }, { n: '虐恋', v: 'nuelian' }, { n: '穿越', v: 'chuanyue' }] }, ...commonFilters]
};

async function init() { }

async function homeVod() {
    let html = await getHtml(baseUrl);
    return parseList(html);
}

function parseList(html, page = 1) {
    if (typeof html !== "string") return backErr('请求html为空');
    let $ = cheerio.load(html);
    let list = $('a.text-decoration-none').map((i, el) => {
        let $el = $(el);
        return {
            vod_id: $el.attr('href') || '',
            vod_name: $el.find('.vod-title').text().trim(),
            vod_pic: $el.find('img').attr('src') || '',
            vod_remarks: $el.find('.vod-subtitle').text().trim()
        };
    }).get();
    return JSON.stringify({ list, pagecount: list.length > 0 ? ++page : page });
}

async function home() {
    return JSON.stringify({
        class: [
            { id: '1', name: '电视剧' },
            { id: '2', name: '电影' },
            { id: '3', name: '动漫' },
            { id: '4', name: '综艺' },
            { id: '5', name: '短剧' }
        ],
        filters: typeFilters
    });
}

async function category(tid, pg, filter, ext) {
    let type = ext?.type || '';
    let area = ext?.area || '';
    let year = ext?.year || '';
    let sort = ext?.sort || 'hot';
    pg = pg || 1;
    let category = `${baseUrl}/filter?channel=${tid}&type=${type}&area=${encodeURIComponent(area)}&year=${year}&sort=${sort}&page=${pg}`;
    mylog({ category });
    let html = await getHtml(category);
    return parseList(html, pg);
}

async function detail(id) {
    let html = await getHtml(baseUrl + id);
    if (typeof html !== "string") return backErr('获取详情页失败');
    let $ = cheerio.load(html);
    let info = {
        vod_id: id,
        vod_name: $('.detail-title').text().trim(),
        vod_pic: $('.detail-poster-wrapper img').attr('src') || '',
        type_name: $('.detail-tags .tag-pill').map((i, el) => $(el).text().trim()).get().join(',')
    };

    $('.meta-item').each((i, el) => {
        let $el = $(el);
        let l = $el.find('.meta-label').text().trim();
        let v = $el.find('.meta-value').text().trim();
        if (l.includes('主演')) info.vod_actor = v;
        else if (l.includes('导演')) info.vod_director = v;
        else if (l.includes('地区')) info.vod_area = v;
        else if (l.includes('年份')) info.vod_year = v;
        else if (l.includes('备注')) info.vod_remarks = v;
    });

    let tabs = $('.source-tabs .source-tab').toArray();
    if (tabs.length === 0) tabs = [{ attribs: { 'data-target': 'default-panel' } }];
    let pf = [];
    let pv = [];

    tabs.forEach(tab => {
        let $t = $(tab);
        let name = $t.text().trim() || '默认线路';
        let tid = $t.attr('data-target');
        pf.push(name);

        let eps = (tid ? $(`#${tid}`) : $('.source-panel').first()).find('.episode-btn').map((j, ep) => {
            let $e = $(ep);
            let n = $e.text().trim();
            let k = $e.attr('href');
            return n && k ? (n + '$' + k) : null;
        }).get().filter(Boolean); pv.push(eps.join('#'));
    }); info.vod_play_from = pf.join('$$$'); info.vod_play_url = pv.join('$$$');
    return JSON.stringify({ list: [info] });
}

async function search(keyword, quick, pg) {
    try {
        pg = pg || 1;
        let url = `${baseUrl}/search?keyword=${encodeURIComponent(keyword)}`;
        let html = await getHtml(url);
        if (typeof html !== "string") return backErr('搜索请求返回空内容');
        let $ = cheerio.load(html);
        let list = $('.search-item').map((i, el) => {
            let $el = $(el);
            let vod_id = $el.find('.search-item-poster').attr('href') || '';
            let vod_name = $el.find('.search-item-title').text().trim();
            let vod_pic = $el.find('.search-item-poster img').attr('src') || '';
            let vod_remarks = $el.find('.search-meta-item .search-meta-value').eq(1).text().trim()
            return vod_id && vod_name ? { vod_id, vod_name, vod_pic, vod_remarks } : null;
        }).get().filter(Boolean);
        return JSON.stringify({ list, pagecount: list.length > 0 ? parseInt(pg) + 1 : parseInt(pg) });
    } catch (e) {
        return backErr(e);
    }
}

async function play(flag, id) {
    try {
        const match = id.match(/\/vodplay\/(\d+)-([^-]+)-(\d+)\.html/);
        if (!match) throw new Error(id + " 解析错误");
        let res = await req(`${baseUrl}/api/play-url?vodId=${match[1]}&playFrom=${match[2]}&index=${match[3]}`, {
            headers: { 'User-Agent': UA, 'Referer': baseUrl + id }
        });
        let data = safeJsonParse(res.content);
        return JSON.stringify({
            parse: 0,
            url: data?.url || '',
            header: { 'User-Agent': UA, 'Referer': baseUrl }
        });
    } catch (e) {
        return backErr(e);
    }
}

export default { init, homeVod, home, category, detail, search, play };