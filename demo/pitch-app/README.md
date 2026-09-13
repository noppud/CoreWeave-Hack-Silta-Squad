# Imported pitch app

Imported from `Hackathon demo slide deck.zip` on 2026-09-13. The supplied design and content are retained. Both the full-size demo on slide 3 and the half-size demo on slide 4 load `../index.html` automatically. This is the repository's current timeline, not a copied or machine-specific version. Its latest update at integration was `6984406`; future updates to `demo/index.html` appear in both embeds.

From the repository root, run:

```sh
python -m http.server 8080 --bind 127.0.0.1
```

Open [the pitch app](http://127.0.0.1:8080/demo/pitch-app/SILTA%20Pitch%20Deck.dc.html). Keep `support.js` and `deck-stage.js` beside the HTML. Internet access is needed for the export's React/Babel runtime, external fonts and the timeline's CDN dependencies. **Unload demo** / **Load live demo** toggles both embeds. Playback controls work inside each embed; each has independent playback state.

The export runtime is deferred until the HTML is parsed to avoid its startup MutationObserver error. The ARIA arrow overlay ignores pointer events so the smaller demo remains interactive.

`github.md` is metadata supplied by the export; its earlier slide count may differ from the final HTML. Product recordings remain placeholders in this export.
