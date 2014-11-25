Frequently Asked Questions
==========================


FAQ 1
-----
Q: What does "advice: please use .pxu as the extension for all files with
plainbox units" mean?

A: It means that you should just rename your ``.txt`` or ``.txt.in`` files
to ``.pxu``. We're doing this because we want to standardize the new file
extension and provide syntax highlighting in common text editors.

For now you can also look at the ``plainbox/contrib/pxu.vim`` directory to use
our experimental syntax highlighting file for Vim. Improvements to suppor other
editors are highly welcome!


FAQ 2
-----
Q: What's the difference between description and purpose/steps/verification
fields in job definition and how should I use them?

A: Description should contain all the information needed to perform the test.
For tests requiring human interaction, description field should contain
information about the purpose of the test, all the steps that the user has to
perform and instruction how to verify the outcome of the test. In order to draw
a finer finer distinction between the aformentioned stages of test execution,
the use of purpose, steps and verification fields is recommended. Since version
0.17 of plainbox some user interfaces take advantage of the new fields set.
They will display the purpose of the test prior to its execution, steps
information while executing them and verification instruction when the test is
done.  Note, that purpose, steps and verification fields are used only in jobs
definitions requiring human interaction i.e. ones of plugin type 'manual',
'user-interact', and 'user-interact-verify'.
