#!/usr/bin/env python3
"""
Kafka 性能测试工具

测试 Kafka 生产者和消费者的性能
"""

import time
import json
import random
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
from dataclasses import dataclass
from typing import List


@dataclass
class KafkaBenchmarkResult:
    """压测结果"""
    topic: str
    messages_sent: int
    messages_received: int
    avg_latency_ms: float
    throughput_msgs_per_sec: float
    throughput_bytes_per_sec: float
    error_count: int


class KafkaBenchmark:
    """Kafka 性能测试"""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumer = None
    
    def setup(self):
        """准备测试环境"""
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            linger_ms=5,
            batch_size=16384,
        )
    
    def benchmark_producer(
        self,
        topic: str,
        message_count: int = 10000,
        message_size: int = 1024,
    ) -> KafkaBenchmarkResult:
        """生产者性能测试"""
        print(f"🚀 开始生产者性能测试: {message_count} 条消息")
        
        start_time = time.time()
        sent_count = 0
        error_count = 0
        total_bytes = 0
        
        for i in range(message_count):
            message = {
                "id": i,
                "timestamp": int(time.time() * 1000),
                "data": "x" * message_size,
            }
            
            try:
                future = self.producer.send(topic, value=message)
                future.add_callback(self._on_success)
                future.add_errback(self._on_error)
                sent_count += 1
                total_bytes += len(json.dumps(message).encode('utf-8'))
            except KafkaError as e:
                error_count += 1
                print(f"Error sending message {i}: {e}")
        
        # 刷新缓冲区
        self.producer.flush()
        
        elapsed = time.time() - start_time
        throughput = sent_count / elapsed if elapsed > 0 else 0
        
        result = KafkaBenchmarkResult(
            topic=topic,
            messages_sent=sent_count,
            messages_received=0,
            avg_latency_ms=(elapsed / sent_count * 1000) if sent_count > 0 else 0,
            throughput_msgs_per_sec=throughput,
            throughput_bytes_per_sec=total_bytes / elapsed if elapsed > 0 else 0,
            error_count=error_count,
        )
        
        print(f"✅ 生产者测试完成: {sent_count} 条消息, 耗时 {elapsed:.2f}s")
        return result
    
    def benchmark_consumer(
        self,
        topic: str,
        timeout_ms: int = 30000,
    ) -> KafkaBenchmarkResult:
        """消费者性能测试"""
        print(f"🚀 开始消费者性能测试: {topic}")
        
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='benchmark-group',
        )
        
        start_time = time.time()
        received_count = 0
        total_bytes = 0
        latencies = []
        
        try:
            for message in consumer:
                elapsed_ms = (time.time() - message.timestamp / 1000) * 1000
                latencies.append(elapsed_ms)
                received_count += 1
                total_bytes += len(message.value)
                
                if time.time() - start_time > timeout_ms / 1000:
                    break
        finally:
            consumer.close()
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        elapsed = time.time() - start_time
        throughput = received_count / elapsed if elapsed > 0 else 0
        
        result = KafkaBenchmarkResult(
            topic=topic,
            messages_sent=0,
            messages_received=received_count,
            avg_latency_ms=avg_latency,
            throughput_msgs_per_sec=throughput,
            throughput_bytes_per_sec=total_bytes / elapsed if elapsed > 0 else 0,
            error_count=0,
        )
        
        print(f"✅ 消费者测试完成: {received_count} 条消息, 平均延迟 {avg_latency:.2f}ms")
        return result
    
    def _on_success(self, record_metadata):
        """发送成功回调"""
        pass
    
    def _on_error(self, error):
        """发送失败回调"""
        print(f"Error: {error}")
    
    def benchmark_end_to_end(
        self,
        topic: str,
        message_count: int = 1000,
    ) -> dict:
        """端到端测试"""
        print(f"\n🚀 开始端到端测试: {message_count} 条消息")
        
        # 生产者测试
        producer_result = self.benchmark_producer(topic, message_count)
        
        # 消费者测试
        consumer_result = self.benchmark_consumer(topic)
        
        return {
            "producer": producer_result,
            "consumer": consumer_result,
        }
    
    def print_report(self, results: dict):
        """打印报告"""
        print("\n" + "=" * 60)
        print("    Kafka 性能测试报告")
        print("=" * 60)
        
        if "producer" in results:
            r = results["producer"]
            print(f"\n【生产者】")
            print(f"  发送消息: {r.messages_sent}")
            print(f"  吞吐量: {r.throughput_msgs_per_sec:.0f} msg/s")
            print(f"  平均延迟: {r.avg_latency_ms:.3f}ms")
            print(f"  错误数: {r.error_count}")
        
        if "consumer" in results:
            r = results["consumer"]
            print(f"\n【消费者】")
            print(f"  接收消息: {r.messages_received}")
            print(f"  吞吐量: {r.throughput_msgs_per_sec:.0f} msg/s")
            print(f"  平均延迟: {r.avg_latency_ms:.3f}ms")
        
        print("\n" + "=" * 60)


def main():
    """主入口"""
    benchmark = KafkaBenchmark()
    benchmark.setup()
    
    topic = "benchmark-topic"
    
    # 运行测试
    results = benchmark.benchmark_end_to_end(topic, message_count=5000)
    benchmark.print_report(results)


if __name__ == "__main__":
    main()
