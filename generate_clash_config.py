"""
Clash配置生成器 - 从订阅链接生成Clash配置文件
"""
import os
import json
import base64
import requests
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
import re


class ClashConfigGenerator:
    def __init__(self, config_path: str = "/root/.config/mihomo/config.yaml"):
        self.config_path = config_path
        self.proxies = []
        self.proxy_groups = []
        self.rules = []
        
    def fetch_subscription(self, url: str) -> str:
        """获取订阅内容"""
        try:
            headers = {
                'User-Agent': 'ClashForWindows/0.20.39'
            }
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                content = resp.text.strip()
                if content.startswith('http'):
                    return self.fetch_subscription(content)
                try:
                    decoded = base64.b64decode(content).decode('utf-8')
                    return decoded
                except:
                    return content
            return ""
        except Exception as e:
            print(f"获取订阅失败: {e}")
            return ""
    
    def parse_vmess(self, link: str) -> Optional[Dict]:
        """解析vmess链接"""
        try:
            data = json.loads(base64.b64decode(link[8:]).decode('utf-8'))
            proxy = {
                'name': data.get('ps', 'vmess'),
                'type': 'vmess',
                'server': data.get('add'),
                'port': int(data.get('port', 443)),
                'uuid': data.get('id'),
                'alterId': int(data.get('aid', 0)),
                'cipher': data.get('scy', 'auto'),
                'udp': True
            }
            
            net = data.get('net', 'tcp')
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {
                    'path': data.get('path', '/'),
                    'headers': {'Host': data.get('host', proxy['server'])}
                }
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {
                    'grpc-service-name': data.get('path', '')
                }
            
            tls = data.get('tls', '')
            if tls == 'tls':
                proxy['tls'] = True
                sni = data.get('sni') or data.get('host', proxy['server'])
                if sni:
                    proxy['servername'] = sni
            
            return proxy
        except Exception as e:
            print(f"解析vmess失败: {e}")
            return None
    
    def parse_vless(self, link: str) -> Optional[Dict]:
        """解析vless链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            proxy = {
                'name': parsed.fragment or 'vless',
                'type': 'vless',
                'server': parsed.hostname,
                'port': parsed.port,
                'uuid': parsed.username,
                'udp': True
            }
            
            flow = params.get('flow', [None])[0]
            if flow:
                proxy['flow'] = flow
            
            security = params.get('security', [None])[0]
            if security == 'tls':
                proxy['tls'] = True
                sni = params.get('sni', [None])[0]
                if sni:
                    proxy['servername'] = sni
            
            net = params.get('type', ['tcp'])[0]
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {
                    'path': params.get('path', ['/'])[0],
                    'headers': {'Host': params.get('host', [proxy['server']])[0]}
                }
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {
                    'grpc-service-name': params.get('serviceName', [''])[0]
                }
            
            return proxy
        except Exception as e:
            print(f"解析vless失败: {e}")
            return None
    
    def parse_trojan(self, link: str) -> Optional[Dict]:
        """解析trojan链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            proxy = {
                'name': parsed.fragment or 'trojan',
                'type': 'trojan',
                'server': parsed.hostname,
                'port': parsed.port,
                'password': parsed.username,
                'udp': True,
                'skip-cert-verify': False
            }
            
            sni = params.get('sni', [None])[0]
            if sni:
                proxy['sni'] = sni
            
            net = params.get('type', ['tcp'])[0]
            if net == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {
                    'path': params.get('path', ['/'])[0]
                }
            elif net == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {
                    'grpc-service-name': params.get('serviceName', [''])[0]
                }
            
            return proxy
        except Exception as e:
            print(f"解析trojan失败: {e}")
            return None
    
    def parse_ss(self, link: str) -> Optional[Dict]:
        """解析ss链接"""
        try:
            parsed = urlparse(link)
            
            if '@' in link:
                match = re.match(r'ss://([^@]+)@([^:]+):(\d+)(?:#(.+))?', link)
                if match:
                    userinfo = base64.urlsafe_b64decode(match.group(1) + '==').decode('utf-8')
                    cipher, password = userinfo.split(':', 1)
                    return {
                        'name': match.group(4) or 'ss',
                        'type': 'ss',
                        'server': match.group(2),
                        'port': int(match.group(3)),
                        'cipher': cipher,
                        'password': password,
                        'udp': True
                    }
            else:
                decoded = base64.urlsafe_b64decode(parsed.netloc + '==').decode('utf-8')
                if '@' in decoded:
                    userinfo, server_info = decoded.split('@')
                    cipher, password = userinfo.split(':', 1)
                    server, port = server_info.split(':')
                    return {
                        'name': parsed.fragment or 'ss',
                        'type': 'ss',
                        'server': server,
                        'port': int(port),
                        'cipher': cipher,
                        'password': password,
                        'udp': True
                    }
            return None
        except Exception as e:
            print(f"解析ss失败: {e}")
            return None
    
    def parse_ss_r(self, link: str) -> Optional[Dict]:
        """解析ssr链接"""
        try:
            decoded = base64.urlsafe_b64decode(link[6:] + '==').decode('utf-8')
            parts = decoded.split(':')
            if len(parts) >= 6:
                server = parts[0]
                port = int(parts[1])
                protocol = parts[2]
                cipher = parts[3]
                obfs = parts[4]
                password_base64 = parts[5].split('/?')[0]
                password = base64.urlsafe_b64decode(password_base64 + '==').decode('utf-8')
                
                name = 'ssr'
                params_part = decoded.split('/?')
                if len(params_part) > 1:
                    params = parse_qs(params_part[1])
                    name = params.get('remarks', ['ssr'])[0]
                    name = base64.urlsafe_b64decode(name + '==').decode('utf-8')
                
                return {
                    'name': name,
                    'type': 'ssr',
                    'server': server,
                    'port': port,
                    'cipher': cipher,
                    'password': password,
                    'protocol': protocol,
                    'obfs': obfs,
                    'udp': True
                }
        except Exception as e:
            print(f"解析ssr失败: {e}")
        return None
    
    def parse_hysteria(self, link: str) -> Optional[Dict]:
        """解析hysteria链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            return {
                'name': parsed.fragment or 'hysteria',
                'type': 'hysteria',
                'server': parsed.hostname,
                'port': parsed.port,
                'password': parsed.username or params.get('auth', [''])[0],
                'obfs': params.get('obfs', [''])[0] or None,
                'alpn': params.get('alpn', ['h3'])[0],
                'protocol': params.get('protocol', ['udp'])[0],
                'up': params.get('up', [''])[0] or '20 Mbps',
                'down': params.get('down', [''])[0] or '100 Mbps',
                'sni': params.get('sni', [parsed.hostname])[0],
                'skip-cert-verify': params.get('insecure', ['0'])[0] == '1'
            }
        except Exception as e:
            print(f"解析hysteria失败: {e}")
            return None
    
    def parse_hysteria2(self, link: str) -> Optional[Dict]:
        """解析hysteria2链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            proxy = {
                'name': parsed.fragment or 'hysteria2',
                'type': 'hysteria2',
                'server': parsed.hostname,
                'port': parsed.port,
                'password': parsed.username or params.get('auth', [''])[0],
            }
            
            sni = params.get('sni', [None])[0]
            if sni:
                proxy['sni'] = sni
            
            obfs = params.get('obfs', [None])[0]
            if obfs:
                proxy['obfs'] = obfs
                proxy['obfs-password'] = params.get('obfs-password', [''])[0]
            
            return proxy
        except Exception as e:
            print(f"解析hysteria2失败: {e}")
            return None
    
    def parse_tuic(self, link: str) -> Optional[Dict]:
        """解析tuic链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            return {
                'name': parsed.fragment or 'tuic',
                'type': 'tuic',
                'server': parsed.hostname,
                'port': parsed.port,
                'uuid': parsed.username,
                'password': parsed.password,
                'alpn': ['h3'],
                'congestion_control': params.get('congestion_control', ['cubic'])[0],
                'sni': params.get('sni', [parsed.hostname])[0],
                'disable_sni': params.get('disable_sni', ['0'])[0] == '1',
                'reduce_rtt': params.get('reduce_rtt', ['1'])[0] == '1',
                'udp_relay_mode': params.get('udp_relay_mode', ['native'])[0]
            }
        except Exception as e:
            print(f"解析tuic失败: {e}")
            return None
    
    def parse_wireguard(self, link: str) -> Optional[Dict]:
        """解析wireguard链接"""
        try:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)
            
            return {
                'name': parsed.fragment or 'wireguard',
                'type': 'wireguard',
                'server': parsed.hostname,
                'port': parsed.port,
                'private-key': parsed.username,
                'ip': params.get('ip', [''])[0],
                'ipv6': params.get('ipv6', [''])[0],
                'public-key': params.get('publickey', [''])[0],
                'dns': params.get('dns', [''])[0],
                'mtu': int(params.get('mtu', ['1280'])[0]),
                'udp': True
            }
        except Exception as e:
            print(f"解析wireguard失败: {e}")
            return None
    
    def parse_link(self, link: str) -> Optional[Dict]:
        """解析单个链接"""
        link = link.strip()
        if not link:
            return None
        
        if link.startswith('vmess://'):
            return self.parse_vmess(link)
        elif link.startswith('vless://'):
            return self.parse_vless(link)
        elif link.startswith('trojan://'):
            return self.parse_trojan(link)
        elif link.startswith('ss://'):
            return self.parse_ss(link)
        elif link.startswith('ssr://'):
            return self.parse_ss_r(link)
        elif link.startswith('hysteria://'):
            return self.parse_hysteria(link)
        elif link.startswith('hysteria2://') or link.startswith('hy2://'):
            return self.parse_hysteria2(link)
        elif link.startswith('tuic://'):
            return self.parse_tuic(link)
        elif link.startswith('wireguard://'):
            return self.parse_wireguard(link)
        return None
    
    def parse_subscription(self, url: str, exclude_keywords: List[str] = None) -> List[Dict]:
        """解析订阅链接"""
        content = self.fetch_subscription(url)
        if not content:
            return []
        
        proxies = []
        exclude_keywords = exclude_keywords or []
        
        for line in content.strip().split('\n'):
            proxy = self.parse_link(line)
            if proxy:
                name = proxy.get('name', '').lower()
                should_exclude = any(kw.lower() in name for kw in exclude_keywords)
                if not should_exclude:
                    proxies.append(proxy)
        
        return proxies
    
    def generate_config(self, subscriptions: List[str], exclude_keywords: List[str] = None,
                       mixed_port: int = 7890, socks_port: int = 7891,
                       external_controller: str = "127.0.0.1:9090") -> str:
        """生成Clash配置文件"""
        
        all_proxies = []
        for sub in subscriptions:
            proxies = self.parse_subscription(sub, exclude_keywords)
            all_proxies.extend(proxies)
        
        if not all_proxies:
            print("警告: 没有可用代理节点")
            all_proxies = [{'name': 'DIRECT', 'type': 'direct'}]
        
        proxy_names = [p['name'] for p in all_proxies if p['type'] != 'direct']
        
        config = f"""# Clash配置 - 自动生成
# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
# 节点数量: {len(all_proxies)}

mixed-port: {mixed_port}
socks-port: {socks_port}
allow-lan: false
bind-address: "127.0.0.1"
mode: rule
log-level: info
ipv6: false
external-controller: {external_controller}

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-filter:
    - '*.lan'
    - localhost.ptlogin2.qq.com
    - '+.srv.nintendo.net'
    - '+.stun.playstation.net'
    - '+.msftconnecttest.com'
    - '+.msftncsi.com'
    - '+.xboxlive.com'
  nameserver:
    - 223.5.5.5
    - 119.29.29.29
  fallback:
    - tls://8.8.8.8:853
    - tls://1.1.1.1:853
  fallback-filter:
    geoip: true
    geoip-code: CN
    ipcidr:
      - 240.0.0.0/4

proxies:
"""
        
        for proxy in all_proxies:
            config += self._proxy_to_yaml(proxy)
        
        config += f"""
proxy-groups:
  - name: "PROXY"
    type: select
    proxies:
      - AUTO
      - DIRECT
{self._format_proxy_list(proxy_names, 6)}

  - name: "AUTO"
    type: url-test
    proxies:
{self._format_proxy_list(proxy_names, 6)}
    url: 'http://www.gstatic.com/generate_204'
    interval: 300

rules:
  - GEOIP,LAN,DIRECT
  - GEOIP,CN,DIRECT
  - MATCH,PROXY
"""
        
        return config
    
    def _proxy_to_yaml(self, proxy: Dict, indent: int = 2) -> str:
        """将代理配置转为YAML格式"""
        spaces = ' ' * indent
        lines = [f"{spaces}- name: {proxy['name']}"]
        
        for key, value in proxy.items():
            if key == 'name':
                continue
            if isinstance(value, bool):
                lines.append(f"{spaces}  {key}: {str(value).lower()}")
            elif isinstance(value, dict):
                lines.append(f"{spaces}  {key}:")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, dict):
                        lines.append(f"{spaces}    {sub_key}:")
                        for k, v in sub_value.items():
                            lines.append(f"{spaces}      {k}: {v}")
                    else:
                        lines.append(f"{spaces}    {sub_key}: {sub_value}")
            elif isinstance(value, list):
                lines.append(f"{spaces}  {key}:")
                for item in value:
                    lines.append(f"{spaces}    - {item}")
            else:
                lines.append(f"{spaces}  {key}: {value}")
        
        return '\n'.join(lines) + '\n'
    
    def _format_proxy_list(self, names: List[str], indent: int = 6) -> str:
        """格式化代理列表"""
        spaces = ' ' * indent
        return '\n'.join([f"{spaces}- {name}" for name in names])
    
    def save_config(self, config: str, path: str = None):
        """保存配置文件"""
        path = path or self.config_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(config)
        print(f"配置已保存到: {path}")
    
    def generate_and_save(self, subscriptions: List[str], exclude_keywords: List[str] = None,
                         output_path: str = None) -> bool:
        """生成并保存配置"""
        config = self.generate_config(subscriptions, exclude_keywords)
        self.save_config(config, output_path)
        return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Clash配置生成器')
    parser.add_argument('--subs', nargs='+', required=True, help='订阅URL列表')
    parser.add_argument('--exclude', nargs='*', default=[], help='排除关键字')
    parser.add_argument('--output', default='/root/.config/mihomo/config.yaml', help='输出路径')
    parser.add_argument('--mixed-port', type=int, default=7890, help='混合端口')
    parser.add_argument('--socks-port', type=int, default=7891, help='SOCKS端口')
    
    args = parser.parse_args()
    
    generator = ClashConfigGenerator()
    generator.generate_and_save(
        subscriptions=args.subs,
        exclude_keywords=args.exclude,
        output_path=args.output
    )
