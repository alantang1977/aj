<?php
header('Content-Type: application/json; charset=utf-8');

// 远程url爬虫聚合器
$sources = $GLOBALS['sources'] ?? [
    "采集之王.js" => [
        "name" => "采集之王.js", 
        "api" => "http://127.0.0.1:9978/vod/api?site=采集之王.js",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "永乐影视" => [
        "name" => "永乐影视", 
        "api" => "http://127.0.0.1:9978/vod/api?site=永乐影视",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "三九影视" => [
        "name" => "三九影视", 
        "api" => "http://127.0.0.1:9978/vod/api?site=三九影视",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "明星影视" => [
        "name" => "明星影视", 
        "api" => "http://127.0.0.1:9978/vod/api?site=明星影视",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "养生知识" => [
        "name" => "养生知识", 
        "api" => "http://127.0.0.1:9978/vod/api?site=养生知识",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "可可影视" => [
        "name" => "可可影视", 
        "api" => "http://127.0.0.1:9978/vod/api?site=可可影视",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "138FM(18+)(js)" => [
        "name" => "138FM(18+)(js)", 
        "api" => "http://127.0.0.1:9978/vod/api?site=138FM(18+)(js)",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "爱壹帆" => [
        "name" => "爱壹帆", 
        "api" => "http://127.0.0.1:9978/vod/api?site=爱壹帆",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "电影港磁力" => [
        "name" => "电影港磁力", 
        "api" => "http://127.0.0.1:9978/vod/api?site=电影港磁力",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "樱花动漫" => [
        "name" => "樱花动漫", 
        "api" => "http://127.0.0.1:9978/vod/api?site=樱花动漫",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "哆啦新番社" => [
        "name" => "哆啦新番社", 
        "api" => "http://127.0.0.1:9978/vod/api?site=哆啦新番社",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "巴士动漫" => [
        "name" => "巴士动漫", 
        "api" => "http://127.0.0.1:9978/vod/api?site=巴士动漫",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "狐狸磁力" => [
        "name" => "狐狸磁力", 
        "api" => "http://127.0.0.1:9978/vod/api?site=狐狸磁力",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "番茄短剧" => [
        "name" => "番茄短剧", 
        "api" => "http://127.0.0.1:9978/vod/api?site=番茄短剧",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "🔞91porn" => [
        "name" => "🔞91porn", 
        "api" => "http://127.0.0.1:9978/vod/api?site=🔞91porn",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "🔞麻豆(js)" => [
        "name" => "🔞麻豆(js)", 
        "api" => "http://127.0.0.1:9978/vod/api?site=🔞麻豆(js)",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "爱优腾搜芒弹幕" => [
        "name" => "爱优腾搜芒弹幕", 
        "api" => "http://127.0.0.1:9978/vod/api?site=爱优腾搜芒弹幕",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "腾讯" => [
        "name" => "腾讯", 
        "api" => "http://127.0.0.1:9978/vod/api?site=腾讯",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "优酷" => [
        "name" => "优酷", 
        "api" => "http://127.0.0.1:9978/vod/api?site=优酷",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "芒果" => [
        "name" => "芒果", 
        "api" => "http://127.0.0.1:9978/vod/api?site=芒果",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "爱奇艺" => [
        "name" => "爱奇艺", 
        "api" => "http://127.0.0.1:9978/vod/api?site=爱奇艺",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ],
    "官方采集(js)" => [
        "name" => "官方采集(js)", 
        "api" => "http://127.0.0.1:9978/vod/api?site=官方采集(js)",
        "style" => ["type" => "rect", "ratio" => 1.33]
    ]
];

$ac = $_GET['ac'] ?? 'detail';
$t = $_GET['t'] ?? '';
$pg = $_GET['pg'] ?? '1';
$f = $_GET['f'] ?? '';
$ids = $_GET['ids'] ?? '';
$wd = $_GET['wd'] ?? '';
$id = $_GET['id'] ?? '';
$flag = $_GET['flag'] ?? '';

// 获取源数据函数
function fetchSourceData($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_TIMEOUT, 10);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
    $result = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode === 200 && $result) {
        return json_decode($result, true);
    }
    return null;
}

// 获取源的分类数据
function getSourceCategories($sourceApi, $sourceKey, $sourceName) {
    $homeUrl = $sourceApi . "&ac=detail";
    $homeData = fetchSourceData($homeUrl);
    
    if ($homeData && isset($homeData['class'])) {
        foreach ($homeData['class'] as &$category) {
            $category['type_id'] = $sourceKey . '_' . $category['type_id'];
            $category['type_name'] = $sourceName . ' - ' . $category['type_name'];
        }
        return $homeData['class'];
    }
    
    return [
        ['type_id' => $sourceKey . '_1', 'type_name' => $sourceName . ' - 电影'],
        ['type_id' => $sourceKey . '_2', 'type_name' => $sourceName . ' - 电视剧'],
        ['type_id' => $sourceKey . '_3', 'type_name' => $sourceName . ' - 综艺'],
        ['type_id' => $sourceKey . '_4', 'type_name' => $sourceName . ' - 动漫']
    ];
}

// 安全获取数组值
function safeGet($array, $key, $default = null) {
    return isset($array[$key]) ? $array[$key] : $default;
}

// 解析分类ID
function parseCategoryId($categoryId) {
    if (strpos($categoryId, '_') !== false) {
        $parts = explode('_', $categoryId, 2);
        if (count($parts) === 2) {
            return [
                'sourceKey' => $parts[0],
                'originalTypeId' => $parts[1],
                'isSourceCategory' => true
            ];
        }
    }
    
    return [
        'sourceKey' => null,
        'originalTypeId' => $categoryId,
        'isSourceCategory' => false
    ];
}

// 检查是否需要解析的源
function isParseSource($sourceKey) {
    $parseSources = ['腾讯', '优酷', '芒果', '爱奇艺', '爱优腾搜芒弹幕'];
    return in_array($sourceKey, $parseSources);
}

// 修复需要解析的源（爱奇艺、优酷、芒果、腾讯等）- 改进版
function fixParseSourceDetail($detailData, $sourceKey) {
    if (!$detailData || !isset($detailData['list']) || empty($detailData['list'])) {
        return $detailData;
    }
    
    foreach ($detailData['list'] as &$item) {
        $vodId = safeGet($item, 'vod_id', '');
        
        // 修复标题 - 更智能的判断
        $currentName = safeGet($item, 'vod_name', '');
        if (empty($currentName) || $currentName === $vodId || $currentName === '未知标题') {
            // 尝试从其他字段获取标题
            $item['vod_name'] = safeGet($item, 'title', 
                              safeGet($item, 'vod_title', 
                              safeGet($item, 'name', '未知标题')));
        }
        
        // 修复简介 - 更智能的判断
        $currentContent = safeGet($item, 'vod_content', '');
        if (empty($currentContent) || $currentContent === $vodId || $currentContent === '暂无简介') {
            // 尝试从其他字段获取简介
            $item['vod_content'] = safeGet($item, 'description', 
                                  safeGet($item, 'vod_blurb', 
                                  safeGet($item, 'content', 
                                  safeGet($item, 'summary', '暂无简介'))));
        }
        
        // 确保播放信息格式正确
        if (empty(safeGet($item, 'vod_play_url', ''))) {
            // 尝试从其他字段获取播放URL
            $playUrl = safeGet($item, 'url', safeGet($item, 'play_url', ''));
            if (!empty($playUrl)) {
                $item['vod_play_url'] = '第1集$' . $playUrl;
            } else {
                // 如果没有播放URL，使用vod_id作为播放地址
                $item['vod_play_url'] = '第1集$' . $vodId;
            }
        }
        
        // 确保有播放来源
        if (empty(safeGet($item, 'vod_play_from', ''))) {
            $item['vod_play_from'] = $sourceKey;
        }
        
        // 确保有播放状态
        if (empty(safeGet($item, 'vod_play_note', ''))) {
            $item['vod_play_note'] = '全';
        }
        
        // 确保有封面图
        if (empty(safeGet($item, 'vod_pic', ''))) {
            $item['vod_pic'] = safeGet($item, 'pic', 
                              safeGet($item, 'cover', 
                              'https://img9.doubanio.com/view/photo/m_ratio_poster/public/p2578045524.jpg'));
        }
    }
    
    return $detailData;
}

// 检查是否有有效的详情数据
function hasValidDetailData($detailData) {
    return $detailData && isset($detailData['list']) && !empty($detailData['list']);
}

// 智能线路识别函数
function detectParseLine($playFrom, $playUrl) {
    $parseLines = [
        'qq' => ['name' => '腾讯视频', 'type' => 'qq'],
        'youku' => ['name' => '优酷视频', 'type' => 'youku'],
        'iqiyi' => ['name' => '爱奇艺', 'type' => 'iqiyi'], 
        'qiyi' => ['name' => '爱奇艺', 'type' => 'iqiyi'],
        'mgtv' => ['name' => '芒果TV', 'type' => 'mgtv'],
        '芒果' => ['name' => '芒果TV', 'type' => 'mgtv'],
        'bilibili' => ['name' => '哔哩哔哩', 'type' => 'bilibili'],
        'bili' => ['name' => '哔哩哔哩', 'type' => 'bilibili'],
        'sohu' => ['name' => '搜狐视频', 'type' => 'sohu'],
        'letv' => ['name' => '乐视视频', 'type' => 'letv'],
        'le' => ['name' => '乐视视频', 'type' => 'letv'],
        'pptv' => ['name' => 'PP视频', 'type' => 'pptv'],
        'wasu' => ['name' => '华数TV', 'type' => 'wasu'],
        'fun' => ['name' => '风行视频', 'type' => 'fun'],
        'fengxing' => ['name' => '风行视频', 'type' => 'fun']
    ];
    
    // 转换为小写进行比较
    $lineLower = strtolower(trim($playFrom));
    
    // 直接匹配线路名称
    if (isset($parseLines[$lineLower])) {
        return [
            'need_parse' => true,
            'line_name' => $parseLines[$lineLower]['name'],
            'line_type' => $parseLines[$lineLower]['type'],
            'reason' => '识别到解析线路: ' . $playFrom
        ];
    }
    
    // 模糊匹配（包含关系）
    foreach ($parseLines as $key => $lineInfo) {
        if (strpos($lineLower, $key) !== false) {
            return [
                'need_parse' => true,
                'line_name' => $lineInfo['name'],
                'line_type' => $lineInfo['type'],
                'reason' => '模糊匹配到解析线路: ' . $playFrom . ' → ' . $key
            ];
        }
    }
    
    // 检查播放URL中的特征
    $urlLower = strtolower($playUrl);
    $urlDomains = [
        'qq.com' => ['name' => '腾讯视频', 'type' => 'qq'],
        'youku.com' => ['name' => '优酷视频', 'type' => 'youku'],
        'iqiyi.com' => ['name' => '爱奇艺', 'type' => 'iqiyi'],
        'mgtv.com' => ['name' => '芒果TV', 'type' => 'mgtv'],
        'bilibili.com' => ['name' => '哔哩哔哩', 'type' => 'bilibili'],
        'sohu.com' => ['name' => '搜狐视频', 'type' => 'sohu'],
        'le.com' => ['name' => '乐视视频', 'type' => 'letv'],
        'pptv.com' => ['name' => 'PP视频', 'type' => 'pptv']
    ];
    
    foreach ($urlDomains as $domain => $lineInfo) {
        if (strpos($urlLower, $domain) !== false) {
            return [
                'need_parse' => true,
                'line_name' => $lineInfo['name'],
                'line_type' => $lineInfo['type'],
                'reason' => 'URL检测到解析域名: ' . $domain
            ];
        }
    }
    
    return [
        'need_parse' => false,
        'line_name' => $playFrom,
        'line_type' => 'unknown',
        'reason' => '非解析线路: ' . $playFrom
    ];
}

// URL智能处理函数
function processVideoUrl($id, $lineType) {
    // 如果已经是完整URL，直接返回
    if (filter_var($id, FILTER_VALIDATE_URL)) {
        return [
            'url' => $id,
            'processed' => false
        ];
    }
    
    // 根据线路类型和ID格式构造URL
    switch ($lineType) {
        case 'qq':
            if (preg_match('/vid=([^&]+)/', $id, $matches)) {
                return [
                    'url' => 'https://v.qq.com/x/cover/' . $matches[1] . '.html',
                    'processed' => true
                ];
            }
            break;
            
        case 'youku':
            if (strpos($id, 'msearch:') !== false) {
                $videoId = str_replace('msearch:', '', $id);
                return [
                    'url' => 'https://v.youku.com/v_show/id_' . $videoId . '.html',
                    'processed' => true
                ];
            } elseif (strpos($id, 'id_') !== false) {
                return [
                    'url' => 'https://v.youku.com/v_show/' . $id . '.html',
                    'processed' => true
                ];
            }
            break;
            
        case 'iqiyi':
            if (preg_match('/showid=([^&]+)/', $id, $matches)) {
                return [
                    'url' => 'https://www.iqiyi.com/' . $matches[1] . '.html',
                    'processed' => true
                ];
            }
            break;
            
        case 'mgtv':
            if (preg_match('/cid=([^&]+)/', $id, $matches)) {
                return [
                    'url' => 'https://www.mgtv.com/h/' . $matches[1] . '.html',
                    'processed' => true
                ];
            }
            break;
    }
    
    // 默认情况：使用ID作为URL
    return [
        'url' => $id,
        'processed' => false
    ];
}

switch ($ac) {
    case 'detail':
        if (!empty($ids)) {
            // 视频详情 - 修复后的逻辑
            $detailData = null;
            $sourceUsed = null;
            
            // 1. 首先尝试需要解析的源
            foreach ($sources as $sourceKey => $sourceConfig) {
                if (isParseSource($sourceKey)) {
                    $sourceUrl = safeGet($sourceConfig, 'api') . "&ac=detail&ids=" . $ids;
                    $detailData = fetchSourceData($sourceUrl);
                    
                    // 关键修复：只有当解析源返回有效数据时才使用
                    if (hasValidDetailData($detailData)) {
                        $sourceUsed = $sourceKey;
                        
                        // 修复需要解析的源
                        $detailData = fixParseSourceDetail($detailData, $sourceKey);
                        
                        // 添加源标识
                        foreach ($detailData['list'] as &$item) {
                            $item['vod_source'] = safeGet($sourceConfig, 'name', $sourceKey);
                        }
                        break;
                    } else {
                        // 如果解析源没有有效数据，重置$detailData，继续尝试其他源
                        $detailData = null;
                    }
                }
            }
            
            // 2. 如果解析源没有获取到有效数据，尝试所有普通源
            if (!$detailData) {
                foreach ($sources as $sourceKey => $sourceConfig) {
                    // 跳过已经尝试过的解析源
                    if (isParseSource($sourceKey)) {
                        continue;
                    }
                    
                    $sourceUrl = safeGet($sourceConfig, 'api') . "&ac=detail&ids=" . $ids;
                    $detailData = fetchSourceData($sourceUrl);
                    
                    // 关键：普通源直接使用原始数据，不做任何修复
                    if (hasValidDetailData($detailData)) {
                        $sourceUsed = $sourceKey;
                        
                        // 普通源保持原样，只添加源标识，不进行任何修复
                        foreach ($detailData['list'] as &$item) {
                            $item['vod_source'] = safeGet($sourceConfig, 'name', $sourceKey);
                        }
                        break;
                    }
                }
            }
            
            echo json_encode($detailData ?: ['error' => 'No detail data found'], JSON_UNESCAPED_UNICODE);
            
        } elseif (!empty($t)) {
            // 分类内容逻辑
            $filters = !empty($f) ? json_decode($f, true) : [];
            $isSubRequest = isset($filters['is_sub']) && $filters['is_sub'] === 'true';
            
            // 处理源主分类（显示子分类）
            if (strpos($t, 'source_') === 0 && !$isSubRequest) {
                $sourceKey = substr($t, 7);
                
                if (isset($sources[$sourceKey])) {
                    $sourceConfig = $sources[$sourceKey];
                    $sourceName = safeGet($sourceConfig, 'name', $sourceKey);
                    $categories = getSourceCategories(safeGet($sourceConfig, 'api'), $sourceKey, $sourceName);
                    
                    $subList = [];
                    foreach ($categories as $category) {
                        $subList[] = [
                            'vod_id' => safeGet($category, 'type_id', $sourceKey . '_1'),
                            'vod_name' => safeGet($category, 'type_name', $sourceName . ' - 未知分类'),
                            'vod_pic' => 'https://img9.doubanio.com/view/photo/m_ratio_poster/public/p2578045524.jpg',
                            'vod_remarks' => '分类',
                            'vod_source' => $sourceName
                        ];
                    }
                    
                    $data = [
                        'is_sub' => true,
                        'list' => $subList,
                        'page' => 1,
                        'pagecount' => 1,
                        'limit' => 20,
                        'total' => count($subList),
                        'parent_category' => $sourceName,
                        'style' => ['type' => 'rect', 'ratio' => 1.5]
                    ];
                    echo json_encode($data, JSON_UNESCAPED_UNICODE);
                } else {
                    echo json_encode(['error' => 'Source not found'], JSON_UNESCAPED_UNICODE);
                }
            } else {
                // 处理具体分类的内容
                $categoryInfo = parseCategoryId($t);
                $targetSourceKey = $categoryInfo['sourceKey'];
                $originalTypeId = $categoryInfo['originalTypeId'];
                
                $allList = [];
                $allFilters = [];
                $pageInfo = ['page' => intval($pg), 'pagecount' => 1, 'limit' => 20, 'total' => 0];
                
                if ($targetSourceKey && isset($sources[$targetSourceKey])) {
                    $sourceConfig = $sources[$targetSourceKey];
                    $sourceUrl = safeGet($sourceConfig, 'api') . "&ac=detail&t=" . $originalTypeId . "&pg=" . $pg;
                    
                    if (!empty($f)) {
                        $sourceUrl .= "&f=" . urlencode($f);
                    }
                    
                    $sourceData = fetchSourceData($sourceUrl);
                    
                    if ($sourceData && isset($sourceData['list'])) {
                        foreach ($sourceData['list'] as &$item) {
                            $item['vod_source'] = safeGet($sourceConfig, 'name', $targetSourceKey);
                        }
                        $allList = $sourceData['list'];
                        
                        if (isset($sourceData['filters'])) {
                            $allFilters = $sourceData['filters'];
                        }
                        
                        $pageInfo['page'] = safeGet($sourceData, 'page', intval($pg));
                        $pageInfo['pagecount'] = safeGet($sourceData, 'pagecount', 1);
                        $pageInfo['limit'] = safeGet($sourceData, 'limit', 20);
                        $pageInfo['total'] = safeGet($sourceData, 'total', count($allList));
                    }
                } else {
                    foreach ($sources as $sourceKey => $sourceConfig) {
                        $sourceUrl = safeGet($sourceConfig, 'api') . "&ac=detail&t=" . $t . "&pg=" . $pg;
                        if (!empty($f)) {
                            $sourceUrl .= "&f=" . urlencode($f);
                        }
                        
                        $sourceData = fetchSourceData($sourceUrl);
                        
                        if ($sourceData && isset($sourceData['list'])) {
                            foreach ($sourceData['list'] as &$item) {
                                $item['vod_source'] = safeGet($sourceConfig, 'name', $sourceKey);
                            }
                            $allList = array_merge($allList, $sourceData['list']);
                            
                            if (isset($sourceData['filters'])) {
                                $allFilters = array_merge($allFilters, $sourceData['filters']);
                            }
                            
                            if (isset($sourceData['pagecount'])) {
                                $pageInfo['pagecount'] = max($pageInfo['pagecount'], $sourceData['pagecount']);
                            }
                            if (isset($sourceData['total'])) {
                                $pageInfo['total'] += $sourceData['total'];
                            }
                        }
                    }
                }
                
                $data = [
                    'list' => $allList,
                    'page' => $pageInfo['page'],
                    'pagecount' => $pageInfo['pagecount'],
                    'limit' => $pageInfo['limit'],
                    'total' => $pageInfo['total'],
                    'style' => ['type' => 'rect', 'ratio' => 1.33]
                ];
                
                if (!empty($allFilters)) {
                    $data['filters'] = $allFilters;
                }
                
                echo json_encode($data, JSON_UNESCAPED_UNICODE);
            }
            
        } else {
            // 首页逻辑
            $homepageList = [];
            
            $firstSource = reset($sources);
            $homeUrl = safeGet($firstSource, 'api') . "&ac=detail";
            $homeData = fetchSourceData($homeUrl);
            
            $classData = [];
            
            foreach ($sources as $sourceKey => $sourceConfig) {
                $classData[] = [
                    'type_id' => 'source_' . $sourceKey,
                    'type_name' => safeGet($sourceConfig, 'name', $sourceKey),
                    'is_source' => true,
                    'source_key' => $sourceKey
                ];
            }
            
            if ($homeData) {
                if (isset($homeData['list'])) {
                    $homepageList = $homeData['list'];
                    $homepageList = array_slice($homepageList, 0, 10);
                }
                
                $filtersData = isset($homeData['filters']) ? $homeData['filters'] : [];
            } else {
                $homepageList[] = [
                    'vod_id' => 'aggregate_demo',
                    'vod_name' => '多源聚合影视 - ' . count($sources) . '个源',
                    'vod_pic' => 'https://img9.doubanio.com/view/photo/m_ratio_poster/public/p2578045524.jpg',
                    'vod_remarks' => '聚合演示',
                    'vod_source' => '聚合源'
                ];
                $filtersData = [];
            }
            
            $data = [
                'class' => $classData,
                'list' => $homepageList,
                'filters' => $filtersData,
                'style' => ['type' => 'rect', "ratio" => 1.33],
                'info' => [
                    'source_count' => count($sources),
                    'sources' => array_keys($sources)
                ]
            ];
            
            echo json_encode($data, JSON_UNESCAPED_UNICODE);
        }
        break;
    
    case 'search':
        // 搜索逻辑
        $searchResults = [];
        $pageInfo = ['page' => intval($pg), 'pagecount' => 1, 'limit' => 20, 'total' => 0];
        
        foreach ($sources as $sourceKey => $sourceConfig) {
            $searchUrl = safeGet($sourceConfig, 'api') . "&ac=search&wd=" . urlencode($wd) . "&pg=" . $pg;
            $searchData = fetchSourceData($searchUrl);
            
            if ($searchData && isset($searchData['list'])) {
                foreach ($searchData['list'] as &$item) {
                    $item['vod_source'] = safeGet($sourceConfig, 'name', $sourceKey);
                }
                $searchResults = array_merge($searchResults, $searchData['list']);
                
                if (isset($searchData['pagecount'])) {
                    $pageInfo['pagecount'] = max($pageInfo['pagecount'], $searchData['pagecount']);
                }
                if (isset($searchData['total'])) {
                    $pageInfo['total'] += $searchData['total'];
                }
            }
        }
        
        $data = [
            'list' => $searchResults,
            'page' => $pageInfo['page'],
            'pagecount' => $pageInfo['pagecount'],
            'limit' => $pageInfo['limit'],
            'total' => $pageInfo['total'],
            'style' => ['type' => 'rect', 'ratio' => 1.33]
        ];
        echo json_encode($data, JSON_UNESCAPED_UNICODE);
        break;
        
    case 'play':
        // 播放逻辑 - 基于线路识别的智能解析
        $playData = null;
        $sourceUsed = null;
        
        // 首先尝试从原始源获取播放数据
        foreach ($sources as $sourceKey => $sourceConfig) {
            $playUrl = safeGet($sourceConfig, 'api') . "&ac=play&id=" . urlencode($id);
            if (!empty($flag)) {
                $playUrl .= "&flag=" . urlencode($flag);
            }
            
            $playData = fetchSourceData($playUrl);
            
            if ($playData) {
                $sourceUsed = $sourceConfig;
                break;
            }
        }
        
        // 智能线路解析判断
        $needParse = false;
        $parseInfo = [
            'line_name' => '未知',
            'line_type' => 'unknown', 
            'reason' => '未检测'
        ];
        
        // 如果获取到了播放数据，分析播放线路
        if ($playData) {
            $playFrom = safeGet($playData, 'from', '');
            $playUrl = safeGet($playData, 'url', '');
            
            // 使用线路识别功能
            $lineDetection = detectParseLine($playFrom, $playUrl);
            $needParse = $lineDetection['need_parse'];
            $parseInfo = $lineDetection;
            
            // 如果源本身已经设置了解析，尊重源的设置
            if (isset($playData['parse']) && $playData['parse'] == 1) {
                $needParse = true;
                $parseInfo['reason'] = '源要求解析';
            }
        } else {
            // 如果没有获取到播放数据，尝试基于ID判断
            $lineDetection = detectParseLine('', $id);
            $needParse = $lineDetection['need_parse'];
            $parseInfo = $lineDetection;
        }
        
        // 处理需要解析的情况
        if ($needParse) {
            // 如果源没有返回数据，创建基础结构
            if (!$playData) {
                $playData = [];
            }
            
            // 设置超级解析参数
            $playData['parse'] = 1;
            $playData['jx'] = 1;
            
            // 智能URL处理
            $currentUrl = safeGet($playData, 'url', $id);
            $processedUrl = processVideoUrl($currentUrl, $parseInfo['line_type']);
            
            if (empty(safeGet($playData, 'url', ''))) {
                $playData['url'] = $processedUrl['url'];
            }
            
            // 添加解析信息
            $playData['from_parse'] = true;
            $playData['parse_source'] = $parseInfo['line_name'];
            $playData['parse_type'] = $parseInfo['line_type'];
            $playData['parse_reason'] = $parseInfo['reason'];
            $playData['url_processed'] = $processedUrl['processed'];
            
            // 根据线路类型设置特定参数
            if ($parseInfo['line_type'] !== 'unknown') {
                $playData['type'] = $parseInfo['line_type'];
            }
        }
        
        // 最终兜底：如果还是没有有效的播放数据，强制使用超级解析
        if (!$playData || (empty($playData['url']) && !isset($playData['parse']))) {
            $playData = [
                'parse' => 1,
                'jx' => 1,
                'url' => processVideoUrl($id, '强制解析')['url'],
                'from_parse' => true,
                'parse_source' => '强制解析',
                'parse_reason' => '兜底机制',
                'type' => 'auto'
            ];
        }
        
        echo json_encode($playData, JSON_UNESCAPED_UNICODE);
        break;
    
    default:
        echo json_encode(['error' => 'Unknown action: ' . $ac], JSON_UNESCAPED_UNICODE);
}
?>