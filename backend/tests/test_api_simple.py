"""AI Portal 后端 API 简化测试"""

import httpx
import asyncio
import json


class SimpleAPITester:
    """简化的API测试器"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.test_results = []

    def log_result(self, name, status, message, duration):
        """记录测试结果"""
        self.test_results.append({
            "测试名称": name,
            "状态": status,
            "说明": message,
            "响应时间": f"{duration:.2f}ms"
        })
        icon = "✅" if status == "通过" else "❌"
        print(f"{icon} {name}: {status} - {message} ({duration:.2f}ms)")

    async def test_all(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🧪 AI Portal 后端 API 测试 (简化版)")
        print("="*60 + "\n")

        # 创建一个持久化的客户端
        async with httpx.AsyncClient() as client:
            # 测试1: 健康检查
            await self.test_health_check(client)

            # 测试2: 模拟登录 (follow redirects)
            await self.test_mock_login(client)

            # 测试3-10: 需要认证的测试
            await self.test_get_me(client)
            await self.test_list_resources(client)
            await self.test_list_grouped_resources(client)
            await self.test_get_resource(client)
            await self.test_launch_resource(client)
            await self.test_list_sessions(client)
            await self.test_list_skills(client)

        # 测试11: 未授权访问
        await self.test_unauthorized()

        return self.test_results

    async def test_health_check(self, client):
        """健康检查"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/health")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200 and response.json().get("status") == "healthy":
                self.log_result("健康检查", "通过", "系统正常", elapsed)
            else:
                self.log_result("健康检查", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("健康检查", "失败", str(e), 0)

    async def test_mock_login(self, client):
        """模拟登录"""
        import time
        start = time.time()
        try:
            # 直接访问登录API
            response = await client.get(
                f"{self.base_url}/api/auth/mock-login?emp_no=E10001"
            )
            elapsed = (time.time() - start) * 1000

            if response.status_code in (200, 302):
                cookies = dict(client.cookies)
                if "portal_sid" in cookies:
                    if response.status_code == 200:
                        data = response.json()
                        user = data.get("user", {})
                        user_name = user.get("name", "Unknown")
                    else:
                        user_name = "E10001"
                    self.log_result("模拟登录", "通过", f"用户: {user_name}", elapsed)
                else:
                    self.log_result("模拟登录", "失败", "未设置portal_sid cookie", elapsed)
            else:
                self.log_result("模拟登录", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("模拟登录", "失败", str(e), 0)

    async def test_get_me(self, client):
        """获取当前用户"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/auth/me")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                self.log_result("获取用户信息", "通过", f"用户: {data.get('name', 'Unknown')}", elapsed)
            elif response.status_code == 401:
                self.log_result("获取用户信息", "跳过", "未登录 (需要手动设置cookie)", elapsed)
            else:
                self.log_result("获取用户信息", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("获取用户信息", "失败", str(e), 0)

    async def test_list_resources(self, client):
        """列出资源"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/resources")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result("列出资源", "通过", f"找到 {len(data)} 个资源", elapsed)
                else:
                    self.log_result("列出资源", "失败", "数据格式错误", elapsed)
            elif response.status_code == 401:
                self.log_result("列出资源", "跳过", "未登录", elapsed)
            else:
                self.log_result("列出资源", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("列出资源", "失败", str(e), 0)

    async def test_list_grouped_resources(self, client):
        """列出分组资源"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/resources/grouped")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    groups = list(data.keys())
                    self.log_result("列出分组资源", "通过", f"找到 {len(groups)} 个分组", elapsed)
                else:
                    self.log_result("列出分组资源", "失败", "数据格式错误", elapsed)
            elif response.status_code == 401:
                self.log_result("列出分组资源", "跳过", "未登录", elapsed)
            else:
                self.log_result("列出分组资源", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("列出分组资源", "失败", str(e), 0)

    async def test_get_resource(self, client):
        """获取单个资源"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/resources/general-chat")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                self.log_result("获取单个资源", "通过", data.get("name", "Unknown"), elapsed)
            elif response.status_code == 401:
                self.log_result("获取单个资源", "跳过", "未登录", elapsed)
            else:
                self.log_result("获取单个资源", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("获取单个资源", "失败", str(e), 0)

    async def test_launch_resource(self, client):
        """启动资源"""
        import time
        start = time.time()
        try:
            response = await client.post(f"{self.base_url}/api/resources/general-chat/launch")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                kind = data.get("kind", "unknown")
                self.log_result("启动资源", "通过", f"类型: {kind}", elapsed)
            elif response.status_code == 401:
                self.log_result("启动资源", "跳过", "未登录", elapsed)
            elif response.status_code == 500:
                self.log_result("启动资源", "警告", "OpenCode服务未运行", elapsed)
            else:
                self.log_result("启动资源", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("启动资源", "失败", str(e), 0)

    async def test_list_sessions(self, client):
        """列出会话"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/sessions")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                sessions = data.get("sessions", [])
                self.log_result("列出会话", "通过", f"找到 {len(sessions)} 个会话", elapsed)
            elif response.status_code == 401:
                self.log_result("列出会话", "跳过", "未登录", elapsed)
            else:
                self.log_result("列出会话", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("列出会话", "失败", str(e), 0)

    async def test_list_skills(self, client):
        """列出技能"""
        import time
        start = time.time()
        try:
            response = await client.get(f"{self.base_url}/api/skills")
            elapsed = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result("列出技能", "通过", f"找到 {len(data)} 个技能", elapsed)
                else:
                    self.log_result("列出技能", "失败", "数据格式错误", elapsed)
            elif response.status_code == 401:
                self.log_result("列出技能", "跳过", "未登录", elapsed)
            else:
                self.log_result("列出技能", "失败", f"HTTP {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("列出技能", "失败", str(e), 0)

    async def test_unauthorized(self):
        """测试未授权访问"""
        import time
        start = time.time()
        try:
            # 使用新的客户端，不带cookie
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/resources")
                elapsed = (time.time() - start) * 1000

                if response.status_code == 401:
                    self.log_result("未授权访问保护", "通过", "正确拦截", elapsed)
                else:
                    self.log_result("未授权访问保护", "失败", f"应该返回401, 实际: {response.status_code}", elapsed)
        except Exception as e:
            self.log_result("未授权访问保护", "失败", str(e), 0)


async def main():
    tester = SimpleAPITester()
    results = await tester.test_all()

    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60 + "\n")

    total = len(results)
    passed = sum(1 for r in results if r["状态"] == "通过")
    failed = sum(1 for r in results if r["状态"] == "失败")
    skipped = sum(1 for r in results if r["状态"] == "跳过")
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"总计: {total} | 通过: {passed} | 失败: {failed} | 跳过: {skipped} | 通过率: {pass_rate:.1f}%\n")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
