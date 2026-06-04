"""
通用多Provider工作流错误自动修复系统

规则（融合全库优点）：
- XXXX_API_KEY 存在 → 启用该Provider
- XXXX_BASE_URL 可覆盖或补充 OpenAI-compatible API 地址
- XXXX_MODEL_LIST 存在 → 使用用户显式配置的模型
- XXXX_PROXY_URL 存在 → 该 Provider 请求走指定代理
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
    "ATOMGIT": "https://api-ai.gitcode.com/v1",
    "OPENROUTER": "https://openrouter.ai/api/v1",
    "DEEPSEEK": "https://api.deepseek.com/v1",
    "MINIMAX": "https://api.minimax.io/v1",
    "MINIMAX_CODING_PLAN": "https://api.minimax.io/v1",
    "MOONSHOT": "https://api.moonshot.cn/v1",
    "XAI": "https://api.x.ai/v1",
    "NVIDIA_NIM": "https://integrate.api.nvidia.com/v1",
    "OPENAI": "https://api.openai.com/v1",
}

# 只保留已确认可由仓库规则支撑的默认模型；其他 Provider 需显式配置 MODEL_LIST。
PROVIDER_DEFAULT_MODELS = {
    "ATOMGIT": ["zai-org/GLM-5", "Qwen/Qwen3.5-397B-A17B"],
    "NVIDIA_NIM": ["nemotron-3-super"],
    "DEEPSEEK": ["deepseek-r1"],
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
            base_url = env.get(f"{prefix}_BASE_URL", "").strip() or PROVIDER_BASE_URLS.get(prefix)
            if not base_url:
                print(f"跳过 {prefix}: 未配置 {prefix}_BASE_URL，且没有内置 OpenAI-compatible 地址")
                continue

            model_list = self._parse_model_list(env.get(f"{prefix}_MODEL_LIST", ""))
            if not model_list:
                model_list = PROVIDER_DEFAULT_MODELS.get(prefix, [])
            if not model_list:
                print(f"跳过 {prefix}: 未配置 {prefix}_MODEL_LIST，且没有可靠默认模型")
                continue

            proxy_url = env.get(f"{prefix}_PROXY_URL", "").strip()

            providers.append({
                "prefix": prefix,
                "name": name,
                "api_key": value.strip(),
                "base_url": base_url,
                "model_list": model_list,
                "proxies": {"http": proxy_url, "https": proxy_url} if proxy_url else None,
            })

        # 排序：免费模型优先（AtomGit、ZEN、NVIDIA NIM、Modal），然后 OpenRouter
        def sort_key(p):
            prefix = p["prefix"]
            # 免费 Provider 优先
            if prefix in ["ATOMGIT", "ZEN", "NVIDIA_NIM", "MODAL"]:
                return (0, 0 if prefix == "ATOMGIT" else 1)
            # OpenRouter 排在免费之后
            if prefix == "OPENROUTER":
                return (1, 0)
            # 有 model_list 的排中间
            if p["model_list"]:
                return (2, 0)
            # 其他排最后
            return (3, 0)

        providers.sort(key=sort_key)
        return providers

    def _parse_model_list(self, value: str) -> List[str]:
        return [m.strip() for m in re.split(r"[\s,;]+", value.strip()) if m.strip()]

    def _fetch_top_models(self) -> List[str]:
        print("\n=== 实时获取最新排行榜 ===")
        try:
            r = requests.get("https://artificialanalysis.ai/leaderboards/models", timeout=15, headers={"User-Agent": "AutoFix/2.0"})
            if r.status_code != 200: return []
            
            text = r.text.lower()
            mapping = {
                "claude": "anthropic/claude-opus-4.6",
                "gemini": "google/gemini-3.1-pro-preview",
                "gpt": "openai/gpt-5.4",
                "deepseek": "deepseek/deepseek-r1",
                "qwen": "qwen/qwen3.5-397b-a17b",
                "minimax": "minimax/minimax-m2.7",
                "mimo": "xiaomi/mimo-v2-pro"
            }
            
            found = []
            for kw in ["gemini", "gpt", "claude", "glm", "minimax", "grok", "mimo", "qwen", "deepseek"]:
                if kw in text and kw in mapping:
                    found.append(mapping[kw])
            
            print(f"映射结果: {found}")
            return found[:10]
        except Exception as e:
            print(f"抓取排行榜失败: {e}")
            return []

    def _resolve_models(self, provider: Dict) -> List[str]:
        if provider["prefix"] == "OPENROUTER" and os.environ.get("AUTO_FIX_DYNAMIC_MODELS", "").lower() in {"1", "true", "yes"}:
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
            
            import json
            try:
                with open(".ai_model_scores.json", "r") as f:
                    scores = json.load(f)
            except Exception:
                scores = {}
            
            models = sorted(self._resolve_models(provider), key=lambda m: scores.get(m, 0), reverse=True)
            
            for model in models[:5]:
                print(f"  → 使用模型: {model}")
                result = self._call_model(provider, model, error_output, context)
                if result:
                    if self._apply_fix(result, provider["name"], model):
                        return True
                    else:
                        scores[model] = scores.get(model, 0) - 2
                        with open(".ai_model_scores.json", "w") as f:
                            json.dump(scores, f, indent=2)
                        print(f"    [Penalty] 模型 {model} 修复失败或产生幻觉，扣分")
        return False

    def _call_model(self, provider: Dict, model: str, error_info: str, context: str) -> Optional[str]:
        prompt = f"分析以下GitHub Actions错误:\n{error_info}\n\n仓库上下文:\n{context}\n\n【AI防幻觉与打分机制】请在修复前确保逻辑正确，不可凭空假设API和类库，务必联网检索确定。若产生幻觉将在下次被扣分。\n用JSON回复(包含 files_to_modify, commands, reasoning, confidence)。格式严格。"
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
            request_kwargs = {"json": payload, "headers": headers, "timeout": 120}
            if provider.get("proxies"):
                request_kwargs["proxies"] = provider["proxies"]
            r = requests.post(url, **request_kwargs)
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
            subprocess.run('git config --local user.email "bot@users.noreply.github.com" && git config --local user.name "bot"', shell=True)

            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True
            )
            if not status_result.stdout.strip():
                print("    ⚠️ AI 未产生任何文件改动，拒绝触发后续流程")
                return False

            # === 推送前语法校验 ===
            print("    🔍 执行语法校验...")
            validate_result = subprocess.run(
                ["python", "custom_scripts/validate_syntax.py"],
                capture_output=True, text=True, timeout=60
            )
            if validate_result.returncode != 0:
                print(f"    ✗ 语法校验失败:\n{validate_result.stdout}\n{validate_result.stderr}")
                print("    ⚠️ 回滚修改，拒绝推送")
                subprocess.run("git checkout -- .", shell=True)
                return False
            print("    ✓ 语法校验通过")
            
            try:
                import json
                scores = {}
                try:
                    with open(".ai_model_scores.json", "r") as f:
                        scores = json.load(f)
                except Exception:
                    pass
                scores[model] = scores.get(model, 0) + 1
                with open(".ai_model_scores.json", "w") as f:
                    json.dump(scores, f, indent=2)
            except Exception:
                pass

            subprocess.run("git add -A", shell=True)
            if subprocess.run("git diff --staged --quiet", shell=True).returncode == 0:
                print("    ⚠️ 未产生可提交的修复改动，拒绝触发后续流程")
                return False

            msg = f"Auto-fix by {provider}/{model}"
            commit_result = subprocess.run(f'git commit -m "{msg}"', shell=True)
            if commit_result.returncode != 0:
                print("    ✗ 提交失败")
                return False

            push_result = subprocess.run(f"git push https://x-access-token:{token}@github.com/{repo}.git", shell=True)
            if push_result.returncode != 0:
                print("    ✗ 推送失败")
                return False
            print("    ✓ 推送成功")
        return True

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            text = re.sub(r"^```json?|```$", "", text.strip(), flags=re.MULTILINE)
            return json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
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
    fixed = WorkflowErrorFixer().fix_error(error_text, sys.argv[2] if len(sys.argv) > 2 else "")
    sys.exit(0 if fixed else 1)
