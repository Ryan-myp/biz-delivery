#!/usr/bin/env python3
"""
生产环境监控告警系统

监控关键指标，实现告警和通知
"""

import json
import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = None


@dataclass
class Alert:
    """告警"""
    metric_name: str
    level: AlertLevel
    message: str
    value: float
    threshold: float
    timestamp: float


class Monitor:
    """监控器"""
    
    def __init__(self, name: str):
        self.name = name
        self.metrics: Dict[str, List[Metric]] = {}
        self.alerts: List[Alert] = []
        self.alert_handlers: List[Callable] = []
        self.thresholds: Dict[str, Dict[str, float]] = {}
        
    def add_metric(self, metric: Metric):
        """添加指标"""
        if metric.name not in self.metrics:
            self.metrics[metric.name] = []
        self.metrics[metric.name].append(metric)
        
        # 保持最近1000个数据点
        if len(self.metrics[metric.name]) > 1000:
            self.metrics[metric.name] = self.metrics[metric.name][-1000:]
        
        # 检查阈值
        self._check_threshold(metric)
        
    def _check_threshold(self, metric: Metric):
        """检查阈值"""
        if metric.name not in self.thresholds:
            return
            
        thresholds = self.thresholds[metric.name]
        
        # 检查警告阈值
        if "warning" in thresholds and metric.value > thresholds["warning"]:
            self._trigger_alert(metric, AlertLevel.WARNING, thresholds["warning"])
            
        # 检查严重阈值
        if "critical" in thresholds and metric.value > thresholds["critical"]:
            self._trigger_alert(metric, AlertLevel.CRITICAL, thresholds["critical"])
            
    def _trigger_alert(self, metric: Metric, level: AlertLevel, threshold: float):
        """触发告警"""
        alert = Alert(
            metric_name=metric.name,
            level=level,
            message=f"{metric.name} 超过阈值: {metric.value} > {threshold}",
            value=metric.value,
            threshold=threshold,
            timestamp=metric.timestamp
        )
        self.alerts.append(alert)
        
        # 调用告警处理器
        for handler in self.alert_handlers:
            handler(alert)
            
    def set_threshold(self, metric_name: str, warning: float, critical: float):
        """设置阈值"""
        self.thresholds[metric_name] = {
            "warning": warning,
            "critical": critical
        }
        
    def add_alert_handler(self, handler: Callable):
        """添加告警处理器"""
        self.alert_handlers.append(handler)
        
    def get_recent_metrics(self, metric_name: str, minutes: int = 5) -> List[Metric]:
        """获取最近指标"""
        if metric_name not in self.metrics:
            return []
            
        cutoff = time.time() - (minutes * 60)
        return [m for m in self.metrics[metric_name] if m.timestamp >= cutoff]
    
    def get_alerts(self, level: Optional[AlertLevel] = None, minutes: int = 5) -> List[Alert]:
        """获取告警"""
        cutoff = time.time() - (minutes * 60)
        alerts = [a for a in self.alerts if a.timestamp >= cutoff]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
            
        return alerts


class PrometheusCollector:
    """Prometheus 指标收集器"""
    
    def __init__(self, monitor: Monitor):
        self.monitor = monitor
        self.registry = {}
        
    def gauge(self, name: str, doc: str):
        """创建 Gauge 指标"""
        self.registry[name] = {
            "type": "gauge",
            "doc": doc,
            "value": 0
        }
        return self
        
    def set(self, name: str, value: float):
        """设置指标值"""
        if name in self.registry:
            self.registry[name]["value"] = value
            self.monitor.add_metric(Metric(
                name=name,
                value=value,
                timestamp=time.time()
            ))
        return self


class AlertNotifier:
    """告警通知"""
    
    def __init__(self):
        self.notifiers = []
        
    def add_notifier(self, notifier: Callable):
        """添加通知器"""
        self.notifiers.append(notifier)
        
    def notify(self, alert: Alert):
        """发送告警"""
        for notifier in self.notifiers:
            try:
                notifier(alert)
            except Exception as e:
                logging.error(f"通知发送失败: {e}")


# 使用示例
if __name__ == "__main__":
    # 创建监控器
    monitor = Monitor("production")
    
    # 设置阈值
    monitor.set_threshold("cpu_usage", warning=80, critical=90)
    monitor.set_threshold("memory_usage", warning=85, critical=95)
    monitor.set_threshold("error_rate", warning=5, critical=10)
    
    # 添加告警通知
    def slack_notify(alert: Alert):
        print(f"[SLACK] {alert.level.value}: {alert.message}")
    
    def email_notify(alert: Alert):
        print(f"[EMAIL] {alert.level.value}: {alert.message}")
    
    monitor.add_alert_handler(slack_notify)
    monitor.add_alert_handler(email_notify)
    
    # 模拟指标
    import random
    for _ in range(100):
        cpu = random.uniform(50, 95)
        memory = random.uniform(60, 98)
        errors = random.uniform(0, 15)
        
        monitor.add_metric(Metric("cpu_usage", cpu, time.time()))
        monitor.add_metric(Metric("memory_usage", memory, time.time()))
        monitor.add_metric(Metric("error_rate", errors, time.time()))
        
        time.sleep(0.1)
    
    # 查看告警
    critical_alerts = monitor.get_alerts(level=AlertLevel.CRITICAL)
    print(f"\n严重告警数: {len(critical_alerts)}")