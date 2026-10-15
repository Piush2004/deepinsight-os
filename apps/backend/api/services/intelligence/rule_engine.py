from typing import Dict, Any, List, Optional


class RuleEngine:
    """
    Evaluates raw metrics against deterministic business rules to generate signals.
    Does NOT use an LLM anywhere in this file - all math below is plain arithmetic so
    it is reproducible and auditable, per docs/PROJECT_RULES.md ("deterministic
    calculations must remain deterministic").
    """

    # Metrics we know how to trend (dimensionless ratios where a % change is meaningful).
    TRENDABLE_METRICS = {"ctr", "open_rate", "click_rate", "bounce_rate", "conversion_rate", "sessions", "revenue"}
    TREND_SIGNIFICANCE_THRESHOLD_PCT = 20.0  # only surface a trend signal beyond this magnitude

    @staticmethod
    def calculate_percentage_change(previous: float, current: float) -> Optional[float]:
        """Relative percentage change from `previous` to `current`.
        Example: previous=0.02, current=0.04 -> +100.0 (a doubling), NOT +2.0.
        Returns None when previous is 0 (relative change is undefined, not infinite)."""
        if previous == 0:
            return None
        return ((current - previous) / previous) * 100.0

    @staticmethod
    def _confidence_from_margin(value: float, threshold: float, scale: float) -> int:
        """Deterministic confidence: how far past the threshold the value sits, scaled
        into 50-99. A value right at the threshold gets low confidence (50); a value far
        past it approaches 99. Never a hardcoded constant."""
        margin = abs(value - threshold) / scale if scale else 0
        confidence = 50 + min(49, margin * 49)
        return int(round(confidence))

    def evaluate_metrics(self, current_metrics: Dict[str, Any], historical_metrics: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        signals = []

        # Email Marketing Rule
        if "open_rate" in current_metrics and "click_rate" in current_metrics:
            if current_metrics["open_rate"] < 0.2 and current_metrics["click_rate"] > 0.05:
                signals.append({
                    "category": "Email",
                    "observation": "Low Open Rate, High Click Rate",
                    "insight": "Subject line is weak, but content is strong and engaging.",
                    "confidence": self._confidence_from_margin(current_metrics["open_rate"], 0.2, 0.2),
                    "actionable": True
                })

        # Website Traffic Rule
        if "ctr" in current_metrics and "bounce_rate" in current_metrics:
            if current_metrics["ctr"] > 0.03 and current_metrics["bounce_rate"] < 0.4:
                signals.append({
                    "category": "Web",
                    "observation": "High CTR, Low Bounce Rate",
                    "insight": "Positive engagement. Audience intent matches landing page content.",
                    "confidence": self._confidence_from_margin(current_metrics["ctr"], 0.03, 0.03),
                    "actionable": False
                })

        # Trend rules: real period-over-period % change for every trendable metric present
        # in both current and historical data.
        if historical_metrics:
            for metric_name in self.TRENDABLE_METRICS:
                if metric_name not in current_metrics or metric_name not in historical_metrics:
                    continue
                previous = historical_metrics[metric_name]
                current = current_metrics[metric_name]
                pct_change = self.calculate_percentage_change(previous, current)
                if pct_change is None or abs(pct_change) < self.TREND_SIGNIFICANCE_THRESHOLD_PCT:
                    continue

                direction = "increased" if pct_change > 0 else "decreased"
                signals.append({
                    "category": "Trend",
                    "observation": f"{metric_name} {direction} {abs(pct_change):.1f}% period-over-period",
                    "insight": f"{metric_name} moved from {previous} to {current} ({pct_change:+.1f}%).",
                    "confidence": int(round(min(99, 50 + min(abs(pct_change), 49)))),
                    "actionable": abs(pct_change) >= 30,
                    "metric": metric_name,
                    "previous_value": previous,
                    "current_value": current,
                    "percentage_change": round(pct_change, 2),
                })

        return signals
