================================================
How to use git to contribute patches to autotest
================================================

Git is a powerful revision control system designed to make contributing
to open source projects simple. Here's how you can contribute to
autotest easily using git:

1) Make sure you have configured git to automatically create your
signature on the commits you make inside your local tree. The following
is an example script to do it, just edit replacing your name, email and
choosing all aliases you want. Needless to say that once you run it, the
configs are persistent (written to the git config files), so you only
need to do this once.

::

    #!/bin/bash
    # personalize these with your own name and email address
    git config --global user.name "John Doe"
    git config --global user.email "john.doe@foo.com"

    # colorize output (Git 1.5.5 or later)
    git config --global color.ui auto

    # colorize output (prior to Git 1.5.5)
    git config --global color.status auto
    git config --global color.diff auto
    git config --global color.branch auto

    # and from 1.5.4 onwards, this will work:
    git config --global color.interactive auto

    # user-friendly paging of some commands which don't use the pager by default
    # (other commands like "git log" already does)
    # to override pass --no-pager or GIT_PAGER=cat
    git config --global pager.status true
    git config --global pager.show-branch true

    # shortcut aliases
    git config --global alias.st status
    git config --global alias.ci commit
    git config --global alias.co checkout

    # this so I can submit patches using git send-email
    git config --global sendemail.smtpserver [your-smtp-server]
    git config --global sendemail.aliasesfile ~/.gitaliases
    git config --global sendemail.aliasfiletype mailrc

    # shortcut aliases for submitting patches for Git itself
    # refer to the "See also" section below for additional information
    echo "alias autotest autotest-kernel@redhat.com" >> ~/.gitaliases

    # another feature that will be available in 1.5.4 onwards
    # this is useful when you use topic branches for grouping together logically related changes
    git config --global format.numbered auto

    # turn on new 1.5 features which break backwards compatibility
    git config --global core.legacyheaders false
    git config --global repack.usedeltabaseoffset true

2) git clone the autotest git mirror repo:

::

    git clone git://github.com/autotest/autotest.git
    cd autotest

3) create a branch for the change you're going to make

::

    git branch [branch-name]
    git checkout [branch-name]

4) Make your changes in the code. For every change, you can make a git
commit. For folks used to other paradigms of version control, don't
worry too much, just have in mind that git trees usually are
independent, and you can commit changes on your local tree. Those
commits can then be generated in the form of patches, that can be
conveniently sent to the maintainers of the upstream project. To commit
you use:

::

    git commit -as

If you have executed the git configuration, you'll see that there is
already a Signed-off-by: with your name and e-mail, sweet, isn't it?
Save and there you have your commit. 

5) A alternative configuration is helpful for some guys who are using
thunderbird, Zimbra or something like that to filter mail subject 
contains "[Autotest]" patches:

::

    git config format.subjectprefix Autotest][PATCH

And then if you run 'git format-patch' later, you will get a patch 
with "[Autotest][PATCH]" mail's subject prefix.

6) When you want to generate the patches, it's as easy as doing a:

::

    git format-patch master

It will generate all the differences between your branch and the master
branch. You can also generate a certain number of patches arbitrarily
from any branch. Let's say you want to pick the last 2 commits you made
and create patch files out of it:

::

    git format-patch -2 --cover-letter

This will generate 2 patches that also happen to be in a unix mailbox
format that can be sent to the mailing list using git send-email ;)

7) Edit your cover letter (patch number 0 generated) with the info you'd
like to include in the patchset.

8) Then you can send the patches with git send-email:

::

    git send-email patch1.patch patch2.patch... patchN.patch --to address@foo.org --cc address@bar.org

Note that the aliases you defined on your configuration will allow you
do do stuff like this:

::

    git send-email patch1.patch --to autotest

So that autotest is expanded to the actual mailing list address.

