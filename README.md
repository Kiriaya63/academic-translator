# 学术翻译弹窗

一个常驻桌面的小型翻译工具：左栏中文、右栏英文，在任意一侧停止输入约 0.5 秒后，另一侧自动出现翻译。基于 DeepL API，偏向学术/科研风格的翻译质量。

## 功能

- 无边框、始终置顶的小弹窗，可拖动，关闭按钮隐藏到系统托盘
- 双向自动翻译：中文 → 英文、英文 → 中文
- 防抖触发，停止输入后自动翻译，避免频繁调用 API
- 底部状态栏显示翻译状态与错误提示（如 key 无效、超出额度）
- 系统托盘菜单：显示/隐藏、始终置顶开关、退出
- 全局快捷键 `Ctrl+Alt+T`：随时呼出/隐藏窗口

## 环境要求

- Python 3.9 及以上

## 安装与运行

1. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

2. 获取 DeepL API key（免费即可）：
   - 打开 <https://www.deepl.com/pro-api> 注册免费账号
   - 在账户页复制你的 `DeepL-Auth-Key`

3. 配置 key：编辑 `config.json`，把 `deepl_api_key` 填上（也可设置环境变量 `DEEPL_AUTH_KEY`，优先级更高）。

4. 运行：

   ```bash
   python main.py
   ```

## 配置说明（config.json）

| 字段 | 说明 | 默认值 |
| --- | --- | --- |
| `deepl_api_key` | DeepL API key | 空 |
| `deepl_endpoint` | `free`（免费版）或 `pro`（付费版） | `free` |
| `debounce_ms` | 停止输入多久后触发翻译（毫秒） | `500` |
| `left_source_lang` | 左栏源语言 | `ZH` |
| `left_target_lang` | 左栏翻译目标 | `EN-US` |
| `right_source_lang` | 右栏源语言 | `EN` |
| `right_target_lang` | 右栏翻译目标 | `ZH` |

## 使用

- 左栏输入中文，停止输入后右栏自动出现英文；右栏反之。
- 拖动顶部标题栏可移动窗口；点 ✕ 隐藏到托盘；托盘图标右键可退出。
- 清空一侧内容时，另一侧会同步清空。

## 常见问题

- **提示「尚未配置 DeepL API key」**：未填写 `config.json` 中的 key。
- **提示「API key 无效（401）」**：key 填写错误，或复制时带了多余空格。
- **提示「已超出 DeepL 免费额度（456）」**：免费版每月约 50 万字符，已用尽，可等下月重置或升级 Pro。

## 打包成 exe

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name Translator main.py
```

产物在 `dist/Translator.exe`。为安全起见，**API key 不打包进 exe**，而是放在 exe 同级的 `config.json` 中；程序启动时优先读取该文件。分发时需把 `Translator.exe` 与 `config.json` 放在一起。

## 项目结构

```
Translator/
├── main.py            # 入口：应用、系统托盘、主窗口
├── window.py          # 主弹窗：双输入框 + 双向翻译逻辑
├── translator.py      # DeepL 封装
├── config.py          # 配置加载
├── config.json        # 你的本地配置（不提交）
├── config.example.json# 配置模板
└── requirements.txt
```
