# ruff: noqa: E501
"""Build an offline browser deck from the actual drawing and local QR library."""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silta.presentation import DEFAULT_DEMO_URL, qr_svg

root = Path(__file__).resolve().parents[1]
drawing = base64.b64encode((root / "fixtures/demo/fixture-block-01.png").read_bytes()).decode()
qr = qr_svg(DEFAULT_DEMO_URL)
page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Silta CNC · Three-minute demo</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#071e2e;color:#eff6fa;font-family:Arial,Helvetica,sans-serif}
main{height:100dvh;display:grid;place-items:center}.slide{display:none;width:min(100vw,177.78vh);aspect-ratio:16/9;padding:5.3%;background:#0e3550;position:relative;overflow:hidden}.slide.active{display:flex;gap:5%;align-items:center}.copy{flex:1}h1{font-size:clamp(34px,5.4vw,78px);line-height:1.02;margin:0 0 28px;font-weight:600;letter-spacing:-.045em}h2{font-size:clamp(28px,4vw,58px);line-height:1.1;margin:0 0 32px;font-weight:500}p{font-size:clamp(16px,2vw,29px);line-height:1.4;color:#bdd6e5;margin:12px 0}.drawing{width:48%;max-height:82%;object-fit:contain;background:#fff}.name{color:#9cc0d6;font-size:clamp(15px,1.5vw,22px);margin-bottom:28px;letter-spacing:.12em}.metric{font-size:clamp(38px,6vw,85px);line-height:1.1;letter-spacing:-.035em}.metric span{color:#5cc894}.note{font-size:clamp(12px,1.2vw,18px);max-width:650px;margin-top:32px}.qr{background:#fff;padding:18px;width:230px;height:230px;display:grid;place-items:center}.qr svg{width:100%;height:100%}.right{display:flex;flex-direction:column;gap:16px;align-items:center;width:30%}a{color:#eff6fa;text-underline-offset:5px}nav{position:fixed;bottom:12px;right:18px;display:flex;gap:12px;align-items:center;font-size:13px}button{background:#134462;color:#eff6fa;border:1px solid #6fa3c2;padding:8px 12px;cursor:pointer}nav a{font-size:13px}.number{position:absolute;bottom:4%;left:5.3%;color:#9cc0d6;font-size:14px}.right p{text-align:center;font-size:18px}
@media print{main{display:block;height:auto}.slide{display:flex!important;width:100vw;height:56.25vw;page-break-after:always;print-color-adjust:exact}nav{display:none}}
</style><main>
<section class="slide active" aria-label="Slide 1">
<div class="copy"><div class="name">SILTA CNC</div><h1>Checked machining plans with memory</h1><p>The part stays fixed while the agent repairs the machining plan.</p><p class="note">A drawing, the available tools and a simulated cut make the result inspectable.</p></div>
<img class="drawing" alt="Actual synthetic demonstration drawing of the fixture block" src="data:image/png;base64,DRAWING">
<div class="number">1 / 2</div></section>
<section class="slide" aria-label="Slide 2">
<div class="copy"><div class="name">MEMORY WITH EVIDENCE</div><h2>The next run reuses what passed</h2><div class="metric">3 attempts first<br><span>1 attempt next</span></div><p>Fresh checks and simulation on both runs.</p><p class="note">Measured in the reproducible fixture demo with scripted candidate plans. The live workbench supports model inference. W&B records live experiments and marimo exposes the product.</p></div>
<div class="right"><div class="qr">QR</div><p><a href="LIVE" target="_blank" rel="noopener">Try Silta CNC</a></p></div>
<div class="number">2 / 2</div></section>
</main><nav><a href="http://localhost:2732" target="silta-demo">Open presenter notebook</a><button id="prev" aria-label="Previous slide">Previous</button><span id="count">1 / 2</span><button id="next" aria-label="Next slide">Next</button><button id="full">Fullscreen</button></nav>
<script>
let index=0;const slides=[...document.querySelectorAll('.slide')];
function show(n){index=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('active',i===index));document.querySelector('#count').textContent=(index+1)+' / 2';}
document.querySelector('#next').onclick=()=>show(index+1);document.querySelector('#prev').onclick=()=>show(index-1);document.querySelector('#full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(index+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(index-1)}if(e.key==='Home')show(0);if(e.key==='End')show(1)});
</script></html>"""
page = (
    page.replace("DRAWING", drawing)
    .replace(">QR<", ">" + qr + "<")
    .replace("LIVE", DEFAULT_DEMO_URL)
)
(root / "demo" / "slides.html").write_text(page)
print(root / "demo" / "slides.html")
