Contributing to Checkbox
========================

.. contents::


Introduction
------------

This document provides the information needed to contribute to Checkbox and its providers.


General recommendations
-----------------------

Setup your editor of choice to run autopep8_ on save. This helps keep everything passing flake8_.
The code doesn’t have to be pylint-clean, but running pylint_ on your code may inform you about issues that could come up later in the review process.


Testing
-------


Hacking on Checkbox and/or its providers
````````````````````````````````````````

If you want to hack on Checkbox or its providers, one method is to install everything you need in a Python virtual environment:

.. code-block:: bash

    # Install the required tools
    $ sudo apt install git python3-virtualenv
    
    # Prepare the development environment
    $ mkdir ~/checkbox-dev/
    $ cd ~/checkbox-dev/
    $ git clone git+ssh://pieq@git.launchpad.net/checkbox-ng
    $ git clone git+ssh://pieq@git.launchpad.net/checkbox-support
    $ git clone git+ssh://pieq@git.launchpad.net/plainbox-provider-resource
    $ git clone git+ssh://pieq@git.launchpad.net/plainbox-provider-checkbox
    
    # Create and activate the Python virtual environment
    $ cd ~/checkbox-dev/checkbox-ng
    $ ./mk-venv
    $ . ~/checkbox-dev/checkbox-ng/venv/bin/activate
    
    # Activate the base providers in the virtual environment
    (venv) $ cd ~/checkbox-dev/plainbox-provider-resource/
    (venv) $ ./manage.py develop -d $PROVIDERPATH
    (venv) $ cd ~/checkbox-dev/plainbox-provider-checkbox
    (venv) $ ./manage.py develop -d $PROVIDERPATH
    
    # Install the Checkbox support library in the virtual environment
    (venv) $ cd ~/checkbox-dev/checkbox-support
    (venv) $ ./setup.py install
    
    # You should now be able to run checkbox, select a test plan and run it
    (venv) $ checkbox-cli


Writing and running unit tests for Checkbox
```````````````````````````````````````````

Writing unit tests for your code is strongly recommended. For functions with an easily defined input and output, use doctest_. For more complex units of code use the standard `unittest library`_.


Writing and running unit tests for providers
````````````````````````````````````````````

Ensure the job and test plan definitions follow the correct syntax using the validate command::

    $ ./manage.py validate


Run checks for code quality of provider hosted scripts and any unit tests for providers::

    $ ./manage.py test


Version control recommendations
-------------------------------


Commit title
````````````

In general, try to follow `Chris Beams’ recommendations`_. In a nutshell:

    - Limit the length of the title to 50 characters
    - Begin title with a capital letter
    - Use the imperative mode (your title should always be able to complete the sentence “If applied, this commit will...”)


In addition, if it makes sense to do so, prefix the title with one of the following terms:

    - Add
    - Change
    - Remove
    - Fix

Example::

    Add: New screen to re-run failed jobs


Commit message body
```````````````````

Quoting again from Chris Beams’ article, use the body to explain what and why vs. how.


Example::

    Change: Shellcheck on bin dir scripts
    
    The test command to manage.py currently looks for python unittests
    in the provider tests/ directory. This change searches the bin/
    directory for files with suffix .sh and automatically generates
    a unittest that runs the shellcheck command on the file.


Linking a commit to a Launchpad bug
```````````````````````````````````

If your commit fixes a Launchpad bug, you can link to it by adding the following line in the commit message body (where “123456” is the Launchpad bug number)::

    LP: #123456

See `this article on the Launchpad blog`_ for more information.


Splitting work in separate commits if required
``````````````````````````````````````````````

If the changes you provide affect different parts of the project, it is better to split them in different commits. This helps others when reviewing the changes, helps investigation later on if a problem is found and usually helps the original developer to better explain and organize his/her changes.


For example, if you add a new screen to the Checkbox text user interface (TUI) and then modify Checkbox internals to work with this new screen, it is good to have one commit for the new screen, and one for the internals changes.


Each commit should be stable, i.e. not introduce regressions or make tests fail. If two or more commits have to be used together, then they should become one commit. 


Rework your changes
```````````````````

Sometimes it is necessary to modify your changes (for instance after they have been reviewed by others). Instead of creating new commits with these new modifications, it is preferred to use Git features such as rebase_ to rework your existing commits.


Merge requests
--------------


General workflow
````````````````

Follow these steps to make a change to a Checkbox-related project. We will use the `Checkbox provider`_ for this example, but the same applies for other projects.


1. Using the instructions provided in the Code section, get the Git repository on your device::

    git clone git+ssh://your-launchpad-id@git.launchpad.net/plainbox-provider-checkbox

2. Add a remote pointing to your own Launchpad account. This will be helpful when pushing the changes and asking for it to be reviewed and merged. Here, I create a remote called “perso” that points to my fork of the repository on Launchpad (replace “pieq” with your own Launchpad username)::

    $ git remote add perso git+ssh://pieq@git.launchpad.net/~pieq/plainbox-provider-checkbox
    $ git remote -v
    origin    git+ssh://pieq@git.launchpad.net/plainbox-provider-checkbox (fetch)
    origin    git+ssh://pieq@git.launchpad.net/plainbox-provider-checkbox (push)
    perso    git+ssh://pieq@git.launchpad.net/~pieq/plainbox-provider-checkbox (fetch)
    perso    git+ssh://pieq@git.launchpad.net/~pieq/plainbox-provider-checkbox (push)
    
3. Create a branch and switch to it to start working on your changes. You can use any branch name, but it is generally good to include the Launchpad bug number it relates to as well as a quick explanation of what the branch is about::

    $ git checkout -b 123456-invalid-session-content
    
4. Work on your changes, test them, iterate, commit your work.

5. Before sending your changes for review, make sure to rebase your work using the most up-to-date data from the main repository::

    $ git checkout master
    $ git pull
    $ git checkout 123456-invalid-session-content
    $ git rebase master
    First, rewinding head to replay your work on top of it...
    Applying: <your commits>

6. Push your changes to your Launchpad repository::

    $ git push perso
    Enumerating objects: 741, done.
    Counting objects: 100% (612/612), done.
    Delta compression using up to 4 threads
    Compressing objects: 100% (242/242), done.
    Writing objects: 100% (522/522), 80.41 KiB | 26.80 MiB/s, done.
    Total 522 (delta 336), reused 460 (delta 280)
    remote: Resolving deltas: 100% (336/336), completed with 54 local objects.
    remote:           
    remote: Create a merge proposal for '123456-invalid-session-content' on Launchpad by visiting:
    remote:           https://code.launchpad.net/~pieq/plainbox-provider-checkbox/+git/plainbox-provider-checkbox/+ref/123456-invalid-session-content/+register-merge
    remote:           
    To git+ssh://git.launchpad.net/~pieq/plainbox-provider-checkbox
     * [new branch]          123456-invalid-session-content -> 123456-invalid-session-content

7. Follow the link provided by Launchpad in the previous step to create a merge request. The most important options of the “Propose for merging” page are:
    a. ``Repository`` and ``Branch``: Where your changes should land once they are approved. It should be already filled with the appropriate information.
    b. ``Description of the change``: Explain why this change is required, how it was tested (and on what hardware) and how other people can test it.
    c. Other fields do not have to be changed. Press the ``Propose Merge`` button and wait for feedback ;-)


What to do if reviewers suggest changes in your merge request?
``````````````````````````````````````````````````````````````

1. Change the top status of the MR to “Work in progress”. This both stops people wasting time reviewing some code which will be changed and also allows Launchpad to indicate to people who have already reviewed that the code should be reviewed again.
2. Instead of adding extra commits to fix your previous commits, use `git rebase features`_ to modify your existing commits. You can push your changes again to your personal repository; you will probably need to use the ``git push --force my_repo`` command since you “modified history”, but this is fine since you are pushing changes that have not been merged into the main repository yet.
3. When you have pushed the new version addressing the previous round of reviews, switch the top status back to “Needs review”. Launchpad will send out an e-mail indicating that reviews are needed again. Do not post a comment with type “Resubmit”; this is not the purpose of that sort of comment.


Finally...
``````````

Once enough people have reviewed and approved your work, it can be merged into the main repository. Ask a member of the Checkbox team to switch the merge request status from “Needs review” to “Approved”. The branch should be then shortly automatically merged. Its status will then change from “Approved” to “Merged”.

.. _autopep8: https://pypi.org/project/autopep8/
.. _flake8: https://flake8.pycqa.org/en/latest/
.. _pylint: https://www.pylint.org/
.. _doctest: https://docs.python.org/3/library/doctest.html
.. _unittest library: https://docs.python.org/3/library/unittest.html
.. _Chris Beams’ recommendations: https://chris.beams.io/posts/git-commit/
.. _this article on the Launchpad blog: https://blog.launchpad.net/code/linking-git-merge-proposals-to-bugs
.. _rebase: https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History
.. _Checkbox provider: https://launchpad.net/plainbox-provider-checkbox
.. _git rebase features: rebase_
