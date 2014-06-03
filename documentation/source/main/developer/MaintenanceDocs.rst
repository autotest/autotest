Autotest Maintenance Docs
=========================

This document was written to increase the `Bus Factor <http://en.wikipedia.org/wiki/Bus_factor>`_
of the autotest project. Jokes aside, distributing tasks makes the project more
maintainable, given that the load is spread across individuals.

So, these are the activities of a project maintainer, according to the current
project conventions:

1) Patch review / Update of development branch
2) Sync of the development / master branches
3) Policy definition and enforcement

Let's talk about each one of them.

Quick primer to pull request maintenance
----------------------------------------

We will talk about all that on the following topics, but we have a little video, part of our autotest weekly
hangout, where I speak about maintenance. It might be useful to watch it, then read the rest of the document.

https://www.youtube.com/watch?v=EzB4fYX5i4s

The actual maintenance talk is between 37:00 - 49:40.

Patch reviewing and devel branch update
---------------------------------------

We strive to keep a model similar to the one described
`in this link <http://nvie.com/posts/a-successful-git-branching-model/>`_
which boils down to:

1) Have a master branch, which is always supposed to be stable
2) Have a next branch, which is the integration branch
3) When the master branch is updated, by definition, this is a stable release

In the case of the autotest project (the framework project) the only exception
is that we define what is a release in terms of desired functionality, so
there might be many syncs next-master before a stable release can be called upon.

On sub projects, such as virt tests, we adopt the model as is, every next-master
sync means a stable release, that we tag with a timestamp in ISO 8601 format. So,
given that this document is the reference document for all projects under the
autotest umbrella, please keep in mind those little differences.

Very well. Autotest currently uses `github <http://github.com>`_ as the project
infrastructure provider. In the past, we used our own hosted solutions, which were
useful at one point, but then became too burdensome to maintain them. Github has
a functionality called `Pull requests <https://help.github.com/articles/using-pull-requests>`_
that pretty much presents a patch set in a graphical, rich way, and allows people
that have github accounts to comment on the patches.

If you're not familiar with the process, please read the docs pointed out above.
Now, the caveat here is that we don't use the pull request functionality of
automatically merge the code to the branch against the code is being developed
against. This is because we have checker scripts used to verify the code being
submitted for:

1) Syntax errors
2) Code that breaks existing unittests
3) Permission problems (like an executable script without executable permissions)
4) Trailing whitespace/inconsistent indentation problems

Like it or not, keeping the code clean with regards to these problems is project
policy, and tends to make our life better in the long term. So here are the
tools that we hope will make your life easier:

Autotest
--------

Pre-Reqs
--------

These tools assume you have a number of dependency packages installed to your
box to run all these effectly, such as pylint, for static checking, Django
libs to run autotest DB unittests, so on and so forth. So you may go to
:doc:`this link <../developer/UnittestSuite>` for instructions on how to install them.


Tools
-----

utils/check_patch.py - This tool is supposed to help you to verify whether a
code from a pull request has no obvious, small problems. It'll:

1) Create a new branch from next (our reference devel branch)
2) Apply the code in the form of a patch
3) Verify if all changed/created files have no syntax problem (run_pylint.py with -q flag)
4) Verify if any changed/created files have no indentation/trailing whitespace problems
5) Verify if any changed/created files have a unittest, in which case it'll execute the unittest and report results

If any problems are found, it will return exit code != 0 and ask you to fix the
problems. In this case, you can point out the code submitter of the problems and
ask him/her to fix them. In order to check a given pull request, say:

https://github.com/autotest/autotest/pull/619

You'll just execute:

::

    utils/check_patch.py -g 619

And that'd be it. This script has also another important function - It is a full
tree checker, useful to check your own code. Just execute:

::

    utils/check_patch.py --full --yes

And it'll scan through all files and point you all problems found.

utils/unittest_suite.py - Runs all unittests. Ideally the output of it should
be like:

::

    utils/unittest_suite.py --full
    Number of test modules found: 81
    autotest.client.kernel_versions_unittest: PASS
    autotest.tko.utils_unittest: PASS
    autotest.mirror.database_unittest: PASS
    autotest.scheduler.gc_stats_unittest: PASS
    autotest.client.shared.settings_unittest: PASS
    autotest.client.shared.control_data_unittest: PASS
    autotest.database_legacy.db_utils_unittest: PASS
    ...
    All passed!

If it is not, please check out the errors.

Virt-Test
---------

tools/check_patch.py - Exactly the same as utils/check_patch.py from autotest,
the difference is the path, really.

tools/run_unittests.py - Exactly the same as the autotest version, only the path
is different.


Applying the code that was reviewed and looks ready for inclusion
-----------------------------------------------------------------

You'll:

1) Apply the code using the check_patch script. The execution should come clean.
2) git checkout next
3) git merge github-[pull request number] that was created by the script
4) git push

That's it. Alternatively, you can use GitHub tools to perform branch merging,
such as hitting the green button, or pulling from the branch manually. As long
as you've done your due dilligence, it's all fine.

Policy enforcement
------------------

There are a number of common mistakes made by people submitting patches to
autotest and offspring projects, more frequent when the contributions are test
modules. So when you find such mistakes, please politely help them localize their
mistakes and refer them to
:doc:`this link on test coding style <Tests/TestCodingStyle>`.

Other than that, trying to give the best of your attention on a patch review is
always important.


Non fast forward updates
------------------------

Sometimes we need to update the development branch in a non fast forward way.
This is fine, considering the dev branch is not supposed to be fast forward,
however, in order to ease the work of your fellow maintainers, some care has
to be taken (we should keep those updates to a minimum). The main use case
for non fast forward update is when there's a patch that introduced a regression,
and we have to either fix the patch or drop it from next.

In case you have to do it, please make an annoucement on the mailing list about
it, explaining the reasons underlying the move.


Sync of the development branches
--------------------------------

The development branch should pass through regular QA in order to capture
regressions in the code that is getting added to the projects. The current tests
comprise:

1) Job runs on a sever that is updated every day with the latest contents of the development branch
2) Unittests on a recent dev platform (F18, Ubuntu 12.04)
3) Static checking on an older system with python 2.4 (such as RHEL5)

So, there are 2 possibilities:

1) The development branch passes all tests, then it is considered apt to release. The merge could've happen right away.
2) The tests fail. The bad commit should be either fixed straight away, or yanked from the branch.

More details about this step should be written at a later point.


Becoming a Maintainer
---------------------

Besides the ability to commit code directly to the ``next`` branch, and being an authority over some aspect of the tree, there is little other difference with working as a public contributor.  That is to say, a maintainer has exactly the same expectations as a contributors, but with the addition of a few more responsibilities.  With that in mind, whether you are nominated or request maintainer access, here is a *guideline* for the minimum requirements:

1) ``X`` Code submissions per month.
2) ``Y`` Community-code submission reviews per month.
3) ``Z`` days elapsed since first code submission.

In general becoming a maintainer follows the following workflow:

1) Candidate is nominated, or pledges to a current maintainer.
2) Data from above is presented to Maintainer council for relevant project aspect (i.e. autotest, virt-test/libvirt, qemu, etc.).
3) Maintainer council reviews data and discusses candidate.
4) Feedback is provided to candidate on decision and/or areas needing improvement.

If the Maintainer Council approves the request:

1. Access is granted.
2. Community announcement delivered.
3. ``MAINTAINERS`` document(s) updated.
4. Requirements and expectations (re-)communicated.
