"""测试包。

测试一律在降级模式下运行：确定性、离线可跑、不消耗 API 额度。
需要验证「大模型在线」的用例（`LLMLiveCase`）会自己临时设置密钥并替换 urlopen。
"""
import os

os.environ["BANK_AGENT_SKIP_ENV_FILE"] = "1"
os.environ.pop("LLM_API_KEY", None)
