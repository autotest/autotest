
Specifying kernels in the Job Creation Interface
=================================================

Autotest has a system to expand Linux kernel versions to actually
downloadable source trees, or even installable distro packages, that
can be used in job creation interfaces, such as CLI and web interfaces.
At the moment, we support the following release schemas:

* Upstream versions. You can specify an upstream version, that will
  expand to an URL pointing to a tarball inside the kernel.org mirror
  you have specified. The script/library ``client/kernelexpand.py``
  has this functionality implement, and lets you test it which versions
  can be actually expanded:

::

    $ client/kernelexpand.py 3.2.1
    http://www.kernel.org/pub/linux/kernel/v3.x/linux-3.2.1.tar.bz2

We still don't allow you to specify an arbitrary distro package version
for autotest to download, for example:

::

    $ client/kernelexpand.py 3.3.4-5.fc17.x86_64
    Kernel '3.3.4-5.fc17.x86_64' not found. Please verify if your version number is correct.


* Direct URLs pointing to rpm and deb packages containing the kernel. Example:


::

    http://example.com/kernel-3.3.1.rpm
    http://example.com/kernel-3.5-rc2.deb

You can specify multiple versions separating them with a comma or space.

Obviously, we'd like to cleanly support other ways of specifying kernels in the
job creation interface, so this makes the complicated logic transparent to
users, but we're not there yet. Please open an issue requesting for a given
method and we'll consider it carefully.
