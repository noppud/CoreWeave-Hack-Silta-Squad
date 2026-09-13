# Imported pitch app

Imported from `Hackathon demo slide deck.zip` on 2026-09-13. The supplied design and content are retained. Both the full-size demo on slide 3 and the half-size demo on slide 4 load `../index.html` automatically. This is the repository's current timeline, not a copied or machine-specific version. Its latest update at integration was `6984406`; future updates to `demo/index.html` appear in both embeds.

From the repository root, run:

```sh
python -m http.server 8080 --bind 127.0.0.1
```

Open [the pitch app](http://127.0.0.1:8080/demo/pitch-app/SILTA%20Pitch%20Deck.dc.html). Keep `support.js` and `deck-stage.js` beside the HTML. Internet access is needed for the export's React/Babel runtime, external fonts and the timeline's CDN dependencies. **Unload demo** / **Load live demo** toggles both embeds. Playback controls work inside each embed; each has independent playback state.

The export runtime is deferred until the HTML is parsed to avoid its startup MutationObserver error. The ARIA arrow overlay ignores pointer events so the smaller demo remains interactive.

The current deck has 11 slides: the original seven story beats plus four evidence slides. The learning animation now has 27 illustrative parts. Product recording slots contain the 114-second film and cage/clevis motion plus finished-stock clips. The actual stage drawing and CAD preview are included. See [the evidence map](evidence/README.md) for exact sources, measurement scope, and media hashes.

Use arrow keys or the sidebar to navigate and each video's play control to start the recording. All media are relative files and travel with the `demo` directory. The imported runtime and fonts still need internet access. `github.md` is historical export metadata; its earlier slide count is stale.
