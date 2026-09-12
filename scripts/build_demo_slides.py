# ruff: noqa: E501
"""Build an offline browser deck from the actual drawing and local QR library."""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silta.presentation import DEFAULT_DEMO_URL, qr_svg

root = Path(__file__).resolve().parents[1]
drawing = base64.b64encode((root / "fixtures/demo/fixture-block-01.png").read_bytes()).decode()
qr = qr_svg(DEFAULT_DEMO_URL)
evaluation = json.loads((root / "demo/evals.json").read_text())
eval_rows = "".join(
    f"<tr><td>{b['display_split']}</td><td>{b['policy']}</td>"
    f"<td>{b['matched']} / {b['cases']}</td><td>{b['simulations']}</td></tr>"
    for b in evaluation["batches"]
)
revised = [b for b in evaluation["batches"] if b["policy"] == "policy-v1"]
eval_title = f"{sum(b['matched'] for b in revised)} / {sum(b['cases'] for b in revised)} fixture expectations matched"
page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Silta CNC · Three-minute demo</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#071e2e;color:#eff6fa;font-family:Arial,Helvetica,sans-serif}
main{height:100dvh;display:grid;place-items:center}.slide{display:none;width:min(100vw,177.78vh);aspect-ratio:16/9;padding:5.3%;background:#0e3550;position:relative;overflow:hidden}.slide.active{display:flex;gap:5%;align-items:center}.copy{flex:1}h1{font-size:clamp(34px,5.4vw,78px);line-height:1.02;margin:0 0 28px;font-weight:600;letter-spacing:-.045em}h2{font-size:clamp(28px,4vw,58px);line-height:1.1;margin:0 0 32px;font-weight:500}p{font-size:clamp(16px,2vw,29px);line-height:1.4;color:#bdd6e5;margin:12px 0}.drawing{width:48%;max-height:82%;object-fit:contain;background:#fff}.name{color:#9cc0d6;font-size:clamp(15px,1.5vw,22px);margin-bottom:28px;letter-spacing:.12em}.metric{font-size:clamp(38px,6vw,85px);line-height:1.1;letter-spacing:-.035em}.metric span{color:#5cc894}.note{font-size:clamp(12px,1.2vw,18px);max-width:650px;margin-top:32px}.qr{background:#fff;padding:18px;width:230px;height:230px;display:grid;place-items:center}.qr svg{width:100%;height:100%}.right{display:flex;flex-direction:column;gap:16px;align-items:center;width:30%}a{color:#eff6fa;text-underline-offset:5px}nav{position:fixed;bottom:12px;right:18px;display:flex;gap:12px;align-items:center;font-size:13px}button{background:#134462;color:#eff6fa;border:1px solid #6fa3c2;padding:8px 12px;cursor:pointer}nav a{font-size:13px}.number{position:absolute;bottom:4%;left:5.3%;color:#9cc0d6;font-size:14px}.right p{text-align:center;font-size:18px}
@media print{main{display:block;height:auto}.slide{display:flex!important;width:100vw;height:56.25vw;page-break-after:always;print-color-adjust:exact}nav{display:none}}
.wide{width:100%}.eval-table{width:100%;border-collapse:collapse;font-size:clamp(17px,1.8vw,28px);margin-top:12px}th,td{text-align:left;border-bottom:1px solid #54748b;padding:12px 16px 12px 0}th{color:#9cc0d6;font-weight:400}.flow{font-size:clamp(24px,3vw,44px);line-height:1.5;margin:0}.green{color:#5cc894}.slide h2{margin-bottom:24px}.eval-note{font-size:clamp(14px,1.5vw,23px);margin-top:20px}nav{background:#071e2e;padding:6px}nav a{margin-right:6px}
</style><main>
<section class="slide active" aria-label="Slide 1">
<div class="copy"><div class="name">SILTA CNC</div><h1>Checked machining plans with memory</h1><p>The part stays fixed while the agent repairs the machining plan.</p><p class="note">A drawing, the available tools and a simulated cut make the result inspectable.</p></div>
<img class="drawing" alt="Actual synthetic demonstration drawing of the fixture block" src="data:image/png;base64,DRAWING">
<div class="number">1 / 5</div></section>
<section class="slide" aria-label="Slide 2">
<div class="wide"><div class="name">THE REPAIR LOOP</div><h2>A fixed target, a revisable process</h2>
<p class="flow">Drawing + shop tools → fixed CAD<br>CAM plan → checks → simulated cut</p>
<p class="flow green">Failure evidence → repair → verify again</p>
<p class="eval-note">Memory stores attempts and passing recipes. Reuse still requires fresh verification.</p>
<p class="note"><a href="http://localhost:2732/" target="silta-demo">Open the interactive demo</a> · Scripted candidate plans; real checks, simulation and memory.</p></div>
<div class="number">2 / 5</div></section>
<section class="slide" aria-label="Slide 3">
<div class="wide"><div class="name">OFFLINE POLICY EVALS</div><h2>EVAL_TITLE</h2>
<table class="eval-table"><thead><tr><th>Fixture split</th><th>Check policy</th><th>Matches</th><th>Simulations</th></tr></thead><tbody>EVAL_ROWS</tbody></table>
<p class="eval-note">The clamp collision is caught before simulation under v1.</p>
<p class="note">Fixed plans, 12 synthetic fixtures. Expected rejections count as correct. Former holdout cases were used in an earlier fix; these are regression evals.<br><a href="evals.html" target="silta-evals">Inspect every case and the raw results</a></p></div>
<div class="number">3 / 5</div></section>
<section class="slide" aria-label="Slide 4">
<div class="copy"><div class="name">MEMORY WITH EVIDENCE</div><h2>The next run reuses what passed</h2><div class="metric">3 attempts first<br><span>1 attempt next</span></div><p>Fresh checks and simulation on both runs.</p><p class="note">Measured in the reproducible fixture demo with scripted candidate plans. The live workbench supports model inference. W&B records live experiments and marimo exposes the product.</p></div>
<div class="number">4 / 5</div></section>
<section class="slide" aria-label="Slide 5">
<div class="copy"><div class="name">SILTA CNC</div><h2>Inspect the result yourself</h2><p>Rotate the part. Inspect the checks.<br>See which recipe the system reused.</p><p class="note">Marimo is the interactive product surface.<br>W&B Charts records live-run metrics.<br>CNC traces and sandbox lesson validation remain integration work.</p></div>
<div class="right"><div class="qr">QR</div><p><a href="LIVE" target="_blank" rel="noopener">Try Silta CNC</a></p></div>
<div class="number">5 / 5</div></section>
</main><nav><a href="guide.html" target="silta-guide">Pitch guide</a><a href="evals.html" target="silta-evals">Evals</a><a href="http://localhost:2732" target="silta-demo">Demo</a><button id="prev" aria-label="Previous slide">Previous</button><span id="count">1 / 5</span><button id="next" aria-label="Next slide">Next</button><button id="full">Fullscreen</button></nav>
<script>
let index=0;const slides=[...document.querySelectorAll('.slide')];
function show(n){index=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('active',i===index));document.querySelector('#count').textContent=(index+1)+' / '+slides.length;history.replaceState(null,'','#'+(index+1));}
document.querySelector('#next').onclick=()=>show(index+1);document.querySelector('#prev').onclick=()=>show(index-1);document.querySelector('#full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(index+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(index-1)}if(e.key==='Home')show(0);if(e.key==='End')show(slides.length-1)});
show((parseInt(location.hash.slice(1),10)||1)-1);
addEventListener('hashchange',()=>show((parseInt(location.hash.slice(1),10)||1)-1));
</script></html>"""
page = (
    page.replace("DRAWING", drawing)
    .replace(">QR<", ">" + qr + "<")
    .replace("LIVE", DEFAULT_DEMO_URL)
    .replace("EVAL_TITLE", eval_title)
    .replace("EVAL_ROWS", eval_rows)
)
(root / "demo" / "slides.html").write_text(page)
print(root / "demo" / "slides.html")
