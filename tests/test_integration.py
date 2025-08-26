#!/usr/bin/env python3
"""
系统集成测试脚本
验证整个AI内容安全监控系统的端到端功能
"""

import asyncio
import aiohttp
import json
import time
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestStep:
    """测试步骤"""
    name: str
    description: str
    passed: bool = False
    error_message: Optional[str] = None
    duration: float = 0.0


class IntegrationTester:
    """集成测试器"""
    
    def __init__(
        self, 
        backend_url: str = "http://localhost:8000",
        frontend_url: str = "http://localhost:3000"
    ):
        self.backend_url = backend_url.rstrip('/')
        self.frontend_url = frontend_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
        self.test_steps: List[TestStep] = []
        self.test_user = {
            "username": f"testuser_{int(time.time())}",
            "password": "testpass123",
            "email": f"test_{int(time.time())}@example.com"
        }
        self.created_task_id: Optional[str] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def add_test_step(self, name: str, description: str) -> TestStep:
        """添加测试步骤"""
        step = TestStep(name=name, description=description)
        self.test_steps.append(step)
        return step
    
    async def request(
        self, 
        method: str, 
        url: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """发送HTTP请求"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.auth_token:
            request_headers["Authorization"] = f"Bearer {self.auth_token}"
        
        if headers:
            request_headers.update(headers)
        
        try:
            async with self.session.request(
                method,
                url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()
                
                return {
                    "status_code": response.status,
                    "data": response_data,
                    "success": 200 <= response.status < 300
                }
        except Exception as e:
            return {
                "status_code": 0,
                "data": None,
                "success": False,
                "error": str(e)
            }
    
    async def test_backend_health(self) -> bool:
        """测试后端健康检查"""
        step = self.add_test_step("backend_health", "测试后端服务健康检查")
        start_time = time.time()
        
        try:
            response = await self.request("GET", f"{self.backend_url}/health")
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 后端健康检查通过")
                return True
            else:
                step.error_message = f"健康检查失败: {response['status_code']}"
                print(f"❌ 后端健康检查失败: {response['status_code']}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 后端健康检查异常: {e}")
            return False
    
    async def test_frontend_access(self) -> bool:
        """测试前端访问"""
        step = self.add_test_step("frontend_access", "测试前端页面访问")
        start_time = time.time()
        
        try:
            response = await self.request("GET", self.frontend_url, headers={"Accept": "text/html"})
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 前端页面访问正常")
                return True
            else:
                step.error_message = f"前端访问失败: {response['status_code']}"
                print(f"❌ 前端页面访问失败: {response['status_code']}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 前端页面访问异常: {e}")
            return False
    
    async def test_user_registration(self) -> bool:
        """测试用户注册"""
        step = self.add_test_step("user_registration", "测试用户注册功能")
        start_time = time.time()
        
        try:
            response = await self.request(
                "POST",
                f"{self.backend_url}/api/v1/auth/register",
                data=self.test_user
            )
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 用户注册成功: {self.test_user['username']}")
                return True
            else:
                step.error_message = f"注册失败: {response.get('data', {}).get('detail', '未知错误')}"
                print(f"❌ 用户注册失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 用户注册异常: {e}")
            return False
    
    async def test_user_login(self) -> bool:
        """测试用户登录"""
        step = self.add_test_step("user_login", "测试用户登录功能")
        start_time = time.time()
        
        try:
            response = await self.request(
                "POST",
                f"{self.backend_url}/api/v1/auth/login",
                data={
                    "username": self.test_user["username"],
                    "password": self.test_user["password"]
                }
            )
            step.duration = time.time() - start_time
            
            if response["success"] and isinstance(response["data"], dict):
                token_data = response["data"].get("data", {})
                self.auth_token = token_data.get("access_token")
                
                if self.auth_token:
                    step.passed = True
                    print(f"✅ 用户登录成功，获取到token")
                    return True
                else:
                    step.error_message = "登录成功但未获取到token"
                    print(f"❌ {step.error_message}")
                    return False
            else:
                step.error_message = f"登录失败: {response.get('data', {}).get('detail', '未知错误')}"
                print(f"❌ 用户登录失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 用户登录异常: {e}")
            return False
    
    async def test_get_user_profile(self) -> bool:
        """测试获取用户信息"""
        step = self.add_test_step("get_user_profile", "测试获取用户信息")
        start_time = time.time()
        
        try:
            response = await self.request("GET", f"{self.backend_url}/api/v1/auth/me")
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 获取用户信息成功")
                return True
            else:
                step.error_message = f"获取用户信息失败: {response['status_code']}"
                print(f"❌ 获取用户信息失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 获取用户信息异常: {e}")
            return False
    
    async def test_create_scan_task(self) -> bool:
        """测试创建扫描任务"""
        step = self.add_test_step("create_scan_task", "测试创建扫描任务")
        start_time = time.time()
        
        try:
            task_data = {
                "target_domain": "example.com",
                "config": {
                    "max_depth": 2,
                    "max_pages_per_domain": 5
                }
            }
            
            response = await self.request(
                "POST",
                f"{self.backend_url}/api/v1/tasks",
                data=task_data
            )
            step.duration = time.time() - start_time
            
            if response["success"] and isinstance(response["data"], dict):
                self.created_task_id = response["data"].get("task_id")
                
                if self.created_task_id:
                    step.passed = True
                    print(f"✅ 创建扫描任务成功: {self.created_task_id}")
                    return True
                else:
                    step.error_message = "任务创建成功但未获取到task_id"
                    print(f"❌ {step.error_message}")
                    return False
            else:
                step.error_message = f"创建任务失败: {response.get('data', {}).get('detail', '未知错误')}"
                print(f"❌ 创建扫描任务失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 创建扫描任务异常: {e}")
            return False
    
    async def test_get_task_list(self) -> bool:
        """测试获取任务列表"""
        step = self.add_test_step("get_task_list", "测试获取任务列表")
        start_time = time.time()
        
        try:
            response = await self.request("GET", f"{self.backend_url}/api/v1/tasks")
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 获取任务列表成功")
                return True
            else:
                step.error_message = f"获取任务列表失败: {response['status_code']}"
                print(f"❌ 获取任务列表失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 获取任务列表异常: {e}")
            return False
    
    async def test_get_task_detail(self) -> bool:
        """测试获取任务详情"""
        if not self.created_task_id:
            print("⚠️ 跳过任务详情测试（无可用任务ID）")
            return True
        
        step = self.add_test_step("get_task_detail", "测试获取任务详情")
        start_time = time.time()
        
        try:
            response = await self.request(
                "GET", 
                f"{self.backend_url}/api/v1/tasks/{self.created_task_id}"
            )
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 获取任务详情成功")
                return True
            else:
                step.error_message = f"获取任务详情失败: {response['status_code']}"
                print(f"❌ 获取任务详情失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 获取任务详情异常: {e}")
            return False
    
    async def test_websocket_connection(self) -> bool:
        """测试WebSocket连接"""
        if not self.auth_token:
            print("⚠️ 跳过WebSocket测试（无认证token）")
            return True
        
        step = self.add_test_step("websocket_connection", "测试WebSocket连接")
        start_time = time.time()
        
        try:
            ws_url = f"ws://localhost:8000/api/v1/monitor/ws?token={self.auth_token}"
            
            async with self.session.ws_connect(ws_url) as ws:
                # 发送ping消息
                await ws.send_str(json.dumps({"type": "ping"}))
                
                # 等待响应
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "pong":
                            step.duration = time.time() - start_time
                            step.passed = True
                            print(f"✅ WebSocket连接测试成功")
                            return True
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        break
                    
                    # 超时检查
                    if time.time() - start_time > 10:
                        break
            
            step.duration = time.time() - start_time
            step.error_message = "WebSocket连接超时或无响应"
            print(f"❌ WebSocket连接测试失败: {step.error_message}")
            return False
            
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ WebSocket连接测试异常: {e}")
            return False
    
    async def test_system_config(self) -> bool:
        """测试系统配置接口"""
        step = self.add_test_step("system_config", "测试系统配置接口")
        start_time = time.time()
        
        try:
            response = await self.request("GET", f"{self.backend_url}/api/v1/config/system")
            step.duration = time.time() - start_time
            
            if response["success"]:
                step.passed = True
                print(f"✅ 系统配置接口测试成功")
                return True
            else:
                step.error_message = f"系统配置接口失败: {response['status_code']}"
                print(f"❌ 系统配置接口测试失败: {step.error_message}")
                return False
                
        except Exception as e:
            step.duration = time.time() - start_time
            step.error_message = str(e)
            print(f"❌ 系统配置接口测试异常: {e}")
            return False
    
    async def cleanup_test_data(self):
        """清理测试数据"""
        print("\n🧹 清理测试数据...")
        
        # 取消创建的任务
        if self.created_task_id:
            try:
                await self.request(
                    "POST",
                    f"{self.backend_url}/api/v1/tasks/{self.created_task_id}/cancel"
                )
                print(f"✅ 已取消测试任务: {self.created_task_id}")
            except Exception as e:
                print(f"⚠️ 取消测试任务失败: {e}")
    
    def print_test_summary(self):
        """打印测试汇总"""
        print("\n" + "="*60)
        print("📊 集成测试结果汇总")
        print("="*60)
        
        total_tests = len(self.test_steps)
        passed_tests = sum(1 for step in self.test_steps if step.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"通过率: {passed_tests/total_tests*100:.1f}%")
        
        print("\n📋 详细结果:")
        print("-"*60)
        
        for step in self.test_steps:
            status_icon = "✅" if step.passed else "❌"
            print(f"{status_icon} {step.name:25} {step.description:30} "
                  f"({step.duration:.3f}s)")
            
            if not step.passed and step.error_message:
                print(f"    错误: {step.error_message}")
        
        return passed_tests == total_tests


async def main():
    """主函数"""
    print("🚀 开始系统集成测试")
    print(f"🕐 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    async with IntegrationTester() as tester:
        # 测试步骤
        tests = [
            tester.test_backend_health,
            tester.test_frontend_access,
            tester.test_user_registration,
            tester.test_user_login,
            tester.test_get_user_profile,
            tester.test_create_scan_task,
            tester.test_get_task_list,
            tester.test_get_task_detail,
            tester.test_websocket_connection,
            tester.test_system_config,
        ]
        
        # 执行测试
        for test_func in tests:
            print(f"\n🔍 执行测试: {test_func.__name__}")
            try:
                await test_func()
            except Exception as e:
                print(f"❌ 测试执行异常: {e}")
            
            # 短暂延迟
            await asyncio.sleep(0.5)
        
        # 清理测试数据
        await tester.cleanup_test_data()
        
        # 打印测试汇总
        success = tester.print_test_summary()
        
        if success:
            print("\n🎉 所有集成测试通过！系统部署成功！")
            sys.exit(0)
        else:
            print("\n❌ 部分测试失败，请检查系统配置")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())