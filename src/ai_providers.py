"""
AI Provider 统一接口层 + 多Key轮询 + 超时重试
"""
import json, time, logging, threading, random
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)

PROVIDER_CONFIGS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-opus-4-5","claude-sonnet-4-5","claude-haiku-4-5",
                   "claude-3-5-sonnet-20241022","claude-3-haiku-20240307"],
        "default_model": "claude-sonnet-4-5",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o","gpt-4o-mini","gpt-4-turbo","gpt-3.5-turbo"],
        "default_model": "gpt-4o",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat","deepseek-reasoner"],
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "name": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max","qwen-plus","qwen-turbo","qwen2.5-72b-instruct","qwen2.5-32b-instruct"],
        "default_model": "qwen-max",
    },
    "ernie": {
        "name": "文心一言 (ERNIE)",
        "base_url": "https://aip.baidubce.com",
        "models": ["ernie-4.0-8k","ernie-3.5-8k","ernie-speed-128k"],
        "default_model": "ernie-4.0-8k",
    },
    "doubao": {
        "name": "豆包 (Doubao)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-pro-4k","doubao-pro-32k","doubao-lite-4k"],
        "default_model": "doubao-pro-32k",
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"],
        "default_model": "moonshot-v1-32k",
    },
    "glm": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4","glm-4-air","glm-4-flash","glm-4-plus"],
        "default_model": "glm-4",
    },
    "spark": {
        "name": "讯飞星火 (Spark)",
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "models": ["spark-max","spark-pro","spark-lite","4.0Ultra"],
        "default_model": "4.0Ultra",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.0-flash","gemini-1.5-pro","gemini-1.5-flash"],
        "default_model": "gemini-2.0-flash",
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile","llama-3.1-8b-instant","mixtral-8x7b-32768"],
        "default_model": "llama-3.3-70b-versatile",
    },
    "custom": {
        "name": "自定义端点",
        "base_url": "",
        "models": [],
        "default_model": "",
    },
}

# ── 超时配置：connect短，read长（AI生成慢）────────────────────────────────────
DEFAULT_TIMEOUT = httpx.Timeout(
    connect=15.0,   # 连接超时
    read=240.0,     # 读取超时（AI出题可能需要较长时间）
    write=30.0,
    pool=10.0,
)


@dataclass
class AIConfig:
    provider: str = "deepseek"
    api_keys: list = field(default_factory=list)
    model: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    poll_strategy: str = "round_robin"
    # 重试配置
    max_retries: int = 3        # 每个Key最多重试次数
    retry_delay: float = 3.0   # 重试间隔（秒）
    timeout_read: float = 240.0 # 读取超时秒数

    @property
    def api_key(self) -> str:
        active = [k for k in self.api_keys if k.strip()]
        return active[0] if active else ""

    @api_key.setter
    def api_key(self, v: str):
        if v and v not in self.api_keys:
            self.api_keys = [v] + [k for k in self.api_keys if k != v]
        elif not self.api_keys and v:
            self.api_keys = [v]


class KeyPool:
    """多API Key 轮询池"""
    def __init__(self, keys: list, strategy: str = "round_robin"):
        self._keys = [k.strip() for k in keys if k.strip()]
        self._strategy = strategy
        self._idx = 0
        self._lock = threading.Lock()
        self._fail_counts: dict = {}

    def next(self) -> str:
        if not self._keys:
            raise ValueError("没有可用的 API Key，请先在 AI配置 中添加")
        with self._lock:
            if self._strategy == "random":
                return random.choice(self._keys)
            elif self._strategy == "failover":
                for k in self._keys:
                    if self._fail_counts.get(k, 0) < 3:
                        return k
                # 全部失败过，重置计数重新用第一个
                self._fail_counts.clear()
                return self._keys[0]
            else:  # round_robin
                key = self._keys[self._idx % len(self._keys)]
                self._idx += 1
                return key

    def mark_fail(self, key: str):
        with self._lock:
            self._fail_counts[key] = self._fail_counts.get(key, 0) + 1
            logger.warning(f"Key调用失败 (累计{self._fail_counts[key]}次): {key[:8]}...")

    def mark_ok(self, key: str):
        with self._lock:
            self._fail_counts.pop(key, None)

    def __len__(self):
        return len(self._keys)


class AIProvider:
    def __init__(self, config: AIConfig):
        self.config = config
        self._pool = KeyPool(config.api_keys, config.poll_strategy)
        # 根据配置动态设置超时
        self.timeout = httpx.Timeout(
            connect=15.0,
            read=max(config.timeout_read, 120.0),
            write=30.0,
            pool=10.0,
        )

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        带多Key轮询 + 超时重试的对话调用。
        策略：每次失败换下一个Key，最多重试 max_retries 次，
        超时错误等待 retry_delay 秒后重试，其余错误立即切Key重试。
        """
        cfg = self.config
        max_attempts = max(cfg.max_retries, len(self._pool)) if len(self._pool) > 1 else cfg.max_retries
        last_err = None

        for attempt in range(max_attempts):
            key = self._pool.next()
            try:
                logger.info(f"AI调用 attempt={attempt+1}/{max_attempts} key={key[:8]}...")
                result = self._do_chat(key, system_prompt, user_prompt)
                self._pool.mark_ok(key)
                if attempt > 0:
                    logger.info(f"第{attempt+1}次重试成功")
                return result

            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                self._pool.mark_fail(key)
                last_err = e
                wait = cfg.retry_delay * (attempt + 1)  # 递增等待
                logger.warning(f"超时 (attempt={attempt+1}): {e}，等待{wait:.0f}s后重试")
                if attempt < max_attempts - 1:
                    time.sleep(wait)

            except httpx.HTTPStatusError as e:
                self._pool.mark_fail(key)
                last_err = e
                # 429 限流：等待更长时间
                if e.response.status_code == 429:
                    wait = cfg.retry_delay * 5
                    logger.warning(f"API限流(429)，等待{wait:.0f}s: {key[:8]}...")
                    time.sleep(wait)
                elif e.response.status_code in (401, 403):
                    # 认证失败，该Key无效，直接切下一个不等待
                    logger.error(f"Key认证失败({e.response.status_code}): {key[:8]}...")
                else:
                    logger.warning(f"HTTP错误{e.response.status_code}: {e}")
                    if attempt < max_attempts - 1:
                        time.sleep(cfg.retry_delay)

            except Exception as e:
                self._pool.mark_fail(key)
                last_err = e
                logger.warning(f"未知错误 (attempt={attempt+1}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(cfg.retry_delay)

        raise RuntimeError(
            f"AI调用失败（已重试{max_attempts}次）: {last_err}\n"
            f"建议：1) 检查网络/代理  2) 增大超时设置  3) 换用其他API Key"
        )

    def _do_chat(self, api_key: str, system_prompt: str, user_prompt: str) -> str:
        p = self.config.provider.lower()
        if p == "anthropic":
            return self._anthropic(api_key, system_prompt, user_prompt)
        elif p == "ernie":
            return self._ernie(api_key, system_prompt, user_prompt)
        else:
            return self._openai_compat(api_key, system_prompt, user_prompt)

    def _anthropic(self, key, sys_p, usr_p) -> str:
        base = self.config.base_url or "https://api.anthropic.com"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": sys_p,
            "messages": [{"role": "user", "content": usr_p}],
            "temperature": self.config.temperature,
        }
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{base}/v1/messages", headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    def _openai_compat(self, key, sys_p, usr_p) -> str:
        cfg_prov = PROVIDER_CONFIGS.get(self.config.provider, {})
        base = self.config.base_url or cfg_prov.get("base_url", "")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": sys_p},
                {"role": "user",   "content": usr_p},
            ],
        }
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{base}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    def _ernie(self, key, sys_p, usr_p) -> str:
        model_ep = {
            "ernie-4.0-8k": "ernie-4.0-8k",
            "ernie-3.5-8k": "ernie-3.5-8k",
            "ernie-speed-128k": "ernie-speed-128k",
        }.get(self.config.model, self.config.model)
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_ep}"
        headers = {"Content-Type": "application/json"}
        payload = {"messages": [{"role": "user", "content": f"{sys_p}\n\n{usr_p}"}]}
        if key.startswith("bce-"):
            headers["Authorization"] = f"Bearer {key}"
        else:
            url += f"?access_token={key}"
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json().get("result", "")

    def test_connection(self) -> tuple:
        try:
            key = self._pool.next()
            result = self._do_chat(key, "你是助手。", "请回复'连接成功'四个字。")
            return True, f"连接成功 (Key: {key[:8]}...): {result[:30]}"
        except Exception as e:
            return False, f"连接失败: {e}"
