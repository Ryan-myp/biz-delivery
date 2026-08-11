#!/usr/bin/env python3
"""
A/B 测试分析工具

分析 A/B 测试数据，计算统计显著性，提供决策建议
"""

import math
import json
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class Decision(Enum):
    """决策结果"""
    ACCEPT = "accept"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    variant: str
    conversions: int
    total: int
    conversion_rate: float
    confidence: float
    decision: Decision
    recommendation: str


class ABTestAnalyzer:
    """A/B 测试分析器"""
    
    def __init__(self, confidence_level: float = 0.95):
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
    
    def analyze(
        self,
        control_conversions: int,
        control_total: int,
        variant_conversions: int,
        variant_total: int,
    ) -> ABTestResult:
        """分析 A/B 测试"""
        
        # 计算转化率
        control_rate = control_conversions / control_total if control_total > 0 else 0
        variant_rate = variant_conversions / variant_total if variant_total > 0 else 0
        
        # 计算相对提升
        lift = (variant_rate - control_rate) / control_rate if control_rate > 0 else 0
        
        # 计算统计显著性
        z_score, p_value = self._calculate_significance(
            control_conversions, control_total,
            variant_conversions, variant_total
        )
        
        # 计算置信区间
        ci_lower, ci_upper = self._calculate_confidence_interval(
            control_rate, variant_rate,
            control_total, variant_total
        )
        
        # 做出决策
        decision, recommendation = self._make_decision(
            lift, p_value, ci_lower, ci_upper
        )
        
        return ABTestResult(
            variant="variant",
            conversions=variant_conversions,
            total=variant_total,
            conversion_rate=variant_rate,
            confidence=1 - p_value,
            decision=decision,
            recommendation=recommendation,
        )
    
    def _calculate_significance(
        self,
        control_conv: int,
        control_total: int,
        variant_conv: int,
        variant_total: int,
    ) -> tuple:
        """计算统计显著性（Z检验）"""
        
        # 合并转化率
        pooled_rate = (control_conv + variant_conv) / (control_total + variant_total)
        
        # 标准误差
        se = math.sqrt(
            pooled_rate * (1 - pooled_rate) * (1/control_total + 1/variant_total)
        )
        
        # Z 分数
        control_rate = control_conv / control_total
        variant_rate = variant_conv / variant_total
        z_score = (variant_rate - control_rate) / se if se > 0 else 0
        
        # P 值（双尾检验）
        p_value = 2 * (1 - self._normal_cdf(abs(z_score)))
        
        return z_score, p_value
    
    def _normal_cdf(self, x: float) -> float:
        """标准正态分布累积函数"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    def _calculate_confidence_interval(
        self,
        control_rate: float,
        variant_rate: float,
        control_total: int,
        variant_total: int,
    ) -> tuple:
        """计算置信区间"""
        
        z = self._get_z_score()
        
        # 控制组置信区间
        se_control = math.sqrt(control_rate * (1 - control_rate) / control_total)
        ci_lower_control = control_rate - z * se_control
        ci_upper_control = control_rate + z * se_control
        
        # 变体组置信区间
        se_variant = math.sqrt(variant_rate * (1 - variant_rate) / variant_total)
        ci_lower_variant = variant_rate - z * se_variant
        ci_upper_variant = variant_rate + z * se_variant
        
        return (ci_lower_variant, ci_upper_variant)
    
    def _get_z_score(self) -> float:
        """获取 Z 分数"""
        # 对于 95% 置信度，Z ≈ 1.96
        return 1.96
    
    def _make_decision(
        self,
        lift: float,
        p_value: float,
        ci_lower: float,
        ci_upper: float,
    ) -> tuple:
        """做出决策"""
        
        if p_value < self.alpha:
            # 统计显著
            if lift > 0:
                if ci_lower > 0:
                    return Decision.ACCEPT, "显著正向，建议采用变体"
                else:
                    return Decision.INCONCLUSIVE, "显著但置信区间包含0，需谨慎"
            else:
                if ci_upper < 0:
                    return Decision.REJECT, "显著负向，建议回滚"
                else:
                    return Decision.INCONCLUSIVE, "显著负向但置信区间包含0，需谨慎"
        else:
            # 不显著
            return Decision.INCONCLUSIVE, "结果不显著，继续测试或回滚"
    
    def calculate_sample_size(
        self,
        baseline_rate: float,
        min_detectable_effect: float,
        power: float = 0.8,
    ) -> int:
        """计算所需样本量"""
        
        z_alpha = self._get_z_score()
        z_beta = self._get_z_score_for_power(power)
        
        # 样本量公式
        numerator = (z_alpha + z_beta) ** 2 * 2 * baseline_rate * (1 - baseline_rate)
        denominator = (min_detectable_effect * baseline_rate) ** 2
        
        sample_size = numerator / denominator
        
        return int(math.ceil(sample_size))
    
    def _get_z_score_for_power(self, power: float) -> float:
        """获取功效对应的 Z 分数"""
        # 对于 80% 功效，Z ≈ 0.84
        return 0.84
    
    def generate_report(
        self,
        control_conv: int,
        control_total: int,
        variant_conv: int,
        variant_total: int,
    ) -> str:
        """生成分析报告"""
        
        result = self.analyze(control_conv, control_total, variant_conv, variant_total)
        
        report = f"""
# A/B 测试分析报告

## 实验概况
- 对照组转化率: {control_conv/control_total*100:.2f}% ({control_conv}/{control_total})
- 实验组转化率: {result.conversion_rate*100:.2f}% ({result.conversions}/{result.total})
- 相对提升: {((result.conversion_rate - control_conv/control_total) / (control_conv/control_total) * 100):.2f}%

## 统计结果
- 置信度: {result.confidence*100:.2f}%
- 决策: {result.decision.value}
- 建议: {result.recommendation}

## 结论
{self._generate_conclusion(result, control_conv/control_total)}
"""
        return report
    
    def _generate_conclusion(
        self,
        result: ABTestResult,
        control_rate: float,
    ) -> str:
        """生成结论"""
        
        if result.decision == Decision.ACCEPT:
            return f"""
✅ 实验成功！

- 实验组比对照组提升 {((result.conversion_rate - control_rate) / control_rate * 100):.2f}%
- 统计显著，置信度 {result.confidence*100:.2f}%
- 建议全量上线
"""
        elif result.decision == Decision.REJECT:
            return f"""
❌ 实验失败！

- 实验组比对照组下降 {((control_rate - result.conversion_rate) / control_rate * 100):.2f}%
- 统计显著，置信度 {result.confidence*100:.2f}%
- 建议回滚到对照组
"""
        else:
            return f"""
⚠️ 结果不明确！

- 统计不显著或置信区间包含0
- 建议继续收集数据
- 或检查实验设置
"""


def main():
    """主入口"""
    analyzer = ABTestAnalyzer(confidence_level=0.95)
    
    # 示例数据
    control_conv = 150
    control_total = 10000
    variant_conv = 180
    variant_total = 10000
    
    # 分析
    result = analyzer.analyze(control_conv, control_total, variant_conv, variant_total)
    
    # 打印报告
    report = analyzer.generate_report(control_conv, control_total, variant_conv, variant_total)
    print(report)
    
    # 计算样本量
    sample_size = analyzer.calculate_sample_size(0.015, 0.005)
    print(f"\n建议最小样本量: {sample_size} per group")


if __name__ == "__main__":
    main()
