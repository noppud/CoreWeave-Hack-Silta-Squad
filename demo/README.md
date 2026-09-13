# Interactive learning-loop demo

[index.html](index.html) is the standalone export of the presentation demo.

From the repository root:

```sh
python -m http.server 8080 --bind 127.0.0.1
```

Open **http://127.0.0.1:8080/demo/** in a browser. No application build or Fusion connection is required. D3 and the fonts load from public CDNs, so the page needs internet access.

Use **Play demo**, **Next step**, or the completed-parts slider. The demo contains 54 shuffled example inputs, two feedback loops, eight learned tests, and an initially empty speed-instruction list. Each judge rejection adds one instruction. Charts use zero-based y-axes; the third averages final machining-time estimates over the latest 20 completed parts.

The outcomes are scripted presentation data and are independent of the real Fusion runs documented in the repository README.

## Check the exported page

With Node.js 20 or later:

```sh
node demo/check-demo.cjs
```

This checks the JavaScript embedded in the exported HTML, including feedback routes, one instruction per judge rejection, replay state, and rolling-average calculations.
