<?php

// 设置时区为 Asia/Shanghai
date_default_timezone_set("Asia/Shanghai");

// 定义URL链接，每个链接有一个分类名称
$urls = [
    //"央视卫视" => "https://judy.diver.eu.org/m3u/migu_weishi.m3u",
    //"咪咕卫视" => "https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt",
    "斯玛特源"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/smart.m3u",   
    "香港频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/MytvSuper.m3u",
    "海外体育"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/beesports.m3u",
    "台湾频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/4gtv.m3u",
    "Litv-源"    => "https://raw.githubusercontent.com/judy-gotv/iptv/main/litv.m3u",
    "ofiii-源"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/ofiii.m3u",
    "Now体育-源" => "https://raw.githubusercontent.com/judy-gotv/iptv/main/Nowsports.m3u",
    "印度频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/Yupptv.m3u",
    "美国频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/TVPass.m3u",
    "伊朗频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/Telewebion.m3u",
    "加拿大频道" => "https://raw.githubusercontent.com/judy-gotv/iptv/main/distrotv.m3u",
    "Tubi TV"    => "https://raw.githubusercontent.com/judy-gotv/iptv/main/tubi_playlist.m3u",
    "Xumo频道"   => "https://raw.githubusercontent.com/judy-gotv/iptv/main/xumo_playlist.m3u",

    //"优酷体育" => "https://caonima.pendy.dpdns.org/youku/event.m3u?...",
    //"优酷轮播" => "https://caonima.pendy.dpdns.org/youku/live.m3u?..."
];

// Curl请求内容
function getUrlContent($url) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, 1);
    curl_setopt($ch, CURLOPT_TIMEOUT, 3600);
    curl_setopt($ch, CURLOPT_USERAGENT, "okhttp/5.2.0");
    $output = curl_exec($ch);
    if (curl_errno($ch)) {
        throw new Exception(curl_error($ch));
    }
    curl_close($ch);
    return $output;
}

// 获取并缓存重定向后的 URL
function getCachedUrl($url)
{
    $cacheFile = __DIR__ . '/cache_' . md5($url);
    if (file_exists($cacheFile) && (filemtime($cacheFile) > (time() - 15))) {
        return file_get_contents($cacheFile);
    } else {
        $startTime = microtime(true);
        $finalUrl = getFinalUrl($url);
        $endTime = microtime(true);
        $duration = $endTime - $startTime;
        if ($duration > 2) {
            error_log("URL请求耗时较长: {$duration}秒, URL: {$url}");
        }
        file_put_contents($cacheFile, $finalUrl);
        return $finalUrl;
    }
}

function getFinalUrl($url)
{
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HEADER, true);
    curl_setopt($ch, CURLOPT_NOBODY, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 15);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 5);
    $result = curl_exec($ch);
    if (curl_errno($ch)) {
        error_log("cURL Error in getFinalUrl(): " . curl_error($ch) . " for URL: " . $url);
        curl_close($ch);
        return $url;
    }
    $finalUrl = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
    curl_close($ch);
    return !empty($finalUrl) ? $finalUrl : $url;
}

// 只保留每行第一个group-title，其余全部去除
function keepOnlyFirstGroupTitle($content) {
    return preg_replace_callback('/(#EXTINF:.*)/', function($matches) {
        $line = $matches[1];
        // 找所有 group-title 出现的位置
        preg_match_all('/group-title="[^"]*"/', $line, $allGroupTitles, PREG_OFFSET_CAPTURE);
        if (count($allGroupTitles[0]) <= 1) return $line;
        // 只保留第一个，其它都去掉
        $first = $allGroupTitles[0][0];
        $result = substr($line, 0, $first[1] + strlen($first[0]));
        $remain = substr($line, $first[1] + strlen($first[0]));
        $remain = preg_replace('/\s*group-title="[^"]*"/', '', $remain);
        return $result . $remain;
    }, $content);
}

// 不删内容，仅保留接口（预留）
function removeM3UContent($content) {
    return $content;
}

// 把一行 #EXTINF 重写为带分类的格式：#EXTINF:-1 group-title="分类" ...
function rewriteExtinfWithCategory($line, $category) {
    // 匹配 #EXTINF / #EXTINF:-1 / #EXTINF:0 等前缀
    if (preg_match('/^#EXTINF(?::-?\d+)?(.*)$/', $line, $m)) {
        $rest = $m[1]; // 例如：' tvg-id="翡翠台"... ,翡翠台'
        return '#EXTINF:-1 group-title="' . $category . '"' . $rest;
    }
    return $line;
}

// 初始化M3U内容
$m3uContent = "#EXTM3U\n\n";

foreach ($urls as $category => $url) {
    try {
        $finalUrl = getCachedUrl($url);
        $response = getUrlContent($finalUrl);
    } catch (Exception $e) {
        error_log("获取 {$category} 源失败: " . $e->getMessage());
        continue;
    }

    if ($response === FALSE || trim($response) === '') {
        continue;
    }

    $m3uContent .= "\n#------ {$category} 分类开始 ------\n\n";

    if (strpos($response, '#EXTINF') !== false) {
        // 兼容 \r\n / \n / \r
        $lines = preg_split("/\r\n|\n|\r/", $response);
        $lineCount = count($lines);

        for ($i = 0; $i < $lineCount; $i++) {
            $line = trim($lines[$i]);
            if ($line === '') {
                continue;
            }

            // 只处理 #EXTINF 开头的行
            if (strpos($line, '#EXTINF') === 0) {
                $extinfLine = rewriteExtinfWithCategory($line, $category);
                $m3uContent .= $extinfLine . "\n";

                // 把当前频道所有相关行（#KODIPROP、其他 # 开头、URL）都带上
                $j = $i + 1;
                for (; $j < $lineCount; $j++) {
                    $nextLine = trim($lines[$j]);
                    if ($nextLine === '') {
                        continue;
                    }

                    // 遇到下一条频道，结束当前频道
                    if (strpos($nextLine, '#EXTINF') === 0) {
                        $i = $j - 1;
                        break;
                    }

                    // 1. 所有以 # 开头的行（包括 #KODIPROP）都保留
                    if ($nextLine[0] === '#') {
                        $m3uContent .= $nextLine . "\n";
                        continue;
                    }

                    // 2. URL 行（http/https）保留
                    if (stripos($nextLine, 'http') === 0) {
                        $m3uContent .= $nextLine . "\n";
                        continue;
                    }

                    // 3. 其他类型行，如不想丢，可以放开下面一行：
                    // $m3uContent .= $nextLine . "\n";
                }

                if ($j >= $lineCount) {
                    $i = $lineCount;
                    break;
                }
            }
        }
    }

    $m3uContent .= "\n#------ {$category} 分类结束 ------\n";
}

// 处理内容
$m3uContent = removeM3UContent($m3uContent);
$m3uContent = keepOnlyFirstGroupTitle($m3uContent);

// 定义输出目录（放在网站根目录下 /m3u/juntv.m3u）
$outputDir = __DIR__ . "/m3u";
if (!is_dir($outputDir)) {
    mkdir($outputDir, 0777, true);
}
$outputFile = $outputDir . "/juntv.m3u";
file_put_contents($outputFile, $m3uContent);

// 记录更新时间
$lastUpdate = date('Y-m-d H:i:s');

// 判断当前访问协议（兼容反向代理 / CDN）
$scheme = 'http';
if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
    $scheme = 'https';
}
if (!empty($_SERVER['HTTP_X_FORWARDED_PROTO'])) {
    $scheme = $_SERVER['HTTP_X_FORWARDED_PROTO'];
}
if (isset($_SERVER['SERVER_PORT']) && $_SERVER['SERVER_PORT'] == 443) {
    $scheme = 'https';
}

$host = $_SERVER['HTTP_HOST'] ?? 'localhost';

// 计算脚本目录
$scriptDir = rtrim(dirname($_SERVER['SCRIPT_NAME']), '/\\');
if ($scriptDir === '/' || $scriptDir === '\\' || $scriptDir === '.') {
    $scriptDir = '';
}
$subscriptionPath = $scriptDir . '/m3u/juntv.m3u';

// 拼出完整订阅 URL
$subscriptionUrl = $scheme . '://' . $host . $subscriptionPath;

// 输出 HTML
header('Content-Type: text/html; charset=utf-8');

?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>IPTV 订阅中心</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg-gradient: radial-gradient(circle at top, #4f46e5 0, #111827 45%, #020617 100%);
            --card-bg: rgba(15, 23, 42, 0.9);
            --accent: #38bdf8;
            --accent-soft: rgba(56, 189, 248, 0.1);
            --text-main: #e5e7eb;
            --text-muted: #9ca3af;
            --border-subtle: rgba(148, 163, 184, 0.3);
        }
        * {
            box-sizing: border-box;
        }
        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Microsoft Yahei", sans-serif;
            background: var(--bg-gradient);
            color: var(--text-main);
        }
        .wrapper {
            width: 100%;
            max-width: 860px;
        }
        .card {
            position: relative;
            background: var(--card-bg);
            border-radius: 20px;
            padding: 24px 24px 26px;
            box-shadow:
                0 30px 80px rgba(15, 23, 42, 0.8),
                0 0 0 1px rgba(148, 163, 184, 0.3);
            overflow: hidden;
        }
        .card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at top left, rgba(56, 189, 248, 0.22), transparent 55%);
            opacity: 0.85;
            pointer-events: none;
        }
        .card-inner {
            position: relative;
            z-index: 1;
        }
        .header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }
        .title-block h1 {
            font-size: 22px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .title-pill {
            font-size: 11px;
            border-radius: 999px;
            padding: 2px 8px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.6);
            color: var(--text-muted);
        }
        .subtitle {
            margin: 4px 0 0;
            font-size: 13px;
            color: var(--text-muted);
        }
        .meta {
            text-align: right;
            font-size: 12px;
            color: var(--text-muted);
        }
        .meta strong {
            color: var(--accent);
        }
        .meta span {
            display: block;
        }
        .section {
            margin-top: 18px;
        }
        .section-title {
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: .12em;
            color: var(--text-muted);
            margin-bottom: 7px;
        }
        .subscription-box {
            background: rgba(15, 23, 42, 0.9);
            border-radius: 14px;
            border: 1px solid var(--border-subtle);
            padding: 10px 12px;
            display: flex;
            gap: 8px;
            align-items: stretch;
        }
        .subscription-url {
            flex: 1;
            background: rgba(15, 23, 42, 0.9);
            border-radius: 10px;
            padding: 7px 9px;
            font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 13px;
            color: #e5e7eb;
            border: 1px solid rgba(75, 85, 99, 0.8);
            overflow-x: auto;
            white-space: nowrap;
        }
        .btn-copy {
            flex-shrink: 0;
            border: none;
            border-radius: 10px;
            padding: 0 14px;
            font-size: 13px;
            cursor: pointer;
            background: linear-gradient(135deg, #38bdf8, #6366f1);
            color: #0b1120;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 10px 25px rgba(37, 99, 235, 0.55);
            transition: transform 0.08s ease-out, box-shadow 0.08s ease-out, filter 0.1s ease-out;
        }
        .btn-copy span.icon {
            font-size: 14px;
        }
        .btn-copy:hover {
            transform: translateY(-1px);
            filter: brightness(1.05);
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.7);
        }
        .btn-copy:active {
            transform: translateY(0);
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5);
        }
        .hint {
            margin-top: 8px;
            font-size: 12px;
            color: var(--text-muted);
        }
        .hint a {
            color: var(--accent);
            text-decoration: none;
        }
        .hint a:hover {
            text-decoration: underline;
        }
        .chips {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 6px;
        }
        .chip {
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.4);
            background: rgba(15, 23, 42, 0.85);
            color: var(--text-muted);
        }
        .footer {
            margin-top: 18px;
            font-size: 11px;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
            gap: 8px;
            flex-wrap: wrap;
        }
        @media (max-width: 640px) {
            body {
                padding: 16px;
            }
            .card {
                padding: 20px 16px 22px;
            }
            .header-row {
                flex-direction: column;
                align-items: flex-start;
            }
            .meta {
                text-align: left;
            }
            .subscription-box {
                flex-direction: column;
            }
            .btn-copy {
                justify-content: center;
                height: 36px;
            }
        }
    </style>
</head>
<body>
<div class="wrapper">
    <div class="card">
        <div class="card-inner">
            <div class="header-row">
                <div class="title-block">
                    <h1>
                        IPTV 订阅中心
                        <span class="title-pill">自动聚合 · M3U</span>
                    </h1>
                    <p class="subtitle">聚合多个地区源，一键订阅到你的 IPTV 播放器。</p>
                </div>
                <div class="meta">
                    <span>最后更新：<strong><?php echo htmlspecialchars($lastUpdate, ENT_QUOTES, 'UTF-8'); ?></strong></span>
                    <span>当前分类：<?php echo count($urls); ?> 个源</span>
                </div>
            </div>

            <div class="section">
                <div class="section-title">订阅链接</div>
                <div class="subscription-box">
                    <div class="subscription-url" id="sub-url">
                        <?php echo htmlspecialchars($subscriptionUrl, ENT_QUOTES, 'UTF-8'); ?>
                    </div>
                    <button class="btn-copy" id="btn-copy" type="button">
                        <span class="icon">📋</span>
                        <span>复制链接</span>
                    </button>
                </div>
                <p class="hint">
                    在 IPTV 播放器中选择「网络订阅 / 远程播放列表」，粘贴上面的链接即可。<br>
                    如果播放器不支持远程订阅，也可以
                    <a href="<?php echo htmlspecialchars($subscriptionPath, ENT_QUOTES, 'UTF-8'); ?>" target="_blank" rel="noopener">
                        点此直接打开 juntv.m3u 文件
                    </a> 并手动导入。
                </p>
            </div>

            <div class="section">
                <div class="section-title">已聚合的分类</div>
                <div class="chips">
                    <?php foreach ($urls as $category => $_): ?>
                        <span class="chip"><?php echo htmlspecialchars($category, ENT_QUOTES, 'UTF-8'); ?></span>
                    <?php endforeach; ?>
                </div>
            </div>

            <div class="footer">
                <span>提示：如果频道列表不更新，可以尝试刷新本页面，让服务器重新拉取各源。</span>
                <span>Powered by juntv · PHP + M3U 聚合</span>
            </div>
        </div>
    </div>
</div>

<script>
    (function () {
        var btn = document.getElementById('btn-copy');
        var urlEl = document.getElementById('sub-url');
        if (!btn || !urlEl) return;

        btn.addEventListener('click', function () {
            var text = urlEl.textContent.trim();
            if (!text) return;

            function setState(label, icon) {
                btn.querySelector('span:nth-child(2)').textContent = label;
                btn.querySelector('.icon').textContent = icon;
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function () {
                    setState('已复制', '✅');
                    setTimeout(function () {
                        setState('复制链接', '📋');
                    }, 1600);
                }).catch(function () {
                    // 失败时退回到旧方法
                    var textarea = document.createElement('textarea');
                    textarea.value = text;
                    textarea.style.position = 'fixed';
                    textarea.style.opacity = '0';
                    document.body.appendChild(textarea);
                    textarea.select();
                    try {
                        document.execCommand('copy');
                        setState('已复制', '✅');
                    } catch (e) {
                        setState('复制失败', '⚠️');
                    }
                    document.body.removeChild(textarea);
                    setTimeout(function () {
                        setState('复制链接', '📋');
                    }, 1600);
                });
            } else {
                // 不支持 clipboard API 的备用方案
                var textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    document.execCommand('copy');
                    setState('已复制', '✅');
                } catch (e) {
                    setState('复制失败', '⚠️');
                }
                document.body.removeChild(textarea);
                setTimeout(function () {
                    setState('复制链接', '📋');
                }, 1600);
            }
        });
    })();
</script>
</body>
</html>
