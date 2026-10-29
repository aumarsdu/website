# 河狸陪官网部署到阿里云 ECS

当前仓库已经补齐 GitHub 一键部署到阿里云 ECS 的基础配置。

## 部署方式

- 触发方式：推送到 `main` 分支，且变更包含 `knowledge/helipei-official/**`
- 执行入口：`.github/workflows/deploy-helipei-official-ecs.yml`
- 发布逻辑：
  - GitHub Actions 打包官网静态文件
  - 通过 SSH 上传到阿里云 ECS
  - 远程执行 `deploy/release.sh`
  - 以 `releases/时间戳` 方式保存版本
  - 自动更新 `current` 软链接
  - 尝试 reload Nginx

## GitHub Secrets

在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 中新增：

| Secret 名称 | 必填 | 说明 |
| :--- | :--- | :--- |
| `ECS_HOST` | 是 | ECS 公网 IP 或域名 |
| `ECS_USER` | 是 | SSH 登录用户名，推荐单独部署用户 |
| `ECS_SSH_PRIVATE_KEY` | 是 | 与服务器公钥配对的私钥 |
| `ECS_PORT` | 否 | SSH 端口，默认 `22` |
| `ECS_DEPLOY_PATH` | 否 | 站点发布目录，默认 `/var/www/helipei-official` |

## 服务器初始化

首次部署前，在 ECS 上完成一次初始化：

```bash
sudo mkdir -p /var/www/helipei-official/releases
sudo chown -R $USER:$USER /var/www/helipei-official
```

然后把 Nginx 配置放到服务器上：

```bash
sudo cp knowledge/helipei-official/deploy/nginx.helipei-official.conf.example /etc/nginx/conf.d/helipei-official.conf
```

按实际域名修改：

- `server_name`
- 根目录默认就是 `/var/www/helipei-official/current`

修改后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## SSH 公钥登录

本地先生成部署密钥：

```bash
ssh-keygen -t ed25519 -C "github-actions-helipei"
```

把公钥追加到 ECS：

```bash
mkdir -p ~/.ssh
cat ~/path/to/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

再把私钥内容填入 GitHub Secret `ECS_SSH_PRIVATE_KEY`。

## 触发部署

满足以下任一条件即可：

- 推送 `main` 分支并修改官网目录
- 在 GitHub Actions 页面手动运行 `Deploy helipei-official to Aliyun ECS`

## 发布结果

服务器目录结构：

```text
/var/www/helipei-official
├── current -> /var/www/helipei-official/releases/20260405xxxxxx
└── releases
    ├── 20260405xxxxxx
    └── 20260405yyyyyy
```

脚本默认只保留最近 5 个版本。

## 回滚

登录 ECS 后，把 `current` 指回旧版本即可：

```bash
ln -sfn /var/www/helipei-official/releases/旧版本目录 /var/www/helipei-official/current
sudo systemctl reload nginx
```

## 相关文件

- 工作流：`.github/workflows/deploy-helipei-official-ecs.yml`
- 远程发布脚本：`knowledge/helipei-official/deploy/release.sh`
- Nginx 示例：`knowledge/helipei-official/deploy/nginx.helipei-official.conf.example`
