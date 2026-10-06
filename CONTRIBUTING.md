# Contributing

Small fixes and focused improvements are welcome. The Python CLI and native Mac
app share one sending engine. Keep protocol logic in `papir/`, UI in `macos/`,
planning in `planning/`, and original artwork in `art/`.

```sh
python3 -m pip install .
python3 test.py
python3 -m unittest discover -s macos/tests -v
```

For a Mac build, run `bash macos/build.sh`, then `bash macos/package.sh` and
`python3 macos/verify-package.py`. See `macos/README.md` for requirements.

Do not include client.json, account tokens, private keys, sign-in redirect URLs,
personal documents, or real device serials in code, tests, logs or issues.
Live sends are opt-in and should use your own account and a harmless test document.
