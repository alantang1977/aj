<?php
// ===================== 合并后的频道数据 =====================
$channels = [
    'cctv1'     => ['name' => 'CCTV-1高清',     'cnlid' => '2024078201', 'livepid' => '600001859', 'defn' => 'fhd'],
    'cctv2'     => ['name' => 'CCTV-2高清',     'cnlid' => '2024075401', 'livepid' => '600001800', 'defn' => 'fhd'],
    'cctv3'     => ['name' => 'CCTV-3高清',     'cnlid' => '2024068501', 'livepid' => '600001801', 'defn' => 'fhd'],
    'cctv4'     => ['name' => 'CCTV-4高清',     'cnlid' => '2029797101', 'livepid' => '600001814', 'defn' => 'fhd'],
    'cctv5'     => ['name' => 'CCTV-5高清',     'cnlid' => '2024078401', 'livepid' => '600001818', 'defn' => 'fhd'],
    'cctv5p'    => ['name' => 'CCTV-5+高清',    'cnlid' => '2024078001', 'livepid' => '600001817', 'defn' => 'fhd'],
    'cctv6'     => ['name' => 'CCTV-6高清',     'cnlid' => '2013693901', 'livepid' => '600108442', 'defn' => 'fhd'],
    'cctv7'     => ['name' => 'CCTV-7高清',     'cnlid' => '2024072001', 'livepid' => '600004092', 'defn' => 'fhd'],
    'cctv8'     => ['name' => 'CCTV-8高清',     'cnlid' => '2029793001', 'livepid' => '600001803', 'defn' => 'fhd'],
    'cctv9'     => ['name' => 'CCTV-9高清',     'cnlid' => '2024078601', 'livepid' => '600004078', 'defn' => 'fhd'],
    'cctv10'    => ['name' => 'CCTV-10高清',    'cnlid' => '2024078701', 'livepid' => '600001805', 'defn' => 'fhd'],
    'cctv11'    => ['name' => 'CCTV-11高清',    'cnlid' => '2027248701', 'livepid' => '600001806', 'defn' => 'fhd'],
    'cctv12'    => ['name' => 'CCTV-12高清',    'cnlid' => '2027248801', 'livepid' => '600001807', 'defn' => 'fhd'],
    'cctv13'    => ['name' => 'CCTV-13高清',    'cnlid' => '2029797201', 'livepid' => '600001811', 'defn' => 'fhd'],
    'cctv14'    => ['name' => 'CCTV-14高清',    'cnlid' => '2027248901', 'livepid' => '600001809', 'defn' => 'fhd'],
    'cctv15'    => ['name' => 'CCTV-15高清',    'cnlid' => '2027249001', 'livepid' => '600001815', 'defn' => 'fhd'],
    'cctv16'    => ['name' => 'CCTV-16高清',    'cnlid' => '2027249101', 'livepid' => '600098637', 'defn' => 'fhd'],
    'cctv164k'  => ['name' => 'CCTV-16(4K)',    'cnlid' => '2027249301', 'livepid' => '600099502', 'defn' => 'fhd'],
    'cctv17'    => ['name' => 'CCTV-17高清',    'cnlid' => '2027249401', 'livepid' => '600001810', 'defn' => 'fhd'],
    'cctv4k'    => ['name' => 'CCTV-4K',        'cnlid' => '2029810301', 'livepid' => '600002264', 'defn' => 'fhd'],
    'cctv8k'    => ['name' => 'CCTV-8K',        'cnlid' => '2026774101', 'livepid' => '600156816', 'defn' => 'fhd'],
    'cgtn'      => ['name' => 'CGTN',           'cnlid' => '2024181701', 'livepid' => '600014550', 'defn' => 'fhd'],
    'cgtnfy'    => ['name' => 'CGTN法语频道',   'cnlid' => '2024181801', 'livepid' => '600084704', 'defn' => 'fhd'],
    'cgtney'    => ['name' => 'CGTN俄语频道',   'cnlid' => '2024181901', 'livepid' => '600084758', 'defn' => 'fhd'],
    'cgtnalby'  => ['name' => 'CGTN阿拉伯语频道','cnlid' => '2024182001', 'livepid' => '600084782', 'defn' => 'fhd'],
    'cgtnxby'   => ['name' => 'CGTN西班牙语频道','cnlid' => '2024182101', 'livepid' => '600084744', 'defn' => 'fhd'],
    'cgtnwyjl'  => ['name' => 'CGTN外语纪录频道','cnlid' => '2024182301', 'livepid' => '600084781', 'defn' => 'fhd'],
    'cctvfyjc'  => ['name' => 'CCTV风云剧场',   'cnlid' => '2025637103', 'livepid' => '600099658', 'defn' => 'shd'],
    'cctvdyjc'  => ['name' => 'CCTV第一剧场',   'cnlid' => '2026874203', 'livepid' => '600099655', 'defn' => 'shd'],
    'cctvhjjc'  => ['name' => 'CCTV怀旧剧场',   'cnlid' => '2026874303', 'livepid' => '600099620', 'defn' => 'shd'],
    'cctvsjdl'  => ['name' => 'CCTV世界地理',   'cnlid' => '2026874403', 'livepid' => '600099637', 'defn' => 'shd'],
    'cctvfyyy'  => ['name' => 'CCTV风云音乐',   'cnlid' => '2026874503', 'livepid' => '600099660', 'defn' => 'shd'],
    'cctvbqkj'  => ['name' => 'CCTV兵器科技',   'cnlid' => '2026874603', 'livepid' => '600099649', 'defn' => 'shd'],
    'cctvfyzq'  => ['name' => 'CCTV风云足球',   'cnlid' => '2026966203', 'livepid' => '600099636', 'defn' => 'shd'],
    'cctvgeqwq' => ['name' => 'CCTV高尔夫·网球','cnlid' => '2026874703', 'livepid' => '600099659', 'defn' => 'shd'],
    'cctvnxss'  => ['name' => 'CCTV女性时尚',   'cnlid' => '2026874803', 'livepid' => '600099650', 'defn' => 'shd'],
    'cctvyswhjp'=> ['name' => 'CCTV央视文化精品','cnlid' => '2026874903', 'livepid' => '600099653', 'defn' => 'shd'],
    'cctvystq'  => ['name' => 'CCTV央视台球',   'cnlid' => '2026875003', 'livepid' => '600099652', 'defn' => 'shd'],
    'cctvdszn'  => ['name' => 'CCTV电视指南',   'cnlid' => '2026875103', 'livepid' => '600099656', 'defn' => 'shd'],
    'cctvwsjk'  => ['name' => 'CCTV卫生健康',   'cnlid' => '2025637003', 'livepid' => '600099651', 'defn' => 'shd'],
    'bjws'      => ['name' => '北京卫视',       'cnlid' => '2024052703', 'livepid' => '600002309', 'defn' => 'fhd'],
    'jsws'      => ['name' => '江苏卫视',       'cnlid' => '2024171103', 'livepid' => '600002521', 'defn' => 'fhd'],
    'dfws'      => ['name' => '东方卫视',       'cnlid' => '2024054503', 'livepid' => '600002483', 'defn' => 'fhd'],
    'zjws'      => ['name' => '浙江卫视',       'cnlid' => '2024054703', 'livepid' => '600002520', 'defn' => 'fhd'],
    'hnws'      => ['name' => '湖南卫视',       'cnlid' => '2024054803', 'livepid' => '600002475', 'defn' => 'fhd'],
    'hbws'      => ['name' => '湖北卫视',       'cnlid' => '2024171203', 'livepid' => '600002508', 'defn' => 'fhd'],
    'gdws'      => ['name' => '广东卫视',       'cnlid' => '2024060903', 'livepid' => '600002485', 'defn' => 'fhd'],
    'gxws'      => ['name' => '广西卫视',       'cnlid' => '2024060703', 'livepid' => '600002509', 'defn' => 'fhd'],
    'hljws'     => ['name' => '黑龙江卫视',     'cnlid' => '2029797003', 'livepid' => '600002498', 'defn' => 'fhd'],
    'hnws2'     => ['name' => '海南卫视',       'cnlid' => '2024055603', 'livepid' => '600002506', 'defn' => 'fhd'],
    'cqws'      => ['name' => '重庆卫视',       'cnlid' => '2024061103', 'livepid' => '600002531', 'defn' => 'fhd'],
    'szws'      => ['name' => '深圳卫视',       'cnlid' => '2024061303', 'livepid' => '600002481', 'defn' => 'fhd'],
    'scws'      => ['name' => '四川卫视',       'cnlid' => '2024061403', 'livepid' => '600002516', 'defn' => 'fhd'],
    'henanws'   => ['name' => '河南卫视',       'cnlid' => '2029797303', 'livepid' => '600002525', 'defn' => 'fhd'],
    'fjdnhz'    => ['name' => '东南卫视',       'cnlid' => '2024061503', 'livepid' => '600002484', 'defn' => 'fhd'],
    'gzhws'     => ['name' => '贵州卫视',       'cnlid' => '2024061603', 'livepid' => '600002490', 'defn' => 'fhd'],
    'jxws'      => ['name' => '江西卫视',       'cnlid' => '2024061703', 'livepid' => '600002503', 'defn' => 'fhd'],
    'lnws'      => ['name' => '辽宁卫视',       'cnlid' => '2024171303', 'livepid' => '600002505', 'defn' => 'fhd'],
    'ahws'      => ['name' => '安徽卫视',       'cnlid' => '2024171403', 'livepid' => '600002532', 'defn' => 'fhd'],
    'hbws2'     => ['name' => '河北卫视',       'cnlid' => '2024171503', 'livepid' => '600002493', 'defn' => 'fhd'],
    'sdws'      => ['name' => '山东卫视',       'cnlid' => '2029787903', 'livepid' => '600002513', 'defn' => 'fhd'],
    'tjws'      => ['name' => '天津卫视',       'cnlid' => '2019927003', 'livepid' => '600152137', 'defn' => 'fhd'],
    'jlws'      => ['name' => '吉林卫视',       'cnlid' => '2025561503', 'livepid' => '600190405', 'defn' => 'fhd'],
    'shanxiws'  => ['name' => '陕西卫视',       'cnlid' => '2029795103', 'livepid' => '600190400', 'defn' => 'fhd'],
    'nxws'      => ['name' => '宁夏卫视',       'cnlid' => '2025608503', 'livepid' => '600190737', 'defn' => 'fhd'],
    'nmgws'     => ['name' => '内蒙古卫视',     'cnlid' => '2025561203', 'livepid' => '600190401', 'defn' => 'fhd'],
    'ynws'      => ['name' => '云南卫视',       'cnlid' => '2025561303', 'livepid' => '600190402', 'defn' => 'fhd'],
    'shanxiws2' => ['name' => '山西卫视',       'cnlid' => '2025560803', 'livepid' => '600190407', 'defn' => 'fhd'],
    'qhws'      => ['name' => '青海卫视',       'cnlid' => '2025559103', 'livepid' => '600190406', 'defn' => 'fhd'],
    'xzws'      => ['name' => '西藏卫视',       'cnlid' => '2025558003', 'livepid' => '600190403', 'defn' => 'fhd'],
    'cetv1'     => ['name' => '中国教育电视台1','cnlid' => '2022823801', 'livepid' => '600171827', 'defn' => 'fhd'],
    'gxpd'      => ['name' => '国学频道',       'cnlid' => '2029360403', 'livepid' => '600213139', 'defn' => 'fhd'],
    'xjws'      => ['name' => '新疆卫视',       'cnlid' => '2019927403', 'livepid' => '600152138', 'defn' => 'fhd']
];

// ===================== 新增：无 id 参数时直接输出 M3U 列表（链接带 |ua=qqlive） =====================
if (!isset($_GET['id'])) {
    $scriptName = basename($_SERVER['SCRIPT_NAME']);
    $domain = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http')
          . '://' . $_SERVER['HTTP_HOST']
          . rtrim(dirname($_SERVER['SCRIPT_NAME']), '/');
    header('Content-Type: audio/x-mpegurl; charset=utf-8');
    header('Content-Disposition: attachment; filename="playlist.m3u"');
    echo "#EXTM3U\n# 央视直播\n\n";
    foreach ($channels as $id => $info) {
        // 关键：在链接末尾添加 |ua=qqlive
        $url = "{$domain}/{$scriptName}?id={$id}|ua=qqlive";
        echo "#EXTINF:-1 group-title=\"直播源\",{$info['name']}\n{$url}\n";
    }
    exit;
}

// ===================== 原有：生成播放列表（保留 ?generate=1 兼容） =====================
if (isset($_GET['generate']) && $_GET['generate'] == 1) {
    $scriptName = basename($_SERVER['SCRIPT_NAME']);
    $domain = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http')
          . '://' . $_SERVER['HTTP_HOST']
          . rtrim(dirname($_SERVER['SCRIPT_NAME']), '/');

    $format = isset($_GET['format']) ? strtolower($_GET['format']) : 'txt';

    if ($format === 'm3u') {
        header('Content-Type: audio/x-mpegurl; charset=utf-8');
        header('Content-Disposition: attachment; filename="playlist.m3u"');
        echo "#EXTM3U\n# 央视直播\n\n";
        foreach ($channels as $id => $info) {
            $url = "{$domain}/{$scriptName}?id={$id}";
            echo "#EXTINF:-1 group-title=\"直播源\",{$info['name']}\n{$url}\n";
        }
    } else {
        header('Content-Type: text/plain; charset=utf-8');
        header('Content-Disposition: attachment; filename="playlist.txt"');
        echo "直播源,#genre#\n";
        foreach ($channels as $id => $info) {
            echo "{$info['name']},{$domain}/{$scriptName}?id={$id}\n";
        }
    }
    die();
}

// ========== 正常播放逻辑（302 跳转，不再代理 TS） ==========
date_default_timezone_set('Asia/Shanghai');
$id = isset($_GET['id']) ? $_GET['id'] : '';
// 如果 id 参数包含 |ua=... 则去掉，只保留纯 id
if (strpos($id, '|') !== false) {
    $id = substr($id, 0, strpos($id, '|'));
}
if (!isset($channels[$id])) {
    die("频道不存在");
}
$channel = $channels[$id];

// ========== CKeyManager 类（完整实现，与原文件一致） ==========
class CKeyManager
{
    const DELTA = 0x9e3779b9;
    const ROUNDS = 16;
    const LOG_ROUNDS = 4;
    const SALT_LEN = 2;
    const ZERO_LEN = 7;
    const TEA_CKEY = '59b2f7cf725ef43c34fdd7c123411ed3';
    const GUARD_TEA_KEY = '110DBEC10C23E7D2E56A1CAD6914EF1B';

    private $xorKey = [0x84, 0x2E, 0xED, 0x08, 0xF0, 0x66, 0xE6, 0xEA, 0x48, 0xB4, 0xCA, 0xA9, 0x91, 0xED, 0x6F, 0xF3];
    private $guardXorKey = [0xB3, 0xC9, 0x53, 0xA0, 0x69, 0x13, 0xAD, 0x4D];
    private $standardAlphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    private $customAlphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=';
    private $guid = '';

    public function __construct()
    {
        error_reporting(E_ALL & ~E_DEPRECATED);
        ini_set('display_errors', 1);
        date_default_timezone_set('Asia/Shanghai');
        $this->generateGuid();
    }

    private function generateGuid()
    {
        $this->guid = sprintf('%08s%04s%04s%04s%12s',
            dechex(mt_rand(0, 0xffffffff)),
            dechex(mt_rand(0, 0xffff)),
            dechex(mt_rand(0, 0xffff)),
            dechex(mt_rand(0, 0xffff)),
            dechex(mt_rand(0, 0xffffffffffff))
        );
        if (strlen($this->guid) !== 32) {
            $this->guid = str_pad($this->guid, 32, '0', STR_PAD_LEFT);
        }
        return $this->guid;
    }

    public function getGuid() { return $this->guid; }

    private function spvcode($defn)
    {
        $height = 1080;
        if (preg_match('/(4k|8k|hdr)/i', $defn)) $height = 2160;
        $frame_rates = [30, 60, 90, 120];
        $h264_parts = $h265_parts = [];
        foreach ($frame_rates as $fps) {
            $h264_parts[] = "{$fps}:{$height}";
            $h265_parts[] = "{$fps}:{$height}";
        }
        $h264_str = implode(',', $h264_parts);
        $h265_str = implode(',', $h265_parts);
        $spvcode_raw = "H({$h264_str}|{$h264_str});2({$h265_str}|{$h265_str})";
        return base64_encode($spvcode_raw);
    }

    private function calcSignature($buffer)
    {
        $signature = 0;
        foreach ($buffer as $byte) {
            $signature = (0x83 * $signature + ($byte & 0xFF)) & 0x7FFFFFFF;
        }
        return $signature;
    }

    private function customDecode($text)
    {
        if (empty($text)) return '';
        $text = rtrim($text, '=');
        if (strlen($text) % 4 != 0) $text .= str_repeat('=', 4 - (strlen($text) % 4));
        $translationTable = [];
        $len = min(strlen($this->customAlphabet), strlen($this->standardAlphabet));
        for ($i = 0; $i < $len; $i++) {
            $translationTable[$this->customAlphabet[$i]] = $this->standardAlphabet[$i];
        }
        return base64_decode(strtr($text, $translationTable));
    }

    private function customEncode($text)
    {
        $encoded = base64_encode($text);
        $translationTable = [];
        $len = min(strlen($this->standardAlphabet), strlen($this->customAlphabet));
        for ($i = 0; $i < $len; $i++) {
            $translationTable[$this->standardAlphabet[$i]] = $this->customAlphabet[$i];
        }
        return rtrim(strtr($encoded, $translationTable), '=');
    }

    private function xorArray($byteArray)
    {
        $ret = [];
        $len = count($byteArray);
        for ($i = 0; $i < $len; $i++) {
            $ret[] = $byteArray[$i] ^ $this->xorKey[$i & 0xF];
        }
        return $ret;
    }

    private function teaEncryptECB($pInBuf, $pKey)
    {
        if (strlen($pInBuf) < 8) $pInBuf = str_pad($pInBuf, 8, "\0");
        $unpacked = unpack('N2', $pInBuf);
        $y = $unpacked[1]; $z = $unpacked[2];
        $k = [
            unpack('N', substr($pKey, 0, 4))[1],
            unpack('N', substr($pKey, 4, 4))[1],
            unpack('N', substr($pKey, 8, 4))[1],
            unpack('N', substr($pKey, 12, 4))[1]
        ];
        $sum = 0;
        for ($i = 0; $i < self::ROUNDS; $i++) {
            $sum = ($sum + self::DELTA) & 0xFFFFFFFF;
            $y = ($y + ((($z << 4) + $k[0]) ^ ($z + $sum) ^ (($z >> 5) + $k[1]))) & 0xFFFFFFFF;
            $z = ($z + ((($y << 4) + $k[2]) ^ ($y + $sum) ^ (($y >> 5) + $k[3]))) & 0xFFFFFFFF;
        }
        return pack('N2', $y, $z);
    }

    private function teaDecryptECB($pInBuf, $pKey)
    {
        $unpacked = unpack('N2', $pInBuf);
        $y = $unpacked[1]; $z = $unpacked[2];
        $k = [
            unpack('N', substr($pKey, 0, 4))[1],
            unpack('N', substr($pKey, 4, 4))[1],
            unpack('N', substr($pKey, 8, 4))[1],
            unpack('N', substr($pKey, 12, 4))[1]
        ];
        $sum = (self::DELTA << self::LOG_ROUNDS) & 0xFFFFFFFF;
        for ($i = 0; $i < self::ROUNDS; $i++) {
            $z = ($z - ((($y << 4) + $k[2]) ^ ($y + $sum) ^ (($y >> 5) + $k[3]))) & 0xFFFFFFFF;
            $y = ($y - ((($z << 4) + $k[0]) ^ ($z + $sum) ^ (($z >> 5) + $k[1]))) & 0xFFFFFFFF;
            $sum = ($sum - self::DELTA) & 0xFFFFFFFF;
        }
        return pack('N2', $y, $z);
    }

    private function oiSymmetryEncrypt2($pInBuf, $nInBufLen, $pKey)
    {
        $nPadSaltBodyZeroLen = $nInBufLen + 1 + self::SALT_LEN + self::ZERO_LEN;
        $nPadlen = $nPadSaltBodyZeroLen % 8;
        if ($nPadlen) $nPadlen = 8 - $nPadlen;

        $pOutBuf = '';
        $src_buf = array_fill(0, 8, 0);
        $src_buf[0] = (mt_rand(0, 255) & 0xF8) | $nPadlen;
        $src_i = 1;

        while ($nPadlen) {
            $src_buf[$src_i] = mt_rand(0, 255);
            $src_i++; $nPadlen--;
        }

        $iv_plain = array_fill(0, 8, 0);
        $iv_crypt = $iv_plain;

        $i = 0;
        while ($i < self::SALT_LEN) {
            if ($src_i < 8) {
                $src_buf[$src_i] = mt_rand(0, 255);
                $src_i++; $i++;
            }
            if ($src_i == 8) {
                for ($j = 0; $j < 8; $j++) $src_buf[$j] ^= $iv_crypt[$j];
                $temp_out = $this->teaEncryptECB(pack('C*', ...$src_buf), $pKey);
                $temp_bytes = array_values(unpack('C*', $temp_out));
                for ($j = 0; $j < 8; $j++) $temp_bytes[$j] ^= $iv_plain[$j];
                $iv_plain = $src_buf;
                $iv_crypt = $temp_bytes;
                $pOutBuf .= pack('C*', ...$temp_bytes);
                $src_i = 0;
            }
        }

        $pInBufIndex = 0;
        while ($nInBufLen) {
            if ($src_i < 8) {
                $src_buf[$src_i] = ord($pInBuf[$pInBufIndex]);
                $pInBufIndex++; $src_i++; $nInBufLen--;
            }
            if ($src_i == 8) {
                for ($j = 0; $j < 8; $j++) $src_buf[$j] ^= $iv_crypt[$j];
                $temp_out = $this->teaEncryptECB(pack('C*', ...$src_buf), $pKey);
                $temp_bytes = array_values(unpack('C*', $temp_out));
                for ($j = 0; $j < 8; $j++) $temp_bytes[$j] ^= $iv_plain[$j];
                $iv_plain = $src_buf;
                $iv_crypt = $temp_bytes;
                $pOutBuf .= pack('C*', ...$temp_bytes);
                $src_i = 0;
            }
        }

        $i = 0;
        while ($i < self::ZERO_LEN) {
            if ($src_i < 8) {
                $src_buf[$src_i] = 0;
                $src_i++; $i++;
            }
            if ($src_i == 8) {
                for ($j = 0; $j < 8; $j++) $src_buf[$j] ^= $iv_crypt[$j];
                $temp_out = $this->teaEncryptECB(pack('C*', ...$src_buf), $pKey);
                $temp_bytes = array_values(unpack('C*', $temp_out));
                for ($j = 0; $j < 8; $j++) $temp_bytes[$j] ^= $iv_plain[$j];
                $iv_plain = $src_buf;
                $iv_crypt = $temp_bytes;
                $pOutBuf .= pack('C*', ...$temp_bytes);
                $src_i = 0;
            }
        }

        if ($src_i > 0) {
            for ($j = $src_i; $j < 8; $j++) $src_buf[$j] = 0;
            for ($j = 0; $j < 8; $j++) $src_buf[$j] ^= $iv_crypt[$j];
            $temp_out = $this->teaEncryptECB(pack('C*', ...$src_buf), $pKey);
            $temp_bytes = array_values(unpack('C*', $temp_out));
            for ($j = 0; $j < 8; $j++) $temp_bytes[$j] ^= $iv_plain[$j];
            $pOutBuf .= pack('C*', ...$temp_bytes);
        }
        return $pOutBuf;
    }

    private function oiSymmetryDecrypt2($pInBuf, $nInBufLen, $pKey)
    {
        if (($nInBufLen % 8) != 0 || $nInBufLen < 16) return false;
        $dest_buf_str = $this->teaDecryptECB(substr($pInBuf, 0, 8), $pKey);
        $dest_buf = array_values(unpack('C*', $dest_buf_str));
        $nPadLen = $dest_buf[0] & 0x07;
        $i = $nInBufLen - 1;
        $i = $i - $nPadLen - self::SALT_LEN - self::ZERO_LEN;
        if ($i < 0) return false;
        $pOutBufLen = $i;

        $iv_pre_crypt = array_fill(0, 8, 0);
        $iv_cur_crypt = array_values(unpack('C*', substr($pInBuf, 0, 8)));
        $pInBufOffset = 8;
        $dest_i = 1;
        $dest_i += $nPadLen;

        $salt_count = 1;
        while ($salt_count <= self::SALT_LEN) {
            if ($dest_i < 8) {
                $dest_i++; $salt_count++;
            } elseif ($dest_i == 8) {
                $iv_pre_crypt = $iv_cur_crypt;
                $iv_cur_crypt = array_values(unpack('C*', substr($pInBuf, $pInBufOffset, 8)));
                for ($j = 0; $j < 8; $j++) {
                    if ($pInBufOffset + $j >= $nInBufLen) return false;
                    $dest_buf[$j] ^= $iv_cur_crypt[$j];
                }
                $temp_buf = $this->teaDecryptECB(pack('C*', ...$dest_buf), $pKey);
                $dest_buf = array_values(unpack('C*', $temp_buf));
                $pInBufOffset += 8;
                $dest_i = 0;
            }
        }

        $nPlainLen = $pOutBufLen;
        $plain_bytes = [];
        while ($nPlainLen > 0) {
            if ($dest_i < 8) {
                $plain_bytes[] = $dest_buf[$dest_i] ^ $iv_pre_crypt[$dest_i];
                $dest_i++; $nPlainLen--;
            } elseif ($dest_i == 8) {
                $iv_pre_crypt = $iv_cur_crypt;
                $iv_cur_crypt = array_values(unpack('C*', substr($pInBuf, $pInBufOffset, 8)));
                for ($j = 0; $j < 8; $j++) {
                    if ($pInBufOffset + $j >= $nInBufLen) return false;
                    $dest_buf[$j] ^= $iv_cur_crypt[$j];
                }
                $temp_buf = $this->teaDecryptECB(pack('C*', ...$dest_buf), $pKey);
                $dest_buf = array_values(unpack('C*', $temp_buf));
                $pInBufOffset += 8;
                $dest_i = 0;
            }
        }
        return pack('C*', ...$plain_bytes);
    }

    private function generateCkGuardTime($timestamp, $guid, $guardData = '-1', $packageName = 'null', $processName = 'null')
    {
        $body = pack('N', $timestamp);
        foreach ([
            $this->guardLastFive($guid),
            $this->guardLastFive($packageName),
            $this->guardLastFive($processName),
            $guardData
        ] as $part) {
            $body .= pack('n', strlen($part)) . $part;
        }
        $plain = pack('n', strlen($body)) . $body;
        $checksum = $this->calcSignature(array_values(unpack('C*', $plain)));
        $encrypted = $this->oiSymmetryEncrypt2($plain, strlen($plain), hex2bin(self::GUARD_TEA_KEY));
        $encrypted .= pack('N', $checksum);
        $bytes = array_values(unpack('C*', $encrypted));
        $len = count($bytes);
        for ($i = 0; $i < $len; $i++) {
            $bytes[$i] ^= $this->guardXorKey[$i & 7];
        }
        return strtoupper(bin2hex(pack('C*', ...$bytes)));
    }

    private function guardLastFive($value)
    {
        $value = (string)$value;
        return strlen($value) >= 5 ? substr($value, -5) : '';
    }

    public function encryptDataToCKey($data)
    {
        $teaCkey = hex2bin(self::TEA_CKEY);
        $data_len = strlen($data);
        $data_array = array_values(unpack('C*', $data));
        $checksum = $this->calcSignature($data_array);
        $encrypted = $this->oiSymmetryEncrypt2($data, $data_len, $teaCkey);
        $encrypted .= pack('N', $checksum);
        $encrypted_array = array_values(unpack('C*', $encrypted));
        $xor_array = $this->xorArray($encrypted_array);
        $xor_encrypted = pack('C*', ...$xor_array);
        $base64_encoded = $this->customEncode($xor_encrypted);
        return "--01" . $base64_encoded;
    }

    public function decryptCKeyToData($ckey)
    {
        $teaCkey = hex2bin(self::TEA_CKEY);
        $ckey_without_prefix = substr($ckey, 4);
        $base64_decoded = $this->customDecode($ckey_without_prefix);
        if (!$base64_decoded) return false;
        $xor_array = array_values(unpack('C*', $base64_decoded));
        $xor_decrypted_array = $this->xorArray($xor_array);
        $xor_decrypted = pack('C*', ...$xor_decrypted_array);
        $data_len = strlen($xor_decrypted) - 4;
        $encrypted_data = substr($xor_decrypted, 0, $data_len);
        $checksum_bytes = substr($xor_decrypted, $data_len);
        $checksum = unpack('N', $checksum_bytes)[1];
        $decrypted = $this->oiSymmetryDecrypt2($encrypted_data, $data_len, $teaCkey);
        return ['data' => $decrypted, 'checksum' => $checksum];
    }

    public function buildPacket($params)
    {
        $data = '';
        $data .= hex2bin('0000004200000004000004d2');
        $data .= pack('N', $params['Platform']);
        $data .= pack('N', 0);
        $data .= pack('N', $params['Timestamp']);

        $sdtfrom = $params['Sdtfrom'];
        $data .= pack('n', strlen($sdtfrom)) . $sdtfrom;
        $randFlag = $params['randFlag'];
        $data .= pack('n', strlen($randFlag)) . $randFlag;
        $appVer = $params['appVer'];
        $data .= pack('n', strlen($appVer)) . $appVer;
        $vid = $params['vid'];
        $data .= pack('n', strlen($vid)) . $vid;
        $guid = $params['guid'];
        $data .= pack('n', strlen($guid)) . $guid;
        $data .= pack('N', 1);
        $data .= pack('N', 1);
        $uid = "2622783A";
        $data .= pack('n', strlen($uid)) . $uid;
        $bundleID = "nil";
        $data .= pack('n', strlen($bundleID)) . $bundleID;
        $uuid4 = $params['uuid4'];
        $data .= pack('n', strlen($uuid4)) . $uuid4;
        $data .= pack('n', strlen($bundleID)) . $bundleID;
        $ckeyVersion = "v0.1.000";
        $data .= pack('n', strlen($ckeyVersion)) . $ckeyVersion;
        $packageName = "com.cctv.yangshipin.app.iphone";
        $data .= pack('n', strlen($packageName)) . $packageName;
        $platform_str = "4330403";
        $data .= pack('n', strlen($platform_str)) . $platform_str;
        $ex_json_bus = "ex_json_bus";
        $data .= pack('n', strlen($ex_json_bus)) . $ex_json_bus;
        $ex_json_vs = "ex_json_vs";
        $data .= pack('n', strlen($ex_json_vs)) . $ex_json_vs;
        $ck_guard_time = $params['ck_guard_time'];
        $data .= pack('n', strlen($ck_guard_time)) . $ck_guard_time;

        $body_length = strlen($data);
        $buffer = pack('n', $body_length) . $data;
        $buffer_array = array_values(unpack('C*', $buffer));
        $signature = $this->calcSignature($buffer_array);
        $buffer = substr($buffer, 0, 18) . pack('N', $signature) . substr($buffer, 22);
        return $buffer;
    }

    public function generateCKey($cnlid, $timestamp = null)
    {
        if ($timestamp === null) $timestamp = time();
        $randFlag = base64_encode(random_bytes(18));
        $uuid4 = sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            mt_rand(0, 0xffff), mt_rand(0, 0xffff),
            mt_rand(0, 0xffff),
            mt_rand(0, 0x0fff) | 0x4000,
            mt_rand(0, 0x3fff) | 0x8000,
            mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
        );
        $ck_guard_time = $this->generateCkGuardTime($timestamp, $this->guid);

        $params = [
            'Platform' => 4330403,
            'Timestamp' => $timestamp,
            'Sdtfrom' => 'dcgh',
            'vid' => $cnlid,
            'guid' => $this->guid,
            'appVer' => 'V8.22.1035.3031',
            'randFlag' => $randFlag,
            'uuid4' => $uuid4,
            'ck_guard_time' => $ck_guard_time
        ];

        $buffer = $this->buildPacket($params);
        $ckey = $this->encryptDataToCKey($buffer);
        return ['ckey' => $ckey, 'params' => $params];
    }

    public function makeLiveRequest($cnlid, $livepid, $defn)
    {
        $this->generateGuid();
        $ckeyResult = $this->generateCKey($cnlid);
        $ckey = $ckeyResult['ckey'];
        $params = $ckeyResult['params'];

        $flowid = sprintf('%s_%d',
            sprintf('%04X%04X-%04X-%04X-%04X-%04X%04X%04X',
                mt_rand(0, 0xffff), mt_rand(0, 0xffff),
                mt_rand(0, 0xffff),
                mt_rand(0, 0x0fff) | 0x4000,
                mt_rand(0, 0x3fff) | 0x8000,
                mt_rand(0, 0xffff), mt_rand(0, 0xffff), mt_rand(0, 0xffff)
            ),
            4330403
        );

        $request_params = [
            "atime" => "120",
            "livepid" => $livepid,
            "cnlid" => $cnlid,
            "appVer" => "V8.22.1035.3031",
            "app_version" => "300090",
            "caplv" => "1",
            "cmd" => "2",
            "defn" => $defn,
            "device" => "iPhone",
            "encryptVer" => "4.2",
            "getpreviewinfo" => "0",
            "hevclv" => "33",
            "lang" => "zh-Hans_JP",
            "livequeue" => "0",
            "logintype" => "1",
            "nettype" => "1",
            "newnettype" => "1",
            "newplatform" => "4330403",
            "platform" => "4330403",
            "sdtfrom" => "v3021",
            "spacode" => "23",
            "spaudio" => "1",
            "spdemuxer" => "6",
            "spdrm" => "2",
            "spdynamicrange" => "7",
            "spflv" => "1",
            "spflvaudio" => "1",
            "sphdrfps" => "60",
            "sphttps" => "0",
            "spvcode" => "MSgzMDoyMTYwLDYwOjIxNjB8MzA6MjE2MCw2MDoyMTYwKTsyKDMwOjIxNjAsNjA6MjE2MHwzMDoyMTYwLDYwOjIxNjAp",
            "spvideo" => "4",
            "stream" => "1",
            "system" => "1",
            "sysver" => "ios18.2.1",
            "uhd_flag" => "4",
            "cKey" => $ckey,
            "guid" => $this->guid,
            "fntick" => $params['Timestamp'],
            "flowid" => $flowid,
            "playbacktime" => "0"
        ];

        return $this->sendHttpRequest($request_params);
    }

    private function sendHttpRequest($params)
    {
        $url = "https://bkliveinfo.ysp.cctv.cn";
        $query_string = http_build_query($params);

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url . '?' . $query_string);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'User-Agent: qqlive',
            'Connection: Keep-Alive',
            'Accept: application/json'
        ]);
        curl_setopt($ch, CURLOPT_TIMEOUT, 15);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);

        $response = curl_exec($ch);
        $error = curl_error($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

        if ($error) {
            return ['success' => false, 'error' => 'cURL错误: ' . $error, 'http_code' => $http_code];
        }

        $data = json_decode($response, true);
        if ($data && isset($data['iretcode'])) {
            return [
                'success' => $data['iretcode'] == 0,
                'iretcode' => $data['iretcode'],
                'http_code' => $http_code,
                'response' => $data,
                'playurl' => $data['playurl'] ?? null
            ];
        }
        return ['success' => false, 'error' => '无效的JSON响应', 'http_code' => $http_code];
    }

    public function getPlayUrl($cnlid, $livepid, $defn)
    {
        $result = $this->makeLiveRequest($cnlid, $livepid, $defn);
        if ($result['success'] && isset($result['playurl'])) {
            return $result['playurl'];
        }
        return null;
    }
}

// ========== 主逻辑（Cookie 缓存播放地址 + 302 跳转） ==========
$ckeyManager = new CKeyManager();
$cookieKey = 'playurl_cache';
$cacheTimeoutLive = 80;
$cookieExpire = time() + 3600;

$cacheJson = $_COOKIE[$cookieKey] ?? '{}';
$cache = json_decode($cacheJson, true) ?: [];

$now = time();
$playUrl = null;

if (isset($cache[$id]) && is_array($cache[$id]) && ($now - $cache[$id]['time']) <= $cacheTimeoutLive) {
    $playUrl = $cache[$id]['url'];
} else {
    $playUrl = $ckeyManager->getPlayUrl($channel['cnlid'], $channel['livepid'], $channel['defn']);
    if (!$playUrl) die("获取播放地址失败\n");
    $cache[$id] = ['url' => $playUrl, 'time' => $now];
    setcookie($cookieKey, json_encode($cache), $cookieExpire, '/');
}

// ========== 302 重定向到 M3U8（不再代理 TS） ==========
header('HTTP/1.1 302 Found');
header('Location: ' . $playUrl);
header('Cache-Control: public, max-age=' . $cacheTimeoutLive);
exit();