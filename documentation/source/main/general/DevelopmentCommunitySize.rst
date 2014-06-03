Autotest Development Community Size
===================================

After re-consideration about the subject, in
April 2012 we have rewritten the entire autotest
tree history. Autotest was a project kept on svn
for about 6 years, and for a long time there was
an unofficial git-svn mirror, that after we adopted
git as the official reference, we just kept that
mirror.

Obviously this does not play well with the
traditional tools to verify stats on git, so
that's why we decided to rewrite. Now you can see
the individual authors that contributed since the
inception of the project:

::

    $ git shortlog -s | wc -l
    202

And all other fun git statistics, such as the number
of organizations that contributed resources to some
extent to the project

::

    $ git shortlog -se | sed -e 's/.*@//g' -e 's/\W*$//g' | sort | uniq | grep -v "<"
    alien8.de
    amd.com
    b1-systems.de
    br.ibm.com
    canonical.com
    chromium.org
    cn.fujitsu.com
    cn.ibm.com
    digium.com
    gelato.unsw.edu.au
    gmail.com
    google.com
    hp.com
    ifup.org
    inf.u-szeged.hu
    in.ibm.com
    intel.com
    intra2net.com
    kerlabs.com
    linux.vnet.ibm.com
    mvista.com
    nokia.com
    openvz.org
    oracle.com
    osdl.org
    oss.ntt.co.jp
    place.org
    raisama.net
    redhat.com
    samba.org
    secretlab.ca
    shadowen.org
    stanford.edu
    stec-inc.com
    suse.com
    suse.cz
    suse.de
    twitter.com
    uk.ibm.com
    us.ibm.com
    windriver.com
    xenotime.net

As not all of them are strictly institutions, and there are different
domains from the same root company, we can estimate about 30 institutions.

Have fun with your git stats, enjoy!
