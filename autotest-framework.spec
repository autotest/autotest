%if ! (0%{?fedora} > 12 || 0%{?rhel} > 5)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%endif

%global commit 0c2ab5b5306f6ccf5b47ff8b989faa2ad412c3d6
%global shortcommit %(c=%{commit}; echo ${c:0:7})

%bcond_with gwt

Name: autotest-framework
Version: 0.15.1.next.git%{shortcommit}
Release: 1%{?dist}
Summary: Framework for fully automated testing
Group: Applications/System
# All content is GPLv2 unless otherwise stated.
# Part of frontend/afe/feeds/feed.py is BSD licensed code from Django
# frontend/afe/json_rpc is a heavily modified fork of the dead
# http://json-rpc.org/wiki/python-json-rpc which is LGPLv2.1+
# frontend/shared/json_html_formatter.py is MIT licensed
License: GPLv2 and BSD and LGPLv2+ and MIT
URL: http://autotest.github.com/
BuildArch: noarch
Source0: https://github.com/downloads/autotest/autotest/autotest-%{version}.tar.gz
BuildRoot: %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

Requires: grubby
Requires: python >= 2.4
Requires: openssh-clients
Requires: openssh-server
Requires: rsync
Requires: tar, gzip, bzip2, unzip

Requires(post): openssh
Requires(pre): shadow-utils

BuildRequires: python >= 2.4, python-sphinx

%description
Autotest is a framework for fully automated testing. It is designed primarily
to test the Linux kernel, though it is useful for many other functions such as
qualifying new hardware. It's an open-source project under the GPL and is used
and developed by a number of organizations, including Google, IBM, and many
others.

The autotest package provides the client harness capable of running autotest
jobs on a single system.


%package server
Summary: Server test harness and front-end for autotest
Group: Applications/System
Requires: %{name} = %{version}-%{release}
Requires: Django >= 1.3
Requires: Django-south
Requires: conmux
Requires: mysql-server
Requires: gnuplot
Requires: httpd
Requires: mod_wsgi
Requires: MySQL-python
Requires: numpy
Requires: python-atfork
Requires: python-crypto
Requires: python-imaging
Requires: python-matplotlib
Requires: python-paramiko
Requires: python-simplejson
Requires: python-setuptools
Requires: python-httplib2

%if 0%{?fedora} >= 10 || 0%{?rhel} >= 6
Requires(post): policycoreutils-python
%else
Requires(post): policycoreutils
%endif

%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
BuildRequires: systemd-units
%else
# This is for /sbin/service
Requires(preun): initscripts
Requires(postun): initscripts
# This is for /sbin/chkconfig
Requires(post): chkconfig
Requires(preun): chkconfig
%endif


%description server
Autotest is a framework for fully automated testing. It is designed primarily
to test the Linux kernel, though it is useful for many other functions such as
qualifying new hardware. It's an open-source project under the GPL and is used
and developed by a number of organizations, including Google, IBM, and many
others.

The autotest-server package provides the server harness capable of running
autotest jobs on a single system.


%if %{with gwt}
%package web
Summary: Web frontend
Group: Applications/System
Requires: %{name} = %{version}-%{release}
Requires: %{name}-server = %{version}-%{release}
BuildRequires: gwt-devel >= 2.3.0
BuildRequires: java-openjdk
%description web
Web frontend for server using GWT
%endif


%prep
%setup -q -n autotest-%{version}

sed -i -e "s|DocumentRoot /usr/local/autotest/apache/www|DocumentRoot %{_datadir}/autotest/www|" apache/apache-web-conf
./installation_support/global_config_set_value.py -p global_config.ini -s COMMON -k autotest_top_path -v %{python_sitelib}/autotest
./installation_support/global_config_set_value.py -p global_config.ini -s COMMON -k test_dir -v %{_sharedstatedir}/autotest/tests/
./installation_support/global_config_set_value.py -p global_config.ini -s COMMON -k test_output_dir -v %{_sharedstatedir}/autotest/
./installation_support/global_config_set_value.py -p global_config.ini -s AUTOSERV -k client_autodir_paths -v %{python_sitelib}/autotest
./installation_support/global_config_set_value.py -p global_config.ini -s CLIENT -k output_dir -v %{_sharedstatedir}/autotest/
./installation_support/global_config_set_value.py -p global_config.ini -s SERVER -k rpc_log_path -v %{_localstatedir}/log/autotest/rpcserver.log
./installation_support/global_config_set_value.py -p global_config.ini -s SERVER -k logs_dir -v %{_localstatedir}/log/autotest
./installation_support/global_config_set_value.py -p global_config.ini -s SERVER -k pid_files_dir -v %{_localstatedir}/run/autotest

sed -i -e "s|^PID_PATH.*|PID_PATH=%{_localstatedir}/run/autotest|" utils/autotest-rh.init
sed -i -e "s|/usr/local/$PROG|%{python_site_lib}/$PROG|" utils/autotest-rh.init

sed -i -e "s|/usr/local/autotest/scheduler/autotest-scheduler-watcher|%{_bindir}/autotest-scheduler-watcher|" utils/autotestd.service

echo "%{version}" > RELEASE-VERSION


%build
python setup.py build
# GWT is not packaged in Fedora, build web frontend that uses it only when --with gwt
%if %{with gwt}
python utils/compile_gwt_clients.py -c 'autotest.EmbeddedSpreadsheetClient autotest.AfeClient autotest.TkoClient autotest.EmbeddedTkoClient'
%endif


%install
rm -rf %{buildroot}
python setup.py install --root %{buildroot} --skip-build

# Fedora specific locations
install -d %{buildroot}%{_localstatedir}/log/autotest
install -d %{buildroot}%{_localstatedir}/run/autotest
install -d %{buildroot}%{_sharedstatedir}/autotest/packages
install -d %{buildroot}%{_sharedstatedir}/autotest/results
install -d %{buildroot}%{_sharedstatedir}/autotest/tests
install -d %{buildroot}%{_sharedstatedir}/autotest/.ssh
install -d %{buildroot}%{_sysconfdir}/httpd/conf.d
install -d %{buildroot}%{_sysconfdir}/httpd/autotest.d
install -d %{buildroot}%{python_sitelib}/autotest/server/tests
install -d %{buildroot}%{python_sitelib}/autotest/server/site_tests

touch %{buildroot}%{_sharedstatedir}/autotest/.ssh/id_rsa
touch %{buildroot}%{_sharedstatedir}/autotest/.ssh/id_rsa.pub

cp -a logs/README README.logs
cp -a packages/README README.packages
cp -a results/README README.results
cp -a client/shared/README README.common_lib
cp -a apache/conf/cgi-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/django-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/tko-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/apache-conf %{buildroot}%{_sysconfdir}/httpd/conf.d/autotest.conf

%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
# Install systemd init script
install -d %{buildroot}%{_unitdir}
cp -a utils/autotestd.service %{buildroot}%{_unitdir}/
%else
# Install SysV initscript instead
install -d %{buildroot}%{_sysconfdir}/rc.d/init.d
cp -a utils/autotest-rh.init %{buildroot}%{_sysconfdir}/rc.d/init.d/autotestd
%endif

%if %{with gwt}
install -d %{buildroot}%{_datadir}/autotest/www
install -d %{buildroot}%{_datadir}/autotest/frontend/client

cp apache/www/* %{buildroot}%{_datadir}/autotest/www
cp -a apache/conf/afe-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/embedded-spreadsheet-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/embedded-tko-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/gwt-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/conf/new-tko-directives %{buildroot}%{_sysconfdir}/httpd/autotest.d
cp -a apache/apache-web-conf %{buildroot}%{_sysconfdir}/httpd/conf.d/autotest-web.conf

rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/.classpath
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/.project
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/AfeClient-shell
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/AfeClient.launch
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/EmbeddedSpreadsheetClient.launch
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/EmbeddedTkoClient-shell
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/EmbeddedTkoClient.launch
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/README.compile
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/TkoClient-shell
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/TkoClient.launch
rm -f %{buildroot}%{python_sitelib}/autotest/frontend/client/generate-javadoc
rm -rf %{buildroot}%{python_sitelib}/autotest/frontend/client/gwt_dir
rm -rf %{buildroot}%{python_sitelib}/autotest/frontend/client/src
rm -rf %{buildroot}%{python_sitelib}/autotest/frontend/client/gwt-unitCache

# frontend/client should go to data dir and from then to -web package
cp -a frontend/client/* %{buildroot}%{_datadir}/autotest/frontend/client/
%else
rm -rf %{buildroot}%{python_sitelib}/autotest/frontend/client
%endif

rm %{buildroot}%{_datadir}/autotest/utils/autotest.init
rm %{buildroot}%{_datadir}/autotest/utils/autotest-rh.init
rm %{buildroot}%{_datadir}/autotest/utils/autotestd.service

rm -rf %{buildroot}%{python_sitelib}/autotest/client/config/*
rm -rf %{buildroot}%{python_sitelib}/autotest/frontend/afe/doctests/*
rm -rf %{buildroot}%{python_sitelib}/autotest/utils/named_semaphore
rm -rf %{buildroot}%{python_sitelib}/autotest/client/deps
rm -rf %{buildroot}%{python_sitelib}/autotest/client/profilers/*
cp -a client/profilers/__init__.py %{buildroot}%{python_sitelib}/autotest/client/profilers/__init__.py
rm -f %{buildroot}%{python_sitelib}/autotest/client/tools/setidle.c
rm -f %{buildroot}%{python_sitelib}/autotest/server/unittest_suite.*
find %{buildroot}%{python_sitelib}/autotest/ -name "*_unittest.*" -exec rm '{}' \;

for lib in $(find %{buildroot}%{python_sitelib}/autotest/ -name '*.py'); do
    sed '1{/#!\/usr\/bin\/python\|env/d}' $lib > $lib.new &&
    touch -r $lib $lib.new &&
    mv $lib.new $lib
done
rm -rf %{buildroot}%{python_sitelib}/autotest-*.egg-info

%clean
rm -rf %{buildroot}


%pre
getent group autotest >/dev/null || groupadd -r autotest
getent passwd autotest >/dev/null || \
useradd -r -g autotest -d %{_sharedstatedir}/autotest -s /bin/bash \
-c "User account for the autotest harness" autotest
exit 0


%post
if [ "$1" -eq 1 ] ; then
    su -c "ssh-keygen -q -t rsa -N '' -f %{_sharedstatedir}/autotest/.ssh/id_rsa" - autotest || exit 0
fi


%post server
if [ $1 -eq 1 ] ; then
    # Initial installation
    restorecon %{python_sitelib}/autotest/tko/*
    %if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
    /usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
    %else
    /sbin/chkconfig --add autotestd >/dev/null 2>&1 || :
    %endif
fi


%preun server
if [ $1 -eq 0 ] ; then
    # Package removal, not upgrade
    %if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
    /usr/bin/systemctl --no-reload disable autotestd.service > /dev/null 2>&1 || :
    /usr/bin/systemctl stop autotestd.service > /dev/null 2>&1 || :
    %else
    /sbin/service autotestd stop >/dev/null 2>&1
    /sbin/chkconfig --del autotestd >/dev/null 2>&1 || :
    %endif
fi


%postun server
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
    # Package upgrade, not uninstall
    %if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
    /usr/bin/systemctl try-restart autotestd.service >/dev/null 2>&1 || :
    %else
    /sbin/service autotestd condrestart >/dev/null 2>&1 || :
    %endif
fi


%files
%defattr(-,root,root,-)
%doc DCO LGPL_LICENSE LICENSE CODING_STYLE README.rst README.fedora documentation/* README.common_lib README.results client/samples/
%dir %{python_sitelib}/autotest
%dir %{_sysconfdir}/autotest
%dir %attr(-, autotest, autotest) %{_sharedstatedir}/autotest
%dir %attr(0700, autotest, autotest) %{_sharedstatedir}/autotest/.ssh
%ghost %attr(-, autotest, autotest) %{_sharedstatedir}/autotest/.ssh/*
%config(noreplace) %{_sysconfdir}/autotest/global_config.ini
%config(noreplace) %{_sysconfdir}/autotest/shadow_config.ini
%{python_sitelib}/autotest/client/
%{python_sitelib}/autotest/__init__.py*
%{python_sitelib}/autotest/common.py*
#%{python_sitelib}/autotest-*.egg-info
%attr(-, autotest, autotest) %{_sharedstatedir}/autotest/results/
%attr(-, autotest, autotest) %{_sharedstatedir}/autotest/tests/
%{_bindir}/autotest-local
%{_bindir}/autotest-local-streamhandler
%{_bindir}/autotest-daemon
%{_bindir}/autotest-daemon-monitor


%files server
%defattr(-,root,root,-)
%doc README.logs README.packages server/samples/
%dir %{_sysconfdir}/httpd/autotest.d
%dir %{_datadir}/autotest/
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/cgi-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/django-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/tko-directives
%config(noreplace) %{_sysconfdir}/httpd/conf.d/autotest.conf
%{python_sitelib}/autotest/cli/
%{python_sitelib}/autotest/database_legacy/
%{python_sitelib}/autotest/frontend/
%if %{with gwt}
%exclude %{python_sitelib}/autotest/frontend/client/
%endif
%{python_sitelib}/autotest/mirror/
%{python_sitelib}/autotest/scheduler/
%{python_sitelib}/autotest/server/
%{python_sitelib}/autotest/utils/
%{python_sitelib}/autotest/tko/
%{python_sitelib}/autotest/installation_support/
%{_datadir}/autotest/mirror/
%{_datadir}/autotest/utils/
%{_datadir}/autotest/tko/
%attr(-, autotest, autotest) %{_localstatedir}/log/autotest/
%attr(-, autotest, autotest) %{_localstatedir}/run/autotest/
%attr(-, autotest, autotest) %{_sharedstatedir}/autotest/packages/
%{_bindir}/autotest-remote
%{_bindir}/autotest-db-delete-job
%{_bindir}/autotest-manage-rpc-server
%{_bindir}/autotest-rpc-change-protection-level
%{_bindir}/autotest-rpc-client
%{_bindir}/autotest-rpc-migrate-host
%{_bindir}/autotest-rpc-query-keyvals
%{_bindir}/autotest-rpc-query-results
%{_bindir}/autotest-tko-parse
%{_bindir}/autotest-scheduler
%{_bindir}/autotest-scheduler-watcher
%{_bindir}/autotest-upgrade-db
%{_bindir}/autotest-database-turnkey
%{_bindir}/autotest-firewalld-add-service
%{_bindir}/autotest-install-packages-deps
%if 0%{?fedora} >= 15 || 0%{?rhel} >= 7
%{_unitdir}/autotestd.service
%else
%{_sysconfdir}/rc.d/init.d/autotestd
%endif

%if %{with gwt}
%files web
%defattr(-,root,root,-)
%config(noreplace) %{_sysconfdir}/httpd/conf.d/autotest-web.conf
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/afe-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/embedded-spreadsheet-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/embedded-tko-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/gwt-directives
%config(noreplace) %{_sysconfdir}/httpd/autotest.d/new-tko-directives
%{_datadir}/autotest/www/
%{_datadir}/autotest/frontend/
%endif


%changelog
* Wed Sep 25 2013 Cleber Rosa <cleber@redhat> - 0.15.1-next-22be0ca7f4c32b80fc42efe96086a4d01d4d7a4c-1
- Make SPEC file handle the latest upstream release
- Substitute systemd location on scripts

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.14.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Mon Nov 19 2012 Cleber Rosa <cleber@redhat.com> - 0.14.4-1
- Package 0.14.4 release
- Dropped patches applied upstream

* Mon Oct 8 2012 Martin Krizek <mkrizek@redhat.com> 0.14.3-2
- replace mod_python with mod_wsgi

* Tue Sep 25 2012 Martin Krizek <mkrizek@redhat.com> 0.14.3-1
- Package 0.14.3 release

* Thu Sep 20 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-7
- add mysql-server and conmux to requires for server
- patches for #502 drone_utility does not respect results directory
- patch for adding system-wide parser utility

* Thu Aug 30 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-6
- do not remove frontend/afe/fixtures

* Mon Aug 13 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-5
- add upstream patches for proper output_dir handling

* Thu Aug 09 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-4
- Remove shebang from Python libraries
- Fix /var/lib/autotest/.ssh permissions

* Mon Aug 06 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-3
- Fix licensing
- Fix systemd scriptlets
- Remove client/tools/setidle.c from RPM
- Fix file permission issues, most of the files are now owned by root:root

* Fri Jul 20 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-2
- Rename package to autotest-framework so it doesn't conflict with a tool of the same name that is part of autoconf

* Wed Jun 27 2012 Martin Krizek <mkrizek@redhat.com> 0.14.2-1
- Package 0.14.2 release

* Wed May 30 2012 Martin Krizek <mkrizek@redhat.com> 0.14.1-1
- Package 0.14.1 release

* Mon Feb 20 2012 Cleber Rosa <crosa@redhat.com> - 0.14.0-0.2.20120208git
- Split apache config among -server and -web
- Make frontend client app installed under /usr/share/autotest

* Wed Feb 08 2012 Martin Krizek <mkrizek@redhat.com> - 0.14.0-0.1.20120208git
- Package pre-0.14.0 release
- Add web sub-package
- Add Fedora specific packaging patches
- Add gwt conditional build
- Change Group
- Change source git repo to upstream
- Change autotest homedir
- cli/,client/,database/,frontend/,mirror/,scheduler/,server/,utils/,tko/ moved to site-packages
- README files renamed to README.$foo

* Wed Jul 06 2011 James Laska <jlaska@redhat.com> - 0.13.0-3
- Updated build_externals disable patch

* Thu Jun 30 2011 James Laska <jlaska@redhat.com> - 0.13.0-2
- Updated s/local/share/ patch

* Thu Jun 23 2011 James Laska <jlaska@redhat.com> - 0.13.0-1
- Update to 0.13.0 release

* Mon Jun 13 2011 James Laska <jlaska@redhat.com> - 0.13.0-0.3.20110607
- Correct policycoreutils-python requires

* Tue Jun 07 2011 James Laska <jlaska@redhat.com> - 0.13.0-0.2.20110607
- Adjust autotestd.service to ensure proper Group= is used
- Additional autotest-server requirements added

* Tue May 31 2011 James Laska <jlaska@redhat.com> - 0.13.0-0.1.20110531
- Package pre-0.13.0 release
- Updated and reduced local patchset
- Remove client/deps and client/profilers/* from package
- Include autotestd.service systemd file
- frontend/settings.py - Disable frontend.planner until complete

* Wed Apr 13 2011 James Laska <jlaska@redhat.com> - 0.12.0-4
- Add filter_requires_in for boottool (perl-Linux-Bootloader)
- Patch for proper systemd support (changeset 5300)

* Tue Jan 25 2011 James Laska <jlaska@redhat.com> - 0.12.0-3
- Add Requires for rsync, openssh-{clients,server}
- Add BuildRequires on python

* Thu Jan 20 2011 James Laska <jlaska@redhat.com> - 0.12.0-2
- Change Requires to java-openjdk

* Tue Jun 22 2010 James Laska <jlaska@redhat.com> - 0.12.0-1
- New upstream release autotest-0.12.0
- Updated patchset
- Combine autotest and autotest-client
- Rename initscript to autotestd
- Add conmux directory, required even if conmux isn't used

* Thu Nov 19 2009 James Laska <jlaska@redhat.com> - 0.11.0-4
- Updated Patch4 (0004-Change-usr-local-to-usr-share.patch) so that
  global_config.ini also uses /usr/share/autotest

* Fri Nov 13 2009 James Laska <jlaska@redhat.com> - 0.11.0-3
- Moved autotest user creation into autotest-client package

* Tue Oct 30 2009 James Laska <jlaska@redhat.com> - 0.11.0-2
- Updated patch2 - new_tko/tko/graphing.py uses simplejson also
- Updated patch3 - correct http log paths
- Updated patch5 - background patch to work against monitor_db_babysitter
- Updated patch7 - RH style initscript updated to use monitor_db_babysitter
- Add patch9 to correct new_tko models.py issue with older django

* Tue Aug 25 2009 Jesse Keating <jkeating@redhat.com> - 0.11.0-1
- Update for 0.11
- Drop unneeded patches
- Re-order patches with new upstream code set

* Fri Jul 31 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-8
- Fix AFE loading with the missing site_rpc_interface

* Tue Jul 14 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-7
- Remove the all-directives file, it is now redundant

* Wed Jul 08 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-6
- Move apache config files into /etc/
- Drop some unneeded files
- Set permissions accordingly
- Remove unneeded #! and add a missing one

* Tue Jul 07 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-5
- Make README.fedora a patch to the source code
- Make initscript a patch to the source code
- re-work background patch to be git compliant
- Remove macros for install
- Drop release level requirement on autotest-client.  Version is good enough

* Mon Jun 29 2009 James Laska <jlaska@redhat.com> - 0.10.0-4
- Add README.fedora
- Add autotest initscript
- Make scheduler/monitor_db.py executable

* Sat Jun 27 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-3
- Move ssh key into autotest home .ssh/ and name it generically
- Ghost the ssh dir
- More selinux fixes

* Fri Jun 26 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-2
- Patch path issues
- Set a shell for the autotest user to allow running init script
- Fix ssh key generation to run as autotest user
- SELinux fixes

* Tue Jun 16 2009 Jesse Keating <jkeating@redhat.com> - 0.10.0-1
- Initial attempt at packaging, adding to start from Lucas Meneghel Rodrigues
  <lmr@redhat.com>
