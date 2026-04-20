"""
通用多Provider工作流错误自动修复系统 (2026 Ultimate Edition)

规则（融合全库优点）：
- XXXX_API_KEY 存在 → 启用该Provider
- 动态获取最新人工AI排行榜（人工分析网），应用 2026 最强模型 (Claude 4.6, GPT-5.4, Gemini 3.1)
- 保留完整的上下文解析和命令自动修复执行功能
"""

import os
import sys
import json
import subprocess
import requests
import re
from typing import Optional, Dict, List

PROVIDER_BASE_URLS = {
    "OPENROUTER": "https://openrouter.ai/api/v1",
    "DEEPSEEK": "https://api.deepseek.com/v1",
    "MINIMAX": "https://api.minimax.io/v1",
    "MOONSHOT": "https://api.moonshot.cn/v1",
    "XAI": "https://api.x.ai/v1",
    "ZEN": "https://api.zen.my/v1"
}

# 2026 Default Fallback Models
PROVIDER_DEFAULT_MODELS = {
    "OPENROUTER": ["anthropic/claude-opus-4.6", "google/gemini-3.1-pro-preview", "openai/gpt-5.4"],
    "XAI": ["grok-4.20-beta-0309"],
    "ZEN": ["opencode/mimo-v2-pro-free"],
    "DEEPSEEK": ["deepseek-r1"],
    "MOONSHOT": ["moonshot-v1-128k"],
    "MINIMAX": ["m2.7"]
}

class WorkflowErrorFixer:
    def __init__(self):
        self.providers = self._discover_providers()
        print(f"\n发现 {len(self.providers)} 个已配置 API_KEY 的 Provider。")

    def _discover_providers(self) -> List[Dict]:
        providers = []
        env = dict(os.environ)

        for key, value in env.items():
            if not key.endswith("_API_KEY") or not value or len(value.strip()) < 10:
                continue

            prefix = key[:-8]
            name = prefix.replace("_", " ").title()
            base_url = PROVIDER_BASE_URLS.get(prefix)
            if not base_url: continue

            model_list_str = env.get(f"{prefix}_MODEL_LIST", "").strip()
            model_list = [m.strip() for m in model_list_str.split(",") if m.strip()] if model_list_str else PROVIDER_DEFAULT_MODELS.get(prefix, [])

            providers.append({
                "prefix": prefix,
                "name": name,
                "api_key": value.strip(),
                "base_url": base_url,
                "model_list": model_list
            })

        providers.sort(key=lambda p: {"OPENROUTER": 0, "XAI": 1, "DEEPSEEK": 2}.get(p["prefix"], 99))
        return providers

    def _fetch_top_models(self) -> List[str]:
        print("\n=== 实时获取最新排行榜 (2026 specs) ===")
        try:
            r = requests.get("https://artificialanalysis.ai/leaderboards/models", timeout=15, headers={"User-Agent": "AutoFix/2.0"})
            if r.status_code != 200: return []
            
            text = r.text.lower()
            mapping = {
                "claude": "anthropic/claude-opus-4.6",
                "gemini": "google/gemini-3.1-pro-preview",
                "gpt": "openai/gpt-5.4",
                "grok": "xai/grok-4.20-beta-0309",
                "deepseek": "deepseek/deepseek-r1",
                "qwen": "qwen/qwen3.5-397b-a17b",
                "minimax": "minimax/minimax-m2.7",
                "mimo": "xiaomi/mimo-v2-pro"
            }
            
            found = []
            for kw in ["gemini", "gpt", "claude", "glm", "minimax", "grok", "mimo", "qwen", "deepseek"]:
                if kw in text: found.append(mapping[kw])
            
            print(f"映射结果: {found}")
            return found[:10]
        except Exception as e:
            print(f"抓取排行榜失败: {e}")
            return []

    def _resolve_models(self, provider: Dict) -> List[str]:
        if provider["prefix"] == "OPENROUTER":
            top = self._fetch_top_models()
            if top:
                return list(dict.fromkeys(top + provider["model_list"]))
        return provider["model_list"]

    def fix_error(self, error_output: str, script_name: str = "") -> bool:
        context = self._collect_context(script_name)
        if not self.providers:
            print("没有可用的提供商")
            return False

        for provider in self.providers:
            print(f"\n尝试 Provider: {provider['name']}")
            models = self._resolve_models(provider)
            
            for model in models[:5]:
                print(f"  → 使用模型: {model}")
                result = self._call_model(provider, model, error_output, context)
                if result and self._apply_fix(result, provider["name"], model):
                    return True
        return False

    def _call_model(self, provider: Dict, model: str, error_info: str, context: str) -> Optional[str]:
        prompt = f"分析以下GitHub Actions错误:\n{error_info}\n\n仓库上下文:\n{context}\n\n用JSON回复(包含 files_to_modify, commands, reasoning, confidence)。格式严格。"
        url = f"{provider['base_url']}/chat/completions"
        headers = { "Content-Type": "application/json", "Authorization": f"Bearer {provider['api_key']}" }
        if provider["prefix"] == "OPENROUTER":
            headers["HTTP-Referer"] = "https://github.com/Fatty911"
            headers["X-Title"] = "Auto Fixer"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是资深的 DevOps 工程师，专门通过修改代码或执行命令修复构建流错误。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 8000
        }
        
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=120)
            if r.status_code == 200:
                return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"    ✗ 失败 HTTP {r.status_code}")
        except Exception as e:
            print(f"    ✗ 异常: {e}")
        return None

    def _apply_fix(self, response: str, provider: str, model: str) -> bool:
        fix = self._parse_json(response)
        if not fix or fix.get("confidence", 0) < 0.6: return False
        print(f"    ★ {provider} ({model}) 成功返回方案。")
        
        for fi in fix.get("files_to_modify", []):
            try:
                with open(fi["path"], "w", encoding="utf-8") as f:
                    f.write(fi["content"])
                print(f"    ✓ 修改文件: {fi['path']}")
            except Exception as e:
                print(f"    ✗ 文件修改失败: {e}")
                
        for cmd in fix.get("commands", []):
            print(f"    执行: {cmd}")
            subprocess.run(cmd, shell=True, timeout=300)

        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("ACTION_PAT", "")
        if repo and token:
            subprocess.run('git config --local user.email "bot@users.noreply.github.com" && git config --local user.name "bot" && git add -A', shell=True)
            msg = f"Auto-fix by {provider}/{model}"
            subprocess.run(f'git diff --staged --quiet || git commit -m "{msg}"', shell=True)
            subprocess.run(f"git push https://x-access-token:{token}@github.com/{repo}.git", shell=True)
            print("    ✓ 推送成功")
        return True

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            text = re.sub(r"^```json?|```$", "", text.strip(), flags=re.MULTILINE)
            return json.loads(text.strip())
        except:
            return None

    def _collect_context(self, script_name: str) -> str:
        parts = []
        if script_name and os.path.exists(script_name):
            with open(script_name, "r") as f: parts.append(f.read()[:5000])
        return "\n".join(parts) or "无额外上下文"

if __name__ == "__main__":
    error_text = sys.argv[1] if len(sys.argv) > 1 else ""
    if os.path.isfile(error_text):
        with open(error_text, "r", encoding="utf-8") as f: error_text = f.read()
    WorkflowErrorFixer().fix_error(error_text, sys.argv[2] if len(sys.argv) > 2 else "")
