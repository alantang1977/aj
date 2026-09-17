# SMT IPTV Proxy Worker
（测试期暂限200个申请名额）
## ‼️频道列表清单文件为加密的，仅支持[@yourtv](https://github.com/horsemail/yourtv)播放器‼️
```url
https://github.com/horsemail/yourtv
```
- ‼️原本在[@smtyourtvbot](https://t.me/smtyourtvbot) Telegram 机器人上申请的用户请转移到:
- ‼️新的机器人 [@smartyourtvbot](https://t.me/smartyourtvbot)上重新用新代码部署
- ‼️旧部署将在数日后失效

这是一个运行在 Cloudflare Workers 上的 IPTV 代理项目，用于安全、稳定地代理直播源。

## 功能特点

- 支持 M3U 播放列表生成（带 token 访问）
- 频道链接自动带上 kv_key / username / password / token 参数
- 支持强制刷新频道列表（&refresh=1）
- 播放链接支持 Range 请求（断点续传）
- 详细日志，便于调试

## 前置要求

1. Cloudflare 账户（免费账户即可）
2. 一个已绑定的 KV Namespace（建议命名为 `SMT_KV`）
3. 环境变量（必须设置，否则无法正常工作）
4. 关注 [@smartyourtvbot](https://t.me/smartyourtvbot) Telegram 机器人，使用 `/register` 命令获得认证参数。
   或者直接打开下面网站与机器人对话
   ```url
   https://t.me/smtyourtvbot
   ```
6. 已经绑定到cloudflare上的域名

## 部署步骤

### 1. 复制本仓库的worker_.js文件的全部内容

### 2. 登录 Cloudflare 并创建 Worker

进入 Cloudflare Dashboard → Workers & Pages → Overview → Create application → Workers → Deploy
选择 “Create a Worker” → 给 Worker 起名（如 smt-proxy）

### 3. 绑定 KV Namespace

在 Worker 设置页面 → Settings → Bindings → KV Namespace Bindings → Add binding
Variable name：填 KV（代码中固定使用 env.KV）
KV namespace：选择你创建的 KV Namespace

### 4. 设置环境变量（Variables）
在 Worker 设置 → Variables & Secrets → Environment Variables → Add variable，添加以下变量：

#### 环境变量配置表

在 Cloudflare Worker 的 **Settings → Variables & Secrets → Environment Variables** 中添加以下变量。

| 变量名            | 值示例                               | 说明                              | 必填 |
|-------------------|--------------------------------------|-----------------------------------|------|
| REQUIRED_TOKEN    | 123456abcdef                         | 访问 M3U 清单的固定 token（订阅链接校验用） | 是   |
| MY_KV_KEY         | tguser_1859999999                    | 认证参数（kv_key）       | 是   |
| MY_USERNAME       | user_c0e9999999                      | 认证参数（username）     | 是   |
| MY_PASSWORD       | 3544228c99999999                     | 认证参数（password）     | 是   |
| MY_TOKEN          | 2e45e0b0e6218b9491ed5dm9999999       | 认证参数（token）        | 是   |

#### 注意事项
- 所有变量均为字符串类型，无需加引号。
- 如果缺少任意一个变量，Worker 将无法访问并返回 500 错误。
- 参数变化后，必须手动更新这些值，更新后立即对所有后续请求生效（旧链接因参数不匹配而失效）。
- 建议在 GitHub 或本地备份这些值，避免丢失。
- 除REQUIRED_TOKEN自定义设置外，其他四个参数由你的telegram账号访问 @smtyourtvbot 机器人发送/register获得。
  
示例添加方式（Cloudflare Dashboard）：
1. 点击 “Add variable”
2. Variable name：REQUIRED_TOKEN
3. Value：123456abcdef
4. 保存并 Deploy

注意：这些值必须与 @smtyourtvbot /register命令返回的四个参数 完全匹配。
### 5. 部署代码

将本仓库的 worker_.js内容复制到 Cloudflare Worker - Edit Code 编辑器中
点击 “Save and Deploy”

### 6. 测试访问

拉取 M3U 清单（订阅地址）：
```text
https://你的worker域名/?token=123456abcdef
```
或强制刷新频道列表：

```text
https://你的worker域名/?token=123456abcdef&refresh=1
```
- 如果出现 #ERROR: ... 或 403，检查日志

- 如果worker默认域名可能无法访问, 请绑定你自己的域名，。

## 日志查看

- Dashboard → Workers → 你的 Worker → 你的worker项目 → Observability 里查看日志，看看什么错误。
- 仔细检查下所有环境变量的设置，不要包含空格，或者删掉重新设置一遍。设置完再按一次deploy。KV设置绑定是否正确。
- 搜索关键词：

## Telegram 群组交流
[@yourtvapp](https://t.me/yourtvapp)

## 免责声明
- 本项目仅用于学习和研究目的，请遵守当地法律法规，不得用于非法传播或商业用途。作者不对任何使用后果负责。
