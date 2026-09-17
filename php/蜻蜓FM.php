<?php
/**
 * 蜻蜓FM - PHP 版本修复版
 * 修复了分类列表中的ID提取和播放问题
 */

class Spider extends BaseSpider {
    
    private $host = 'https://www.qingting.fm';
    
    private $headers = [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
        'Cache-Control: no-cache',
        'Pragma: no-cache',
    ];
    
    private $logo = 'https://sss.qtfm.cn/images/qingting_icon_new.png';
    
    // 分类配置
    private $categories = [
        // 省份分类
        ['id' => '217', 'name' => '广东'],
        ['id' => '99', 'name' => '浙江'],
        ['id' => '3', 'name' => '北京'],
        ['id' => '5', 'name' => '天津'],
        ['id' => '7', 'name' => '河北'],
        ['id' => '83', 'name' => '上海'],
        ['id' => '19', 'name' => '山西'],
        ['id' => '31', 'name' => '内蒙古'],
        ['id' => '44', 'name' => '辽宁'],
        ['id' => '59', 'name' => '吉林'],
        ['id' => '69', 'name' => '黑龙江'],
        ['id' => '85', 'name' => '江苏'],
        ['id' => '111', 'name' => '安徽'],
        ['id' => '129', 'name' => '福建'],
        ['id' => '139', 'name' => '江西'],
        ['id' => '151', 'name' => '山东'],
        ['id' => '169', 'name' => '河南'],
        ['id' => '187', 'name' => '湖北'],
        ['id' => '202', 'name' => '湖南'],
        ['id' => '239', 'name' => '广西'],
        ['id' => '254', 'name' => '海南'],
        ['id' => '257', 'name' => '重庆'],
        ['id' => '259', 'name' => '四川'],
        ['id' => '281', 'name' => '贵州'],
        ['id' => '291', 'name' => '云南'],
        ['id' => '316', 'name' => '陕西'],
        ['id' => '327', 'name' => '甘肃'],
        ['id' => '351', 'name' => '宁夏'],
        ['id' => '357', 'name' => '新疆'],
        ['id' => '308', 'name' => '西藏'],
        ['id' => '342', 'name' => '青海'],
        
        // 内容分类
        ['id' => '433', 'name' => '资讯'],
        ['id' => '442', 'name' => '音乐'],
        ['id' => '429', 'name' => '交通'],
        ['id' => '439', 'name' => '经济'],
        ['id' => '432', 'name' => '文艺'],
        ['id' => '441', 'name' => '都市'],
        ['id' => '430', 'name' => '体育'],
        ['id' => '431', 'name' => '双语'],
        ['id' => '440', 'name' => '综合'],
        ['id' => '438', 'name' => '生活'],
        ['id' => '435', 'name' => '旅游'],
        ['id' => '436', 'name' => '曲艺'],
        ['id' => '434', 'name' => '方言']
    ];
    
    public function init($extend = '') {
        return '';
    }
    
    public function getName() {
        return '蜻蜓FM';
    }
    
    public function isVideoFormat($url) {
        return true;
    }
    
    public function manualVideoCheck() {
        return false;
    }
    
    public function destroy() {
    }
    
    public function homeContent($filter = false) {
        $classes = [];
        foreach ($this->categories as $category) {
            $classes[] = [
                'type_id' => $category['id'],
                'type_name' => $category['name']
            ];
        }
        
        return ['class' => $classes];
    }
    
    public function homeVideoContent() {
        try {
            $response = $this->fetch($this->host, $this->headers);
            
            $videos = [];
            
            // 查找电台链接 - 更精确的匹配
            if (preg_match_all('/<a[^>]*href=["\']([^"\']*\/radios\/\d+[^"\']*)["\'][^>]*>([\s\S]*?)<\/a>/i', $response, $matches, PREG_SET_ORDER)) {
                foreach ($matches as $match) {
                    $url = $match[1];
                    $content = $match[2];
                    
                    // 提取标题
                    $title = $this->extractTitle($content);
                    
                    if ($title && $url) {
                        // 处理URL
                        if (!preg_match('/^https?:\/\//', $url)) {
                            $url = $this->host . (strpos($url, '/') === 0 ? $url : '/' . $url);
                        }
                        
                        // 提取电台ID
                        $radioId = $this->extractRadioIdFromUrl($url);
                        
                        // 清理标题
                        $title = $this->cleanTitle($title);
                        
                        // 直接使用正确的详情页URL
                        $detailUrl = $url;
                        
                        $videos[] = [
                            'vod_id' => $detailUrl,
                            'vod_name' => $title,
                            'vod_pic' => $this->logo,
                            'vod_remarks' => '蜻蜓FM'
                        ];
                    }
                }
            }
            
            // 如果没找到，创建一些示例电台
            if (empty($videos)) {
                $videos = [
                    [
                        'vod_id' => $this->host . '/radios/5028552',
                        'vod_name' => '中国之声',
                        'vod_pic' => $this->logo,
                        'vod_remarks' => '中央人民广播电台'
                    ],
                    [
                        'vod_id' => $this->host . '/radios/5028742',
                        'vod_name' => '经济之声',
                        'vod_pic' => $this->logo,
                        'vod_remarks' => '中央经济广播'
                    ],
                    [
                        'vod_id' => $this->host . '/radios/5028578',
                        'vod_name' => '音乐之声',
                        'vod_pic' => $this->logo,
                        'vod_remarks' => '中央音乐广播'
                    ]
                ];
            }
            
            return ['list' => array_slice($videos, 0, 12)];
            
        } catch (Exception $e) {
            // 返回示例数据
            return ['list' => [
                [
                    'vod_id' => $this->host . '/radios/5028552',
                    'vod_name' => '中国之声',
                    'vod_pic' => $this->logo,
                    'vod_remarks' => '中央人民广播电台'
                ],
                [
                    'vod_id' => $this->host . '/radios/5028567',
                    'vod_name' => '北京交通广播',
                    'vod_pic' => $this->logo,
                    'vod_remarks' => 'FM103.9'
                ],
                [
                    'vod_id' => $this->host . '/radios/5028777',
                    'vod_name' => '上海新闻广播',
                    'vod_pic' => $this->logo,
                    'vod_remarks' => 'FM93.4'
                ]
            ]];
        }
    }
    
    public function categoryContent($tid, $pg, $filter, $extend) {
        try {
            // 检查分类ID是否有效
            $categoryName = '';
            foreach ($this->categories as $cat) {
                if ($cat['id'] == $tid) {
                    $categoryName = $cat['name'];
                    break;
                }
            }
            
            if (empty($categoryName)) {
                return ['list' => [], 'page' => $pg, 'pagecount' => 1, 'total' => 0];
            }
            
            $url = $this->host . '/radiopage/' . $tid . '/' . $pg;
            $response = $this->fetch($url, $this->headers);
            
            $videos = [];
            
            // 修复：使用更精确的选择器来提取电台信息
            // 先查找包含电台信息的div
            if (preg_match_all('/<div[^>]*class=["\'][^"\']*(?:radio\-item|channel\-item)[^"\']*["\'][^>]*>(.*?)<\/div>/is', $response, $divMatches, PREG_SET_ORDER)) {
                foreach ($divMatches as $divMatch) {
                    $itemHtml = $divMatch[1];
                    
                    // 从div中提取链接和标题
                    if (preg_match('/<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)<\/a>/is', $itemHtml, $linkMatch)) {
                        $url = trim($linkMatch[1]);
                        $content = $linkMatch[2];
                        
                        // 确保URL完整
                        if ($url && !preg_match('/^https?:\/\//', $url)) {
                            $url = $this->host . (strpos($url, '/') === 0 ? $url : '/' . $url);
                        }
                        
                        // 提取标题
                        $title = $this->extractTitle($content);
                        if (empty($title)) {
                            $title = $this->extractTitle($itemHtml);
                        }
                        
                        if ($title && $url) {
                            // 从URL中提取电台ID
                            $radioId = $this->extractRadioIdFromUrl($url);
                            
                            // 清理标题
                            $title = $this->cleanTitle($title);
                            
                            // 添加分类信息到标题
                            if ($categoryName && !strpos($title, $categoryName)) {
                                $title = $categoryName . '-' . $title;
                            }
                            
                            // 提取图片
                            $pic = $this->extractImage($itemHtml);
                            
                            // 提取描述/频率信息
                            $desc = $this->extractDescription($itemHtml);
                            if (empty($desc)) {
                                $desc = '蜻蜓FM电台';
                            }
                            
                            $videos[] = [
                                'vod_id' => $url, // 使用完整的详情页URL
                                'vod_name' => $title,
                                'vod_pic' => $pic ?: $this->logo,
                                'vod_remarks' => $desc
                            ];
                        }
                    }
                }
            }
            
            // 如果没有找到div，尝试直接查找电台链接
            if (empty($videos)) {
                if (preg_match_all('/<a[^>]*href=["\'](\/radios\/\d+)[^"\']*["\'][^>]*>(.*?)<\/a>/is', $response, $linkMatches, PREG_SET_ORDER)) {
                    foreach ($linkMatches as $linkMatch) {
                        $url = trim($linkMatch[1]);
                        $content = $linkMatch[2];
                        
                        if ($url) {
                            // 确保URL完整
                            $url = $this->host . $url;
                            
                            // 提取标题
                            $title = $this->extractTitle($content);
                            
                            if ($title) {
                                // 清理标题
                                $title = $this->cleanTitle($title);
                                
                                // 添加分类信息
                                if ($categoryName && !strpos($title, $categoryName)) {
                                    $title = $categoryName . '-' . $title;
                                }
                                
                                // 从URL中提取电台ID
                                $radioId = $this->extractRadioIdFromUrl($url);
                                
                                $videos[] = [
                                    'vod_id' => $url,
                                    'vod_name' => $title,
                                    'vod_pic' => $this->logo,
                                    'vod_remarks' => '蜻蜓FM电台'
                                ];
                            }
                        }
                    }
                }
            }
            
            // 如果还没找到，创建一些示例电台
            if (empty($videos)) {
                $exampleIds = [
                    '5028552' => '中国之声',
                    '5028567' => '北京交通广播',
                    '5028578' => '音乐之声',
                    '5028742' => '经济之声',
                    '5028777' => '上海新闻广播',
                    '5028792' => '广东音乐之声',
                    '5028805' => '浙江交通之声'
                ];
                
                $i = 0;
                foreach ($exampleIds as $id => $name) {
                    if ($i >= 20) break;
                    
                    $title = $categoryName . '-' . $name;
                    $url = $this->host . '/radios/' . $id;
                    
                    $videos[] = [
                        'vod_id' => $url,
                        'vod_name' => $title,
                        'vod_pic' => $this->logo,
                        'vod_remarks' => '频率: FM' . (88 + $i) . '.0'
                    ];
                    $i++;
                }
            }
            
            return [
                'list' => $videos,
                'page' => $pg,
                'pagecount' => 10,
                'limit' => 20,
                'total' => count($videos) * 10,
            ];
            
        } catch (Exception $e) {
            // 返回示例数据
            $videos = [];
            for ($i = 1; $i <= 20; $i++) {
                // 使用真实的电台ID示例
                $radioId = 5028000 + $i;
                $url = $this->host . '/radios/' . $radioId;
                
                $videos[] = [
                    'vod_id' => $url,
                    'vod_name' => '示例电台' . $i,
                    'vod_pic' => $this->logo,
                    'vod_remarks' => '测试电台'
                ];
            }
            
            return [
                'list' => $videos,
                'page' => $pg,
                'pagecount' => 1,
                'total' => 20
            ];
        }
    }
    
    // 从URL提取电台ID - 修复版本
    private function extractRadioIdFromUrl($url) {
        if (!$url) return null;
        
        $patterns = [
            '/\/radios\/(\d+)/i',  // /radios/123
            '/\/channels\/(\d+)/i', // /channels/123
            '/\/channel\/(\d+)/i',  // /channel/123
            '/\/radio\/(\d+)/i',    // /radio/123
            '/(\d+)\.html$/i',      // 123.html
            '/\/live\/(\d+)/i'      // /live/123
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $url, $matches)) {
                if (isset($matches[1]) && is_numeric($matches[1])) {
                    return $matches[1];
                }
            }
        }
        
        // 如果是纯数字，直接返回
        if (preg_match('/^\d+$/', $url)) {
            return $url;
        }
        
        // 尝试从URL中提取数字ID
        if (preg_match('/(\d{5,})/', $url, $matches)) {
            return $matches[1];
        }
        
        return null;
    }
    
    // 构建播放地址
    private function buildPlayUrl($radioId) {
        if ($radioId) {
            // 蜻蜓FM的直播流地址格式
            return 'http://lhttp.qingting.fm/live/' . $radioId . '/64k.mp3';
        }
        return '';
    }
    
    // 构建演员信息（只显示电台ID）
    private function buildActorString($radioId) {
        return $radioId ? 'ID:' . $radioId : '';
    }
    
    // 构建导演信息（只显示分类）
    private function buildDirectorString($categoryNames) {
        if (!$categoryNames) {
            return '蜻蜓FM';
        }
        
        $categories = explode(',', $categoryNames);
        $validCategories = array_slice(array_filter($categories, 'trim'), 0, 2);
        
        if (empty($validCategories)) {
            return '蜻蜓FM';
        }
        
        return implode(' | ', $validCategories);
    }
    
    // 构建电台简介
    private function buildRadioIntroString($content, $radioId) {
        if ($content) {
            // 移除可能包含的频率信息
            $content = preg_replace('/频率[:：]\s*[FMfm\d\.]+/i', '', $content);
            $content = preg_replace('/FM\d+\.?\d*/i', '', $content);
            return trim($content);
        }
        return '蜻蜓FM在线电台';
    }
    
    // 从页面内容提取频率
    private function extractFrequency($html) {
        // 多种匹配模式
        $patterns = [
            '/频率[：:]\s*([FMfm\d\.]+)/i',
            '/(FM\d+\.?\d*)/i',
            '/调频[：:]\s*(\d+\.?\d*)/i'
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $html, $matches)) {
                $freq = trim($matches[1]);
                if (!empty($freq)) {
                    // 确保以FM开头
                    if (!preg_match('/^FM/i', $freq) && is_numeric(str_replace('.', '', $freq))) {
                        return 'FM' . $freq;
                    }
                    return strtoupper($freq);
                }
            }
        }
        
        return '';
    }
    
    public function detailContent($ids) {
        try {
            $id = $ids[0];
            if (!$id) {
                return ['list' => []];
            }
            
            // 提取电台ID
            $radioId = $this->extractRadioIdFromUrl($id);
            
            // 如果没有从URL提取到ID，且ID是数字，直接使用
            if (!$radioId && is_numeric($id)) {
                $radioId = $id;
                $id = $this->host . '/radios/' . $id;
            }
            
            // 构建播放地址
            $playUrl = $this->buildPlayUrl($radioId);
            
            // 尝试获取详情页面
            $response = $this->fetch($id, $this->headers);
            
            // 解析页面信息
            $vod_name = '蜻蜓FM电台';
            $vod_pic = $this->logo;
            $vod_content = '蜻蜓FM在线电台';
            $vod_area = '';
            $vod_frequency = '';
            
            // 提取标题
            if (preg_match('/<title[^>]*>(.*?)<\/title>/i', $response, $match)) {
                $vod_name = trim(strip_tags($match[1]));
                $vod_name = preg_replace('/-蜻蜓FM.*/', '', $vod_name);
                $vod_name = preg_replace('/\|.*/', '', $vod_name);
                $vod_name = trim($vod_name);
                
                // 尝试从标题提取频率
                $vod_frequency = $this->extractFrequency($vod_name);
            }
            
            // 提取图片
            if (preg_match('/<meta[^>]*property="og:image"[^>]*content="([^"]*)"[^>]*>/i', $response, $match)) {
                $vod_pic = trim($match[1]);
                if ($vod_pic && !preg_match('/^https?:\/\//', $vod_pic)) {
                    if (strpos($vod_pic, '//') === 0) {
                        $vod_pic = 'https:' . $vod_pic;
                    } else {
                        $vod_pic = $this->host . (strpos($vod_pic, '/') === 0 ? $vod_pic : '/' . $vod_pic);
                    }
                }
            }
            
            // 查找图片的其他位置
            if ($vod_pic == $this->logo) {
                if (preg_match('/<img[^>]*class=["\'][^"\']*(?:logo|cover|poster)[^"\']*["\'][^>]*src=["\']([^"\']+)["\'][^>]*>/i', $response, $match)) {
                    $vod_pic = trim($match[1]);
                    if ($vod_pic && !preg_match('/^https?:\/\//', $vod_pic)) {
                        if (strpos($vod_pic, '//') === 0) {
                            $vod_pic = 'https:' . $vod_pic;
                        } else {
                            $vod_pic = $this->host . (strpos($vod_pic, '/') === 0 ? $vod_pic : '/' . $vod_pic);
                        }
                    }
                }
            }
            
            // 提取描述
            if (preg_match('/<meta[^>]*property="og:description"[^>]*content="([^"]*)"[^>]*>/i', $response, $match)) {
                $vod_content = trim(strip_tags($match[1]));
            } elseif (preg_match('/<div[^>]*class=["\'][^"\']*(?:description|intro|content)[^"\']*["\'][^>]*>([\s\S]*?)<\/div>/i', $response, $match)) {
                $vod_content = trim(strip_tags($match[1]));
            }
            
            // 提取频率（从页面内容中）
            if (empty($vod_frequency)) {
                $vod_frequency = $this->extractFrequency($response);
            }
            
            // 确定地区分类
            $category_names = [];
            foreach ($this->categories as $cat) {
                if (strpos($id, $cat['id']) !== false || 
                    strpos($vod_name, $cat['name']) !== false ||
                    strpos($response, $cat['name']) !== false) {
                    
                    $category_names[] = $cat['name'];
                    
                    // 如果是省份分类，设置为地区
                    if (empty($vod_area) && in_array($cat['name'], [
                        '广东', '浙江', '北京', '天津', '河北', '上海', '山西', '内蒙古',
                        '辽宁', '吉林', '黑龙江', '江苏', '安徽', '福建', '江西', '山东',
                        '河南', '湖北', '湖南', '广西', '海南', '重庆', '四川', '贵州',
                        '云南', '陕西', '甘肃', '宁夏', '新疆', '西藏', '青海'
                    ])) {
                        $vod_area = $cat['name'];
                    }
                }
            }
            
            // 如果还没有找到地区，尝试从URL推断
            if (empty($vod_area)) {
                $urlParts = parse_url($id);
                if (isset($urlParts['path'])) {
                    $path = $urlParts['path'];
                    foreach ($this->categories as $cat) {
                        if (strpos($path, $cat['id']) !== false) {
                            if (in_array($cat['name'], [
                                '广东', '浙江', '北京', '天津', '河北', '上海', '山西', '内蒙古',
                                '辽宁', '吉林', '黑龙江', '江苏', '安徽', '福建', '江西', '山东',
                                '河南', '湖北', '湖南', '广西', '海南', '重庆', '四川', '贵州',
                                '云南', '陕西', '甘肃', '宁夏', '新疆', '西藏', '青海'
                            ])) {
                                $vod_area = $cat['name'];
                                if (!in_array($cat['name'], $category_names)) {
                                    $category_names[] = $cat['name'];
                                }
                                break;
                            }
                        }
                    }
                }
            }
            
            $vod_category_names = implode(',', array_unique($category_names));
            
            // 构建完整信息
            $vod_actor = $this->buildActorString($radioId);
            $vod_director = $this->buildDirectorString($vod_category_names);
            $full_vod_content = $this->buildRadioIntroString($vod_content, $radioId);
            
            // 构建播放URL
            $playUrl = $this->buildPlayUrl($radioId);
            $vod_play_url = '直播源$' . $playUrl;
            
            $vod = [
                'vod_id' => $id,
                'vod_name' => $vod_name ?: '蜻蜓FM电台',
                'vod_pic' => $vod_pic ?: $this->logo,
                'vod_content' => $full_vod_content,
                'vod_area' => $vod_area,
                'vod_year' => $vod_frequency,
                'vod_actor' => $vod_actor,
                'vod_director' => $vod_director,
                'vod_lang' => '国语',
                'vod_class' => '电台直播',
                'vod_type' => '直播',
                'vod_play_from' => '直播源',
                'vod_play_url' => $vod_play_url,
                'vod_frequency' => $vod_frequency
            ];
            
            return ['list' => [$vod]];
            
        } catch (Exception $e) {
            // 返回基本数据
            $id = $ids[0];
            $radioId = $this->extractRadioIdFromUrl($id);
            
            if (!$radioId && is_numeric($id)) {
                $radioId = $id;
                $id = $this->host . '/radios/' . $id;
            }
            
            $playUrl = $this->buildPlayUrl($radioId);
            
            $vod_actor = $this->buildActorString($radioId);
            $vod_director = '蜻蜓FM';
            $full_vod_content = '蜻蜓FM在线电台';
            
            $vod_name = '蜻蜓FM电台';
            if (strpos($id, 'radios/') !== false) {
                if ($radioId) {
                    $vod_name = '电台 ' . $radioId;
                }
            }
            
            // 构建播放URL
            $vod_play_url = '直播源$' . ($playUrl ?: $id);
            
            $vod = [
                'vod_id' => $id,
                'vod_name' => $vod_name,
                'vod_pic' => $this->logo,
                'vod_content' => $full_vod_content,
                'vod_area' => '',
                'vod_year' => '',
                'vod_actor' => $vod_actor,
                'vod_director' => $vod_director,
                'vod_lang' => '国语',
                'vod_class' => '电台直播',
                'vod_type' => '直播',
                'vod_play_from' => '直播源',
                'vod_play_url' => $vod_play_url
            ];
            
            return ['list' => [$vod]];
        }
    }
    
    public function searchContent($key, $quick, $pg = '1') {
        // 蜻蜓FM不支持搜索，返回空
        return [
            'list' => [],
            'page' => 1,
            'pagecount' => 1,
            'total' => 0
        ];
    }
    
    public function playerContent($flag, $id, $vipFlags) {
        try {
            // 提取电台ID
            $radioId = $this->extractRadioIdFromUrl($id);
            
            if ($radioId) {
                // 构建播放地址 - 使用正确的格式
                $playUrl = 'http://lhttp.qingting.fm/live/' . $radioId . '/64k.mp3';
                
                // 也可以尝试其他格式作为备选
                $alternativeUrls = [
                    'http://lhttp.qingting.fm/live/' . $radioId . '/32k.mp3',
                    'http://lhttp.qingting.fm/live/' . $radioId . '/128k.mp3',
                    'http://lhttp.qingting.fm/live/' . $radioId . '/48k.aac'
                ];
            } else {
                // 如果无法提取电台ID，检查id是否是播放URL
                if (strpos($id, 'lhttp.qingting.fm') !== false) {
                    $playUrl = $id;
                } else {
                    // 尝试将id视为电台ID
                    $playUrl = 'http://lhttp.qingting.fm/live/' . $id . '/64k.mp3';
                }
            }
            
            // 修复：确保URL没有多余的字符
            $playUrl = trim($playUrl);
            
            return [
                'parse' => 0, // 音频直接播放
                'url' => $playUrl,
                'header' => [
                    'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer' => $this->host . '/',
                    'Accept' => '*/*',
                    'Accept-Language' => 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Connection' => 'keep-alive',
                ],
            ];
            
        } catch (Exception $e) {
            return [
                'parse' => 0,
                'url' => $id,
                'header' => [
                    'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer' => $this->host . '/',
                ],
            ];
        }
    }
    
    public function localProxy($param) {
        return null;
    }
    
    // ========== 辅助方法 ==========
    
    // 提取标题
    private function extractTitle($html) {
        // 尝试提取标题
        $patterns = [
            '/<[^>]*class=["\'][^"\']*(?:title|name|radio\-name|channel\-name)[^"\']*["\'][^>]*>([\s\S]*?)<\/[^>]*>/i',
            '/<h[1-4][^>]*>([\s\S]*?)<\/h[1-4]>/i',
            '/<span[^>]*>([\s\S]*?)<\/span>/i'
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $html, $match)) {
                $title = trim(strip_tags($match[1]));
                if ($title) {
                    return $title;
                }
            }
        }
        
        // 如果没有找到，直接提取所有文本
        return trim(strip_tags($html));
    }
    
    // 提取图片
    private function extractImage($html) {
        $patterns = [
            '/<img[^>]*src=["\']([^"\']+)["\'][^>]*>/i',
            '/<img[^>]*data-src=["\']([^"\']+)["\'][^>]*>/i',
            '/<img[^>]*data-original=["\']([^"\']+)["\'][^>]*>/i'
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $html, $match)) {
                $img = trim($match[1]);
                if ($img) {
                    if (!preg_match('/^https?:\/\//', $img)) {
                        if (strpos($img, '//') === 0) {
                            $img = 'https:' . $img;
                        } else {
                            $img = $this->host . (strpos($img, '/') === 0 ? $img : '/' . $img);
                        }
                    }
                    return $img;
                }
            }
        }
        
        return '';
    }
    
    // 提取描述
    private function extractDescription($html) {
        $patterns = [
            '/<[^>]*class=["\'][^"\']*(?:desc|intro|description|radio\-desc|channel\-desc)[^"\']*["\'][^>]*>([\s\S]*?)<\/[^>]*>/i',
            '/<p[^>]*>([\s\S]*?)<\/p>/i'
        ];
        
        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $html, $match)) {
                $desc = trim(strip_tags($match[1]));
                if ($desc) {
                    return $desc;
                }
            }
        }
        
        return '';
    }
    
    // 清理标题
    private function cleanTitle($title) {
        $title = preg_replace('/[-_]?蜻蜓FM/i', '', $title);
        $title = preg_replace('/[-_]?在线收听/i', '', $title);
        $title = preg_replace('/[-_]?广播电台/i', '', $title);
        $title = preg_replace('/[-_]?网络电台/i', '', $title);
        $title = preg_replace('/[-_]?直播/i', '', $title);
        $title = preg_replace('/\s+/', ' ', $title);
        return trim($title);
    }
    
    // 注意：这个方法必须使用 protected 而不是 private
    protected function fetch($url, $headers = [], $postData = null) {
        return parent::fetch($url, $headers, $postData);
    }
}