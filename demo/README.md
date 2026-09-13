# Interactive learning-loop demo

For the agreed loop behavior, final visual decisions, metric definitions, and the distinction between this scripted artifact and the real product, read the [project context](../docs/project-context.md).

## Pitch deck

[slides.html](slides.html) is the six-slide SILTA CAD pitch, with [presenter notes](guide.html). Open **http://127.0.0.1:8080/demo/slides.html** using the server below. The interactive demo and video areas are placeholders until the final presentation media is selected. Weave integration and ARIA's proposed evaluations are explicitly marked as unfinished.

Edit `scripts/pitch_template.html` and `docs/demo-3min.md`, then run `python scripts/build_demo_slides.py` (requires Python Markdown) to rebuild the deck. The team photo is embedded for standalone viewing.

## Interactive demo

[index.html](index.html) is the standalone export of the presentation demo.

From the repository root:

```sh
python -m http.server 8080 --bind 127.0.0.1
```

Open **http://127.0.0.1:8080/demo/** in a browser. No application build or Fusion connection is required. D3 and the fonts load from public CDNs, so the page needs internet access.

Use **Play demo**, **Next step**, or the completed-parts slider. The demo contains 54 shuffled example inputs, two feedback loops, eight learned tests, and an initially empty speed-instruction list. Each judge rejection adds one instruction. Charts use zero-based y-axes; the third averages final machining-time estimates over the latest 20 completed parts.

The opaque part marker moves over box content along connected paths: from a box centre to the outgoing arrow, through the arrow, and into the next box centre. It also travels back across the boxes to Input between parts instead of teleporting. Both desktop and mobile routes are checked for continuity.

The outcomes are scripted presentation data and are independent of the real Fusion runs documented in the repository README.

Playback follows one continuous curve across all 54 parts and their individual steps: `T(x) = 24000 * (1 - 1/sqrt(1 + 0.64*x)) / (1 - 1/sqrt(1 + 0.64*54))`, where `x` is fractional completed-part progress and `T` is elapsed milliseconds. The first parts take approximately 6.32, 3.42, 2.22, and 1.59 seconds, with no special timing switch after part 2. Total uninterrupted playback is 24 seconds. Frame delays are carried forward rather than added to each step. Pausing intentionally extends the presentation; a suspended browser tab cannot guarantee a wall-clock finish.

## Check the exported page

With Node.js 20 or later:

```sh
node demo/check-demo.cjs
```

This checks the JavaScript embedded in the exported HTML, including feedback routes, one instruction per judge rejection, replay state, and rolling-average calculations.
