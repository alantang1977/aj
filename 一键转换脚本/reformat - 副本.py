#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多 JSON 文件合并去重并格式化工具（灵活文件存在版）
功能：
- 自动合并摸鱼儿.json 和 X.json（只合并存在的文件）
- 支持 //、##、# 注释
- 将 sites、lives、parses、flags、ijk 等数组合并并去重（忽略代理前缀差异）
- 输出 final.json，顶层属性按指定顺序排列
- 数组元素压缩为单行，缩进 2 空格
- 只要至少有一个输入文件存在即可运行
"""

import json
import re
import os
import sys

# ---------- 配置 ----------
# 需要合并的顶层数组键
ARRAY_KEYS = ['sites', 'lives', 'parses', 'flags', 'ijk', 'rules', 'doh', 'ads', 'proxy']

# 常见代理前缀（去重时忽略）
PROXY_PREFIXES = [
    'https://gh-proxy.org/',
    'https://ghfast.top/',
    'https://raw.githubusercontent.com/',
    'https://gitee.com/',
    'https://seep.eu.org/',
    'https://wget.la/',
    'https://tvv.tw/',
]

# 输出时顶层属性的优先顺序
ORDERED_KEYS = [
    'spider', 'logo', 'wallpaper', 'danmaku', 'sites', 'lives',
    'parses', 'flags', 'ijk', 'doh', 'rules', 'ads', 'proxy', 'headers'
]

# ---------- 工具函数 ----------
def remove_comments(json_str):
    """移除 //、##、# 单行注释"""
    lines = json_str.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('##') or stripped.startswith('#'):
            continue
        in_string = False
        escape = False
        comment_start = -1
        for i, ch in enumerate(line):
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if not in_string and (ch == '/' or ch == '#'):
                if ch == '#':
                    comment_start = i
                    break
                elif i + 1 < len(line) and line[i+1] == ch:
                    comment_start = i
                    break
        if comment_start != -1:
            line = line[:comment_start].rstrip()
        cleaned.append(line)
    return '\n'.join(cleaned)


def fix_trailing_commas(json_str):
    """去除对象/数组末尾的多余逗号"""
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    return json_str


def normalize_url(url):
    """去除代理前缀，用于去重比较"""
    if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
        return url
    changed = True
    while changed:
        changed = False
        for prefix in PROXY_PREFIXES:
            if url.startswith(prefix):
                url = url[len(prefix):]
                changed = True
                break
    return url


def normalize_obj(obj):
    """递归规范化对象中的 URL"""
    if isinstance(obj, dict):
        return {k: normalize_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize_obj(item) for item in obj]
    elif isinstance(obj, str) and (obj.startswith('http://') or obj.startswith('https://')):
        return normalize_url(obj)
    else:
        return obj


def deduplicate_list(items):
    """去重（基于规范化后的内容），保留首次出现顺序"""
    seen = set()
    unique = []
    for item in items:
        norm = normalize_obj(item)
        try:
            key = json.dumps(norm, sort_keys=True, ensure_ascii=False)
        except:
            key = str(norm)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def compress_obj(obj):
    """递归压缩对象为单行字符串"""
    if isinstance(obj, dict):
        return '{' + ','.join(f'"{k}":{compress_obj(v)}' for k, v in obj.items()) + '}'
    elif isinstance(obj, list):
        if all(isinstance(x, (str, int, float, bool)) or x is None for x in obj):
            return '[' + ','.join(json.dumps(x, ensure_ascii=False) for x in obj) + ']'
        else:
            return '[' + ','.join(compress_obj(x) for x in obj) + ']'
    else:
        return json.dumps(obj, ensure_ascii=False)


def load_json_file(filepath):
    """加载并解析 JSON，自动清理注释并修复尾随逗号"""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    clean = remove_comments(raw)
    clean = fix_trailing_commas(clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        # 尝试将内容当作数组包裹为 {"lives": [...]}
        try:
            if clean.strip().startswith('['):
                data = json.loads(clean)
                return data
            else:
                wrapped = '{"lives": ' + clean + '}'
                return json.loads(wrapped)
        except:
            print(f"❌ 文件 {filepath} 解析失败: {e}")
            print("提示：请手动检查该文件是否有未闭合括号或缺失值。")
            return None


def merge_files(input_files, output_file, conflict_strategy='first'):
    """合并多个 JSON 文件（仅处理存在的文件）"""
    # 过滤掉不存在的文件
    existing_files = [f for f in input_files if os.path.exists(f)]
    if not existing_files:
        print("❌ 未找到任何可合并的文件，请确保至少有一个输入文件存在。")
        return

    data_list = []
    for f in existing_files:
        data = load_json_file(f)
        if data is None:
            return
        data_list.append(data)

    merged = {}
    first_data = data_list[0]

    # 合并数组
    for key in ARRAY_KEYS:
        combined = []
        for data in data_list:
            if isinstance(data, list):
                if key == 'lives':
                    combined.extend(data)
                continue
            if key in data and isinstance(data[key], list):
                combined.extend(data[key])
        if combined:
            print(f"📦 {key} 合并前总项数: {len(combined)}")
            merged[key] = deduplicate_list(combined)
            print(f"📦 {key} 去重后项数: {len(merged[key])}")

    # 处理非数组属性（取第一个文件的值）
    for key, value in first_data.items():
        if key not in ARRAY_KEYS:
            for i, data in enumerate(data_list[1:], start=1):
                if key in data and data[key] != value:
                    if conflict_strategy == 'warn':
                        print(f"⚠️ 属性 '{key}' 在文件 {existing_files[i]} 中不同，已采用第一个文件的值。")
            merged[key] = value

    # 移除空数组
    for key in ARRAY_KEYS:
        if key in merged and not merged[key]:
            del merged[key]

    # 压缩数组元素
    for key in ARRAY_KEYS:
        if key in merged and isinstance(merged[key], list):
            merged[key] = [compress_obj(item) for item in merged[key]]

    # 按顺序输出
    all_keys = list(merged.keys())
    ordered_keys = []
    for k in ORDERED_KEYS:
        if k in all_keys:
            ordered_keys.append(k)
    for k in all_keys:
        if k not in ordered_keys:
            ordered_keys.append(k)

    lines = ['{']
    for idx, k in enumerate(ordered_keys):
        is_last = (idx == len(ordered_keys) - 1)
        v = merged[k]
        if k in ARRAY_KEYS and isinstance(v, list):
            lines.append(f'  "{k}": [')
            for i, item in enumerate(v):
                lines.append(f'    {item}' + (',' if i < len(v)-1 else ''))
            lines.append('  ]' + ('' if is_last else ','))
        else:
            if isinstance(v, str):
                lines.append(f'  "{k}": "{v}"' + ('' if is_last else ','))
            elif isinstance(v, (int, float, bool)):
                lines.append(f'  "{k}": {json.dumps(v)}' + ('' if is_last else ','))
            elif v is None:
                lines.append(f'  "{k}": null' + ('' if is_last else ','))
            else:
                lines.append(f'  "{k}": {json.dumps(v, ensure_ascii=False)}' + ('' if is_last else ','))
    lines.append('}')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"✅ 合并完成！输出文件：{output_file}")


# ---------- 固定入口（灵活文件存在） ----------
if __name__ == '__main__':
    # 指定要检查的文件列表（可自由增删）
    possible_files = ['fish.json', 'X.json']
    # 只保留实际存在的文件
    existing = [f for f in possible_files if os.path.exists(f)]
    if not existing:
        print("❌ 未找到任何可合并的文件（fish.json 或 X.json）。")
        sys.exit(1)
    print(f"📂 找到以下文件：{', '.join(existing)}")
    output_file = 'final.json'
    merge_files(existing, output_file, conflict_strategy='first')