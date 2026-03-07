"""
代理管理器 - 支持机场订阅解析和负载均衡
"""
import os
import json
import base64
import random
import time
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs


class ProxyManager:
    def __init__(self, config_file: str = "proxies.json"):
        self.config_file = config_file
        self.proxies: List[Dict] = []
        self.proxy_stats: Dict[str, Dict] = {}
        self.current_index = 0
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.proxies = config.get('proxies', [])
                self.proxy_stats = config.get('stats', {})

    def save_config(self):
        config = {
            'proxies': self.proxies,
            'stats': self.proxy_stats
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def add_http_proxy(self, name: str, host: str, port: int, 
                       username: str = None, password: str = None):
        proxy = {
            'name': name,
            'type': 'http',
            'host': host,
            'port': port,
            'username': username,
            'password': password
        }
        self.proxies.append(proxy)
        self.proxy_stats[name] = {'success': 0, 'fail': 0, 'last_used': 0}
        self.save_config()

    def add_socks5_proxy(self, name: str, host: str, port: int,
                         username: str = None, password: str = None):
        proxy = {
            'name': name,
            'type': 'socks5',
            'host': host,
            'port': port,
            'username': username,
            'password': password
        }
        self.proxies.append(proxy)
        self.proxy_stats[name] = {'success': 0, 'fail': 0, 'last_used': 0}
        self.save_config()

    def parse_clash_config(self, config_text: str) -> List[Dict]:
        import yaml
        try:
            config = yaml.safe_load(config_text)
            proxies = []
            for p in config.get('proxies', []):
                proxy = {
                    'name': p.get('name', 'unnamed'),
                    'type': p.get('type'),
                    'host': p.get('server'),
                    'port': p.get('port'),
                }
                if p.get('type') == 'ss':
                    proxy.update({
                        'cipher': p.get('cipher'),
                        'password': p.get('password'),
                    })
                elif p.get('type') == 'vmess':
                    proxy.update({
                        'uuid': p.get('uuid'),
                        'alterId': p.get('alterId', 0),
                        'cipher': p.get('cipher', 'auto'),
                    })
                elif p.get('type') == 'trojan':
                    proxy.update({
                        'password': p.get('password'),
                    })
                elif p.get('type') == 'socks5':
                    proxy.update({
                        'username': p.get('username'),
                        'password': p.get('password'),
                    })
                
                if proxy['host'] and proxy['port']:
                    proxies.append(proxy)
                    self.proxy_stats[proxy['name']] = {'success': 0, 'fail': 0, 'last_used': 0}
            
            self.proxies.extend(proxies)
            self.save_config()
            return proxies
        except Exception as e:
            print(f"解析Clash配置失败: {e}")
            return []

    def parse_v2ray_subscription(self, subscription_url: str) -> List[Dict]:
        try:
            resp = requests.get(subscription_url, timeout=30)
            if resp.status_code != 200:
                print(f"获取订阅失败: {resp.status_code}")
                return []
            
            content = base64.b64decode(resp.text).decode('utf-8')
            proxies = []
            
            for line in content.strip().split('\n'):
                line = line.strip()
                if line.startswith('vmess://'):
                    try:
                        vmess_data = json.loads(base64.b64decode(line[8:]).decode('utf-8'))
                        proxy = {
                            'name': vmess_data.get('ps', 'vmess'),
                            'type': 'vmess',
                            'host': vmess_data.get('add'),
                            'port': int(vmess_data.get('port', 443)),
                            'uuid': vmess_data.get('id'),
                            'alterId': int(vmess_data.get('aid', 0)),
                            'cipher': vmess_data.get('scy', 'auto'),
                            'network': vmess_data.get('net', 'tcp'),
                            'tls': vmess_data.get('tls', '') == 'tls',
                        }
                        proxies.append(proxy)
                        self.proxy_stats[proxy['name']] = {'success': 0, 'fail': 0, 'last_used': 0}
                    except Exception as e:
                        print(f"解析vmess链接失败: {e}")
                
                elif line.startswith('ss://'):
                    try:
                        import re
                        match = re.match(r'ss://([^@]+)@([^:]+):(\d+)(?:#(.+))?', line)
                        if match:
                            userinfo = base64.b64decode(match.group(1)).decode('utf-8')
                            cipher, password = userinfo.split(':', 1)
                            proxy = {
                                'name': match.group(4) or 'ss',
                                'type': 'ss',
                                'host': match.group(2),
                                'port': int(match.group(3)),
                                'cipher': cipher,
                                'password': password,
                            }
                            proxies.append(proxy)
                            self.proxy_stats[proxy['name']] = {'success': 0, 'fail': 0, 'last_used': 0}
                    except Exception as e:
                        print(f"解析ss链接失败: {e}")
                
                elif line.startswith('trojan://'):
                    try:
                        parsed = urlparse(line)
                        proxy = {
                            'name': parsed.fragment or 'trojan',
                            'type': 'trojan',
                            'host': parsed.hostname,
                            'port': parsed.port,
                            'password': parsed.username,
                        }
                        proxies.append(proxy)
                        self.proxy_stats[proxy['name']] = {'success': 0, 'fail': 0, 'last_used': 0}
                    except Exception as e:
                        print(f"解析trojan链接失败: {e}")
            
            self.proxies.extend(proxies)
            self.save_config()
            return proxies
        except Exception as e:
            print(f"解析订阅失败: {e}")
            return []

    def get_proxy(self, strategy: str = 'round_robin') -> Optional[Dict]:
        if not self.proxies:
            return None
        
        if strategy == 'random':
            return random.choice(self.proxies)
        
        elif strategy == 'round_robin':
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy
        
        elif strategy == 'least_used':
            min_use = float('inf')
            selected = None
            for p in self.proxies:
                stats = self.proxy_stats.get(p['name'], {})
                use_count = stats.get('success', 0) + stats.get('fail', 0)
                if use_count < min_use:
                    min_use = use_count
                    selected = p
            return selected
        
        elif strategy == 'best_performance':
            best_score = -1
            selected = None
            for p in self.proxies:
                stats = self.proxy_stats.get(p['name'], {})
                success = stats.get('success', 0)
                fail = stats.get('fail', 0)
                total = success + fail
                if total > 0:
                    score = success / total
                else:
                    score = 0.5
                if score > best_score:
                    best_score = score
                    selected = p
            return selected or self.proxies[0]
        
        return self.proxies[0]

    def report_success(self, proxy_name: str):
        if proxy_name in self.proxy_stats:
            self.proxy_stats[proxy_name]['success'] += 1
            self.proxy_stats[proxy_name]['last_used'] = time.time()
            self.save_config()

    def report_failure(self, proxy_name: str):
        if proxy_name in self.proxy_stats:
            self.proxy_stats[proxy_name]['fail'] += 1
            self.save_config()

    def get_requests_proxies(self, proxy: Dict) -> Dict[str, str]:
        if not proxy:
            return {}
        
        if proxy.get('username') and proxy.get('password'):
            auth = f"{proxy['username']}:{proxy['password']}@{proxy['host']}:{proxy['port']}"
        else:
            auth = f"{proxy['host']}:{proxy['port']}"
        
        if proxy['type'] == 'http':
            return {'http': f'http://{auth}', 'https': f'http://{auth}'}
        elif proxy['type'] == 'socks5':
            return {'http': f'socks5://{auth}', 'https': f'socks5://{auth}'}
        else:
            print(f"注意: {proxy['type']} 类型代理需要本地客户端转换，请确保本地有监听端口")
            return {}

    def list_proxies(self) -> str:
        result = []
        for p in self.proxies:
            stats = self.proxy_stats.get(p['name'], {})
            success = stats.get('success', 0)
            fail = stats.get('fail', 0)
            total = success + fail
            rate = f"{success}/{total}" if total > 0 else "N/A"
            result.append(f"  {p['name']}: {p['type']} {p['host']}:{p['port']} [{rate}]")
        return "\n".join(result)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='代理管理工具')
    parser.add_argument('--add-http', nargs=4, metavar=('NAME', 'HOST', 'PORT', 'USER:PASS'), help='添加HTTP代理')
    parser.add_argument('--add-socks5', nargs=4, metavar=('NAME', 'HOST', 'PORT', 'USER:PASS'), help='添加SOCKS5代理')
    parser.add_argument('--sub', type=str, help='解析V2Ray订阅链接')
    parser.add_argument('--clash', type=str, help='解析Clash配置文件路径')
    parser.add_argument('--list', action='store_true', help='列出所有代理')
    parser.add_argument('--test', action='store_true', help='测试代理可用性')
    args = parser.parse_args()

    pm = ProxyManager()

    if args.add_http:
        name, host, port = args.add_http[:3]
        auth = args.add_http[3].split(':') if len(args.add_http) > 3 else None
        pm.add_http_proxy(name, host, int(port), auth[0] if auth else None, auth[1] if auth else None)
        print(f"已添加HTTP代理: {name}")

    elif args.add_socks5:
        name, host, port = args.add_http[:3]
        auth = args.add_socks5[3].split(':') if len(args.add_socks5) > 3 else None
        pm.add_socks5_proxy(name, host, int(port), auth[0] if auth else None, auth[1] if auth else None)
        print(f"已添加SOCKS5代理: {name}")

    elif args.sub:
        proxies = pm.parse_v2ray_subscription(args.sub)
        print(f"从订阅解析出 {len(proxies)} 个节点")

    elif args.clash:
        with open(args.clash, 'r', encoding='utf-8') as f:
            proxies = pm.parse_clash_config(f.read())
        print(f"从Clash配置解析出 {len(proxies)} 个节点")

    elif args.list:
        print(f"共 {len(pm.proxies)} 个代理:")
        print(pm.list_proxies())

    elif args.test:
        print("测试代理可用性...")
        for p in pm.proxies[:5]:
            print(f"测试 {p['name']}...")
            proxies = pm.get_requests_proxies(p)
            if proxies:
                try:
                    resp = requests.get('https://httpbin.org/ip', proxies=proxies, timeout=10)
                    if resp.status_code == 200:
                        print(f"  ✓ 成功: {resp.json()}")
                        pm.report_success(p['name'])
                    else:
                        print(f"  ✗ 失败: {resp.status_code}")
                        pm.report_failure(p['name'])
                except Exception as e:
                    print(f"  ✗ 异常: {e}")
                    pm.report_failure(p['name'])
            else:
                print(f"  - 跳过: 需要 {p['type']} 本地客户端")

    else:
        parser.print_help()
