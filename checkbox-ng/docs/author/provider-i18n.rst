=============================
Provider Internationalization
=============================

About
-----

:term:`PlainBox` offers a way for test authors to create localized testing
experience.  This allows test developers to mark certain strings as
translatable and make them a part of existing internationalization and
localization frameworks.

Working with translations
-------------------------

In practical terms, the summary and description of each job definition can now
be translated to other languages. The provider management tool (``manage.py``)
can now extract, merge and build translation catalogs that will be familiar to
many developers.

The job definition file format already supported this syntax but it was not
supported by PlainBox before, if you are maintaining an existing provider the
only new thing, for you, may be the fact that a job name (summary) is now also
translatable and that there are dedicated tools that make the process easier.

Looking at an example job definition from the :doc:`provider-template`::

    id: examples/trivial/always-pass
    _summary: A test that always passes
    _description:
       A test that always passes
       .
       This simple test will always succeed, assuming your
       platform has a 'true' command that returns 0.
    plugin: shell
    estimated_duration: 0.01
    command: true

The summary and description fields are prefixed with ``_`` which allows their
value to be collected to a translation catalog.

Updating Translations
---------------------

Whenever you edit those fields you should run ``./manage.py i18n``. This
command will perform several steps:

* All files mentioned in ``po/POTFILES.in`` will be scanned and translatable
  messages will be extracted.
* The ``po/*.pot`` file will be rewritten based on all of the extracted
  strings.
* The ``po/*.po`` files will be merged with the new template. New strings may
  be added, similar but changed strings will be marked as *fuzzy* so that a
  human translator can ensure they are okay (and typically make small changes)
  by removing the fuzzy tag. Unused strings will be commented out but not
  removed.
* Each ``po/*.po`` file will be compiled to a ``build/mo/*/LC_MESSAGES/*.mo``
  file. Those files are what is actually used at runtime. If you ran
  ``manage.py develop`` on your provider you should now see translated values
  being available.

Each of those actions can be individually disabled. See ``manage.py i18n
--help`` for details. This may be something you need to do in your build
system.

Translating Job Definitions
---------------------------

After generating the template file at least once you can translate all of the
job definitions into other languages.

There are many tools available to make this task easier. To get started just
copy the ``.pot`` file to ``LL.po`` where LL code of the language you want to
translate to and start editing. Run ``manage.py i18n`` often to spot syntax
issues and get updated values as you typically will edit code and translations
at the same time. Make sure that your editor can detect when a file is being
overwritten and offer to refresh the edited copy, ``manage.py i18n`` almost
always changes the layout of the file. 

Once you commit the template file to your version control then you can use
tooling support offered by code hosting sites, such as Launchpad.net, to allow
the community to contribute translations. You can also seek paid services that
offer professional translations on a deadline. In both cases you should end up
with additional ``.po`` files in your repository.

.. note::
    If English is not your first language it's a very good idea to try to keep
    all of the strings translated to your language of choice and use the
    translated version daily. This process allows you to think about the
    English text, correct confusing statements, reword sentences and think
    about the terminology used throughout your tests. It will also show missing
    strings (those that are not marked for translation) or missing translator
    comments.
    
    Remember: If you, the author of the test, cannot reasonably translate your
    test definitions into your native language, how can anyone else do it?

Translating Test Programs
-------------------------

Test definitions are not the whole story. It is probably even more important to
translate various testing programs or utilities that your test definitions
depend on.

Standard development practices apply, you should make properly translated
testing applications. It is advisable to reuse the same gettext domain as your
test definitions so that you can reasonably measure how much of your test
definition content is available in a given language. 

For third party applications you may consider ensuring that they can be
localized and translated, file bugs or contribute patches, including
translations, for the languages that you care about.

Working with Version Control Systems
------------------------------------

It is advisable to separate commits that change the original string to the
commits that update the translation template file and individual translation
catalogues. The latter tend to be very long and almost impossible for anyone to
review without specialized tools.

Keep in mind that changes to actual translations that are *not* caused by
updates to the template file should be separated as well. This will allow
reviewers to actually look at the changes in text (assuming that more than one
person on the team knows that language).

Lastly you should never commit any of the build/ files (especially the
generated, compiled ``.mo`` files) into the version control system.

Further Reading
---------------

You may find those links handy:

* https://help.launchpad.net/Translations/YourProject 
* https://help.launchpad.net/Translations/StartingToTranslate
* https://www.transifex.com/
* https://www.gnu.org/software/gettext/manual/gettext.html
