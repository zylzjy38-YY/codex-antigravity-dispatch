# Codex 与 Antigravity 按领域协作

由 Codex 负责拆解、整合和验收，按专业领域向 Antigravity 准备任务包。当前为 **Alpha**，已接入官方独立 `agy` CLI 的显式纯文本联调；仓库代码修改任务的自动执行仍未实现。

## 当前分工示例

| 领域 | 优先负责方 |
|---|---|
| 前端视觉与页面实现 | Antigravity |
| 复杂工作成果制作、高难学术问答 | Antigravity |
| 架构、后端、调试、测试、跨模块集成 | Codex |
| 其他领域 | 按任务判断并确认 |

这是可编辑偏好，不代表某个模型在对应领域一定领先。无论交给谁执行，最终验收仍由 Codex 负责。默认目标标签为 Gemini 4 Argon；实际模型 ID、账号权限和推理档位不能靠标签判断。

## 安装与使用

需要 Python 3.10+，无第三方运行时依赖。

```powershell
python -m pip install .
cadispatch init
cadispatch status
cadispatch route --domain frontend_visual --mode auto
```

状态默认保存在用户主目录的 `.codex-antigravity-dispatch`。可以在子命令前加 `--state-dir <绝对目录>`，或设置 `CODEX_ANTIGRAVITY_STATE`。初始化不会覆盖现有目录，不修改全局 Codex 规则，不安装或登录反重力。

复制 `examples/task.json`，填写绝对工作目录、目标、背景、输入、允许修改范围和验收条件：

```powershell
cadispatch prepare --task C:\项目外的任务目录\task.json --mode antigravity
cadispatch inspect --run-id <返回的任务编号>
```

模式 `independent` 表示由 Codex 处理；`auto` 表示按领域选人；`antigravity` 表示用户明确指定反重力。`auto` 不会启动后台派工。普通 `dispatch` 仍返回 blocked，避免把原型当成熟执行器。

## 真实 CLI 联调

独立 `agy` 与 IDE 启动脚本不同，需要另外按[官方文档](https://antigravity.google/docs/cli/install/)安装并登录。`agy models` 可查看模型。对纯文本任务，可显式运行：

```powershell
cadispatch run --run-id <任务编号> --test-model gemini-3.8-flash-medium --allow-execution --timeout 120
```

PATH 找不到 CLI 时，用 `--agy <agy.exe绝对路径>` 指定。测试模型只作用于这次调用，不改默认 Argon 目标。任务必须没有输入文件、没有写入路径、声明只读且不浏览网络。模型服务本身仍需联网。

测试在新建空目录运行，使用 CLI 的 plan 模式和 sandbox，检查 JSON 状态、结构化结果、错误提示、超时和目录变化。**这些措施不等同于强制整机只读沙箱**，也没有隔离 CLI 全局规则和工具；请仅使用不敏感的测试文字。

收到结构化回复不等于验收通过，也不等于已从运行元数据验证模型。`inspect` 显示不可变的离线准备记录，真实联调报告保存在任务目录下 `execution/result.json`。本地运行目录、原始输出、账号资料和凭据都不应上传 GitHub。

## 换账号

框架不绑定邮箱、不保存密码或 token。**桌面/IDE 登录与独立 CLI 登录分开**，桌面换号不一定改变 CLI 账号。请在官方 CLI 完成换号，重新确认目标模型权限和额度，再进行新任务。

不会自动换账号、切模型、改付费方式或重试。超时只做本地进程终止，不能证明远端任务已停止；旧任务包不会自动补跑。异常遗留锁时，先确认原进程及远端任务已结束，再删除该锁文件。

## 成熟度

已具备可安装结构、可配置领域路由、任务校验、运行记录、显式纯文本 CLI 测试、错误处理、测试与跨平台 CI 配置。仍需完成文件权限强制控制、真实模型核验、远端取消、账号切换实测及跨版本兼容验证，才适合无人值守派工。

详见[英文完整使用说明](README.md)、[验证记录](docs/VERIFICATION.md)及[后续计划](docs/ROADMAP.md)。MIT 许可证；独立项目，非 OpenAI 或 Google 官方产品。
