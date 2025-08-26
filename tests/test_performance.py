#!/usr/bin/env python3
"""
API性能测试脚本
测试系统在高并发情况下的性能表现
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import json


@dataclass
class PerformanceResult:
    """性能测试结果"""
    endpoint: str
    total_requests: int
    concurrent_users: int
    total_time: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    success_rate: float
    requests_per_second: float
    errors: List[str]


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.auth_token: str = ""
    
    async def login(self) -> bool:
        """登录获取token"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "admin123"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        token_data = data.get("data", {})
                        self.auth_token = token_data.get("access_token", "")
                        return bool(self.auth_token)
            except Exception as e:
                print(f"登录失败: {e}")
        return False
    
    async def single_request(
        self, 
        session: aiohttp.ClientSession,
        method: str,
        endpoint: str,
        data: Dict = None
    ) -> Dict[str, Any]:
        """发送单个请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        
        start_time = time.time()
        try:
            async with session.request(
                method,
                url,
                json=data,
                headers=headers
            ) as response:
                response_time = time.time() - start_time
                
                return {
                    "success": 200 <= response.status < 300,
                    "status_code": response.status,
                    "response_time": response_time,
                    "error": None
                }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "success": False,
                "status_code": 0,
                "response_time": response_time,
                "error": str(e)
            }
    
    async def concurrent_requests(
        self,
        method: str,
        endpoint: str,
        data: Dict = None,
        concurrent_users: int = 10,
        requests_per_user: int = 10
    ) -> PerformanceResult:
        """并发请求测试"""
        print(f"🚀 测试 {method} {endpoint}")
        print(f"📊 并发用户: {concurrent_users}, 每用户请求数: {requests_per_user}")
        
        all_results = []
        errors = []
        
        start_time = time.time()
        
        # 创建并发会话
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        async with aiohttp.ClientSession(connector=connector) as session:
            
            # 创建所有任务
            tasks = []
            for user in range(concurrent_users):
                for req in range(requests_per_user):
                    task = self.single_request(session, method, endpoint, data)
                    tasks.append(task)
            
            # 执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # 处理结果
        response_times = []
        success_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
                continue
            
            all_results.append(result)
            response_times.append(result["response_time"])
            
            if result["success"]:
                success_count += 1
            else:
                errors.append(f"HTTP {result['status_code']}: {result.get('error', 'Unknown error')}")
        
        total_requests = len(all_results)
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
        
        return PerformanceResult(
            endpoint=endpoint,
            total_requests=total_requests,
            concurrent_users=concurrent_users,
            total_time=total_time,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            success_rate=success_rate,
            requests_per_second=total_requests / total_time if total_time > 0 else 0,
            errors=errors[:10]  # 只显示前10个错误
        )
    
    async def test_health_endpoint(self):
        """测试健康检查接口性能"""
        return await self.concurrent_requests(
            "GET", 
            "/health",
            concurrent_users=20,
            requests_per_user=50
        )
    
    async def test_auth_endpoint(self):
        """测试认证接口性能"""
        return await self.concurrent_requests(
            "POST",
            "/api/v1/auth/login",
            data={
                "username": "admin",
                "password": "admin123"
            },
            concurrent_users=10,
            requests_per_user=10
        )
    
    async def test_tasks_list_endpoint(self):
        """测试任务列表接口性能"""
        if not self.auth_token:
            await self.login()
        
        return await self.concurrent_requests(
            "GET",
            "/api/v1/tasks",
            concurrent_users=15,
            requests_per_user=20
        )
    
    async def test_task_creation_endpoint(self):
        """测试任务创建接口性能"""
        if not self.auth_token:
            await self.login()
        
        return await self.concurrent_requests(
            "POST",
            "/api/v1/tasks",
            data={
                "target_domain": "test.example.com",
                "config": {"max_depth": 1}
            },
            concurrent_users=5,
            requests_per_user=5  # 降低数量避免创建太多任务
        )
    
    async def test_config_endpoint(self):
        """测试配置接口性能"""
        if not self.auth_token:
            await self.login()
        
        return await self.concurrent_requests(
            "GET",
            "/api/v1/config/system",
            concurrent_users=10,
            requests_per_user=15
        )
    
    def print_result(self, result: PerformanceResult):
        """打印测试结果"""
        print(f"\n📋 {result.endpoint} 性能测试结果:")
        print("-" * 60)
        print(f"总请求数:     {result.total_requests}")
        print(f"并发用户:     {result.concurrent_users}")
        print(f"总耗时:       {result.total_time:.2f}s")
        print(f"平均响应时间: {result.avg_response_time*1000:.2f}ms")
        print(f"最小响应时间: {result.min_response_time*1000:.2f}ms")
        print(f"最大响应时间: {result.max_response_time*1000:.2f}ms")
        print(f"成功率:       {result.success_rate:.1f}%")
        print(f"QPS:          {result.requests_per_second:.2f}")
        
        if result.errors:
            print(f"\n❌ 错误 (显示前10个):")
            for error in result.errors:
                print(f"   {error}")
    
    def evaluate_performance(self, result: PerformanceResult) -> str:
        """评估性能等级"""
        if result.success_rate < 95:
            return "❌ 差"
        elif result.avg_response_time > 2.0:
            return "⚠️ 一般"
        elif result.avg_response_time > 1.0:
            return "✅ 良好"
        else:
            return "🚀 优秀"


async def main():
    """主函数"""
    print("🚀 开始API性能测试")
    print("=" * 60)
    
    tester = PerformanceTester()
    results = []
    
    try:
        # 测试健康检查接口
        health_result = await tester.test_health_endpoint()
        results.append(health_result)
        tester.print_result(health_result)
        
        # 测试认证接口
        auth_result = await tester.test_auth_endpoint()
        results.append(auth_result)
        tester.print_result(auth_result)
        
        # 登录以获取token
        await tester.login()
        
        # 测试任务列表接口
        tasks_result = await tester.test_tasks_list_endpoint()
        results.append(tasks_result)
        tester.print_result(tasks_result)
        
        # 测试配置接口
        config_result = await tester.test_config_endpoint()
        results.append(config_result)
        tester.print_result(config_result)
        
        # 测试任务创建接口（可选，会创建实际任务）
        # task_creation_result = await tester.test_task_creation_endpoint()
        # results.append(task_creation_result)
        # tester.print_result(task_creation_result)
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 性能测试汇总")
    print("=" * 60)
    
    for result in results:
        performance_level = tester.evaluate_performance(result)
        print(f"{performance_level} {result.endpoint:30} "
              f"QPS: {result.requests_per_second:6.1f} "
              f"RT: {result.avg_response_time*1000:6.1f}ms "
              f"成功率: {result.success_rate:5.1f}%")
    
    # 整体评估
    avg_success_rate = sum(r.success_rate for r in results) / len(results)
    avg_response_time = sum(r.avg_response_time for r in results) / len(results)
    total_qps = sum(r.requests_per_second for r in results)
    
    print(f"\n📈 整体性能指标:")
    print(f"平均成功率: {avg_success_rate:.1f}%")
    print(f"平均响应时间: {avg_response_time*1000:.1f}ms")
    print(f"总QPS: {total_qps:.1f}")
    
    if avg_success_rate >= 95 and avg_response_time <= 1.0:
        print("🚀 系统性能优秀！")
    elif avg_success_rate >= 90 and avg_response_time <= 2.0:
        print("✅ 系统性能良好")
    elif avg_success_rate >= 80:
        print("⚠️ 系统性能一般，需要优化")
    else:
        print("❌ 系统性能较差，需要紧急优化")


if __name__ == "__main__":
    # 运行性能测试
    asyncio.run(main())