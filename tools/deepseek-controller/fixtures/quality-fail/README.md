# quality-fail fixture

Run:

```bash
python3 tools/deepseek-controller/cli.py quality \
  --project tools/deepseek-controller/fixtures/out-swiss-motion \
  --skip-heavy --allow-unchecked \
  --force-fail fixture_forced_fail \
  -o tools/deepseek-controller/fixtures/quality-fail/quality.json
```

Expect exit 1 and `overall=FAIL`.

`tests/test_mvp.sh` runs the same command on a scratch copy of `out-swiss-motion` and writes its report to a temp dir, so the committed `quality.json` is a sample report only (its absolute paths come from the machine that produced it).
