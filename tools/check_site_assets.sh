#!/usr/bin/env bash
# 发布前的非空守卫：site/ 里页面依赖的产物必须存在且非空。
#
# 为什么抽成脚本：这份清单原先只写在 publish-site.yml 里，而每日自动部署走的是
# daily.yml —— 那条路径直接 upload-pages-artifact 就部署，一道守卫都没有。
# 每天自动跑的链路反而没保护，是更贵的那个缺口。
# 复制一份清单到第二个 workflow 会立刻开始漂移（同一信息两处维护），
# 所以两个 workflow 都调这个脚本，清单只有这一份。
#
# 用法：tools/check_site_assets.sh [site 目录，默认 site]
set -euo pipefail

SITE="${1:-site}"

# 渲染器产出的页面与数据
PRODUCTS=(
  index.html
  daily.html
  random.html
  archive/index.html
  pool.min.json
  artists.min.json
)

# 静态签入的资源 —— 【不由任何脚本重新生成】，只靠 checkout 带过来。
# 正因为没有东西会重造它们，误删之后一路静默：页面照开，只是 404 几个请求、
# 加到手机主屏拿不到图标。所以它们尤其需要被守卫点名。
STATIC=(
  manifest.webmanifest
  icon-192.png
  icon-512.png
  icon-180.png
  icon-maskable-512.png
)

fail=0
for f in "${PRODUCTS[@]}" "${STATIC[@]}"; do
  if [ ! -s "$SITE/$f" ]; then
    echo "::error::$SITE/$f 缺失或为空，拒绝发布"
    fail=1
  fi
done
[ "$fail" -eq 0 ] || exit 1

echo "$SITE/ 共 $(find "$SITE" -type f | wc -l) 个文件，$(( ${#PRODUCTS[@]} + ${#STATIC[@]} )) 项必需产物齐全"
