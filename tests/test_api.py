#!/usr/bin/env python3
"""
API接口测试脚本
用于测试域名合规扫描系统的各个API接口
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestResult:
    """测试结果"""
    endpoint: str
    method: str
    status_code: int
    success: bool
    response_data: Any
    error_message: Optional[str] = None
    duration: float = 0.0


class APITester:
    """API测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_token: Optional[str] = None
        self.test_results: List[TestResult] = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> TestResult:
        """发送HTTP请求"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        url = f"{self.base_url}{endpoint}"
        
        # 设置默认headers
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 添加认证token
        if self.auth_token:
            request_headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # 合并自定义headers
        if headers:
            request_headers.update(headers)
        
        start_time = time.time()
        
        try:
            async with self.session.request(
                method,
                url,
                json=data,
                params=params,
                headers=request_headers
            ) as response:
                duration = time.time() - start_time
                
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()
                
                result = TestResult(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status,
                    success=200 <= response.status < 300,
                    response_data=response_data,
                    duration=duration
                )
                
                self.test_results.append(result)
                return result
                
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                success=False,
                response_data=None,
                error_message=str(e),
                duration=duration
            )
            
            self.test_results.append(result)
            return result
    
    async def login(self, username: str = "admin", password: str = "admin123") -> bool:
        """登录获取认证token"""
        print(f"🔐 正在登录用户: {username}")
        
        result = await self.request(
            "POST",
            "/api/v1/auth/login",
            data={
                "username": username,
                "password": password
            }
        )
        
        if result.success and isinstance(result.response_data, dict):
            token_data = result.response_data.get("data", {})
            self.auth_token = token_data.get("access_token")
            if self.auth_token:
                print(f"✅ 登录成功")
                return True
        
        print(f"❌ 登录失败: {result.response_data}")
        return False
    
    async def test_auth_endpoints(self):
        """测试认证相关接口"""
        print("\n📋 测试认证接口...")
        
        # 测试注册
        await self.request(
            "POST",
            "/api/v1/auth/register",
            data={
                "username": f"testuser_{int(time.time())}",
                "password": "testpass123",
                "email": f"test_{int(time.time())}@example.com"
            }
        )
        
        # 测试登录
        await self.login()
        
        # 测试获取当前用户信息
        await self.request("GET", "/api/v1/auth/me")
        
        # 测试刷新token
        await self.request("POST", "/api/v1/auth/refresh")
    
    async def test_task_endpoints(self):
        """测试任务相关接口"""
        print("\n📋 测试任务接口...")
        
        if not self.auth_token:
            print("❌ 需要先登录")
            return
        
        # 创建测试任务
        create_result = await self.request(
            "POST",
            "/api/v1/tasks",
            data={
                "target_domain": "example.com",
                "config": {
                    "max_depth": 2,
                    "max_pages_per_domain": 10
                }
            }
        )
        
        task_id = None
        if create_result.success and isinstance(create_result.response_data, dict):
            task_id = create_result.response_data.get("task_id")
        
        # 获取任务列表
        await self.request("GET", "/api/v1/tasks")
        
        # 获取任务列表（带分页）
        await self.request(
            "GET", 
            "/api/v1/tasks",
            params={"skip": 0, "limit": 5}
        )
        
        # 获取任务列表（按状态过滤）
        await self.request(
            "GET", 
            "/api/v1/tasks",
            params={"status": "pending"}
        )
        
        if task_id:
            # 获取任务详情
            await self.request("GET", f"/api/v1/tasks/{task_id}")
            
            # 获取任务状态
            await self.request("GET", f"/api/v1/tasks/{task_id}/status")
            
            # 获取任务日志
            await self.request("GET", f"/api/v1/tasks/{task_id}/logs")
            
            # 等待一会儿让任务开始
            await asyncio.sleep(2)
            
            # 取消任务
            await self.request("POST", f"/api/v1/tasks/{task_id}/cancel")
            
            # 再次获取任务状态确认取消
            await self.request("GET", f"/api/v1/tasks/{task_id}/status")
    
    async def test_config_endpoints(self):
        """测试配置相关接口"""
        print("\n📋 测试配置接口...")
        
        if not self.auth_token:
            print("❌ 需要先登录")
            return
        
        # 获取AI配置
        await self.request("GET", "/api/v1/config/ai")
        
        # 更新AI配置
        await self.request(
            "PUT",
            "/api/v1/config/ai",
            data={
                "model": "gpt-3.5-turbo",
                "max_tokens": 2048,
                "temperature": 0.2
            }
        )
        
        # 获取扫描配置
        await self.request("GET", "/api/v1/config/scan")
        
        # 获取通知配置
        await self.request("GET", "/api/v1/config/notification")
        
        # 获取安全配置
        await self.request("GET", "/api/v1/config/security")
        
        # 获取系统配置
        await self.request("GET", "/api/v1/config/system")
    
    async def test_websocket_endpoint(self):
        """测试WebSocket接口"""
        print("\n📋 测试WebSocket接口...")
        
        if not self.auth_token:
            print("❌ 需要先登录")
            return
        
        try:
            ws_url = f"ws://localhost:8000/api/v1/monitor/ws?token={self.auth_token}"
            
            async with self.session.ws_connect(ws_url) as ws:
                # 发送ping消息
                await ws.send_str(json.dumps({"type": "ping"}))
                
                # 接收响应
                response = await ws.receive()
                if response.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(response.data)
                    print(f"✅ WebSocket响应: {data}")
                
                print("✅ WebSocket连接测试成功")
                
        except Exception as e:
            print(f"❌ WebSocket测试失败: {e}")
    
    async def test_health_endpoints(self):
        """测试健康检查接口"""
        print("\n📋 测试健康检查接口...")
        
        # 测试健康检查
        await self.request("GET", "/health")
        
        # 测试API根路径
        await self.request("GET", "/")
        
        # 测试API文档
        await self.request("GET", "/docs")
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "="*60)
        print("📊 测试结果汇总")
        print("="*60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests
        
        print(f"总测试数: {total_tests}")
        print(f"成功: {successful_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {successful_tests/total_tests*100:.1f}%")
        
        print("\n📋 详细结果:")
        print("-"*60)
        
        for result in self.test_results:
            status_icon = "✅" if result.success else "❌"
            status_text = f"{result.status_code}" if result.status_code > 0 else "ERROR"
            
            print(f"{status_icon} {result.method:6} {result.endpoint:30} "
                  f"{status_text:3} ({result.duration:.3f}s)")
            
            if not result.success:
                if result.error_message:
                    print(f"    错误: {result.error_message}")
                elif isinstance(result.response_data, dict):
                    error_detail = result.response_data.get("detail", "未知错误")
                    print(f"    错误: {error_detail}")
        
        print("\n📋 失败的测试:")
        print("-"*60)
        
        failed_results = [r for r in self.test_results if not r.success]
        if failed_results:
            for result in failed_results:
                print(f"❌ {result.method} {result.endpoint}")
                if result.error_message:
                    print(f"   {result.error_message}")
                elif isinstance(result.response_data, dict):
                    print(f"   {result.response_data}")
                print()
        else:
            print("🎉 所有测试都通过了！")


async def main():
    """主函数"""
    print("🚀 开始API接口测试")
    print(f"🕐 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with APITester() as tester:
        # 测试健康检查接口
        await tester.test_health_endpoints()
        
        # 测试认证接口
        await tester.test_auth_endpoints()
        
        # 测试任务接口
        await tester.test_task_endpoints()
        
        # 测试配置接口
        await tester.test_config_endpoints()
        
        # 测试WebSocket接口
        await tester.test_websocket_endpoint()
        
        # 打印测试结果
        tester.print_results()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())