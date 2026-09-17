<?php
/* 频道对照表 */
$map = [
    'cctv1'=>1,'cctv2'=>2,'cctv3'=>3,'cctv4'=>4,'cctv5'=>5,'cctv6'=>6,'cctv7'=>7,'cctv8'=>8,
    'cctv9'=>9,'cctv10'=>10,'cctv13'=>13,'cctv16'=>16,'cctv5p'=>17,
    'bjws'=>18,'ahws'=>19,'dnws'=>20,'gsws'=>21,'gdws'=>22,'gxws'=>23,'gzws'=>24,'hnws'=>25,
    'hbws'=>26,'hnws2'=>27,'hljws'=>28,'hubws'=>29,'hunws'=>30,'jlws'=>31,'jsws'=>32,'jxws'=>33,
    'lnws'=>34,'qhws'=>35,'sdws'=>36,'szws'=>37,'scws'=>38,'tjws'=>39,'ynws'=>40,'zjws'=>41,
    'cqws'=>42,'dfws'=>43,
    'khdy1'=>131,'khdy2'=>132,'khdy3'=>133,'gpdy1'=>134,'gpdy2'=>135,'gpdy3'=>136,
    'cjdy'=>138,'mrxl'=>139,'mwdy'=>140,'jxdz'=>141,'jsdy'=>142,'gwdz'=>143,
    'gnxj'=>144,'gndz'=>145,'zxc'=>231,'lzy'=>233,'wj'=>235,
    'stml'=>57,'sb'=>53,'jl'=>54,'jdjp'=>55,'zbs'=>56,
];

$name = strtolower(trim($_GET['id'] ?? ''));
if (!isset($map[$name])) {
    http_response_code(404);
    exit('Unknown channel');
}
$cid = $map[$name];

/* 抓远程 js */
$js = file_get_contents('https://zxbv5123.xymjzxyey.com/assets/js/tv.js', false,
    stream_context_create(['http'=>['timeout'=>10,'header'=>'User-Agent: Mozilla/5.0']]));
if (!$js) exit('fetch failed');

/* 先尝试解析 tvdata */
if (preg_match('/var\s+tvdata\s*=\s*(\[.*?\])/is', $js, $m)) {
    $json = preg_replace('/(\w+):/', '"$1":', $m[1]);
    $json = str_replace("'", '"', $json);
    $json = preg_replace('/,\s*}/', '}', $json);
    $arr = json_decode($json, true);
    if ($arr) foreach ($arr as $g) foreach ($g['tvlist'] ?? [] as $ch)
        if (($ch['id'] ?? 0) == $cid && !empty($ch['vurl']))
            redirect($ch['vurl']);
}

/* 兜底正则 */
if (preg_match_all('/\{[^}]*\bid:\s*(\d+)[^}]*\bvurl:\s*["\'](.*?)["\'][^}]*}/is', $js, $mm))
    foreach ($mm[1] as $k => $v) if ((int)$v === $cid) redirect($mm[2][$k]);

http_response_code(404); exit('stream not found');

function redirect(string $url): void
{
    header('Location: ' . $url, true, 302);
    exit;
}