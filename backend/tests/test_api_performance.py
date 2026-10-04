"""API Performance Test for AgentMatrix backend."""

import asyncio
import aiohttp
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


class APITester:
    """API tester class for performance testing."""
    
    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
    
    async def test_endpoint(
        self,
        session: aiohttp.ClientSession,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Test a single API endpoint."""
        url = f"{BASE_URL}{endpoint}"
        start_time = time.time()
        
        try:
            response: aiohttp.ClientResponse
            if method.upper() == "GET":
                async with session.get(url) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = await response.text()
            elif method.upper() == "POST":
                async with session.post(url, json=data) as response:
                    status = response.status
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = await response.text()
            else:
                return {"error": "Unsupported method: " + method}
            
            duration = time.time() - start_time
            
            result: Dict[str, Any] = {
                "endpoint": endpoint,
                "method": method,
                "description": description,
                "status": status,
                "duration_ms": round(duration * 1000, 2),
                "success": status in [200, 201],
                "response_size": len(str(response_data)) if isinstance(response_data, (dict, list)) else len(response_data)
            }
            
            if not result["success"]:
                result["error"] = response_data
                
        except Exception as e:
            duration = time.time() - start_time
            result = {
                "endpoint": endpoint,
                "method": method,
                "description": description,
                "status": -1,
                "duration_ms": round(duration * 1000, 2),
                "success": False,
                "error": str(e)
            }
        
        self.results.append(result)
        return result
    
    async def run_performance_test(self, iterations: int = 3) -> None:
        """Run comprehensive performance tests."""
        print("\n" + "=" * 60)
        print("[TEST] AgentMatrix API Performance Test")
        print("=" * 60 + "\n")
        
        async with aiohttp.ClientSession() as session:
            print("[PHASE 1] Basic Health Check")
            print("-" * 40)
            
            await self.test_endpoint(session, "GET", "/metrics/", "System Metrics")
            await self.test_endpoint(session, "GET", "/chat/health", "Chat Service Health")
            await self.test_endpoint(session, "GET", "/knowledge/", "Knowledge Base")
            
            print("\n[PHASE 2] Workflow Execution (Cold Start)")
            print("-" * 40)
            
            workflow_result = await self.test_endpoint(
                session, "POST", "/workflow/execute",
                {"user_input": "test workflow execution"},
                "Workflow Cold Start"
            )
            print("  First execution: " + str(workflow_result["duration_ms"]) + "ms")
            
            print("\n[PHASE 3] Workflow Execution (Cached)")
            print("-" * 40)
            
            for i in range(iterations):
                cached_result = await self.test_endpoint(
                    session, "POST", "/workflow/execute",
                    {"user_input": "test workflow execution"},
                    "Workflow Cache Test #" + str(i + 1)
                )
                print("  Cached execution #" + str(i + 1) + ": " + str(cached_result["duration_ms"]) + "ms")
            
            print("\n[PHASE 4] Chat API Performance")
            print("-" * 40)
            
            chat_cold = await self.test_endpoint(
                session, "POST", "/chat/send",
                {"content": "hello, this is a test"},
                "Chat Cold Start"
            )
            print("  First chat: " + str(chat_cold["duration_ms"]) + "ms")
            
            for i in range(iterations):
                chat_cached = await self.test_endpoint(
                    session, "POST", "/chat/send",
                    {"content": "hello, this is a test"},
                    "Chat Cache Test #" + str(i + 1)
                )
                print("  Cached chat #" + str(i + 1) + ": " + str(chat_cached["duration_ms"]) + "ms")
            
            print("\n[PHASE 5] Knowledge Base Operations")
            print("-" * 40)
            
            await self.test_endpoint(session, "GET", "/knowledge/search?query=AI", "Knowledge Search")
            await self.test_endpoint(session, "GET", "/knowledge/keyword/AI", "Get Keyword")
            
            print("\n[PHASE 6] Agent API")
            print("-" * 40)
            
            await self.test_endpoint(session, "GET", "/agents/", "Get All Agents")
            await self.test_endpoint(session, "GET", "/agents/knowledge/status", "Knowledge Agent Status")
            
            print("\n[PHASE 7] Batch Requests")
            print("-" * 40)
            
            batch_data = [{"content": "test message " + str(i)} for i in range(3)]
            batch_result = await self.test_endpoint(
                session, "POST", "/chat/send/batch",
                batch_data,
                "Batch Messages"
            )
            print("  Batch request: " + str(batch_result["duration_ms"]) + "ms")
        
        self.print_summary()
    
    async def run_stress_test(self, concurrent_requests: int = 10) -> None:
        """Run stress test with concurrent requests."""
        print("\n" + "=" * 60)
        print("[STRESS TEST] Concurrent Requests")
        print("=" * 60 + "\n")
        
        async with aiohttp.ClientSession() as session:
            tasks: List[asyncio.Task[Dict[str, Any]]] = []
            start_time = time.time()
            
            for i in range(concurrent_requests):
                task = asyncio.create_task(
                    self.test_endpoint(
                        session, "POST", "/chat/send",
                        {"content": "stress test request " + str(i)},
                        "Concurrent Request #" + str(i)
                    )
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            total_duration = time.time() - start_time
            
            print("Completed " + str(concurrent_requests) + " concurrent requests")
            print("Total time: " + str(total_duration * 1000) + "ms")
            print("Throughput: " + str(concurrent_requests / total_duration) + " req/s")
    
    def print_summary(self) -> None:
        """Print test summary and save report."""
        print("\n" + "=" * 60)
        print("[TEST SUMMARY]")
        print("=" * 60)
        
        successes = [r for r in self.results if r["success"]]
        failures = [r for r in self.results if not r["success"]]
        
        avg_duration = sum(r["duration_ms"] for r in successes) / len(successes) if successes else 0
        max_duration = max(r["duration_ms"] for r in successes) if successes else 0
        min_duration = min(r["duration_ms"] for r in successes) if successes else 0
        
        print("\n[STATS]")
        print("   Total tests: " + str(len(self.results)))
        print("   Success: " + str(len(successes)))
        print("   Failed: " + str(len(failures)))
        print("   Success rate: " + str(len(successes) / len(self.results) * 100) + "%")
        
        print("\n[RESPONSE TIME]")
        print("   Average: " + str(avg_duration) + "ms")
        print("   Min: " + str(min_duration) + "ms")
        print("   Max: " + str(max_duration) + "ms")
        
        cached_requests = [r for r in self.results if "Cache" in r["description"]]
        if cached_requests:
            avg_cached = sum(r["duration_ms"] for r in cached_requests) / len(cached_requests)
            print("\n[CACHE EFFECTIVENESS]")
            print("   Cached requests: " + str(len(cached_requests)))
            print("   Average time: " + str(avg_cached) + "ms")
        
        if failures:
            print("\n[FAILED REQUESTS]")
            for r in failures:
                print("   - " + r["method"] + " " + r["endpoint"] + ": " + str(r["status"]) + " - " + str(r.get("error", "Unknown")))
        
        print("\n" + "=" * 60)
        
        timestamp = datetime.now().isoformat()
        report = {
            "timestamp": timestamp,
            "total_tests": len(self.results),
            "successes": len(successes),
            "failures": len(failures),
            "success_rate": len(successes) / len(self.results) * 100,
            "avg_duration_ms": avg_duration,
            "min_duration_ms": min_duration,
            "max_duration_ms": max_duration,
            "results": self.results
        }
        
        with open("tests/test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("Test report saved to: tests/test_report.json")


if __name__ == "__main__":
    tester = APITester()
    asyncio.run(tester.run_performance_test(iterations=3))
    asyncio.run(tester.run_stress_test(concurrent_requests=10))