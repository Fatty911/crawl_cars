#!/usr/bin/env python3
"""
带代理支持的爬虫启动脚本
"""
import os
import sys
import time
import argparse
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='带代理的爬虫启动器')
    parser.add_argument('--time-limit', type=int, default=7200, help='运行时间限制(秒)')
    parser.add_argument('--max-cars', type=int, default=500, help='最大车型数')
    parser.add_argument('--proxy', type=str, default=None, 
                       help='代理策略: off/random/round_robin/least_used/best_performance')
    parser.add_argument('--skip-autohome', action='store_true', help='跳过汽车之家')
    parser.add_argument('--skip-dongchedi', action='store_true', help='跳过懂车帝')
    args = parser.parse_args()

    print(f"=== 开始运行 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"时间限制: {args.time_limit}秒, 最大车型: {args.max_cars}")

    if args.proxy:
        try:
            from proxy_manager import ProxyManager
            pm = ProxyManager()
            print(f"代理模式: {args.proxy}, 可用节点: {len(pm.proxies)}")
        except ImportError:
            print("警告: 未安装代理管理器, 禁用代理")
            args.proxy = None

    # 运行汽车之家
    if not args.skip_autohome:
        print("\n--- 汽车之家 ---")
        cmd = f"python3 test_autohome.py --step 1 --auto --time-limit {args.time_limit} --max-cars {args.max_cars}"
        if args.proxy:
            cmd += f" --proxy {args.proxy}"
        
        exit_code = os.system(cmd)
        
        if exit_code == 10 * 256:  # Python exit code 10
            print("汽车之家未完成,等待下次运行")
            return 10
        elif exit_code == 0:
            print("汽车之家第一步完成,运行后续步骤...")
            for step in [2, 3, 4, 5, 6]:
                os.system(f"python3 test_autohome.py --step {step}")

    # 运行懂车帝
    if not args.skip_dongchedi:
        print("\n--- 懂车帝 ---")
        cmd = f"python3 crawl_dongchedi.py --step 2 --auto --time-limit {args.time_limit} --max-series {args.max_cars}"
        
        exit_code = os.system(cmd)
        
        if exit_code == 10 * 256:
            print("懂车帝未完成,等待下次运行")
            return 10
        elif exit_code == 0:
            print("懂车帝第二步完成,运行后续步骤...")
            for step in [3, 4]:
                os.system(f"python3 crawl_dongchedi.py --step {step}")

    # 合并数据
    autohome_files = [f for f in os.listdir('.') if f.startswith('autoHome_') and f.endswith('.json')]
    dongchedi_files = [f for f in os.listdir('.') if f.startswith('dongchedi_') and f.endswith('.json')]
    
    if autohome_files and dongchedi_files:
        print("\n--- 合并数据 ---")
        os.system("python3 merge_data.py")

    print(f"\n=== 运行结束 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    return 0

if __name__ == '__main__':
    sys.exit(main())
