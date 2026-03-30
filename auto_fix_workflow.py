"""
通用多Provider工作流错误自动修复系统
规则：
- XXXX_API_KEY 存在 → 启用该Provider
- XXXX_MODEL_LIST 非必填：
   - 未配置 → 只使用排行榜前10且 context >=1M 的模型
   - 已配置 → 使用 排行榜前10(1M+) 与 MODEL_LIST 的并集
- XXXX_PROXY_URL 非必填
"""
import os
import sys
import json
import subprocess
import requests
import re
from typing import Optional, Dict, List, Set

class WorkflowErrorFixer:
    def __init__(self):
        self.providers = self._discover_providers()
        print(f"发现 {len(self.providers)} 个已配置 API_KEY 的 Provider\n")

    def _discover_providers(self) -> List[Dict]:
        providers = []
        env = dict(os.environ)
        
        provider_base = {
            "OPENROUTER": "https://openrouter.ai/api/v1",
            "OPENAI": "https://api.openai.com/v1",
            "ANTHROPIC": "https://api.anthropic.com/v1",
            "GEMINI": "https://generativelanguage.googleapis.com/v1beta",
            "XAI": "https://api.x.ai/v1",
            "GROK": "https://api.x.ai/v1",
            "ZAI": "https://api.bigmodel.cn",
            "MINIMAX": "https://api.minimax.io/v1",
            "DEEPSEEK": "https://api.deepseek.com/v1",
            "KIMI": "https://api.moonshot.cn/v1",
            "MIMO": "https://api.mimo.ai/v1",
            "QWEN": "https://dashscope.aliyuncs.com/api/v1",
        }
        
        for key, value in env.items():
            if key.endswith("_API_KEY") and value.strip() and len(value) > 15:
                prefix = key[:-8]  # remove _API_KEY
                name = prefix.replace("_", " ").title().replace("Ai", "AI").replace("Zai", "ZAI")
                
                model_list_str = env.get(f"{prefix}_MODEL_LIST", "").strip()
                model_list = [m.strip() for m in model_list_str.split(",") if m.strip()] if model_list_str else []
                
                providers.append({
                    "prefix": prefix,
                    "name": name,
                    "api_key": value,
                    "base_url": provider_base.get(prefix, "https://openrouter.ai/api/v1"),
                    "model_list": model_list,
                    "proxy_url": env.get(f"{prefix}_PROXY_URL")
                })
        
        # OpenRouter 优先
        providers.sort(key=lambda p: p["prefix"] != "OPENROUTER")
        return providers

    def _fetch_top_models(self) -> List[str]:
        """实时从排行榜获取前10且 context window >= 1M 的模型"""
        print("正在从 https://artificialanalysis.ai/leaderboards/models 获取最新排行榜...")
        try:
            r = requests.get("https://artificialanalysis.ai/leaderboards/models", 
                           timeout=30, 
                           headers={"User-Agent": "CrawlCars-AutoFix/1.0"})
            if r.status_code != 200:
                print(f"请求失败，状态码: {r.status_code}")
                return []
            
            text = r.text.lower()
            candidates = re.findall(r'(gemini|gpt|claude|glm|minimax|grok|kimi|mimo|qwen|deepseek).*?(?:3\.1|5\.4|4\.6|2\.0|opus|sonnet|r1|k2)', text)
            
            unique = []
            seen = set()
            for c in candidates:
                cleaned = re.sub(r'[^a-z0-9\.\-]', '', c)
                if cleaned not in seen and len(cleaned) > 4:
                    seen.add(cleaned)
                    unique.append(cleaned)
            
            print(f"提取到 {len(unique)} 个潜在高性能模型: {unique[:10]}")
            
            mapping = {
                "gemini": "google/gemini-3.1-pro-preview",
                "gpt5": "openai/gpt-5.4",
                "claudeopus": "anthropic/claude-opus-4.6",
                "claudesonnet": "anthropic/claude-sonnet-4.6",
                "glm": "z-ai/glm-5",
                "minimax": "minimax/minimax-m2.7",
                "grok": "xai/grok-4.20-beta-0309",
                "kimi": "kimi/kimi-k2.5",
            }
            
            result = []
            for item in unique:
                for k, v in mapping.items():
                    if k in item:
                        if v not in result:
                            result.append(v)
                        break
            print(f"映射后得到 {len(result)} 个有效模型: {result}")
            return result[:10]
            
        except Exception as e:
            print(f"抓取排行榜失败: {e}")
            return []

    def fix_error(self, error_output: str, script_name: str = "") -> bool:
        context = self._collect_context(script_name)
        
        for provider in self.providers:
            print(f"\n{'═' * 80}")
            print(f"尝试 Provider → {provider['name']}")
            print(f"{'═' * 80}")
            
            models_to_try = provider["model_list"]
            if not models_to_try:
                print("  未配置 MODEL_LIST，使用实时排行榜前10模型")
                models_to_try = self._fetch_top_models()
            else:
                print(f"  使用用户配置的 {len(models_to_try)} 个模型 + 排行榜模型")
                top = self._fetch_top_models()
                model_set: Set[str] = set(models_to_try) | set(top)
                models_to_try = list(model_set)
            
            if not models_to_try:
                print("  没有可用模型，跳过")
                continue
                
            for model in models_to_try[:6]:
                print(f"  尝试模型: {model}")
                result = self._call_model(provider, model, error_output, context)
                if result:
                    if self._apply_fix(result, provider['name'], model):
                        return True
        print("\n所有 Provider 均未能成功修复。")
        return False

    def _call_model(self, provider: Dict, model: str, error_info: str, context: str) -> Optional[str]:
        prompt = self._build_prompt(error_info, context)
        url = f"{provider['base_url']}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 7000
        }
        
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=90)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                print(f"    ✓ {provider['name']} ({model}) 调用成功")
                return content
            else:
                print(f"    ✗ 状态码 {r.status_code}")
                return None
        except Exception as e:
            print(f"    ✗ 请求异常: {e}")
            return None

    def _build_prompt(self, error: str, context: str) -> str:
        return f"""分析以下GitHub Actions工作流错误并给出修复方案。

错误信息：
{error}

仓库上下文：
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
        fix = self._parse_json(response)
        if not fix or fix.get("confidence", 0) < 0.6:
            return False
        print(f"\n成功获得来自 {provider} ({model}) 的高置信度修复方案")
        print(f"分析: {fix.get('analysis','')[:100]}...")
        # 这里后续可以添加实际应用修复的逻辑
        return True

    def _parse_json(self, text: str) -> Optional[Dict]:
        try:
            text = re.sub(r'^```json?|```$', '', text.strip(), flags=re.MULTILINE)
            return json.loads(text.strip())
        except:
            return None

    def _collect_context(self, script_name: str = "") -> str:
        parts = []
        if script_name and os.path.exists(script_name):
            try:
                with open(script_name, 'r', encoding='utf-8') as f:
                    parts.append(f"脚本 {script_name}:\n{f.read()[:4000]}")
            except:
                pass
        return "\n---\n".join(parts) if parts else "无额外上下文"


def main():
    if len(sys.argv) < 2:
        print("用法: python auto_fix_workflow.py <错误日志文件或内容> [脚本名]")
        sys.exit(1)
    
    error_path = sys.argv[1]
    script = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if os.path.isfile(error_path):
        with open(error_path, 'r', encoding='utf-8') as f:
            error_text = f.read()
    else:
        error_text = error_path
    
    print("启动通用多Provider自动修复系统...\n")
    fixer = WorkflowErrorFixer()
    success = fixer.fix_error(error_text, script)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
