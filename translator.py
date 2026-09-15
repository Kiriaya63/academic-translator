"""DeepL 翻译封装。"""
import requests

from config import api_key, endpoint_url


class TranslateError(Exception):
    """翻译错误，message 为面向用户的中文提示。"""


_ERROR_MESSAGES = {
    400: "请求格式错误（400）",
    401: "API key 无效或缺失（401）",
    403: "API key 无权限（403）",
    404: "请求的资源不存在（404）",
    429: "请求过于频繁，请稍候再试（429）",
    456: "已超出 DeepL 免费额度（456）",
    503: "DeepL 服务暂时不可用（503）",
}


def translate(text: str, source_lang: str, target_lang: str) -> str:
    """把 text 从 source_lang 翻译成 target_lang，返回译文。"""
    text = text.strip()
    if not text:
        return ""

    key = api_key()
    if not key:
        raise TranslateError("尚未配置 DeepL API key，请编辑 config.json")

    headers = {"Authorization": f"DeepL-Auth-Key {key}"}
    data = {
        "text": text,
        "source_lang": source_lang,
        "target_lang": target_lang,
    }

    try:
        resp = requests.post(endpoint_url(), headers=headers, data=data, timeout=15)
    except requests.exceptions.Timeout:
        raise TranslateError("请求超时，请检查网络") from None
    except requests.exceptions.ConnectionError:
        raise TranslateError("无法连接 DeepL，请检查网络") from None

    if resp.status_code != 200:
        msg = _ERROR_MESSAGES.get(resp.status_code, f"DeepL 返回错误（{resp.status_code}）")
        raise TranslateError(msg)

    try:
        payload = resp.json()
        return payload["translations"][0]["text"]
    except (KeyError, IndexError, ValueError):
        raise TranslateError("DeepL 返回了无法解析的数据") from None
