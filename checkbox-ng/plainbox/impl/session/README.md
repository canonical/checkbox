# System Information Collection

Checkbox collects various information about the system using Collectors.
A Collector is a class that wraps a tool that can provide a JSON-serializable
set of information.
When Checkbox starts, it uses these collectors to collect and store
in the session storage all the information it can gather. This is done before
the first session checkpoint is created. From then onward, these information
will remain in memory (and on disk in the checkpoint). When generating a
submission report, Checkbox will include all the information in a top-level
field of the json called "system_information".

## Format

A collector can either run succesfully or fail. Regardless of the result,
running a collector will create a new field in the submission file following
this format:

```
"system_information" : {
  collector_name : {
    "version" : collector_version,
    "success" : true/false,
    "outputs" : { ... }
}
```

The outputs field's format depends on the success of the collection.

If it ran successfully, the output field will have the follwing structure:

```
  "outputs" : {
    "json_output" : collector_json_output,
    "stderr" : collector_error_log
  }
```
Where the `collector_json_output` is either an array or a dictionary.

If it failed to run, the output field will have the following structure:

```
  "outputs" : {
    "stdout" : collector_output_log,
    "stderr" : collector_error_log
  }
```
Where `collector_error_log` and `collector_output_log` are a string.

## Creating new collectors

To create a new collector, one has to create a class that uses the
`CollectorMeta` metaclass. Additionally every collector has to define
a `COLLECTOR_NAME`. Refer to the docstring of `CollectorMeta` for a more
in-dept description.

> Note: Before creating a new collector, verify if the functionality that
> is needed is already implemented in an existing `collector`. If so, always
> prefer using an already existing collector than creating a new one


### Using external tools

If the collector needs a tool, it should be added, when appropriate, to the
vendorized section of Checkbox. Vendorization refers to the inclusion of
external resource to a project's codebase.

To vendorize a tool, locate the `vendor` module within Checkbox and place
the vendorized version of the tool there, add to `vendor/__init__.py`
the path to the executable that you have added.

**It is appropriate** to add a vendorized tool when it is an executable script
interpreted by any interpreter pre-installed on **every** version of Ubuntu that
Checkbox supports. The tool must have a compatible license with the Checkbox
license (GPLv3).

**It is not appropriate** to add a compiled tool of any kind. Since Checkbox
is designed to run on various architectures, compiled tools might not be
universally compatible, leading to operational issues.
