"""
通用多Provider工作流错误自动修复系统

规则（参考 Lobe-Chat 风格）：
- XXXX_API_KEY 存在 → 启用该Provider
- XXXX_MODEL_LIST 非必填：
   - 未配置 → 只使用排行榜前10且 context >=1M 的模型
   - 已配置 → 使用 排行榜前10(1M+) 与 MODEL_LIST 的并集
- XXXX_PROXY_URL 非必填
- 如果未读取到 XXXX_MODEL_LIST，不要报错
"""

import os
import sys
import json
import subprocess
import requests
import re
from typing import Optional, Dict, List, Set


# 已知 Provider 的 base_url 映射
PROVIDER_BASE_URLS = {
    "OPENROUTER": "https://openrouter.ai/api/v1",
    "OPENAI": "https://api.openai.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1",
    "GEMINI": "https://generativelanguage.googleapis.com/v1beta",
    "XAI": "https://api.x.ai/v1",
    "GROK": "https://api.x.ai/v1",
    "ZAI": "https://open.bigmodel.cn/api",
    "ATOMGIT": "https://api-ai.gitcode.com/v1",
    "MINIMAX": "https://api.minimax.io/v1",
    "MINIMAX_CODING_PLAN": "https://api.minimax.io/v1",
    "DEEPSEEK": "https://api.deepseek.com/v1",
    "MOONSHOT": "https://api.moonshot.cn/v1",
    "KIMI": "https://api.moonshot.cn/v1",
    "MIMO": "https://api.mimo.ai/v1",
    "QWEN": "https://dashscope.aliyuncs.com/api/v1",
    "MODELSCOPE": "https://dashscope.aliyuncs.com/api/v1",
    "NVIDIA_NIM": "https://integrate.api.nvidia.com/v1",
    "MODAL": "https://modal-labs--llm-api-proxy.modal.run/v1",
    "ZEN": "https://opencode.ai/zen/v1",
}

# 已知 Provider 的默认模型（仅在有 API_KEY 但无 MODEL_LIST 时作为兜底）
PROVIDER_DEFAULT_MODELS = {
    "OPENROUTER": [],  # 依赖排行榜动态获取
    "ATOMGIT": ["zai-org/GLM-5", "Qwen/Qwen3.5-397B-A17B"],
    "MINIMAX": ["m2.7"],
    "MINIMAX_CODING_PLAN": ["m2.7"],
    "XAI": ["grok-4.20-beta-0309-reasoning"],
    "ZEN": ["mimo-v2-pro-free", "minimax-m2.5-free", "nemotron-3-super-free"],
    "NVIDIA_NIM": ["nemotron-3-super"],
    "MOONSHOT": ["moonshot-v1-128k"],
    "MODELSCOPE": ["qwen3.5-397b-a17b"],
    "MODAL": [],  # 依赖排行榜
}


class WorkflowErrorFixer:
    def __init__(self):
        self.providers = self._discover_providers()
        print(f"\n发现 {len(self.providers)} 个已配置 API_KEY 的 Provider：")
        for p in self.providers:
            ml = p.get("model_list", [])
            print(
                f"  - {p['name']} (base_url={p['base_url']}, MODEL_LIST={'已配置 ' + str(len(ml)) + ' 个' if ml else '未配置(将使用排行榜模型)'})"
            )

    def _discover_providers(self) -> List[Dict]:
        """动态发现所有配置了 _API_KEY 的 Provider"""
        providers = []
        env = dict(os.environ)

        for key, value in env.items():
            if not key.endswith("_API_KEY"):
                continue
            if not value or not value.strip() or len(value.strip()) < 16:
                continue

            prefix = key[:-8]  # 去掉 _API_KEY
            name = prefix.replace("_", " ").title()
            # 修正常见名称
            for old, new in [
                ("Ai", "AI"),
                ("Zai", "ZAI"),
                ("Nim", "NIM"),
                ("Xai", "xAI"),
            ]:
                name = name.replace(old, new)

            base_url = PROVIDER_BASE_URLS.get(prefix, "https://openrouter.ai/api/v1")

            model_list_str = env.get(f"{prefix}_MODEL_LIST", "").strip()
            if model_list_str:
                model_list = [m.strip() for m in model_list_str.split(",") if m.strip()]
            else:
                model_list = PROVIDER_DEFAULT_MODELS.get(prefix, [])

            providers.append(
                {
                    "prefix": prefix,
                    "name": name,
                    "api_key": value.strip(),
                    "base_url": base_url,
                    "model_list": model_list,
                    "proxy_url": env.get(f"{prefix}_PROXY_URL"),
                }
            )

        # 排序：有 model_list 的优先，OpenRouter 最优先
        def sort_key(p):
            if p["prefix"] == "OPENROUTER":
                return (0, 0)
            if p["model_list"]:
                return (1, 0)
            return (2, 0)

        providers.sort(key=sort_key)
        return providers

    def _fetch_top_models(self) -> List[str]:
        """实时从排行榜获取前10且 context window >= 1M 的模型"""
        url = "https://artificialanalysis.ai/leaderboards/models"
        print(f"\n=== 实时获取最新排行榜 ===")
        print(f"URL: {url}")

        try:
            r = requests.get(
                url, timeout=45, headers={"User-Agent": "CrawlCars-AutoFix/1.0"}
            )
            print(f"HTTP状态码: {r.status_code} | 响应大小: {len(r.text)} 字符")

            if r.status_code != 200:
                print(f"请求失败，将使用各 Provider 的默认模型")
                return []

            text = r.text.lower()

            # 从页面提取模型关键词
            keywords = [
                "gemini",
                "gpt-5",
                "claude",
                "glm",
                "minimax",
                "grok",
                "kimi",
                "mimo",
                "qwen",
                "deepseek",
                "nemotron",
            ]
            found = []
            seen = set()
            for kw in keywords:
                if kw in text and kw not in seen:
                    seen.add(kw)
                    found.append(kw)

            print(f"从页面提取到模型关键词: {found}")

            # 映射为 OpenRouter 格式
            mapping = {
                "gemini": "google/gemini-3.1-pro-preview",
                "gpt-5": "openai/gpt-5.4",
                "claude": "anthropic/claude-opus-4.6",
                "glm": "z-ai/glm-5",
                "minimax": "minimax/minimax-m2.7",
                "grok": "xai/grok-4.20-beta-0309",
                "kimi": "kimi/kimi-k2.5",
                "mimo": "xiaomi/mimo-v2-pro",
                "qwen": "qwen/qwen3.5-397b-a17b",
                "deepseek": "deepseek/deepseek-r1",
                "nemotron": "nvidia/nemotron-3-super",
            }

            result = []
            for kw in found:
                if kw in mapping:
                    result.append(mapping[kw])

            print(f"映射为 OpenRouter 模型ID: {result}")
            return result[:10]

        except Exception as e:
            print(f"抓取排行榜失败: {e}")
            return []

    def _resolve_models(self, provider: Dict) -> List[str]:
        """根据规则确定要使用的模型列表"""
        configured = provider.get("model_list", [])

        if configured:
            # 有 MODEL_LIST → 与排行榜并集
            top = self._fetch_top_models()
            merged = list(dict.fromkeys(configured + top))  # 保序去重
            print(
                f"  MODEL_LIST({len(configured)}) + 排行榜({len(top)}) = 并集({len(merged)}) 个模型"
            )
            return merged
        else:
            # 无 MODEL_LIST → 只使用排行榜
            top = self._fetch_top_models()
            if top:
                print(f"  未配置 MODEL_LIST，使用排行榜 {len(top)} 个模型")
                return top
            else:
                # 排行榜也失败 → 使用 Provider 默认模型
                defaults = PROVIDER_DEFAULT_MODELS.get(provider["prefix"], [])
                if defaults:
                    print(
                        f"  排行榜获取失败，使用 {provider['name']} 默认模型: {defaults}"
                    )
                else:
                    print(f"  排行榜获取失败，且 {provider['name']} 无默认模型，跳过")
                return defaults

    def fix_error(self, error_output: str, script_name: str = "") -> bool:
        """主函数：尝试所有 Provider 修复错误"""
        context = self._collect_context(script_name)

        for provider in self.providers:
            print(f"\n{'═' * 70}")
            print(f"Provider: {provider['name']} ({provider['base_url']})")
            print(f"{'═' * 70}")

            models = self._resolve_models(provider)
            if not models:
                print(f"  {provider['name']} 无可用模型，跳过")
                continue

            for model in models[:8]:
                print(f"  → 尝试模型: {model}")
                result = self._call_model(provider, model, error_output, context)
                if result:
                    if self._apply_fix(result, provider["name"], model):
                        return True

        print("\n所有 Provider 均未能成功修复。")
        return False

    def _call_model(
        self, provider: Dict, model: str, error_info: str, context: str
    ) -> Optional[str]:
        """调用单个模型"""
        prompt = self._build_prompt(error_info, context)
        url = f"{provider['base_url']}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
        }
        # OpenRouter 需要额外 header
        if provider["prefix"] == "OPENROUTER":
            headers["HTTP-Referer"] = "https://github.com/Fatty911/crawl_cars"
            headers["X-Title"] = "CrawlCars Auto Fix"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是专业的代码调试助手，擅长修复 Python 爬虫和 GitHub Actions 工作流错误。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 7000,
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=120)
            if r.status_code == 200:
                data = r.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                if content:
                    print(f"    ✓ 调用成功，返回 {len(content)} 字符")
                    return content
                else:
                    print(f"    ✗ 返回内容为空")
                    return None
            else:
                err = r.text[:200] if r.text else ""
                print(f"    ✗ HTTP {r.status_code}: {err}")
                return None
        except requests.exceptions.Timeout:
            print(f"    ✗ 请求超时 (120s)")
            return None
        except Exception as e:
            print(f"    ✗ 请求异常: {e}")
            return None

    def _build_prompt(self, error: str, context: str) -> str:
        return f"""分析以下GitHub Actions工作流错误并给出修复方案。

## 错误信息
{error}

## 仓库上下文
{context}

请严格用以下JSON格式回复，不要加任何其他文字：
{{
  "analysis": "错误原因简析",
  "fix_type": "code|command|config|skip",
  "files_to_modify": [{{"path":"文件路径","content":"完整代码"}}],
  "commands": ["要执行的命令"],
  "confidence": 0.85,
  "reasoning": "修复理由"
}}"""

    def _apply_fix(self, response: str, provider: str, model: str) -> bool:
        """解析模型返回并应用修复"""
        fix = self._parse_json(response)
        if not fix:
            print(f"    ✗ JSON解析失败，跳过")
            return False

        confidence = fix.get("confidence", 0)
        if confidence < 0.6:
            print(f"    ✗ 置信度过低 ({confidence})，跳过")
            return False

        print(
            f"\n    ★ 获得来自 {provider} ({model}) 的修复方案 (置信度: {confidence})"
        )
        print(f"    分析: {fix.get('analysis', '')[:150]}")
        print(f"    推理: {fix.get('reasoning', '')[:150]}")

        fix_type = fix.get("fix_type", "")
        if fix_type == "skip":
            print("    模型建议跳过")
            return True

        # 修改文件
        for fi in fix.get("files_to_modify", []):
            path = fi.get("path", "")
            content = fi.get("content", "")
            if path and content:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"    已修改: {path}")
                except Exception as e:
                    print(f"    修改失败 {path}: {e}")
                    return False

        # 执行命令
        for cmd in fix.get("commands", []):
            print(f"    执行: {cmd}")
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    print(f"    命令失败: {result.stderr[:200]}")
                    return False
            except Exception as e:
                print(f"    命令异常: {e}")
                return False

        # 提交推送
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("ACTION_PAT", "")
        if repo and token:
            subprocess.run(
                'git config --local user.email "github-actions[bot]@users.noreply.github.com"',
                shell=True,
            )
            subprocess.run(
                'git config --local user.name "github-actions[bot]"', shell=True
            )
            subprocess.run("git add -A", shell=True)
            msg = f"Auto-fix by {provider}/{model}: {fix.get('analysis', '')[:80]}".replace(
                '"', '\\"'
            )
            subprocess.run(
                f'git diff --staged --quiet || git commit -m "{msg}"', shell=True
            )
            r = subprocess.run(
                f"git push https://x-access-token:{token}@github.com/{repo}.git",
                shell=True,
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                print("    推送成功")
            else:
                print(f"    推送失败: {r.stderr[:200]}")

        return True

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            text = re.sub(r"^```json?|```$", "", text.strip(), flags=re.MULTILINE)
            return json.loads(text.strip())
        except:
            return None

    def _collect_context(self, script_name: str = "") -> str:
        parts = []
        if script_name and os.path.exists(script_name):
            try:
                with open(script_name, "r", encoding="utf-8") as f:
                    parts.append(f"脚本 {script_name}:\n{f.read()[:5000]}")
            except:
                pass
        for pf in ["progress.json", "dongchedi/progress.json"]:
            if os.path.exists(pf):
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        parts.append(f"进度 {pf}:\n{f.read()[:2000]}")
                except:
                    pass
        return "\n---\n".join(parts) if parts else "无额外上下文"


def main():
    if len(sys.argv) < 2:
        print("用法: python auto_fix_workflow.py <错误日志文件或内容> [脚本名]")
        sys.exit(1)

    error_input = sys.argv[1]
    script = sys.argv[2] if len(sys.argv) > 2 else ""

    if os.path.isfile(error_input):
        with open(error_input, "r", encoding="utf-8") as f:
            error_text = f.read()
    else:
        error_text = error_input

    print("╔══════════════════════════════════════════════╗")
    print("║   通用多Provider工作流错误自动修复系统 v2    ║")
    print("╚══════════════════════════════════════════════╝")

    fixer = WorkflowErrorFixer()
    success = fixer.fix_error(error_text, script)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
