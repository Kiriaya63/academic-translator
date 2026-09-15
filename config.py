"""配置加载：DeepL key、端点、防抖时长、语言映射。

API key 读取优先级：环境变量 DEEPL_AUTH_KEY > config.json。

打包成 exe 后（sys.frozen），config.json 的查找顺序：
  1) exe 同级目录的 config.json（可编辑覆盖）
  2) 打包进 exe 的默认 config.json（sys._MEIPASS）
"""
import json
import os
import sys
from pathlib import Path

DEFAULTS = {
    "deepl_api_key": "",
    "deepl_endpoint": "free",       # "free" 或 "pro"
    "debounce_ms": 500,             # 停止输入多久后自动翻译（毫秒）
    "left_source_lang": "ZH",       # 左栏（中文）源语言
    "left_target_lang": "EN-US",    # 左栏翻译目标
    "right_source_lang": "EN",      # 右栏（英文）源语言
    "right_target_lang": "ZH",      # 右栏翻译目标
}


def _config_candidates() -> list:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", ""))
        return [exe_dir / "config.json", bundle_dir / "config.json"]
    return [Path(__file__).resolve().parent / "config.json"]


def _load_file() -> dict:
    for path in _config_candidates():
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
    return {}


def get_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(_load_file())
    env_key = os.environ.get("DEEPL_AUTH_KEY")
    if env_key:
        cfg["deepl_api_key"] = env_key
    return cfg


CONFIG = get_config()


def api_key() -> str:
    return str(CONFIG.get("deepl_api_key", "")).strip()


def endpoint_url() -> str:
    if CONFIG.get("deepl_endpoint") == "pro":
        return "https://api.deepl.com/v2/translate"
    return "https://api-free.deepl.com/v2/translate"


def debounce_ms() -> int:
    try:
        return max(100, int(CONFIG.get("debounce_ms", 500)))
    except (TypeError, ValueError):
        return 500


def left_langs() -> tuple:
    return (
        str(CONFIG.get("left_source_lang", "ZH")),
        str(CONFIG.get("left_target_lang", "EN-US")),
    )


def right_langs() -> tuple:
    return (
        str(CONFIG.get("right_source_lang", "EN")),
        str(CONFIG.get("right_target_lang", "ZH")),
    )
