# 河狸陪官网部署到阿里云 OSS

你现在使用的是阿里云 OSS，因此官网最适合走：

`GitHub -> GitHub Actions -> 阿里云 OSS -> 自定义域名`

当前仓库已经有现成的自动部署工作流：

- 工作流文件：`.github/workflows/deploy-helipei-official-oss.yml`
- 发布脚本：`knowledge/helipei-official/deploy_aliyun.py`

> 如果你使用 OSS，这次**不需要配置任何 `ECS_*` Secrets**。`ECS_HOST`、`ECS_USER`、`ECS_SSH_PRIVATE_KEY`、`ECS_PORT`、`ECS_DEPLOY_PATH` 都是服务器部署方案才会用到。

## 一、GitHub 需要配置的 Secrets

进入：

`GitHub 仓库 -> Settings -> Secrets and variables -> Actions -> New repository secret`

新增以下 4 个：

| Secret 名称 | 必填 | 示例 | 说明 |
| :--- | :--- | :--- | :--- |
| `ALIYUN_ACCESS_KEY_ID` | 是 | `LTAI5...` | 阿里云 AccessKey ID |
| `ALIYUN_ACCESS_KEY_SECRET` | 是 | `xxxxxx` | 阿里云 AccessKey Secret |
| `ALIYUN_OSS_BUCKET` | 是 | `helipei-official` | 你的 OSS Bucket 名称 |
| `ALIYUN_OSS_ENDPOINT` | 是 | `https://oss-cn-shenzhen.aliyuncs.com` | Bucket 所在地域的 Endpoint |

### 直接照着填

如果你的 Bucket 是北京地域，那么可按下面填写：

| Secret 名称 | 建议填写方式 |
| :--- | :--- |
| `ALIYUN_ACCESS_KEY_ID` | 你的阿里云 AccessKey ID |
| `ALIYUN_ACCESS_KEY_SECRET` | 你的阿里云 AccessKey Secret |
| `ALIYUN_OSS_BUCKET` | `helipei` |
| `ALIYUN_OSS_ENDPOINT` | `https://oss-cn-beijing.aliyuncs.com` |

## 二、这些值去哪里找

### 1）ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET

去阿里云控制台：

`右上角头像 -> AccessKey 管理`

建议：

- 不要使用主账号 AccessKey
- 新建 RAM 用户
- 给这个 RAM 用户只授予当前 OSS Bucket 的最小权限

## 2）ALIYUN_OSS_BUCKET

去阿里云 OSS 控制台，找到你要部署官网的 Bucket 名称。

例如：

- `helipei-official`
- `www-helipei-com`

## 3）ALIYUN_OSS_ENDPOINT

去该 Bucket 的概览页，查看所属地域。

常见写法：

- 深圳：`https://oss-cn-shenzhen.aliyuncs.com`
- 上海：`https://oss-cn-shanghai.aliyuncs.com`
- 杭州：`https://oss-cn-hangzhou.aliyuncs.com`
- 北京：`https://oss-cn-beijing.aliyuncs.com`

注意：

- 这里填的是 **Endpoint**
- 不是你的自定义域名
- 要带 `https://`

## 三、OSS 侧需要提前配置

在 OSS 控制台确认：

- Bucket 已创建
- 静态页面托管已开启
- 默认首页设置为 `index.html`
- 404 页面可按需设置
- 如需直接公网访问，Bucket 或自定义域名链路可正常访问

如果你要绑定正式域名，还需要：

- 在 OSS 中绑定自定义域名
- 在域名 DNS 中添加 CNAME 到 OSS
- 按需开启 CDN 和 HTTPS

## 四、GitHub Actions 如何触发

工作流会在以下情况自动执行：

- 推送到 `main` 分支
- 且修改了 `knowledge/helipei-official/**`

也可以手动触发：

- 打开 GitHub 仓库的 `Actions`
- 选择 `Deploy helipei-official to Aliyun OSS`
- 点击 `Run workflow`

## 五、当前发布内容

发布脚本会上传官网静态资源，包括：

- `index.html`
- `about.html`
- `workshops.html`
- `resources.html`
- `manifest.json`
- `robots.txt`
- `css/`
- `js/`
- `assets/`
- 图标与图片资源

不会上传：

- Python 脚本
- 部署目录
- Markdown 文档
- 隐藏文件

## 六、部署成功后访问方式

如果直接用 OSS 默认外网地址，通常类似：

```text
https://<bucket-name>.<endpoint-host>/index.html
```

如果你已绑定自定义域名，则直接访问你的域名即可，例如：

```text
https://helipei.com
```

## 七、建议的安全做法

- 不要把 AccessKey 写进仓库代码
- 使用 GitHub Secrets 保存密钥
- 最好使用 RAM 用户最小权限
- 如历史上有明文 AccessKey，建议立即轮换

## 八、相关文件

- OSS 工作流：`.github/workflows/deploy-helipei-official-oss.yml`
- OSS 发布脚本：`knowledge/helipei-official/deploy_aliyun.py`
- ECS 方案说明：`knowledge/helipei-official/DEPLOY_TO_ALIYUN_ECS.md`
