# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo==0.24.2", "anywidget==0.11.0"]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    from pathlib import Path

    import anywidget
    import marimo as mo

    class CNCStoryboard(anywidget.AnyWidget):
        _esm = Path(__file__).with_name("loop_storyboard.js")

    mo.ui.anywidget(CNCStoryboard())
    return


if __name__ == "__main__":
    app.run()
