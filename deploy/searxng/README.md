# 自建 SearXNG 部署

CiaBotlloNya 联网搜索的搜索后端，用 docker-compose 一键部署官方 `searxng/searxng:latest`。

## 快速开始

```bash
# 1. 生成 settings.yml（随机密钥）
cp settings.yml.example settings.yml
python3 -c "import secrets; print(secrets.token_hex(32))"   # 打印随机密钥
# 把上面输出的值手动填入 settings.yml 的 secret_key（替换 CHANGE_ME）

# 2. 起容器
docker compose up -d

# 3. 让 bot 容器能通过容器名访问（首次）
docker network connect searxng-net ncatbot

# 4. 验证 JSON 端点
curl -s 'http://127.0.0.1:8888/search?q=hello&format=json' | head -c 200
```

## 端口与网络

- 宿主端口 `127.0.0.1:8888`（仅本机，不暴露公网）→ 容器 `8080`。换端口改 `docker-compose.yml` 的 `ports` 与 `SEARXNG_BASE_URL` 两处数字。
- 网络 `searxng-net`：bot 容器经 `docker network connect` 加入后，以 `http://searxng:8080` 访问。

## 配置要点（settings.yml）

- `use_default_settings: true`：继承镜像默认引擎列表。
- `server.secret_key`：随机密钥（部署时生成）。
- `server.limiter: false`：私有单用户，关闭限流避免偶发 429。
- `search.formats: [html, json]`：**必须**显式启用 json（镜像默认仅 html，缺了 json 会让 `format=json` 返回 403）。

## 关联

- bot 侧配置：`core/config/config.yaml` 的 `llm.enhance.search.instance_url` 设为 `http://searxng:8080`。
- 运维细节：见 [`qq/OPERATIONS.md`](../../qq/OPERATIONS.md)。
- 设计依据：见 [`docs/search-rag-design.md`](../../docs/search-rag-design.md)。
