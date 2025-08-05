# <img src=https://code.visualstudio.com/assets/images/code-stable.png alt="Visual Studio Code" height=30 align="absmiddle">&nbsp;&nbsp;VS Code Development Setup

This directory contains VS Code configuration for the Checkbox project:
* [launch.json](./launch.json)
* [settings.json](./settings.json)


### Setup Python Interpreter
>**Precondition**: Setup Python virtual environment described in [CONTRIBUTING.md](../CONTRIBUTING.md#install-checkbox-and-its-providers-in-a-virtual-environment)

To set up the Python interpreter, follow these steps:
1. Open the command palette using `Ctrl + Shift + P`.
2. Type `Python: Select Interpreter` and press `Enter`.
3. Select `Python` from the virtual environment. For example, if you name your virtual environment `venv` and place it in the checkbox-ng directory, the path should be `./checkbox-ng/venv/bin/python`.
4. (Optional) Open the command palette again, type `Developer: Reload Window`, and press `Enter`. This ensures that the changes are applied.

### Unit Tests Discovery
Tests are discovered in [Test Explorer](https://code.visualstudio.com/docs/debugtest/testing#_automatic-test-discovery-in-testing-view). You can run and debug them. Currently, only tests from [checkbox-ng](../checkbox-ng/) are loaded in the Test Explorer.
Alternatively, you can run tests directly from the VS Code terminal:
```bash
pytest ./checkbox-ng        # run tests from checkbox-ng
pytest ./checkbox-support   # run tests from checkbox-support
```
### Run and Debug
The code can be run and debugged using the VS Code [Debugger](https://code.visualstudio.com/docs/debugtest/debugging#_debugger-user-interface). In the Debugger, the `Start Debugging` dropdown offers these options:
1. `Debug checkbox-cli` runs *checkbox-cli* in the integrated terminal with *--clear-cache* and *--clear-old-sessions* parameters.
2. `Debug checkbox-cli with args` prompts you to enter parameters and uses them to run *checkbox-cli*.
