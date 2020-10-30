.. _nested-test-plan:

Checkbox nested test plans tutorial
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We designed checkbox to consume test providers. Hence the test harness and the
tests are completely separated. Checkbox can load tests from multiple providers.
They can be installed as Debian packages or loaded from source to build a snap.

To load the tests and run them we need a test plan. Test plans for checkbox are
a collection of job (test) ids meant to be run one by one.

Most of the time when we create a new test plan, there's a need to include a 
generic section, common to several other test plans. But the test plan unit was 
not allowing such feature and we ended up having a lot of duplication across 
our projects. And duplication means duplicated efforts to maintain all those 
test plan sections in sync and up-to-date.

What if it could be possible now to have nested test plans. One being built by
aggregating sections from one or more "base test plans"?

Let's review in detail this new feature available in checkbox since plainbox 0.29

Quick start
===========

The only thing to add to your test plan is the identifier of the test plan you
want to include, as follow:

::

    nested_part:
        com.canonical.certification::my_base_test_plan

The test plan order will then be test plan ``include`` + all nested test plan 
``include``, in that order.

Loading nested parts will load the ``include``, ``mandatory_include`` and 
``bootstrap_include`` sections and all the overrides (``category``, 
``certification status``).

Note: All mandatory includes will always be run first.

Note: Job and test plan ids can be listed in their abbreviated form (without 
the namespace prefix) if the job definitions reside in the same namespace as 
the provider that is defining the test plan.

Use cases
=========

All the following examples are available here: 
https://github.com/yphus/nested_testplan_demo To test them locally you just 
need to develop the 3 providers and run one of the demo launchers:

::

    git clone https://github.com/yphus/nested_testplan_demo.git
    cd nested_testplan_demo/
    find . -name manage.py -exec {} develop \;
    ./demo1 # or demo2, 3, 4, 5, 6.

How to use a base test plan?
----------------------------

Let's use two providers, both belonging to the same namespace, ``com.ubuntu``:

``com.ubuntu:foo`` and ``com.ubuntu:baz``

Baz provider contains the following units, 4 jobs and a test plan (our base 
test plan):

::

    id: hello
    command: echo hello
    flags: simple
    
    id: bye
    command: echo bye
    flags: simple
    
    id: mandatory
    command: true
    flags: simple
    
    id: bootstrap
    command: echo os: ubuntu
    plugin: resource
    flags: simple
    
    unit: test plan
    id: baz_tp
    _name: Generic baz test plan
    _description: This test plan contains generic test cases
    estimated_duration: 1m
    include:
        hello       certification-status=blocker
        bye         certification-status=non-blocker
    mandatory_include:
        mandatory   certification-status=blocker
    bootstrap_include:
        bootstrap

Foo provider contains two new tests:

::

    id: always-pass
    command: true
    flags: simple
    
    id: always-fail
    command: true
    flags: simple

We want to reuse the ``baz_tp`` in a new test plan (in the Foo provider) with 
the two new tests. Such test plan will look like this:


::

    unit: test plan
    id: foo_tp_1
    _name: Foo test plan 1
    _description: This test plan contains generic tests + 2 new tests
    include:
        always-pass       certification-status=blocker
        always-fail
    nested_part:
        baz_tp

The jobs execution order is:

- ``bootstrap``
- ``mandatory``
- ``always-pass``
- ``always-fail``
- ``hello``
- ``bye``

How to use a base test plan, but without running them last?
-----------------------------------------------------------

Let's keep the previous providers, Foo and Baz. This time we want to run the 
base test plan between ``always-pass`` and ``always-fail``. In order to change 
the job execution order, the new test plan will be made of several nested 
parts, since they will follow the list order. Let's create in the Foo provider
2 new test plans that we'll use as nested parts to fine tune the job ordering:

::

    unit: test plan
    id: foo_tp_part1
    _name: Foo test plan part 1
    _description: This test plan contains part 1
    estimated_duration: 1m
    include:
        always-pass       certification-status=blocker
    
    unit: test plan
    id: foo_tp_part2
    _name: Foo test plan part 2
    _description: This test plan contains part 2
    estimated_duration: 1m
    include:
        always-fail

The final test plan will only contain nested parts:

::

    unit: test plan
    id: foo_tp_2
    _name: Foo test plan 2
    _description:
     This test plan contains generic tests + 2 new tests (but ordered differently)
    include:
    nested_part:
        foo_tp_part1
        baz_tp
        foo_tp_part2

Note: Always keep the ``include`` section (even empty) as this field is 
mandatory and validation would fail otherwise (and the test plan would never be loaded 
by checkbox)

The jobs execution order is:

- ``bootstrap``
- ``mandatory``
- ``always-pass``
- ``hello``
- ``bye``
- ``always-fail``

How to change category or certification status of jobs coming from nested parts?
--------------------------------------------------------------------------------

The `test plan override mechanism
<http://plainbox.readthedocs.io/en/latest/manpages/plainbox-test-plan-units.html?highlight=category-overrides>`_
still works with nested parts. For example the ``hello`` job from the Baz
provider was defined as a blocker and did not have a category.

Let's update the previous use case:

::

    unit: test plan
    id: foo_tp_3
    _name: Foo test plan 3
    _description: This test plan contains generic tests + 2 new tests + overrides
    include:
        always-pass       certification-status=blocker
        always-fail
    nested_part:
        baz_tp
    certification_status_overrides:
        apply non-blocker to hello
    category_overrides:
        apply com.canonical.plainbox::audio to hello

To check that overrides worked as expected, you can open the json exporter 
report:

::

    "result_map": {
        "com.ubuntu::hello": {
            "summary": "hello",
            "category_id": "com.canonical.plainbox::audio",
            "certification_status": "non-blocker"
    [...]

How to include a nested part from another namespace?
----------------------------------------------------

You can include a nested part from another namespace, just prefix the test plan
identifier with the provider namespace.

Let's use a third provider (Bar, under the ``com.ubuntu`` namespace) as an
example:

::

    id: sleep
    command: sleep 1
    flags: simple
    
    id: uname
    command: uname -a
    flags: simple
    
    unit: test plan
    id: bar_tp
    _name: bar test plan
    _description: This test plan contains bar test cases
    estimated_duration: 1m
    include:
        sleep
        uname

Now in provider Foo, a test plan including a part from provider Bar will look 
like this:

::

    unit: test plan
    id: foo_tp_4
    _name: Foo test plan 4
    _description:
     This test plan contains generic tests + 2 new tests + 2 tests from a
     different namespace provider
    include:
        always-pass       certification-status=blocker
        always-fail
    nested_part:
        baz_tp
        com.ubuntu::bar_tp

The jobs execution order is:

- ``bootstrap``
- ``mandatory``
- ``always-pass``
- ``always-fail``
- ``hello``
- ``bye``
- ``sleep``
- ``uname``

Is it possible to have multiple levels of nesting?
--------------------------------------------------

Yes, it's possible to have multiple levels of nesting, a nested part being 
built from another nested part, each level bringing its own set of new tests.

Let's add a new test plan to provider Baz:

::

    unit: test plan
    id: baz_tp_2
    _name: Generic baz test plan 2
    _description: This test plan contains generic test cases + a nested part
    include:
        hello       certification-status=blocker
        bye         certification-status=non-blocker
    mandatory_include:
        mandatory   certification-status=blocker
    bootstrap_include:
        bootstrap
    nested_part:
        com.ubuntu::bar_tp

As you can see this test plan includes a part from provider Bar (the same used 
in the previous example). In provider Foo, we can create a new test plan 
including `baz_tp_2`:

::

    unit: test plan
    id: foo_tp_5
    _name: Foo test plan 5
    _description: This test plan is built from multiple level of nested test plans
    include:
        always-pass       certification-status=blocker
        always-fail
    nested_part:
        baz_tp_2

The jobs execution order is still:

- ``bootstrap``
- ``mandatory``
- ``always-pass``
- ``always-fail``
- ``hello``
- ``bye``
- ``sleep``
- ``uname``

How to use a base test plan except a few jobs?
----------------------------------------------

The test plan units support an optional field - ``exclude`` - that we can use
to remove jobs from a nested part ``include`` section. 

Note: The ``exclude`` ids cannot remove jobs that are parts of the 
``mandatory_include`` sections (nested or not).

The test plan below (from provider Foo) won't run the ``hello`` job of provider 
Baz:

::

    unit: test plan
    id: foo_tp_6
    _name: Foo test plan 6
    _description: This test plan contains generic tests + 2 new tests - hello job
    include:
        always-pass       certification-status=blocker
        always-fail
    exclude:
        hello
    nested_part:
        baz_tp

The jobs execution order is:

- ``bootstrap``
- ``mandatory``
- ``always-pass``
- ``always-fail``
- ``bye``

Known limitations
=================

You can create infinite loops if a nested part is calling itself or if 
somewhere in the nested chain such a loop exists. Checkbox won't like that and 
so far there's no validation to prevent it, be warned!
