# GitHub 接入说明

## 当前已经准备好的内容

- 代码主目录已经统一为 `framework/`
- 运行产物已经统一为 `artifacts/reports/` 和 `artifacts/report_data/`
- 仓库适合直接初始化为 Git 仓库
- `.github/workflows/pr-check.yml` 会做提交与 PR 质量检查
- `.github/workflows/docker-publish.yml` 会在主干分支发布 Docker 镜像

## 你需要提供的信息

为了把仓库真正连到 GitHub，我还需要你提供下面这些信息：

- GitHub 用户名或组织名
- 仓库名
- 仓库是 `public` 还是 `private`
- 你打算用 `HTTPS` 还是 `SSH` 方式推送
- 如果仓库已经创建好，直接给我远端地址即可

拿到这些信息后，我就可以继续帮你完成本地远端配置说明。

## 本地初始化

如果当前目录还不是 Git 仓库，执行：

```bash
git init -b main
```

## 关联 GitHub 远端

在 GitHub 上创建一个空仓库后，执行：

```bash
git remote add origin <你的仓库地址>
git add .
git commit -m "chore: initialize android ui automation framework"
git push -u origin main
```

## 当前 GitHub Actions 会做什么

### `PR Check`

- 安装项目依赖
- 编译 `framework/`、`tests/`、`scripts/`
- 执行不依赖真机的测试：
  - `tests/test_case_generator.py`
  - `tests/test_image_engine.py`
- 上传测试报告工件

### `Docker Publish`

- 在 `main` 分支 push 后再次执行基础测试
- 构建 Docker 镜像
- 发布到：
  - `ghcr.io/leaveeeeeee/ai-android-ui-autotest-framework`

## 是否需要 GitHub 流水线

建议需要，而且这个仓库已经提前配好了基础流水线。

作用：

- 每次 push 或提 PR 时自动检查基础质量
- 提前发现语法错误、导包错误、基础能力回归
- 让多人协作时更容易发现问题

当前配置文件：

- [/.github/workflows/pr-check.yml](/Volumes/SD%20Card/从入门到%20recode/uiauto/.github/workflows/pr-check.yml)
- [/.github/workflows/docker-publish.yml](/Volumes/SD%20Card/从入门到%20recode/uiauto/.github/workflows/docker-publish.yml)

`PR Check` 除了运行检查外，还会上传一份 `ci-reports` 工件，里面包含：

- `ci_pytest_report.html`
- `ci_junit.xml`

## 不建议直接放到 GitHub 的内容

- `artifacts/reports/` 下的运行结果
- `artifacts/report_data/` 下的截图、日志、Allure 原始数据
- 本地虚拟环境和缓存目录

这些内容已经建议放进 `.gitignore`。
