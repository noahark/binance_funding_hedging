#!/usr/bin/env bash
# 远程部署：本机执行，把指定 commit 构建成镜像并在服务器上切换。
#
# 架构（2026-08-28 实地勘察）：应用跑在 Docker 里，systemd 单元
# funding-hedging.service 的 ExecStart 直接写死镜像 tag，而 tag 就是 commit sha
# ——单元文件本身即版本记录。前面 Caddy(funding-hedging-proxy.service) 反代 HTTPS。
# 服务器上没有 git 仓库，构建 context 由本机打包推送。
#
# 用法：
#   scripts/deploy.sh                 # 部署当前 origin/main
#   scripts/deploy.sh <commit-ish>    # 部署指定 commit
#   DEPLOY_HOST=root@1.2.3.4 scripts/deploy.sh
#
# 认证走 SSH key。没配 key 时可临时 export SSHPASS=... 用密码（需要 sshpass）；
# 密码只经环境变量传递，绝不写入本文件、日志或服务器。
set -euo pipefail

HOST="${DEPLOY_HOST:-root@47.240.168.162}"
UNIT="funding-hedging.service"
IMAGE="funding-hedging"
HEALTH_URL="http://127.0.0.1:8787/readyz"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
KEEP_IMAGES="${KEEP_IMAGES:-3}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
die() { printf '\033[31m!!\033[0m %s\n' "$*" >&2; exit 1; }

if [ -n "${SSHPASS:-}" ]; then
  command -v sshpass >/dev/null || die "SSHPASS 已设置但未安装 sshpass"
  SSH=(sshpass -e ssh -o StrictHostKeyChecking=accept-new)
else
  SSH=(ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes)
fi
remote() { "${SSH[@]}" "$HOST" "$@"; }

# ---------------------------------------------------------------- 前置检查
REF="${1:-origin/main}"
git rev-parse --verify --quiet "$REF^{commit}" >/dev/null || die "找不到 commit: $REF"
SHA_FULL="$(git rev-parse "$REF^{commit}")"
SHA="${SHA_FULL:0:7}"

[ -z "$(git status --porcelain)" ] || die "工作区不干净，提交或 stash 后再部署"

# 部署的必须是已推送到远端的 commit —— 否则服务器上的版本无从追溯
git fetch origin --quiet
git merge-base --is-ancestor "$SHA_FULL" origin/main 2>/dev/null \
  || die "$SHA 不在 origin/main 上。先合并并推送，再部署（服务器版本必须可追溯）"

log "目标版本 $SHA  $(git log -1 --format=%s "$SHA_FULL")"

# ---------------------------------------------------------------- 连通性 + 当前状态
remote true 2>/dev/null || die "连不上 $HOST（未配 SSH key 时请 export SSHPASS=...）"

CUR_TAG="$(remote "grep -o '${IMAGE}:[a-f0-9]\{7,\}' /etc/systemd/system/${UNIT}" | head -1 | cut -d: -f2)"
[ -n "$CUR_TAG" ] || die "无法从 $UNIT 解析当前镜像 tag"
log "服务器当前版本 $CUR_TAG"
[ "$CUR_TAG" = "$SHA" ] && { log "已是目标版本，无需部署"; exit 0; }

# ---------------------------------------------------------------- 构建
# 只推 Dockerfile 需要的四项，与线上镜像内容一致（不含 .git/docs/reports）。
log "打包 context 并远程构建（服务器内存仅 1.8G，构建约需 1-2 分钟）"
BUILD_CTX="$(mktemp -d)"
trap 'rm -rf "$BUILD_CTX"' EXIT
git archive "$SHA_FULL" backend frontend schemas requirements.txt > "$BUILD_CTX/ctx.tar"

cat > "$BUILD_CTX/Dockerfile" <<EOF
FROM python:3.11.16-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt jsonschema==4.26.0
COPY backend ./backend
COPY frontend ./frontend
COPY schemas ./schemas
LABEL org.opencontainers.image.revision="$SHA_FULL"
CMD ["python", "-m", "backend.app.server"]
EOF
tar -rf "$BUILD_CTX/ctx.tar" -C "$BUILD_CTX" Dockerfile

remote "docker build -q -t ${IMAGE}:${SHA} -" < "$BUILD_CTX/ctx.tar" \
  || die "镜像构建失败，服务未改动"
log "镜像 ${IMAGE}:${SHA} 构建完成"

# ---------------------------------------------------------------- 切换 + 健康检查
rollback() {
  log "回滚到 $CUR_TAG"
  remote "sed -i 's|${IMAGE}:${SHA}|${IMAGE}:${CUR_TAG}|g' /etc/systemd/system/${UNIT} \
          && systemctl daemon-reload && systemctl restart ${UNIT}"
  die "部署失败，已回滚到 $CUR_TAG"
}

log "切换 systemd 单元并重启"
remote "sed -i 's|${IMAGE}:${CUR_TAG}|${IMAGE}:${SHA}|g' /etc/systemd/system/${UNIT} \
        && systemctl daemon-reload && systemctl restart ${UNIT}" || rollback

log "等待 readyz 200（最多 ${HEALTH_TIMEOUT}s）"
remote "for i in \$(seq 1 ${HEALTH_TIMEOUT}); do
          code=\$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 ${HEALTH_URL} || true)
          [ \"\$code\" = 200 ] && { echo \"readyz 200 (\${i}s)\"; exit 0; }
          sleep 1
        done; exit 1" || rollback

# ---------------------------------------------------------------- 收尾
log "清理旧镜像（保留最近 ${KEEP_IMAGES} 个）"
remote "docker images --format '{{.Tag}} {{.CreatedAt}}' ${IMAGE} | sort -k2 -r \
        | tail -n +\$((${KEEP_IMAGES}+1)) | awk '{print \$1}' \
        | xargs -r -I{} docker rmi ${IMAGE}:{} 2>/dev/null || true"

log "部署完成：$CUR_TAG -> $SHA"
remote "systemctl is-active ${UNIT} ${UNIT%.service}-proxy.service | tr '\n' ' '; echo"
