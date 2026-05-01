"""
personality_report.py — 股性分析 HTML 报告生成器
"""
import os
import json
from typing import List
from .personality_metrics import PersonalityResult


class PersonalityReportGenerator:
    """HTML 报告生成器"""

    def generate_single(self, result: PersonalityResult, output_path: str) -> str:
        """生成单只股票的 HTML 报告"""
        html = self._build_single_html(result)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    def generate_batch(self, results: List[PersonalityResult], title: str, output_path: str) -> str:
        """生成批量分析 HTML 汇总报告"""
        html = self._build_batch_html(results, title)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_path

    # ------------------------------------------------------------------
    # 单只报告
    # ------------------------------------------------------------------

    def _build_single_html(self, r: PersonalityResult) -> str:
        scores_json = json.dumps(
            [r.scores.get('temperament', 0), r.scores.get('habit', 0),
             r.scores.get('volume_profile', 0), r.scores.get('market_position', 0)]
        )
        kline_json = json.dumps(r.kline_data)
        limit_up_json = json.dumps(r.limit_up_dates)
        fail_board_json = json.dumps(r.fail_board_dates)
        ma_json = json.dumps(r.best_ma_values)

        cat_colors = {"A": "#4CAF50", "B": "#FF5722", "C": "#FF9800", "D": "#9E9E9E"}
        cat_color = cat_colors.get(r.category, "#666")

        # 置信度条
        secondary_html = ""
        for s in r.secondary_traits:
            secondary_html += f'<span class="badge" style="background:{cat_colors.get(s.category,"#999")}">{s.category}({s.category_name}) {s.confidence}%</span> '

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{r.name}({r.ts_code}) 股性分析报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
{self._css()}
</head>
<body>
<div class="container">
  <header>
    <h1>{r.category_emoji} {r.name} <span class="code">({r.ts_code})</span></h1>
    <div class="meta">{r.market} · {r.industry} · {r.analysis_period}</div>
  </header>

  <div class="card category-card" style="border-left: 6px solid {cat_color}">
    <div class="cat-header">
      <span class="cat-label" style="background:{cat_color}">{r.category}</span>
      <span class="cat-name">{r.category_name}</span>
      <span class="cat-conf">置信度 {r.confidence}%</span>
    </div>
    <div class="tactic">{r.tactic}</div>
    <div class="secondary">次要特征：{secondary_html if secondary_html else "无"}</div>
  </div>

  <div class="card">
    <h2>📊 四维评分雷达</h2>
    <div id="radar" style="width:100%;height:350px;"></div>
  </div>

  <div class="card">
    <h2>📈 K线走势 & 关键标注</h2>
    <div id="kline" style="width:100%;height:450px;"></div>
    <div class="legend">
      <span class="dot red"></span> 涨停日
      <span class="dot yellow"></span> 炸板日
      <span class="line blue"></span> {r.habit.best_ma}日均线（真命天子）
    </div>
  </div>

  {self._dimension_card("🔥 维度一：脾气 — 波动率与涨停基因", r.temperament.score, self._temperament_detail(r))}
  {self._dimension_card("📐 维度二：习惯 — 均线契合度与趋势延续性", r.habit.score, self._habit_detail(r))}
  {self._dimension_card("🍔 维度三：饭量 — 量价配合度", r.volume_profile.score, self._volume_detail(r))}
  {self._dimension_card("👑 维度四：江湖地位 — 板块联动与大盘逆反", r.market_position.score, self._position_detail(r))}

  <footer>股性分析报告 · 仅供学习参考，不构成投资建议</footer>
</div>

<script>
// 雷达图
var radar = echarts.init(document.getElementById('radar'));
radar.setOption({{
  radar: {{ indicator: [
    {{name:'脾气(爆发力)',max:100}}, {{name:'习惯(趋势性)',max:100}},
    {{name:'饭量(量价)',max:100}}, {{name:'地位(龙头性)',max:100}}
  ], radius: '65%' }},
  series: [{{ type:'radar', data:[{{ value:{scores_json}, name:'评分',
    areaStyle:{{opacity:0.3}}, lineStyle:{{width:2}} }}] }}]
}});

// K线图
var kline = echarts.init(document.getElementById('kline'));
var rawData = {kline_json};
var dates = rawData.map(d=>d[0]);
var ohlc = rawData.map(d=>[d[1],d[2],d[3],d[4]]);
var limitDates = {limit_up_json};
var failDates = {fail_board_json};
var maData = {ma_json};

// 标注点
var markData = [];
limitDates.forEach(function(d){{
  markData.push({{coord:[d,null], symbol:'triangle', symbolSize:8, itemStyle:{{color:'#f44336'}}}});
}});
failDates.forEach(function(d){{
  markData.push({{coord:[d,null], symbol:'diamond', symbolSize:8, itemStyle:{{color:'#FF9800'}}}});
}});

// 找到标注点对应的价格
markData.forEach(function(m){{
  var idx = dates.indexOf(m.coord[0]);
  if(idx >= 0) m.coord[1] = ohlc[idx][1]; // close
}});

var series = [
  {{ type:'candlestick', data:ohlc, markPoint:{{ data:markData }},
     itemStyle:{{ color:'#ef5350', color0:'#26a69a', borderColor:'#ef5350', borderColor0:'#26a69a' }} }}
];

if(maData.length > 0) {{
  var maDates = maData.map(d=>d[0]);
  var maVals = maData.map(d=>d[1]);
  // 对齐到主x轴
  var alignedMa = dates.map(function(d){{
    var idx = maDates.indexOf(d);
    return idx >= 0 ? maVals[idx] : null;
  }});
  series.push({{ type:'line', data:alignedMa, smooth:true, lineStyle:{{color:'#2196F3',width:1.5}},
    symbol:'none', name:'{r.habit.best_ma}日线' }});
}}

kline.setOption({{
  tooltip:{{ trigger:'axis', axisPointer:{{type:'cross'}} }},
  xAxis:{{ type:'category', data:dates, axisLabel:{{rotate:45}} }},
  yAxis:{{ scale:true }},
  dataZoom:[{{ type:'inside', start:70, end:100 }}, {{ type:'slider', start:70, end:100 }}],
  series: series
}});

window.addEventListener('resize', function(){{ radar.resize(); kline.resize(); }});
</script>
</body></html>'''

    # ------------------------------------------------------------------
    # 批量报告
    # ------------------------------------------------------------------

    def _build_batch_html(self, results: List[PersonalityResult], title: str) -> str:
        cat_colors = {"A": "#4CAF50", "B": "#FF5722", "C": "#FF9800", "D": "#9E9E9E"}

        # 统计
        cat_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for r in results:
            cat_counts[r.category] = cat_counts.get(r.category, 0) + 1

        stats_html = ""
        for cat in ["A", "B", "C", "D"]:
            from .personality_config import CATEGORY_DEFS
            d = CATEGORY_DEFS[cat]
            stats_html += f'<div class="stat-card" style="border-top:4px solid {cat_colors[cat]}"><div class="stat-num">{cat_counts[cat]}</div><div class="stat-label">{d["emoji"]} {d["name"]}</div></div>'

        # 表格行
        rows_html = ""
        for r in sorted(results, key=lambda x: x.confidence, reverse=True):
            rows_html += f'''<tr>
<td><span class="cat-dot" style="background:{cat_colors[r.category]}">{r.category}</span></td>
<td>{r.name}</td><td class="code">{r.ts_code}</td><td>{r.industry}</td>
<td>{r.temperament.score}</td><td>{r.habit.score}</td>
<td>{r.volume_profile.score}</td><td>{r.market_position.score}</td>
<td>{r.confidence}%</td>
<td class="diag">{r.temperament.diagnosis[:30]}...</td>
</tr>'''

        return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - 股性分析批量报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
{self._css()}
</head><body>
<div class="container">
<header><h1>📋 {title}</h1><div class="meta">共分析 {len(results)} 只股票</div></header>
<div class="stats-row">{stats_html}</div>
<div class="card"><h2>分析结果总览</h2>
<table><thead><tr><th>类别</th><th>名称</th><th>代码</th><th>行业</th>
<th>脾气</th><th>习惯</th><th>饭量</th><th>地位</th><th>置信度</th><th>摘要</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<div id="pie" style="width:100%;height:350px;"></div>
<footer>股性分析报告 · 仅供学习参考，不构成投资建议</footer>
</div>
<script>
var pie = echarts.init(document.getElementById('pie'));
pie.setOption({{
  title:{{text:'归类分布',left:'center'}},
  series:[{{type:'pie',radius:'60%',data:[
    {{value:{cat_counts["A"]},name:'白马/核心资产',itemStyle:{{color:'#4CAF50'}}}},
    {{value:{cat_counts["B"]},name:'题材龙头/妖股',itemStyle:{{color:'#FF5722'}}}},
    {{value:{cat_counts["C"]},name:'渣男/震荡股',itemStyle:{{color:'#FF9800'}}}},
    {{value:{cat_counts["D"]},name:'僵尸股',itemStyle:{{color:'#9E9E9E'}}}}
  ]}}]
}});
</script></body></html>'''

    # ------------------------------------------------------------------
    # 维度详情
    # ------------------------------------------------------------------

    def _dimension_card(self, title: str, score: float, detail: str) -> str:
        color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#f44336"
        return f'''<div class="card dim-card">
<div class="dim-header"><h2>{title}</h2><span class="dim-score" style="color:{color}">{score}</span></div>
<div class="dim-body">{detail}</div></div>'''

    def _temperament_detail(self, r) -> str:
        t = r.temperament
        rows = f'''<table class="detail-table">
<tr><td>涨停次数</td><td><b>{t.limit_up_count}</b> 次 ({t.limit_up_frequency}次/年)</td></tr>
<tr><td>最大连板</td><td><b>{t.max_consecutive_limit}</b> 板 {"🔥 妖股基因" if t.has_monster_gene else ""}</td></tr>
<tr><td>涨停质量</td><td>放量首板 {t.quality_big_volume_count} | 缩量一字 {t.quality_no_volume_count} | 尾盘偷袭 {t.quality_late_count}</td></tr>
<tr><td>日均振幅</td><td>{t.avg_amplitude}% (中位{t.median_amplitude}%, P90={t.amplitude_p90}%)</td></tr>
<tr><td>炸板率</td><td>{t.fail_board_count}/{t.touch_limit_count} = <b>{t.fail_board_rate}%</b></td></tr>
</table><div class="diagnosis">{t.diagnosis}</div>'''
        return rows

    def _habit_detail(self, r) -> str:
        h = r.habit
        ma_str = " | ".join(f"{k}日:{v}%" for k, v in h.ma_success_rates.items())
        return f'''<table class="detail-table">
<tr><td>趋势类型</td><td><b>{h.trend_type}</b></td></tr>
<tr><td>上涨波段</td><td>平均 {h.avg_uptrend_days} 天, 最长 {h.max_uptrend_days} 天</td></tr>
<tr><td>A字杀次数</td><td>{h.a_kill_count} 次</td></tr>
<tr><td>真命天子均线</td><td><b>{h.best_ma}日线</b> (反弹成功率 {h.best_ma_success_rate}%)</td></tr>
<tr><td>各均线成功率</td><td>{ma_str}</td></tr>
</table><div class="diagnosis">{h.diagnosis}</div>'''

    def _volume_detail(self, r) -> str:
        v = r.volume_profile
        return f'''<table class="detail-table">
<tr><td>资金类型</td><td><b>{v.capital_type}</b></td></tr>
<tr><td>换手率</td><td>均{v.avg_turnover}% / 最高{v.max_turnover}% / 高换手天数{v.high_turnover_days}</td></tr>
<tr><td>缩量回调</td><td>比值 {v.volume_shrink_ratio} → <b>{v.shrink_quality}</b></td></tr>
<tr><td>活跃度趋势</td><td><b>{v.activity_trend}</b> (近3月{v.recent_avg_amplitude}% vs 历史{v.historical_avg_amplitude}%)</td></tr>
</table><div class="diagnosis">{v.diagnosis}</div>'''

    def _position_detail(self, r) -> str:
        p = r.market_position
        return f'''<table class="detail-table">
<tr><td>定位</td><td><b>{p.position_type}</b> (基准: {p.benchmark_index})</td></tr>
<tr><td>Beta</td><td>{p.beta}</td></tr>
<tr><td>大盘跌日表现</td><td>平均 {p.bear_day_avg_return}% (抗跌评分 {p.anti_drop_score})</td></tr>
<tr><td>大盘涨日表现</td><td>平均 {p.bull_day_avg_return}% (领涨评分 {p.lead_rally_score})</td></tr>
</table><div class="diagnosis">{p.diagnosis}</div>'''

    # ------------------------------------------------------------------
    # CSS
    # ------------------------------------------------------------------

    def _css(self) -> str:
        return '''<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#0f0f1a;color:#e0e0e0;line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:20px}
header{text-align:center;padding:30px 0}
header h1{font-size:2em;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.code{font-size:0.6em;color:#888}
.meta{color:#888;margin-top:8px}
.card{background:#1a1a2e;border-radius:12px;padding:24px;margin:16px 0;box-shadow:0 4px 20px rgba(0,0,0,0.3)}
.category-card{display:flex;flex-direction:column;gap:12px}
.cat-header{display:flex;align-items:center;gap:12px}
.cat-label{display:inline-block;width:40px;height:40px;border-radius:50%;color:#fff;font-size:1.4em;font-weight:bold;text-align:center;line-height:40px}
.cat-name{font-size:1.3em;font-weight:bold;color:#fff}
.cat-conf{margin-left:auto;color:#aaa;font-size:0.9em}
.tactic{background:#16213e;padding:12px 16px;border-radius:8px;color:#90caf9;font-size:0.95em}
.secondary{color:#888;font-size:0.85em}
.badge{display:inline-block;padding:2px 10px;border-radius:10px;color:#fff;font-size:0.8em;margin:0 4px}
.dim-header{display:flex;justify-content:space-between;align-items:center}
.dim-score{font-size:2em;font-weight:bold}
.detail-table{width:100%;margin:12px 0;border-collapse:collapse}
.detail-table td{padding:8px 12px;border-bottom:1px solid #2a2a4a}
.detail-table td:first-child{color:#888;width:120px;white-space:nowrap}
.diagnosis{background:#16213e;padding:12px;border-radius:8px;margin-top:12px;color:#81d4fa;font-size:0.9em;border-left:3px solid #2196F3}
.legend{text-align:center;margin-top:8px;color:#888;font-size:0.85em}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px}
.dot.red{background:#f44336}.dot.yellow{background:#FF9800}
.line{display:inline-block;width:20px;height:2px;margin:0 4px;vertical-align:middle}
.line.blue{background:#2196F3}
.stats-row{display:flex;gap:12px;flex-wrap:wrap}
.stat-card{flex:1;min-width:150px;background:#1a1a2e;border-radius:12px;padding:20px;text-align:center}
.stat-num{font-size:2em;font-weight:bold;color:#fff}
.stat-label{color:#aaa;font-size:0.85em;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.85em}
thead{background:#16213e}
th,td{padding:8px;text-align:left;border-bottom:1px solid #2a2a4a}
.cat-dot{display:inline-block;width:24px;height:24px;border-radius:50%;color:#fff;text-align:center;line-height:24px;font-weight:bold;font-size:0.8em}
.diag{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#888}
footer{text-align:center;padding:30px;color:#555;font-size:0.8em}
</style>'''
