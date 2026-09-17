<?php
/**
 * TVB云播 - PHP 版本
 * 基于甜圈短剧模板修改
 */

class Spider extends BaseSpider {
    
    private $ahost = 'http://www.viptv01.com';
    
    private $headers = [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding: gzip, deflate',
        'Connection: keep-alive',
        'Upgrade-Insecure-Requests: 1',
        'Cache-Control: max-age=0',
    ];
    
    public function init($extend = '') {
        return '';
    }
    
    public function getName() {
        return 'TVB云播';
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
        $result = [
            'class' => [
                ['type_id' => '2', 'type_name' => '剧集'],
                ['type_id' => '1', 'type_name' => '电影'],
                ['type_id' => '3', 'type_name' => '综艺'],
                ['type_id' => '4', 'type_name' => '动漫'],
                ['type_id' => '5', 'type_name' => '短剧'],
                ['type_id' => '16', 'type_name' => '日韩剧'],
                ['type_id' => '13', 'type_name' => '国产剧'],
                ['type_id' => '15', 'type_name' => '欧美剧'],
                ['type_id' => '14', 'type_name' => '港台剧']
            ]
        ];
        return $result;
    }
    
    public function homeVideoContent() {
        return ['list' => []];
    }
    
    public function categoryContent($tid, $pg, $filter, $extend) {
        $url = $this->ahost . "/vod/show/id/{$tid}/page/{$pg}.html";
        $response = $this->fetch($url);
        
        if (empty($response)) {
            return ['list' => [], 'page' => $pg, 'pagecount' => 0, 'limit' => 20];
        }
        
        $list = [];
        
        // 使用正则表达式提取视频列表 - 改进版本
        // 匹配整个视频项目块
        preg_match_all('/<li class="col-lg-8 col-md-6 col-sm-4 col-xs-3">(.*?)<\/li>/s', $response, $itemMatches);
        
        foreach ($itemMatches[1] as $itemHtml) {
            // 提取链接和标题
            if (preg_match('/<a[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>/', $itemHtml, $linkMatch)) {
                $vod_id = $linkMatch[1];
                $vod_name = isset($linkMatch[2]) ? htmlspecialchars_decode($linkMatch[2]) : '';
                
                // 提取图片 - 改进的图片提取逻辑
                $vod_pic = '';
                
                // 尝试多种图片属性
                $imgPatterns = [
                    '/<img[^>]*data-original="([^"]+)"[^>]*>/',
                    '/<img[^>]*data-src="([^"]+)"[^>]*>/',
                    '/<img[^>]*src="([^"]+)"[^>]*>/',
                    '/background-image:\s*url\([\'"]?([^\'"\)]+)[\'"]?\)/'
                ];
                
                foreach ($imgPatterns as $pattern) {
                    if (preg_match($pattern, $itemHtml, $imgMatch)) {
                        $vod_pic = $imgMatch[1];
                        // 清理图片URL
                        $vod_pic = str_replace(['&quot;', '&#039;'], ['"', "'"], $vod_pic);
                        $vod_pic = trim($vod_pic);
                        
                        // 处理相对路径
                        if ($vod_pic && !preg_match('/^https?:\/\//', $vod_pic)) {
                            if (strpos($vod_pic, '//') === 0) {
                                $vod_pic = 'http:' . $vod_pic;
                            } elseif (strpos($vod_pic, '/') === 0) {
                                $vod_pic = $this->ahost . $vod_pic;
                            } else {
                                $vod_pic = $this->ahost . '/' . $vod_pic;
                            }
                        }
                        break;
                    }
                }
                
                // 如果还是没有找到图片，尝试从a标签的style中提取
                if (empty($vod_pic)) {
                    if (preg_match('/<a[^>]*style="[^"]*background-image:\s*url\([\'"]?([^\'"\)]+)[\'"]?\)[^"]*"[^>]*>/', $itemHtml, $styleMatch)) {
                        $vod_pic = $styleMatch[1];
                        if ($vod_pic && !preg_match('/^https?:\/\//', $vod_pic)) {
                            if (strpos($vod_pic, '//') === 0) {
                                $vod_pic = 'http:' . $vod_pic;
                            } elseif (strpos($vod_pic, '/') === 0) {
                                $vod_pic = $this->ahost . $vod_pic;
                            }
                        }
                    }
                }
                
                // 提取备注
                $vod_remarks = '';
                if (preg_match('/<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]+)<\/span>/', $itemHtml, $remarkMatch)) {
                    $vod_remarks = $remarkMatch[1];
                }
                
                // 如果备注为空，尝试其他选择器
                if (empty($vod_remarks) && preg_match('/<span[^>]*class="[^"]*tag[^"]*"[^>]*>([^<]+)<\/span>/', $itemHtml, $tagMatch)) {
                    $vod_remarks = $tagMatch[1];
                }
                
                $list[] = [
                    'vod_id' => $vod_id,
                    'vod_name' => $vod_name,
                    'vod_pic' => $vod_pic,
                    'vod_remarks' => $vod_remarks
                ];
            }
        }
        
        // 备用方法：如果上面没找到，尝试更宽松的匹配
        if (empty($list)) {
            preg_match_all('/<a[^>]*href="(\/vod\/detail[^"]+)"[^>]*>/', $response, $linkMatches);
            foreach ($linkMatches[1] as $index => $vod_id) {
                // 获取标题
                $vod_name = '';
                if (preg_match('/title="([^"]+)"/', $linkMatches[0][$index], $titleMatch)) {
                    $vod_name = htmlspecialchars_decode($titleMatch[1]);
                }
                
                // 获取图片
                $vod_pic = '';
                if (preg_match('/data-original="([^"]+)"/', $linkMatches[0][$index], $imgMatch)) {
                    $vod_pic = $imgMatch[1];
                    if (!preg_match('/^https?:\/\//', $vod_pic)) {
                        if (strpos($vod_pic, '//') === 0) {
                            $vod_pic = 'http:' . $vod_pic;
                        } elseif (strpos($vod_pic, '/') === 0) {
                            $vod_pic = $this->ahost . $vod_pic;
                        }
                    }
                }
                
                if ($vod_name) {
                    $list[] = [
                        'vod_id' => $vod_id,
                        'vod_name' => $vod_name,
                        'vod_pic' => $vod_pic,
                        'vod_remarks' => ''
                    ];
                }
            }
        }
        
        // 获取总页数
        $pagecount = 999;
        if (preg_match('/<li><a[^>]*>(\d+)<\/a><\/li>\s*<\/ul>/', $response, $pageMatch)) {
            $pagecount = intval($pageMatch[1]);
        } elseif (preg_match_all('/<a[^>]*href="[^"]*\/page\/(\d+)[^"]*"[^>]*>\d+<\/a>/', $response, $pageMatches)) {
            if (!empty($pageMatches[1])) {
                $pagecount = max($pageMatches[1]);
            }
        }
        
        return [
            'list' => $list,
            'page' => intval($pg),
            'pagecount' => $pagecount,
            'limit' => 20,
            'total' => count($list)
        ];
    }
    
    public function detailContent($ids) {
        $url = $this->ahost . $ids[0];
        $response = $this->fetch($url);
        
        if (empty($response)) {
            return ['list' => []];
        }
        
        $vod = [
            'vod_id' => $ids[0],
            'vod_name' => '',
            'vod_pic' => '',
            'vod_type' => '',
            'vod_year' => '',
            'vod_area' => '',
            'vod_content' => '',
            'vod_play_from' => '',
            'vod_play_url' => ''
        ];
        
        // 提取标题
        if (preg_match('/<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\/h1>/', $response, $titleMatch)) {
            $vod['vod_name'] = htmlspecialchars_decode(trim($titleMatch[1]));
        }
        
        // 提取图片
        if (preg_match('/<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]+)"[^>]*>/', $response, $picMatch)) {
            $vod['vod_pic'] = $picMatch[1];
            // 处理相对路径
            if ($vod['vod_pic'] && !preg_match('/^https?:\/\//', $vod['vod_pic'])) {
                if (strpos($vod['vod_pic'], '//') === 0) {
                    $vod['vod_pic'] = 'http:' . $vod['vod_pic'];
                } elseif (strpos($vod['vod_pic'], '/') === 0) {
                    $vod['vod_pic'] = $this->ahost . $vod['vod_pic'];
                }
            }
        }
        
        // 提取类型、年份、地区
        if (preg_match('/<div[^>]*class="[^"]*data[^"]*"[^>]*>(.*?)<\/div>/', $response, $dataMatch)) {
            $dataHtml = $dataMatch[1];
            if (preg_match_all('/<a[^>]*>([^<]+)<\/a>/', $dataHtml, $dataLinks)) {
                if (isset($dataLinks[1][0])) $vod['vod_area'] = $dataLinks[1][0];
                if (isset($dataLinks[1][1])) $vod['vod_type'] = $dataLinks[1][1];
                if (isset($dataLinks[1][2])) $vod['vod_year'] = $dataLinks[1][2];
            }
        }
        
        // 提取剧情简介
        if (preg_match('/<div[^>]*class="[^"]*text-collapse[^"]*"[^>]*>.*?<span[^>]*>(.*?)<\/span>/s', $response, $descMatch)) {
            $vod['vod_content'] = trim(strip_tags($descMatch[1]));
        }
        
        // 提取播放列表
        $playFrom = [];
        $playUrl = [];
        
        // 查找所有播放面板
        preg_match_all('/<div[^>]*class="[^"]*myui-panel[^"]*"[^>]*>(.*?)<\/div>\s*<\/div>\s*<\/div>/s', $response, $panelMatches);
        
        foreach ($panelMatches[1] as $panelHtml) {
            // 提取面板标题
            if (preg_match('/<h3[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<\/h3>/', $panelHtml, $titleMatch)) {
                $title = trim($titleMatch[1]);
                
                // 排除非播放列表的面板
                if (strpos($title, '猜你喜欢') !== false || 
                    strpos($title, '热播') !== false ||
                    strpos($title, '剧情介绍') !== false ||
                    strpos($title, '演员') !== false ||
                    strpos($title, '角色') !== false) {
                    continue;
                }
                
                // 提取播放列表项
                $episodes = [];
                preg_match_all('/<a[^>]*href="([^"]+)"[^>]*>([^<]+)<\/a>/', $panelHtml, $episodeMatches, PREG_SET_ORDER);
                
                foreach ($episodeMatches as $episodeMatch) {
                    $epName = trim($episodeMatch[2]);
                    $epUrl = $episodeMatch[1];
                    $episodes[] = $epName . '$' . $epUrl;
                }
                
                if (!empty($episodes)) {
                    // 清理标题
                    $cleanTitle = preg_replace('/播放列表$|线路\d+$/', '', $title);
                    $cleanTitle = trim($cleanTitle);
                    
                    if (empty($cleanTitle)) {
                        $cleanTitle = '线路' . (count($playFrom) + 1);
                    }
                    
                    $playFrom[] = $cleanTitle;
                    $playUrl[] = implode('#', $episodes);
                }
            }
        }
        
        // 备用方法：如果上面没找到，尝试查找播放列表
        if (empty($playFrom)) {
            preg_match_all('/<ul[^>]*class="[^"]*myui-content__list[^"]*"[^>]*>(.*?)<\/ul>/s', $response, $listMatches);
            foreach ($listMatches[1] as $listIndex => $listHtml) {
                $episodes = [];
                preg_match_all('/<a[^>]*href="([^"]+)"[^>]*>([^<]+)<\/a>/', $listHtml, $episodeMatches, PREG_SET_ORDER);
                
                foreach ($episodeMatches as $episodeMatch) {
                    $epName = trim($episodeMatch[2]);
                    $epUrl = $episodeMatch[1];
                    $episodes[] = $epName . '$' . $epUrl;
                }
                
                if (!empty($episodes)) {
                    $playFrom[] = '线路' . ($listIndex + 1);
                    $playUrl[] = implode('#', $episodes);
                }
            }
        }
        
        if (!empty($playFrom)) {
            $vod['vod_play_from'] = implode('$$$', $playFrom);
            $vod['vod_play_url'] = implode('$$$', $playUrl);
        }
        
        return ['list' => [$vod]];
    }
    
    public function searchContent($key, $quick, $pg = '1') {
        $encodedKey = urlencode($key);
        $url = $this->ahost . "/vod/search/page/{$pg}?wd={$encodedKey}&submit=";
        
        $headers = $this->headers;
        $headers[] = "Referer: " . $this->ahost;
        
        $response = $this->fetch($url, $headers);
        
        if (empty($response)) {
            return ['list' => [], 'page' => $pg, 'pagecount' => 0, 'limit' => 20];
        }
        
        $list = [];
        
        // 使用正则表达式提取搜索结果
        preg_match_all('/<div class="myui-vodlist__box">(.*?)<\/div>/s', $response, $boxMatches);
        
        foreach ($boxMatches[1] as $boxHtml) {
            // 提取链接和标题
            if (preg_match('/<a[^>]*href="([^"]+)"[^>]*title="([^"]*)"[^>]*>/', $boxHtml, $linkMatch)) {
                $vod_id = $linkMatch[1];
                $vod_name = isset($linkMatch[2]) ? htmlspecialchars_decode($linkMatch[2]) : '';
                
                // 检查标题是否包含搜索关键词
                if (stripos($vod_name, $key) === false) {
                    continue;
                }
                
                // 提取图片
                $vod_pic = '';
                if (preg_match('/<img[^>]*data-original="([^"]+)"[^>]*>/', $boxHtml, $imgMatch)) {
                    $vod_pic = $imgMatch[1];
                    // 处理相对路径
                    if ($vod_pic && !preg_match('/^https?:\/\//', $vod_pic)) {
                        if (strpos($vod_pic, '//') === 0) {
                            $vod_pic = 'http:' . $vod_pic;
                        } elseif (strpos($vod_pic, '/') === 0) {
                            $vod_pic = $this->ahost . $vod_pic;
                        }
                    }
                }
                
                // 提取备注
                $vod_remarks = '';
                if (preg_match('/<span[^>]*class="pic-text[^"]*"[^>]*>([^<]+)<\/span>/', $boxHtml, $remarkMatch)) {
                    $vod_remarks = $remarkMatch[1];
                }
                
                $list[] = [
                    'vod_id' => $vod_id,
                    'vod_name' => $vod_name,
                    'vod_pic' => $vod_pic,
                    'vod_remarks' => $vod_remarks
                ];
            }
        }
        
        // 获取总页数
        $pagecount = intval($pg);
        if (preg_match_all('/<a[^>]*href="[^"]*\/page\/(\d+)[^"]*"[^>]*>\d+<\/a>/', $response, $pageMatches)) {
            if (!empty($pageMatches[1])) {
                $pagecount = max($pageMatches[1]);
            }
        }
        
        return [
            'list' => $list,
            'page' => intval($pg),
            'pagecount' => $pagecount,
            'limit' => 20,
            'total' => count($list)
        ];
    }
    
    public function playerContent($flag, $id, $vipFlags) {
        $url = $this->ahost . $id;
        $response = $this->fetch($url);
        
        if (empty($response)) {
            return [
                'parse' => 1,
                'url' => $url
            ];
        }
        
        // 尝试提取播放地址
        $playUrl = '';
        
        // 模式1: player_xxxx = { ... }
        if (preg_match('/player_[^=]*=\s*(\{[^;]+\});/s', $response, $playerMatch)) {
            try {
                $playerData = json_decode($playerMatch[1], true);
                
                if (isset($playerData['url'])) {
                    $playUrl = $playerData['url'];
                    
                    // 处理加密
                    if (isset($playerData['encrypt'])) {
                        if ($playerData['encrypt'] == '1') {
                            $playUrl = urldecode($playUrl);
                        } elseif ($playerData['encrypt'] == '2') {
                            $playUrl = base64_decode($playUrl);
                        }
                    }
                }
            } catch (Exception $e) {
                error_log('JSON解析失败: ' . $e->getMessage());
            }
        }
        
        // 模式2: 直接查找视频URL
        if (empty($playUrl)) {
            $videoPatterns = [
                '/"url"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"/',
                '/"url":"([^"]+\.(?:m3u8|mp4)[^"]*)"/',
                '/src="([^"]+\.(?:m3u8|mp4)[^"]*)"/',
                '/file:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']/',
                '/unescape\s*\(\s*["\']([^"\']+)["\']\s*\)/'
            ];
            
            foreach ($videoPatterns as $pattern) {
                if (preg_match($pattern, $response, $urlMatch)) {
                    $playUrl = $urlMatch[1];
                    break;
                }
            }
        }
        
        // 模式3: 查找base64编码的URL
        if (empty($playUrl) && preg_match('/base64_decode\s*\(\s*["\']([^"\']+)["\']\s*\)/', $response, $base64Match)) {
            $playUrl = base64_decode($base64Match[1]);
        }
        
        // 清理URL - 修复斜杠转义问题
        if (!empty($playUrl)) {
            // 解码URL编码
            $playUrl = urldecode($playUrl);
            
            // 修复常见的转义字符
            $playUrl = str_replace(
                ['\/\/', '\/', '\:', '\?', '\=', '\&', '\\"', "\\'"],
                ['//', '/', ':', '?', '=', '&', '"', "'"],
                $playUrl
            );
            
            // 移除多余的转义
            $playUrl = stripslashes($playUrl);
            $playUrl = trim($playUrl);
            
            // 如果是相对路径，转换为绝对路径
            if (strpos($playUrl, 'http') !== 0) {
                if (strpos($playUrl, '//') === 0) {
                    $playUrl = 'http:' . $playUrl;
                } elseif (strpos($playUrl, '/') === 0) {
                    $playUrl = $this->ahost . $playUrl;
                } else {
                    $playUrl = $this->ahost . '/' . $playUrl;
                }
            }
            
            // 最终清理，确保URL格式正确
            $playUrl = html_entity_decode($playUrl, ENT_QUOTES | ENT_HTML5);
            
            return [
                'parse' => 0,
                'url' => $playUrl,
                'header' => [
                    'User-Agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer' => $this->ahost
                ]
            ];
        }
        
        // 如果无法解析，返回原始页面
        return [
            'parse' => 1,
            'url' => $url
        ];
    }
    
    public function localProxy($param) {
        return null;
    }
}