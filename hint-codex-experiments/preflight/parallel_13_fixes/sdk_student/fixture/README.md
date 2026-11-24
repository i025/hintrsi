# Window report

`window_report.py` loads observations from the twenty JSON shards in `data/` and reports the count, total value, and first and last timestamps inside a requested window.

Run the checks with `python -m unittest -v test_window_report.py`.

Run a report with `python window_report.py data 0 39`.

Provider-neutral repository: OpenAI and Anthropic clients are independent integrations. The window-report issue does not change either provider.
