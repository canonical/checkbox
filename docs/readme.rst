Documentation starter pack
==========================

See the `Sphinx and Read the Docs <https://canonical-documentation-with-sphinx-and-readthedocscom.readthedocs-hosted.com/>`_ guide for instructions on how to get started with Sphinx documentation.

Then go through the following sections to use this starter pack to set up your docs repository.

Download and install
--------------------

* *Incorporate this starter pack into an existing code repository* - copy all
  the files from this repository into your project's directory structure,
  and rename this directory to ``docs`` or similar.

* *Start a standalone documentation project* - clone this locally and start
  working.

In documentation directory, run::

	make install

This invokes the ``install`` command in the ``Makefile``, and creates a
virtual environment (``.sphinx/venv``) and installs dependencies in
``.sphinx/requirements.txt``.

A complete set of pinned, known-working dependencies is included in
``.sphinx/pinned-requirements.txt``.


Build and serve the documentation
---------------------------------

Start the ``sphinx-autobuild`` documentation server::

	make run

The documentation will be available at `127.0.0.1:8000 <http://127.0.0.1:8000>`_.

The command:

* activates the virtual environment and starts serving the documentation
* rebuilds the documentation each time you save a file
* sends a reload page signal to the browser when the documentation is rebuilt

(This is the most convenient way to work on the documentation, but you can still use
the more standard ``make html``.)


Configure the documentation
---------------------------

In ``conf.py``, you will need to check or edit several settings in the *Project information* section:

* ``project``
* ``author``
* ``copyright`` - in most cases, replace the first ``%s`` with the year the project started
* ``release`` - only required if you're actually using release numbers
  (beyond the scope of this guide, but you can also use Python to pull this
  out of your code itself)
* ``ogp_site_url`` - the URL of the documentation output (needed to generate a preview when linking from another website)
* ``ogp_site_name`` - the title you want to use for the documentation in previews on other websites (by default, this is set to the project name)
* ``ogp_image`` - an image that will be used in the preview on other websites

In the ``html_context`` variable, update the following settings:

* ``discourse_prefix`` - the URL to the Discourse instance your project uses (needed to add links to posts using the ``:discourse:`` metadata at the top of a file)
* ``github_url`` - the link to your GitHub repository (needed to create the Edit link in the footer and the feedback button)
* ``github_version`` - the branch that contains this version of the documentation
* ``github_folder`` - the folder that contains the documentation files
* ``github_filetype`` - the file type of the documentation files (usually ``rst`` or ``md``)

Save ``conf.py``.

Configure the spelling check
----------------------------

If your documentation uses US English instead of UK English, change this in the
``.sphinx/spellingcheck.yaml`` file.

After replacing the placeholder "lorem ipsum" text, clean up the ``.wordlist.txt``
file and remove all words starting from line 10.
(They are currently included to make the spelling check work on the start pack
repository.)

Configure the link check
------------------------

If you have links in the documentation that you don't want to be checked (for
example, because they are local links or give random errors even though they
work), you can add them to the ``linkcheck_ignore`` variable in the ``conf.py``
file.

Activate/deactivate feedback button
-----------------------------------

A feedback button is included by default, which appears at the top of each page
in the documentation. It redirects users to your GitHub issues page, and
populates an issue for them with details of the page they were on when they
clicked the button. 

If your project does not use GitHub issues, or you don't want the feedback
button for another reason, you can deactivate the button by removing the
``github_issue_links.js`` script from the ``conf.py`` file.
