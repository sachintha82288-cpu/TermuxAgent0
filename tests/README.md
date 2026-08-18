# Tests

This directory contains helpers for verifying TermuxAgent0 end-to-end.

## mock_server.py

A tiny OpenAI-compatible HTTP server used to test the agent without hitting a
real LLM. It understands three scenarios triggered by keywords in the user message:

- `shell_test` → asks the client to run `shell("echo hello from mock")`
- `file_test` → asks for `write_file` + `read_file` in parallel
- `ls_test` → asks the client to `ls("/tmp")`
- anything else → streams a short greeting

### Run the mock + agent manually

```bash
# terminal 1
python tests/mock_server.py          # listens on http://127.0.0.1:8765/v1

# terminal 2
python main.py --api-key test --base-url http://127.0.0.1:8765/v1 -m test-model
# then type: shell_test   /   file_test   /   ls_test   /   hello
```

The server prints each request it receives so you can observe the tool-call
loop in action without spending API credits.
