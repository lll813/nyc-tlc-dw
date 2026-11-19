# 把项目发布到 GitHub（代码仓库 + 在线看板）

> 目标：得到一个能写进简历的 GitHub 链接 + 一个能点开看的在线看板链接。
> 全程你自己在 Git Bash 执行；涉及 GitHub 网页的步骤已单独标出。

---

## 0. 发布前必须确认（否则会出事故）

1. **先亲手跑一遍项目**（你目前还没跑过）：
   ```bash
   cd D:/29098/deepseek/nyc_tlc_dw
   python run_all.py --skip-download
   ```
   跑通、能对 `docs/interview.md` 讲出数字后，这个项目才真正属于你。**没跑过就发布 = 简历埋雷**。

2. **确认大文件不会入库**。`.gitignore` 已排除 `data/`、`db/`、`tools/`、`lib/`。初始化前用 dry-run 看一遍待提交清单：
   ```bash
   cd D:/29098/deepseek/nyc_tlc_dw
   git init
   git add -n . | head -40
   ```
   输出里**不应出现任何 `.parquet` / `.duckdb` / `lib/` / `tools/`**。若出现，停下来修 `.gitignore`。

---

## 1. 本地提交

```bash
git add .
git commit -m "Initial commit: NYC TLC 1.28亿行出行数仓全链路"
```

---

## 2. 在 GitHub 网页创建仓库（你自己在浏览器操作）

1. 打开 https://github.com/new
2. Repository name 填 `nyc-tlc-dw`（或你喜欢的名字）
3. 选 **Public**（简历链接必须公开可见）
4. **不要**勾选 "Add a README file" / ".gitignore" / "license"（本地已有，避免冲突）
5. 点 Create repository

---

## 3. 推送到 GitHub

把下面命令里的 `你的用户名` 换成你的 GitHub 用户名（git 配置里是 `lvliling`，但 GitHub 账号名可能不同，以网页为准）：

```bash
git remote add origin https://github.com/你的用户名/nyc-tlc-dw.git
git branch -M main
git push -u origin main
```

> 若弹出登录：GitHub 已不支持密码，需用 Personal Access Token（PAT）。
> 生成路径：GitHub 头像 → Settings → Developer settings → Personal access tokens → Tokens(classic) → Generate new token，勾选 `repo` 权限，复制 token 当密码用。

---

## 4. 开启 GitHub Pages（发布在线看板）

1. 打开你的仓库页 → **Settings** → 左侧 **Pages**
2. Build and deployment → Source 选 **Deploy from a branch**
3. Branch 选 `main`，目录选 **`/docs`** → Save
4. 等 1-2 分钟，刷新页面，顶部会出现发布成功的绿色提示和网址

在线看板地址：`https://你的用户名.github.io/nyc-tlc-dw/`

> 为什么能直接看：`output/dashboard.html` 是自包含的（无外部 CDN，图片都内嵌），
> 我已复制到 `docs/index.html`，Pages 以 `/docs` 为根，打开就是看板首页。

---

## 5. 填回 README 与简历

- 把 `README.md` 顶部的 `<你的用户名>` / `<仓库名>` 换成真实值，再 `git add README.md && git commit -m "docs: 填在线看板链接" && git push`
- 简历项目下方贴两个链接：
  - 代码：`https://github.com/你的用户名/nyc-tlc-dw`
  - 看板：`https://你的用户名.github.io/nyc-tlc-dw/`

---

## 6. 验收清单

- [ ] 仓库页面能打开，README 渲染正常，能看到架构图和看板截图
- [ ] 仓库里**没有**任何 `.parquet` / `.duckdb` 大文件
- [ ] 看板链接能打开，图表和 6 张图都显示正常
- [ ] 问自己：README 里每个数字（`1.28 亿行`、`48.4%`、`17 PASS`）我都能对着 `docs/interview.md` 讲出来

---

## 常见坑

| 现象 | 原因 / 解决 |
|---|---|
| push 报 403 / Authentication failed | 用了密码，GitHub 需要 PAT（见第 3 步） |
| Pages 打开 404 | 目录选错，要选 `/docs` 不是 `/ (root)`；或还没构建完，等 2 分钟 |
| Pages 打开是空白 | `docs/index.html` 没上传成功，检查仓库 docs 目录 |
| 仓库体积过大 / push 很慢 | 有大文件混进来了，回到第 0 步 dry-run 检查 |
| 看板图片不显示 | `dashboard.html` 图片是 base64 内嵌的，正常不会丢；若用了外链版会丢 |
