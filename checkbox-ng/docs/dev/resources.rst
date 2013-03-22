Resources
=========

Resources are a mechanism that allows to constrain certain :term:`job` to
execute only on devices with appropriate hardware or software dependencies.
This mechanism allows some types of jobs to publish resource objects to an
abstract namespace and to a way to evaluate a resource program to determine if
a job can be started.

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

In addition to that, each resource expression must use exactly one variable,
which must be used like an object with attributes. The name of that variable
must correspond to the name of the job that generates resources. Attempts to
use more than one variable or to not use any variables are detected early and
rejected as invalid resource expressions.

The name of the variable determines which resource group to use. It must match
the name of the job that generates such resources.

In the examples elsewhere in this page the  ``package`` resources are generated
by the ``package`` job. PlainBox uses this to know which resources to try but
also to implicitly to express dependencies so that the ``package`` job does not
have to be explicitly selected and marked for execution prior to the job that
in fact depends on it. This is all done automatically.

Evaluation
----------

Due to mandatory compatibility with existing :term:`CheckBox` jobs there are
some unexpected aspects of how evaluation is performed. Those are marked as
**unexpected** below:

1. First PlainBox looks at the resource program and splits it into lines. Each
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

Exactly one variable per expression
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each resource expression must refer to exactly one variable. This is a side
effect of the way the evaluator works. It basically bind one object (a
particular resource) to that variable and evaluates the expression.

The expression parser / syntax analyzer identifies expressions with this
problem early and rejects them with an appropriate error message. Here are
some examples of hypothetical expressions that exhibit this problem.

"I want to have mplayer and an audio device so that I can play some sounds"::

    device.category == "AUDIO" and package.name == "mplayer"

To work around this, split the expression to two separate expressions. The
evaluator will put an implicit ``and`` between them and it will do exactly what
you intended::

    device.category == "AUDIO"
    package.name == "mplayer"

"I want to always run this test"::

    True

To work around this, simply remove the requirement program entirely!

"I want to never run this test"::

    False

To work around this remove this job from the selection. You may also use a
special resource that produces one constant value, and check that it is equal
to something different.

Exactly one resource bound to a variable at once
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It's not possible to refer to two different resources, from the same resource
group, in one resource expression. In other terms, the variable always points
to one object, it is not a collection of objects.

For example, let's consider this program::

    package.name == 'xorg' and package.name == 'procps'

Seemingly the intent was to ensure that both ``xorg`` and ```procps`` are
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
    touch_mode: dependant

    device_class: XITouchClass
    touch_mode: something else

Now, this expression will evaluate to ``True``, as the second resource fulfils
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

Considered enhancements
-----------------------

We are currently considering one improvement to resource programs. This would
allow us to introduce a fix that resolves some issues in a backwards compatible
way. Technical aspects are not yet resolved as that extension would not be
available in :term:`CheckBox` until CheckBox can be built on top of
:term:`PlainBox`

Implicit any(), explicit all()
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This proposal changes the way resource expressions are evaluated.

The implicit ``any()`` implemented as a loop over all resources from the
resource group designated by variable name would be configurable.

A developer may choose to wrap the whole expression in the ``all()`` function
to indicate that the expression inside ``all()`` must evaluate to ``True`` for
**all** iterations (all resources).

This would allow solving the case where a job can only run, for example, when a
certain package is **not** installed.  This could be expressed as::

    all(package.name != 'ubuntu-desktop')
