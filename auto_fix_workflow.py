"""
工作流错误自动修复脚本
依次尝试: Minimax m2.7 -> Zen MiMo v2 pro free -> Grok 4.2 beta reasoning
"""
import os
import sys
import json
import subprocess
import requests
from typing import Optional, Dict, Any


class WorkflowErrorFixer:
    def __init__(self):
        self.models = [
            # OpenRouter - 调用排行榜前10且 context window ≥ 1M 模型
            {
                "name": "OpenRouter Top Models",
                "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
                "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "models": [
                    "google/gemini-3.1-pro-preview",
                    "openai/gpt-5.4",
                    "anthropic/claude-opus-4.6",
                    "anthropic/claude-sonnet-4.6",
                    "z-ai/glm-5",
                    "minimax/minimax-m2.7",
                    "xai/grok-4.20-beta-0309",
                    "openai/gpt-5.4-mini",
                    "kimi/kimi-k2.5"
                ],
                "format": "openai"
            },
            {
                "name": "Minimax m2.7",
                "api_key": os.environ.get("MINIMAX_API_KEY", ""),
                "endpoint": "https://api.minimax.io/v1/chat/completions",
                "model": "m2.7",
                "format": "openai"
            },
            {
                "name": "Zen MiMo v2 pro free",
                "api_key": os.environ.get("ZEN_API_KEY", ""),
                "endpoint": "https://opencode.ai/zen/v1/chat/completions",
                "model": "mimo-v2-pro-free",
                "format": "openai"
            },
            {
                "name": "xAI Grok 4.2",
                "api_key": os.environ.get("XAI_API_KEY", ""),
                "endpoint": "https://api.x.ai/v1/chat/completions",
                "model": "grok-4.2-beta-0309-reasoning",
                "format": "openai"
            }
        ]
    
    def call_model(self, model_config: Dict, error_info: str, repo_context: str) -> Optional[str]:
        """调用大模型分析错误并生成修复方案"""
        if not model_config.get("api_key"):
            print(f"跳过 {model_config['name']}: API key 未配置")
            return None

        # OpenRouter 多模型尝试
        if model_config["name"] == "OpenRouter Top Models":
            for model_name in model_config["models"]:
                print(f"\n尝试使用 OpenRouter - {model_name} 分析错误...")
                if self._call_openrouter(model_config, model_name, error_info, repo_context):
                    return self._call_openrouter(model_config, model_name, error_info, repo_context)
            return None

        # 其他单模型
        prompt = self._build_prompt(error_info, repo_context)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config['api_key']}"
        }
        if model_config.get("headers"):
            headers.update(model_config["headers"])

        payload = {
            "model": model_config.get("model", model_config.get("models", [None])[0]),
            "messages": [
                {"role": "system", "content": "你是专业的代码调试助手，擅长分析和修复 Python 代码和 GitHub Actions 工作流错误。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                model_config["endpoint"],
                headers=headers,
                json=payload,
                timeout=180
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"{model_config['name']} 返回结果成功")
                return content
            else:
                print(f"{model_config['name']} 请求失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"{model_config['name']} 调用异常: {e}")
            return None

    def _call_openrouter(self, config: Dict, model: str, error_info: str, repo_context: str) -> Optional[str]:
        """调用 OpenRouter 单个模型"""
        prompt = self._build_prompt(error_info, repo_context)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
            "HTTP-Referer": "https://github.com/Fatty911/crawl_cars",
            "X-Title": "CrawlCars Auto Fix"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是专业的代码调试助手，擅长分析和修复 Python 代码和 GitHub Actions 工作流错误。" },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 8000
        }
        
        try:
            response = requests.post(
                config["endpoint"],
                headers=headers,
                json=payload,
                timeout=180
            )
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"OpenRouter - {model} 返回成功")
                return content
            else:
                print(f"OpenRouter - {model} 失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"OpenRouter - {model} 异常: {e}")
            return None

    def _build_prompt(self, error_info: str, repo_context: str) -> str:
        return f"""你是一个专业的 Python/GitHub Actions 调试专家。请分析以下工作流错误并提供修复方案。

## 错误信息
{error_info}

## 仓库上下文
{repo_context}

## 要求
1. 分析错误原因
2. 提供具体的修复代码（如果需要修改文件）
3. 提供要执行的 shell 命令（如果需要）
4. 如果是爬虫被反爬或网络问题，建议如何处理

请以 JSON 格式回复：
{{
    "analysis": "错误分析",
    "fix_type": "code" | "command" | "config" | "skip",
    "fix_content": "具体的修复代码或命令",
    "files_to_modify": [{{"path": "文件路径", "content": "新内容"}}],
    "commands": ["要执行的命令"],
    "confidence": 0.0-1.0,
    "reasoning": "为什么这个修复方案有效"
}}

只返回 JSON，不要其他内容。"""
    
    def parse_fix_response(self, response: str) -> Optional[Dict]:
        """解析模型返回的修复方案"""
        try:
            # 尝试提取 JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return None
    
    def apply_fix(self, fix: Dict) -> bool:
        """应用修复方案"""
        fix_type = fix.get("fix_type", "")
        
        if fix_type == "skip":
            print(f"跳过修复: {fix.get('reasoning', '')}")
            return True
        
        if fix_type == "code":
            files = fix.get("files_to_modify", [])
            for file_info in files:
                path = file_info.get("path", "")
                content = file_info.get("content", "")
                if path and content:
                    try:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"已修改文件: {path}")
                    except Exception as e:
                        print(f"修改文件失败 {path}: {e}")
                        return False
        
        if fix_type in ["code", "command", "config"]:
            commands = fix.get("commands", [])
            for cmd in commands:
                print(f"执行命令: {cmd}")
                try:
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=300
                    )
                    if result.returncode != 0:
                        print(f"命令执行失败: {result.stderr}")
                        return False
                    print(f"命令输出: {result.stdout[:500]}")
                except Exception as e:
                    print(f"命令执行异常: {e}")
                    return False
        
        return True
    
    def commit_and_push(self, message: str) -> bool:
        """提交修复并推送"""
        commands = [
            'git config --local user.email "github-actions[bot]@users.noreply.github.com"',
            'git config --local user.name "github-actions[bot]"',
            'git add -A',
            'git diff --staged --quiet || git commit -m "fix: ' + message.replace('"', '\\"') + '"',
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0 and "nothing to commit" not in result.stderr:
                print(f"Git 命令失败: {result.stderr}")
                return False
        
        # Push
        repo_url = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("ACTION_PAT", "")
        if repo_url and token:
            push_cmd = f'git push https://x-access-token:{token}@github.com/{repo_url}.git'
            result = subprocess.run(push_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("推送成功")
                return True
            else:
                print(f"推送失败: {result.stderr}")
                return False
        return False
    
    def fix_error(self, error_output: str, script_name: str = "") -> bool:
        """主函数：分析并修复错误"""
        # 收集上下文信息
        repo_context = self.collect_context(script_name)
        
        # 依次尝试每个模型
        for model_config in self.models:
            response = self.call_model(model_config, error_output, repo_context)
            if not response:
                continue
            
            fix = self.parse_fix_response(response)
            if not fix:
                continue
            
            confidence = fix.get("confidence", 0)
            print(f"\n{model_config['name']} 分析结果:")
            print(f"分析: {fix.get('analysis', 'N/A')}")
            print(f"置信度: {confidence}")
            print(f"推理: {fix.get('reasoning', 'N/A')}")
            
            if confidence >= 0.7:
                print(f"\n使用 {model_config['name']} 的修复方案...")
                if self.apply_fix(fix):
                    self.commit_and_push(f"Auto-fix by {model_config['name']}: {fix.get('analysis', '')[:100]}")
                    return True
            else:
                print(f"置信度过低 ({confidence})，尝试下一个模型...")
        
        print("\n所有模型都无法提供高置信度的修复方案")
        return False
    
    def collect_context(self, script_name: str) -> str:
        """收集仓库上下文"""
        context_parts = []
        
        # 收集脚本内容
        if script_name and os.path.exists(script_name):
            try:
                with open(script_name, "r", encoding="utf-8") as f:
                    content = f.read()
                    context_parts.append(f"## 脚本 {script_name} 内容\n{content[:5000]}")
            except Exception:
                pass
        
        # 收集进度文件
        progress_files = ["progress.json", "dongchedi/progress.json"]
        for pf in progress_files:
            if os.path.exists(pf):
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        content = f.read()
                        context_parts.append(f"## 进度文件 {pf}\n{content[:2000]}")
                except Exception:
                    pass
        
        # 收集 requirements.txt
        if os.path.exists("requirements.txt"):
            with open("requirements.txt", "r") as f:
                context_parts.append(f"## 依赖\n{f.read()}")
        
        return "\n\n".join(context_parts)


def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_fix_workflow.py <error_log_file_or_string> [script_name]")
        sys.exit(1)
    
    error_input = sys.argv[1]
    script_name = sys.argv[2] if len(sys.argv) > 2 else ""
    
    # 读取错误信息
    if os.path.exists(error_input):
        with open(error_input, "r", encoding="utf-8") as f:
            error_output = f.read()
    else:
        error_output = error_input
    
    fixer = WorkflowErrorFixer()
    success = fixer.fix_error(error_output, script_name)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
