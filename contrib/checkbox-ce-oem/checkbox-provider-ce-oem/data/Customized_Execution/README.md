# Customized Command Readme File

## Purpose

In most cases, the commands to be executed are written inside the Checkbox job's script, and full execution paths are not—and should not be—specified. However, due to the design of Checkbox Snap and the variety of binary installation methods (e.g., deb or snap), it is easy to execute a binary from the wrong path.

Therefore, we implemented a flexible approach that uses a predefined JSON file to define which commands to modify, allowing customized commands to be executed seamlessly within the same job.

## Design Concept

### Json Schema

```json
{
    <execuable_command>: {
        "LD_PATH": [],
        "<env key>": <value>,
        "<env key 2>": <value2>,
    }
}
```

- `LD_PATH` (optional) prepends entries to `LD_LIBRARY_PATH` before the command is run.
- Any other key/value pair is prepended as an environment variable assignment.

### Checkbox Environment Variable

`EXECUTABLE_JSON_PATH`: the path of predefined JSON file that need to be fed into Checkbox.
- No matter the file path is relative or absolute, we try to find it under `$PLAINBOX_PROVIDER_DATA` folder first
    - If you defiend it as `relative path` like `Customized_Execution/genio_customized_execution.json`, we will look for it from the `$PLAINBOX_PROVIDER_DATA/Customized_Execution/genio_customized_execution.json`
    - If the JSON file doesn't exist, then we will look for the file according to the value you defiended, in this example, it's `Customized_Execution/genio_customized_execution.json`. So, it means you can also use the `absolute path` to get the JSON file from anywhere.

## How to Use

### Without predefiend JSON

Suppose a Python script that needs to execute two commands, `foo` and `bar`, we don't hardcode the full path of them, instead, we tend to use the name of command like below

```python
# example.py
CMD_FOO="foo"   # suppose foo is installed via deb
CMD_BAR="bar"   # suppose bar is installed via snap
subprocess.run(CMD_FOO)
subprocess.run(CMD_BAR)
```

Checkbox Job Design
```
plugin: shell
id: ce-oem-demo/foo_bar
_summary: Execute foo and bar commands
command: example.py
```

In this way, Checkbox job will execute the `foo` and `bar` commands which be found in the `PATH` environment variable. For example, `/usr/bin/foo` and `/snap/bin/bar`.

### With predefiend JSON to build the customized command

Suppose you only want to customized your `foo` command to be `LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" hello="world" /usr/bin/foo`, you can prepare a predefined JSON file like below:

```json
// my_customized_cmd.json
{
    <foo>: {
        "LD_PATH": ["/path/to/lib1"],
        "hello": "world"
    }
}
```

Then create a JSON file and assign its file path to Checkbox Job's environment variable, [`EXECUTABLE_JSON_PATH`](#Checkbox-Environment-Variable).

```
plugin: shell
id: ce-oem-demo/foo_bar
_summary: Execute foo and bar commands
environ: PLAINBOX_PROVIDER_DATA EXECUTABLE_JSON_PATH
command: example.py
```

Import helper functions from `general_utils.py` into your script to
customize your commands.

```python
# example.py

from general_utils import resolve_executable_commands 

CMD_FOO="foo"
CMD_BAR="bar"

def resolve_commands(enable_logger: bool = False):
    resolved_commands = resolve_executable_commands(
        default_commands=[CMD_FOO, CMD_BAR],
        enable_logger=enable_logger,
    )
    return resolved_commands

customized_commands = resolve_commands(False)

print(customized_commands.get(CMD_FOO))
# LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" hello="world" /usr/bin/foo
print(customized_commands.get(CMD_BAR))
# /snap/bin/bar
```

### With decorator for single-command function

If your function takes a command argument (for example `cmd`), you can
use a decorator to resolve that argument at runtime.

```python
# example.py

from general_utils import with_resolved_commands

@with_resolved_commands
def run_cmd(cmd: str):
    print(f"Running: {cmd}")


run_cmd("foo")
# Running: LD_LIBRARY_PATH="/path/to/lib1:$LD_LIBRARY_PATH" hello="world" /usr/bin/foo
```

For functions that take a different argument name:

```python
@with_resolved_commands(target_arg="command", enable_logger=False)
def execute_tool(command: str, timeout: int = 10):
    print(f"Executing: {command} with timeout {timeout}")


execute_tool("foo")
```

For multi-command workflows, prefer the non-decorator example above
(`resolve_executable_commands`) to keep the logic explicit.
