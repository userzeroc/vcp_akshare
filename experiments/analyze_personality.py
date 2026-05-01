"""
股性分析演示脚本

用法:
  python scratch/analyze_personality.py --ts_code 600519.SH
  python scratch/analyze_personality.py --industry 白酒
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.data.reader.stock_reader import StockReader
from src.analysis.stock_personality import StockPersonalityAnalyzer
from src.analysis.personality_config import PersonalityConfig
from src.analysis.personality_report import PersonalityReportGenerator


def main():
    parser = argparse.ArgumentParser(description="股性分析工具")
    parser.add_argument("--ts_code", type=str, help="股票代码，如 600519.SH")
    parser.add_argument("--industry", type=str, help="按行业分析，如 白酒")
    parser.add_argument("--output_dir", type=str, default=str(settings.paths.reports_dir), help="报告输出目录")
    args = parser.parse_args()

    reader = StockReader()
    config = PersonalityConfig()
    analyzer = StockPersonalityAnalyzer(reader, config)
    reporter = PersonalityReportGenerator()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.ts_code:
        print(f"\n{'='*60}")
        print(f"  股性分析: {args.ts_code}")
        print(f"{'='*60}\n")

        result = analyzer.analyze(args.ts_code)
        if result:
            _print_summary(result)
            fname = args.ts_code.replace('.', '_')
            path = os.path.join(args.output_dir, f"personality_{fname}.html")
            reporter.generate_single(result, path)
            print(f"\n📄 HTML报告已生成: {path}")

    elif args.industry:
        print(f"\n{'='*60}")
        print(f"  行业股性分析: {args.industry}")
        print(f"{'='*60}\n")

        results = analyzer.analyze_industry(args.industry)
        if results:
            print(f"\n分析完成，有效结果 {len(results)} 只：\n")
            for r in sorted(results, key=lambda x: x.confidence, reverse=True):
                print(f"  {r.category_emoji} [{r.category}] {r.name}({r.ts_code}) "
                      f"置信度{r.confidence}% | 脾气{r.temperament.score} 习惯{r.habit.score} "
                      f"饭量{r.volume_profile.score} 地位{r.market_position.score}")

            path = os.path.join(args.output_dir, f"personality_industry_{args.industry}.html")
            reporter.generate_batch(results, f"行业分析: {args.industry}", path)
            print(f"\n📄 HTML报告已生成: {path}")
    else:
        parser.print_help()


def _print_summary(r):
    print(f"  股票: {r.name} ({r.ts_code})")
    print(f"  板块: {r.market} | 行业: {r.industry}")
    print(f"  分析区间: {r.analysis_period}")
    print(f"\n  {'─'*50}")
    print(f"  归类: {r.category_emoji} 抽屉{r.category} — {r.category_name} (置信度 {r.confidence}%)")
    print(f"  战术: {r.tactic}")
    print(f"\n  {'─'*50}")
    print(f"  四维评分:")
    print(f"    🔥 脾气(爆发力): {r.temperament.score}")
    print(f"    📐 习惯(趋势性): {r.habit.score}")
    print(f"    🍔 饭量(量价):   {r.volume_profile.score}")
    print(f"    👑 地位(龙头性): {r.market_position.score}")
    print(f"\n  {'─'*50}")
    print(f"  诊断摘要:")
    print(f"    {r.temperament.diagnosis}")
    print(f"    {r.habit.diagnosis}")
    print(f"    {r.volume_profile.diagnosis}")
    print(f"    {r.market_position.diagnosis}")


if __name__ == "__main__":
    main()
