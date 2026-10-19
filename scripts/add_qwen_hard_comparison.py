#!/usr/bin/env python3
"""Add the frozen Qwen C/pi run to the existing static hard-all gallery."""
import argparse
import hashlib
import json
import re
import shutil
import statistics as stats
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path, help='pi-abcd run containing C/pi and gallery-metrics.json')
parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1] / 'hard-all-model-comparison')
args = parser.parse_args()
site, run = args.site, args.run
page = site / 'index.html'
html = page.read_text()
pattern = r'window\.__STATIC_RESULTS__ = (.*?);</script>'
data = json.loads(re.search(pattern, html, re.S).group(1))
model = 'qwen-3.8-27b-c'
label = 'Qwen 3.8 27B · Pi C'
gallery = json.loads((run / 'gallery-metrics.json').read_text())
data['models'] = [m for m in data['models'] if m['id'] != model] + [{'id': model, 'label': label}]
records = []
for item in data['items']:
    case = item['id']
    source = run / 'C/pi' / case
    evaluation = json.loads((source / 'evaluation.json').read_text())
    artifact = evaluation['last_renderable']
    assert artifact['renderable'] and evaluation['success'], case
    assert hashlib.sha256((source / 'reference.jpg').read_bytes()).digest() == hashlib.sha256((site / item['reference']).read_bytes()).digest(), case
    svg = source / artifact['svg']
    assert hashlib.sha256(svg.read_bytes()).hexdigest() == artifact['sha256'], case
    visual = gallery['images'][f'C/pi/{case}/{artifact["preview"]}']
    root = ET.parse(svg).getroot()
    tags = [e.tag.split('}')[-1] for e in root.iter()]
    # Published SVGs must be self-contained; previews are the frozen scored PNGs.
    for e in root.iter():
        for key, value in e.attrib.items():
            if key.endswith('href'):
                assert value.startswith(('data:', '#')), (case, value[:80])
    dest = site / 'runs' / model / case
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(svg, dest / 'figure.svg')
    shutil.copy2(source / artifact['preview'], dest / 'preview.png')
    record = {'model': model, 'state': 'complete', 'svg': f'./runs/{model}/{case}/figure.svg',
              'preview': f'./runs/{model}/{case}/preview.png', 'pptx': None, 'trace': None,
              'elapsed_seconds': evaluation['elapsed_seconds'], 'model_turns': evaluation['cost']['model_calls'],
              'normal_completion': evaluation['normal_completion'], 'budget_exhausted': evaluation['budget_exhausted'],
              'metrics': {'visual': {k: visual[k] for k in ('ssim','lpips','psnr','foreground_iou')},
                          'metric_size': visual['metric_size'], 'reference_size': visual['reference_size'],
                          'svg': {'native_drawable_count': sum(tags.count(t) for t in ('path','rect','circle','ellipse','line','polyline','polygon','text')), 'text_count': tags.count('text')},
                          'output_tokens': evaluation['cost']['tokens']['output']}}
    item['results'] = [r for r in item['results'] if r['model'] != model] + [record]
    records.append(record)
summary = data['summary']
summary['total_runs'] = len(data['models']) * len(data['items'])
for key in ('completed_by_model','available_by_model'):
    summary[key][model] = len(records)
metric = {'case_count': len(records), 'success_count': len(records), 'metric_count': len(records),
          'elapsed_median_seconds': stats.median(r['elapsed_seconds'] for r in records),
          'svg_native_drawable_mean': stats.mean(r['metrics']['svg']['native_drawable_count'] for r in records),
          'output_tokens_mean': stats.mean(r['metrics']['output_tokens'] for r in records)}
for key in ('ssim','lpips','psnr','foreground_iou'):
    metric[key + '_mean'] = stats.mean(r['metrics']['visual'][key] for r in records)
summary['metrics_by_model'][model] = metric
turns = [r['model_turns'] for r in records]
summary['model_turns_by_model'][model] = {'count':len(turns),'total':sum(turns),'mean':stats.mean(turns),'median':stats.median(turns),'min':min(turns),'max':max(turns)}
for baseline in [m['id'] for m in data['models'] if m['id'] != model]:
    deltas = [next(r for r in i['results'] if r['model']==model)['metrics']['visual']['ssim'] - next(r for r in i['results'] if r['model']==baseline)['metrics']['visual']['ssim'] for i in data['items']]
    summary['comparisons'][f'{model}_vs_{baseline}'] = {'baseline':baseline,'candidate':model,'metric':'ssim','paired_count':len(deltas),'wins':sum(d>0 for d in deltas),'ties':sum(d==0 for d in deltas),'losses':sum(d<0 for d in deltas),'mean_delta':stats.mean(deltas)}
summary['qwen_source'] = {'run':run.name,'group':'C/pi','model':'qwen38-27b','thinking':'xhigh','turn_budget':20,'artifact':'last_renderable','metric_method':gallery['method'],'normal_completion_count':sum(r['normal_completion'] for r in records)}
data['generated_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
html = re.sub(pattern, lambda _: 'window.__STATIC_RESULTS__ = ' + json.dumps(data, ensure_ascii=False) + ';</script>', html, flags=re.S)
html = html.replace('三组 Codex 模型', 'GPT-6、GPT-5.6 与 Qwen 3.8 27B 模型').replace('三组', '四组')
html = html.replace('repeat(4, minmax(270px, 1fr))', 'repeat(5, minmax(270px, 1fr))')
html = html.replace('lazyImage(result.svg,', 'lazyImage(result.preview || result.svg,')
html = html.replace('${stateLabels[result.state]}${result.elapsed_seconds', '${result.budget_exhausted ? "预算耗尽 · 有产物" : stateLabels[result.state]}${result.elapsed_seconds')
html = html.replace('>Turns：${escapeHtml(stats.model_turns_method', '>Codex Turns：${escapeHtml(stats.model_turns_method')
note = 'Qwen 3.8 27B：Pi C 组，xhigh，直接生成初版后自由迭代，最多 20 次上游调用（含重试、压缩），展示最后可渲染版本；20/20 有产物不代表全部正常结束。Qwen 使用冻结 Chromium 预览，白底 RGB、最长边 960、SSIM / AlexNet LPIPS / PSNR / 前景 IoU；未使用原尺寸 SSIM。GPT 保留原有历史结果与指标，工作流、渲染环境、预算和 Turns 统计口径不同，本页用于结果对照，不是同条件模型排名。Qwen 仅生成 SVG，PPT 与命令统计缺项显示 —。'
if 'id="qwen-method"' not in html:
    html = html.replace('<div id="metrics-overview"></div>', '<div id="metrics-overview"></div>\n<p class="metrics-empty" id="qwen-method">' + note + ' <a href="comparison-data.json">下载完整对比数据 JSON</a></p>')
page.write_text(html)
(site / 'comparison-data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(metric, indent=2))
print('Added', len(records), 'Qwen results; total', summary['total_runs'])
