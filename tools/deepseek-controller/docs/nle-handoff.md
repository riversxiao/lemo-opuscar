# Controller → NLE handoff

After mux + `--delivery` PASS:

```sh
python3 tools/deepseek-controller/cli.py handoff --project /path/to/film --target both --lint
```

Or the POSIX wrappers: `tools/openfilm_handoff.sh`, `tools/hyperframes_export.sh`.

Full inventory / blockers: [`docs/integrations/nle-handoff.md`](../../../docs/integrations/nle-handoff.md).
