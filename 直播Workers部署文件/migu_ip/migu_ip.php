<?php
$file = __DIR__ . '/migu_ip.txt';

if (!is_file($file)) {
    http_response_code(500);
    echo 'migu_ip.txt not found';
    exit;
}

$lines = file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
$endpoints = [];
foreach ($lines as $line) {
    $line = trim($line);
    if ($line !== '') {
        $endpoints[] = $line;
    }
}

if (!$endpoints) {
    http_response_code(500);
    echo 'No endpoints found';
    exit;
}

function testEndpoints(array $endpoints, int $timeout = 5): array
{
    $mh = curl_multi_init();
    $handles = [];

    foreach ($endpoints as $ep) {
        $url = 'http://' . $ep;
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HEADER => false,
            CURLOPT_NOBODY => false,
            CURLOPT_CONNECTTIMEOUT => $timeout,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS => 3,
            CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; migu_ip.php/1.0)',
        ]);
        curl_multi_add_handle($mh, $ch);
        $handles[$ep] = $ch;
    }

    do {
        $status = curl_multi_exec($mh, $active);
        if ($active) {
            curl_multi_select($mh, 1.0);
        }
    } while ($active && $status === CURLM_OK);

    $results = [];
    foreach ($handles as $ep => $ch) {
        $info = curl_getinfo($ch);
        $error = curl_error($ch);
        $httpCode = $info['http_code'] ?? 0;
        $totalTime = $info['total_time'] ?? null;

        $results[$ep] = [
            'ok' => ($error === '' && $httpCode > 0),
            'http_code' => $httpCode,
            'time' => $totalTime,
            'error' => $error,
        ];

        curl_multi_remove_handle($mh, $ch);
        curl_close($ch);
    }

    curl_multi_close($mh);
    return $results;
}

function fetchBody(string $endpoint, int $timeout = 10): array
{
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => 'http://' . $endpoint,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HEADER => false,
        CURLOPT_CONNECTTIMEOUT => $timeout,
        CURLOPT_TIMEOUT => $timeout,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_USERAGENT => 'Mozilla/5.0 (compatible; migu_ip.php/1.0)',
    ]);

    $body = curl_exec($ch);
    $error = curl_error($ch);
    $info = curl_getinfo($ch);
    curl_close($ch);

    return [
        'body' => $body,
        'error' => $error,
        'content_type' => $info['content_type'] ?? 'text/plain; charset=UTF-8',
        'http_code' => $info['http_code'] ?? 0,
    ];
}

$results = testEndpoints($endpoints, 5);
$okResults = [];
foreach ($results as $ep => $item) {
    if ($item['ok'] && is_numeric($item['time'])) {
        $okResults[$ep] = $item['time'];
    }
}

if (!$okResults) {
    http_response_code(502);
    header('Content-Type: text/plain; charset=UTF-8');
    echo 'All endpoints failed';
    exit;
}

asort($okResults, SORT_NUMERIC);
$fastest = array_key_first($okResults);

if (isset($_GET['debug']) || isset($_GET['test']) || isset($_GET['result'])) {
    header('Content-Type: text/plain; charset=UTF-8');
    echo "Fastest: {$fastest}\n\n";
    echo "Test Results:\n";
    foreach ($results as $ep => $item) {
        if ($item['ok']) {
            echo sprintf("%s\t%.3f ms\tHTTP %d\n", $ep, $item['time'] * 1000, $item['http_code']);
        } else {
            echo sprintf("%s\tFAILED\t%s\n", $ep, $item['error'] ?: ('HTTP ' . $item['http_code']));
        }
    }
    exit;
}

$response = fetchBody($fastest, 10);
if ($response['error'] !== '' || $response['http_code'] === 0) {
    http_response_code(502);
    header('Content-Type: text/plain; charset=UTF-8');
    echo 'Failed to fetch fastest endpoint: ' . ($response['error'] ?: ('HTTP ' . $response['http_code']));
    exit;
}

if (!headers_sent() && !empty($response['content_type'])) {
    header('Content-Type: ' . $response['content_type']);
}

echo $response['body'];