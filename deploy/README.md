# 部署到 wordtest.tumei.online（腾讯云 · 大陆访问）

参照背单词项目（`word.tumei.online`）的方式，把高考词汇诊断发布到**已备案的国内服务器**，
保证大陆学生稳定访问。GitHub Pages（`goodesam.github.io/gaokao-vocabulary-size-test/`）保留作海外备份。

## 现状
- **网址**：https://wordtest.tumei.online/ （DNS 生效 + 证书签发后可用）
- **服务器**：腾讯云轻量，广州，`43.139.242.52`，OpenCloudOS，系统 Nginx 1.26.3
  （与 `word.tumei.online`、`home.tumei.online` 同一台）
- **站点根目录**：`/var/www/wordtest.tumei.online`（只有一个 `index.html`，单文件应用）
- **Nginx 配置**：`/etc/nginx/conf.d/wordtest.tumei.online.conf`
- **部署密钥**：本机 `~/.ssh/tumei_deploy`（与背单词项目共用）

## 日常更新内容
改完 `index.html` 后，一条命令：
```bash
bash deploy/deploy-tumei.sh
```
（脚本用 rsync 覆盖服务器上的 `index.html` 并 reload nginx。`index.html` 配了
`Cache-Control: no-cache`，学生刷新即拿到最新版。）

## 首次部署是怎么搭起来的（备查）
1. **DNS**（DNSPod / 腾讯云域名解析 → `tumei.online`）：
   添加记录 `wordtest`　类型 `A`　记录值 `43.139.242.52`。
2. 服务器建目录 `/var/www/wordtest.tumei.online`，rsync 上传 `index.html`。
3. 写 `/etc/nginx/conf.d/wordtest.tumei.online.conf`（root + index.html 不缓存），
   `nginx -t && systemctl reload nginx`。
4. DNS 生效后签发证书 + 开启强制 HTTPS：
   ```bash
   ssh -i ~/.ssh/tumei_deploy root@43.139.242.52 \
     'certbot --nginx -d wordtest.tumei.online --redirect -n --agree-tos -m sgoode017@gmail.com'
   ```
   certbot 会自动改写上面的 conf，加上 443 + 80→443 跳转，并配置自动续期。

## 备注
- 端口 80/443 已随 `word.tumei.online` 一并放行，无需再开。
- “下载完整报告长图”用到 jsdelivr CDN（dom-to-image），大陆可能偏慢；
  如需更稳，可把该库下载到服务器本地自托管（非核心功能，可后续优化）。
