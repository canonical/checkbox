==================
Resource Job Units
==================

Resources
=========

Resources are a mechanism that allows to constrain certain job to
execute only on devices with appropriate hardware or software dependencies.
This mechanism allows some types of jobs to publish resource objects to an
abstract namespace and to a way to evaluate a resource program to determine if
a job can be started.

Resources also serve as a 'generator' for template units.
See :ref:`templates`

Resource Jobs
-------------

Resource Jobs are jobs with a plugin set to resource::

    plugin: resource

Command that they run should print resource information in a predefined manner.
This command may be considered a Resource Program

Resource programs
-----------------

Resource programs are multi-line statements that can be embedded in job
definitions. By far, the most common use case is to check if a required package
is installed, and thus, the job can use it as a part of a test. A check like
this looks like this::

    package.name == "fwts"

This resource program codifies that the job needs the ``fwts`` package to run.
There is a companion job with the same name that interrogates the local package
database and publishes a set of resource objects. Each such object is a
collection of arbitrary key-value pairs. The ``package`` job simply publishes
the ``name`` and ``version`` of each installed package but the mechanism is
generic and applies to all resources.

As stated, resource programs can be multi-line, a real world example of that is
presented below::

     device.category == 'CDROM'
     optical_drive.cd == 'writable'

This example is much like the one above, referring to some resources, here
coming from jobs ``device`` and ``optical_drive``. What is important to point
out is that, as a rule of a thumb, multi line programs have an implicit ``and``
operator between each line. This program would only evaluate to True if there
is a writable CD-ROM available.

Each resource program is composed of resource expressions. Each line maps
directly onto one expression so the example program above uses two resource
expressions.

Resource expressions
--------------------

Resource expressions are evaluated like normal python programs. They use all of
the same syntax, semantics and behavior. None of the operators are overridden
to do anything unexpected. The evaluator tries to follow the principle of least
surprise but this is not always possible.

Resource expressions cannot execute arbitrary python code. In general almost
everything is disallowed, except as noted below:

* Expressions can use any literals (strings, numbers, True, False, lists and tuples)
* Expressions can use boolean operators (``and``, ``or``, ``not``)
* Expressions can use all comparison operators
* Expressions can use all binary and unary operators
* Expressions can use the set membership operator (``in``)
* Expressions can use read-only attribute access

Anything else is rejected as an invalid resource expression.

In addition to that, each resource expression must use at least one variable,
which must be used like an object with attributes. The name of that variable
must correspond to the name of the job that generates resources. You can use
the ``imports`` field (at a job definition level) to rename a resource job to
be compatible with the identifier syntax. It can also be used to refer to
resources from another namespace.

In the examples elsewhere in this page the  ``package`` resources are generated
by the ``package`` job. Plainbox uses this to know which resources to try but
also to implicitly to express dependencies so that the ``package`` job does not
have to be explicitly selected and marked for execution prior to the job that
in fact depends on it. This is all done automatically.

Example
-------

The job definition below generates a RTC resource::

    id: rtc
    estimated_duration: 0.02
    plugin: resource
    command:
      if [ -e /sys/class/rtc ]
      then
          echo "state: supported"
      else
          echo "state: unsupported"
      fi
    _description: Creates resource info for RTC

Next let's define a Job that uses that resource.

.. note:
    This job uses two other resources as well, skipped for brevity.

::

    plugin: shell
    category_id: com.canonical.plainbox::power-management
    id: power-management/rtc
    requires:
      rtc.state == 'supported'
      package.name == 'util-linux'
      cpuinfo.other != 'emulated by qemu'
    user: root
    command: hwclock -r
    estimated_duration: 0.02
    _summary: Test that RTC functions properly (if present)
    _description:
     Verify that the Real-time clock (RTC) device functions properly, if present.

Now the power-management/rtc job will only be run on systems where
``/sys/class/rtc`` directory exists (which is true for systems supporting RTC)

Evaluation
----------

1. First Plainbox looks at the resource program and splits it into lines. Each
   non-empty line is parsed and converted to a resource expression.

2. **unexpected** Each resource expression is repeatedly evaluated, once for
   each resource from the group determined by the variable name. All exceptions
   are silently ignored and treated as if the iteration had evaluated to False.
   The whole resource expression evaluates to ``True`` if any of the iterations
   evaluated to ``True``. In other words, there is an implicit ``any()`` around
   each resource expression, iterating over all resources.

3. **unexpected** The resource program evaluates to ``True`` only if all
   resource expressions evaluated to ``True``. In other words, there is an
   implicit ``and`` between each line.

Limitations
-----------

The design of resource programs has the following shortcomings. The list is
non-exhaustive, it only contains issues that we came across found not to work
in practice.

Joins are not optimized
^^^^^^^^^^^^^^^^^^^^^^^

Starting with plainbox 0.24, a resource expression can use more than one
resource object (resource job) at the same time. This allows the use of joins
as the whole expression is evaluated over the cartesian product of all the
resource records. This operation is not optimized, you can think of it as a
JOIN that is performed on a database without any indices.

Let's look at a practical example::

    package.name == desired_package.name

Here, two resource jobs would run. The classic *package* resource (that
produces, typically, a great number of resource records, one for each package
installed on the system) and a hypothetical *desired_package* resource (for
this example let's pretend that it is a simple constant resource that just
contains one object). Here, this operation is not any worse than before because
``size(desired_package) * size(package)`` is not any larger. If, however,
*desired_package* was on the same order as *package* (approximately a thousand
resource objects). Then the computational cost of evaluating that expression
would be quadratic.

In general, the cost, assuming all resources have the same order, is
exponential with the number of distinct resource jobs referenced by the
expression.

Exactly one resource bound to a variable at once
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It's not possible to refer to two different resources, from the same resource
group, in one resource expression. In other terms, the variable always points
to one object, it is not a collection of objects.

For example, let's consider this program::

    package.name == 'xorg' and package.name == 'procps'

Seemingly the intent was to ensure that both ``xorg`` and ``procps`` are
installed. The reason why this does not work is that at each iteration of the
the expression evaluator, the name ``package`` refers to exactly one resource
object. In other words, that expression is equivalent to this one::

    A == True and A == False

This type of error is not captured by our limited semantic analyzer. It will
silently evaluate to False and inhibit the job from being stated.

To work around this, split the expression to two consecutive lines. As stated
in rule 3 in the list above, there is an implicit ``and`` operator between all
expressions. A working example that expresses the same intent looks like this::

    package.name == 'xorg'
    package.name == 'procps'

Operator != is useless
^^^^^^^^^^^^^^^^^^^^^^

This is strange at first but quickly becomes obvious once you recall rule 2
from the list above. That rule states that the expression is evaluated
repeatedly for each resource from a particular group and that any ``True``
iteration marks the whole expression as ``True``).

Let's look at a real-world example::

    xinput.device_class == 'XITouchClass' and xinput.touch_mode != 'dependent'

So seemingly, the intent here was to have at least ``xinput`` resource with a
``device_class`` attribute equal to ``XITouchClass`` that has ``touch_mode``
attribute equal to anything but ``dependent``.

Now let's assume that we have exactly two resources in the ``xinput`` group::

    device_class: XITouchClass
    touch_mode: dependent

    device_class: XITouchClass
    touch_mode: something else

Now, this expression will evaluate to ``True``, as the second resource fulfills
the requirements. Is this what the test designer had expected? That's hard to
say. The problem here is that this expression can be understood as *at least
one resource isn't something* **or** *all resources weren't something*. Both
are equally valid desires and, depending on how the test is implemented, may or
many not work correctly in practice.

Currently there is no workaround. We are considering adding a new syntax that
would allow to specify this explicitly. The proposal is documented below as
"implicit any(), explicit all()"

Everything is a string
^^^^^^^^^^^^^^^^^^^^^^

Resource programs are regular python programs evaluated in unusual ways but
all of the variables that are exposed through the resource object are strings.

This has considerable impact on comparison, unless you are comparing to a
string the comparison will always silently fail as python has dynamic but
strict, not loose types (there is no implicit type conversion). To alleviate
this problem several type names / conversion functions are allowed in
requirement programs. Those are:

* :py:class:`int`, to convert to integer numbers
* :py:class:`float`, to convert to floating point numbers
* :py:class:`bool`, to convert to a boolean context
