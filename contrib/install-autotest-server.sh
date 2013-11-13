#!/bin/bash

ATHOME_DEFAULT=/usr/local/autotest
AUTOTEST_DEFAULT_GIT_REPO='git://github.com/autotest/autotest.git'
AUTOTEST_DEFAULT_GIT_BRANCH='master'
DATETIMESTAMP=$(date "+%m-%d-%Y-%H-%M-%S")
BASENAME=$(echo $(basename $0) | cut -f1 -d '.')
LOG="/tmp/$BASENAME-$DATETIMESTAMP.log"
ATPASSWD=
MYSQLPW=
INSTALL_PACKAGES_ONLY=0
export LANG=en_US.utf8

print_log() {
echo $(date "+%H:%M:%S") $1 '|' $2 | tee -a $LOG
}

usage() {
cat << EOF
usage: $0 [options]

This script installs the autotest server on a given system.

Currently tested systems - Up to date versions of:

 * Fedora 16
 * Fedora 17
 * Fedora 18
 * RHEL 6.2
 * Ubuntu 12.04
 * Ubuntu 12.10

GENERAL OPTIONS:
   -h      Show this message
   -u      Autotest user password
   -d      MySQL password (both mysql root and autotest_web db)
   -a      Autotest base dir (defaults to $ATHOME_DEFAULT)
   -g      Autotest git repo (defaults to $AUTOTEST_DEFAULT_GIT_REPO)
   -b      Autotest git branch (defaults to $AUTOTEST_DEFAULT_GIT_BRANCH)
   -t      Autotest tests branch (defaults to $AUTOTEST_DEFAULT_GIT_BRANCH)
   -c      Autotest git commit (defaults to no commit)

If you plan on testing your own autotest branch, make sure to set -t to a
valid upstream branch (such as master or next).

INSTALLATION STEP SELECTION:
   -p      Only install packages
   -n      Do not update autotest git repo. Useful if using a modified
           local tree, usually when testing a modified version of this script
EOF
}

while getopts "hpna:g:b:c:u:d:t:" OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         a)
             ATHOME=$OPTARG
             ;;
         u)
             ATPASSWD=$OPTARG
             ;;
         d)
             MYSQLPW=$OPTARG
             ;;
         g)
             AUTOTEST_GIT_REPO=$OPTARG
             ;;
         b)
             AUTOTEST_GIT_BRANCH=$OPTARG
             ;;
         t)
             AUTOTEST_TESTS_BRANCH=$OPTARG
             ;;
         c)
             AUTOTEST_GIT_COMMIT=$OPTARG
             ;;
         p)
             INSTALL_PACKAGES_ONLY=1
             ;;
         n)
             DONT_UPDATE_GIT=1
             ;;
         ?)
             usage
             exit
             ;;
     esac
done

check_command_line_params() {
if [[ -z $ATPASSWD ]] || [[ -z $MYSQLPW ]]
then
     usage
     exit 1
fi
if [[ -z $ATHOME ]]
then
     ATHOME=$ATHOME_DEFAULT
fi
if [[ -z $AUTOTEST_GIT_REPO ]]
then
     AUTOTEST_GIT_REPO=$AUTOTEST_DEFAULT_GIT_REPO
fi
if [[ -z $AUTOTEST_GIT_BRANCH ]]
then
     AUTOTEST_GIT_BRANCH=$AUTOTEST_DEFAULT_GIT_BRANCH
fi
if [[ -z $AUTOTEST_TESTS_BRANCH ]]
then
     AUTOTEST_TESTS_BRANCH=$AUTOTEST_GIT_BRANCH
fi
}

check_disk_space() {
LOCALFREE=$(df -kP /usr/local | awk '{ print $4 }' | grep -v Avai)
VARFREE=$(df -kP /var | awk '{ print $4 }' | grep -v Avai)

LOCALFREE_HUMAN=$(df -HP /usr/local | awk '{ print $4 }' | grep -v Avai)
VARFREE_HUMAN=$(df -HP /var | awk '{ print $4 }' | grep -v Avai)

print_log "INFO" "/usr/local free $LOCALFREE_HUMAN"
print_log "INFO" "/var free $VARFREE_HUMAN"

if expr $LOCALFREE \< 5000 > /dev/null
then
    print_log "ERROR" "You should have more free space in /usr/local"
    exit 1
fi
if expr $VARFREE \< 10000 > /dev/null
then
    print_log "ERROR" "You should have more free space in /var"
    exit 1
fi
}

setup_substitute() {
if [ ! -x /usr/local/bin/substitute ]
then
    mkdir -p /usr/local/bin
    cat << EOF > /usr/local/bin/substitute
#! /bin/sh

if [ "\$1" = "" -o "\$3" = "" ]
then
    echo usage : \$0 old_string new_string files ...
    exit 1
fi

old_string=\$1
new_string=\$2
shift
shift

echo Substituting \$old_string by \$new_string in

while [ "\$1" != "" ]
do
    echo -n \$1 " : "
    # To avoid the basename expression to be evaluated
    tmpname=$(echo '$(basename $1)')
    if [ ! -f "\$1" ]
    then
        echo warning : \$1 "doesn't exist"
        shift
        continue
    fi
    if [ -L "\$1" ]
    then
        echo warning : \$1 symbolic link, skipped
        shift
        continue
    fi
    if [ ! -w "\$1" ]
    then
        echo warning : \$1 non writable, skipped
        shift
       continue
    fi

    rm -f /tmp/substitute_\$\$_\$1

    sed s+"\$old_string"+"\$new_string"+g < \$1 > /tmp/substitute_\$\$_\$tmpname

    if [ "\$?" != "0" ]
    then
        echo no change
        rm -f /tmp/substitute_\$\$_\$tmpname
    else
        if [ "\$?" = "1" ]
    then
        echo changed
        mv \$1 \$1.old
        mv /tmp/substitute_\$\$_\$tmpname \$1
    else
        echo "trouble ..."
        rm -f /tmp/substitute_\$\$_\$tmpname
        exit 1
    fi
    fi
    shift
done

EOF
    chmod +x /usr/local/bin/substitute

fi
}

setup_epel_repo() {
if [ -f /etc/redhat-release ]
then

    if [ ! -f /etc/yum.repos.d/epel.repo ]
    then
        if [ "`grep 'release 6' /etc/redhat-release`" != "" ]
        then
            print_log "INFO" "Adding EPEL 6 repository"
            rpm -ivh http://download.fedoraproject.org/pub/epel/6/`arch`/epel-release-6-8.noarch.rpm >> $LOG 2>&1
        fi
    fi
fi
}

install_basic_pkgs_rh() {
    print_log "INFO" "Installing basic packages"
    yum install -y git passwd >> $LOG 2>&1
    if [ $? != 0 ]
    then
        print_log "ERROR" "Failed to install basic packages"
        exit 1
    fi
}

install_basic_pkgs_deb() {
    print_log "INFO" "Installing basic packages"
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y git makepasswd >> $LOG 2>&1
    if [ $? != 0 ]
    then
        print_log "ERROR" "Failed to install basic packages"
        exit 1
    fi
}

install_packages() {
    print_log "INFO" "Installing packages dependencies"
    $ATHOME/installation_support/autotest-install-packages-deps >> $LOG 2>&1
    if [ $? != 0 ]
    then
        print_log "ERROR" "Failed to install autotest packages dependencies"
        exit 1
    fi
}

setup_selinux() {
# Turns out the problem "AttributeError: 'module' object has no attribute 'default'"
# is in fact an SELinux problem. I did try to fix it, but couldn't, this needs to
# be investigated more carefully.
print_log "INFO" "Disabling SELinux (sorry guys...)"
if [ -f /selinux/enforce ]
then
    echo 0 > /selinux/enforce
fi

setenforce 0

if [ -f /etc/selinux/config ]
then
    /usr/local/bin/substitute 'SELINUX=enforcing' 'SELINUX=permissive' /etc/selinux/config
fi
}

setup_mysql_service_deb() {
print_log "INFO" "Enabling MySQL server on boot"
update-rc.d mysql defaults >> $LOG
}

setup_mysql_service_rh() {
print_log "INFO" "Enabling MySQL server on boot"
if [ -x /etc/init.d/mysqld ]
then
    chkconfig --level 2345 mysqld on >> $LOG
else
    systemctl enable mysqld.service >> $LOG
fi
}

create_autotest_user_deb() {
print_log "INFO" "Creating autotest user"
if [ "$(grep "^autotest:" /etc/passwd)" = "" ]
then
    print_log "INFO" "Adding user autotest"
    echo $ATPASSWD > /tmp/pwd
    useradd -d $ATHOME autotest -s /bin/bash -p $(makepasswd --crypt-md5 --clearfrom=/tmp/pwd | awk '{print $2}')
    rm -rf /tmp/pwd
fi
}

create_autotest_user_rh() {
print_log "INFO" "Creating autotest user"
if [ "$(grep "^autotest:" /etc/passwd)" = "" ]
then
    print_log "INFO" "Adding user autotest"
    useradd -d $ATHOME autotest
    print_log "INFO" "Setting autotest user password"
    echo "$ATPASSWD
$ATPASSWD" | passwd --stdin autotest >> $LOG
fi
}

get_autotest_from_git() {
print_log "INFO" "Cloning autotest repo $AUTOTEST_GIT_REPO, branch $AUTOTEST_GIT_BRANCH in $ATHOME"
cd $ATHOME
git init
git remote add origin $AUTOTEST_GIT_REPO
git config branch.$AUTOTEST_GIT_BRANCH.remote origin
git config branch.$AUTOTEST_GIT_BRANCH.merge refs/heads/$AUTOTEST_GIT_BRANCH
git pull
git checkout $AUTOTEST_GIT_BRANCH
if [ -n $AUTOTEST_GIT_COMMIT ]; then
    git checkout $AUTOTEST_GIT_COMMIT
    git checkout -b specific-commit-branch
fi
}

install_autotest() {
print_log "INFO" "Installing autotest"
mkdir -p $ATHOME
if [ ! -e $ATHOME/.git/config ]
then
    get_autotest_from_git
else
    if [ -z $DONT_UPDATE_GIT ]; then
       print_log "INFO" "Updating autotest repo in $ATHOME"
       cd $ATHOME
       git checkout master
       git pull
    fi
fi

print_log "INFO" "Initializing and updating tests to the latest $AUTOTEST_TESTS_BRANCH"
cd $ATHOME
git submodule init
git submodule update --recursive
cd $ATHOME/client/tests
git checkout $AUTOTEST_TESTS_BRANCH
cd $ATHOME/client/tests/virt
git checkout $AUTOTEST_TESTS_BRANCH
cd $ATHOME/server/tests
git checkout $AUTOTEST_TESTS_BRANCH

print_log "INFO" "Setting proper permissions for the autotest directory"
chown -R autotest:autotest $ATHOME
chmod 775 $ATHOME
}

update_packages() {
print_log "INFO" "Updating package dependencies"
$ATHOME/installation_support/autotest-install-packages-deps >> $LOG 2>&1
}


check_mysql_password() {
print_log "INFO" "Setting MySQL root password"
mysqladmin -u root password $MYSQLPW > /dev/null 2>&1

print_log "INFO" "Verifying MySQL root password"
$ATHOME/installation_support/autotest-database-turnkey --check-credentials --root-password=$MYSQLPW
if [ $? != 0 ]
then
    print_log "ERROR" "MySQL already has a different root password"
    exit 1
fi
}

create_autotest_database() {
print_log "INFO" "Creating MySQL databases for autotest"
$ATHOME/installation_support/autotest-database-turnkey -s --root-password=$MYSQLPW -p $MYSQLPW > /dev/null 2>&1
if [ $? != 0 ]
then
    print_log "ERROR" "Error creating MySQL database"
    exit 1
fi
}

build_external_packages() {
print_log "INFO" "Running autotest dependencies build (may take a while since it might download files)"
cat << EOF | su - autotest >> $LOG 2>&1
$ATHOME/utils/build_externals.py
EOF
}

relocate_global_config() {
if [ $ATHOME != $ATHOME_DEFAULT ]
then
    print_log "INFO" "Relocating global_config.ini entries to $ATHOME"
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/global_config.ini
fi
}

relocate_frontend_wsgi() {
if [ $ATHOME != $ATHOME_DEFAULT ]
then
    print_log "INFO" "Relocating frontend.wsgi to $ATHOME"
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/frontend/frontend.wsgi
fi
}

relocate_webserver() {
if [ $ATHOME != $ATHOME_DEFAULT ]
then
    print_log "INFO" "Relocating apache config files to $ATHOME"
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/afe-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/django-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/embedded-spreadsheet-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/embedded-tko-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/new-tko-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/conf/tko-directives
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/apache-conf
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/apache-web-conf
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/apache/drone-conf
fi
}

configure_webserver_deb() {
print_log "INFO" "Configuring Web server"
if [ ! -e  /etc/apache2/sites-enabled/001-autotest ]
then
    /usr/local/bin/substitute "WSGISocketPrefix run/wsgi" "#WSGISocketPrefix run/wsgi" $ATHOME/apache/conf/django-directives
    sudo rm /etc/apache2/sites-enabled/000-default
    if [ -f /etc/apache2/mods-available/version.load ]; then
	sudo ln -s /etc/apache2/mods-available/version.load /etc/apache2/mods-enabled/
    fi
    sudo ln -s $ATHOME/apache/conf /etc/apache2/autotest.d
    sudo ln -s $ATHOME/apache/apache-conf /etc/apache2/sites-enabled/001-autotest
    sudo ln -s $ATHOME/apache/apache-web-conf /etc/apache2/sites-enabled/002-autotest
fi
a2enmod rewrite
update-rc.d apache2 defaults
}

configure_webserver_rh() {
print_log "INFO" "Configuring Web server"
if [ ! -e  /etc/httpd/conf.d/autotest.conf ]
then
    # if for some reason, still running with mod_python, let it be parsed before the
    # autotest config file, which has some directives to detect it
    ln -s $ATHOME/apache/conf /etc/httpd/autotest.d
    ln -s $ATHOME/apache/apache-conf /etc/httpd/conf.d/z_autotest.conf
    ln -s $ATHOME/apache/apache-web-conf /etc/httpd/conf.d/z_autotest-web.conf
fi
if [ -x /etc/init.d/httpd ]
then
    chkconfig --level 2345 httpd on
else
    systemctl enable httpd.service >> $LOG
fi
}

restart_mysql_deb() {
print_log "INFO" "Re-starting MySQL server"
service mysql restart >> $LOG
}

restart_mysql_rh() {
print_log "INFO" "Re-starting MySQL server"
if [ -x /etc/init.d/mysqld ]
then
    service mysqld restart >> $LOG
else
    systemctl restart mysqld.service >> $LOG
fi
}

patch_python27_bug() {
#
# We may not be on python 2.7
#
if [ -d  /usr/lib64/python2.7 ]
then
    # Patch up a python 2.7 problem
    if [ "$(grep '^CFUNCTYPE(c_int)(lambda: None)' /usr/lib64/python2.7/ctypes/__init__.py)" != "" ]
    then
        /usr/local/bin/substitute 'CFUNCTYPE(c_int)(lambda: None)' '# CFUNCTYPE(c_int)(lambda: None)' /usr/lib64/python2.7/ctypes/__init__.py
    fi
fi
}

build_web_rpc_client() {
print_log "INFO" "Building the web rpc client (may take up to 10 minutes)"
cat << EOF | su - autotest >> $LOG
$ATHOME/utils/compile_gwt_clients.py -a
EOF
}

import_tests() {
print_log "INFO" "Import the base tests and profilers"
cat << EOF | su - autotest >> $LOG
$ATHOME/utils/test_importer.py -A
EOF
}

restart_apache_deb() {
print_log "INFO" "Restarting web server"
service apache2 restart
}

restart_apache_rh() {
print_log "INFO" "Restarting web server"
if [ -x /etc/init.d/httpd ]
then
    service httpd restart
else
    systemctl restart httpd.service
fi
}

relocate_scheduler() {
if [ $ATHOME != $ATHOME_DEFAULT ]
then
    print_log "INFO" "Relocating scheduler scripts and service files to $ATHOME"
    /usr/local/bin/substitute "BASE_DIR=$ATHOME_DEFAULT" "BASE_DIR=$ATHOME" $ATHOME/utils/autotest.init
    /usr/local/bin/substitute 'AUTOTEST_DIR="/usr/local/$PROG"' "AUTOTEST_DIR=$ATHOME" $ATHOME/utils/autotest-rh.init
    /usr/local/bin/substitute $ATHOME_DEFAULT $ATHOME $ATHOME/utils/autotestd.service
fi
}

start_scheduler_deb() {
print_log "INFO" "Installing/starting scheduler"
cp $ATHOME/utils/autotest.init /etc/init.d/autotest >> $LOG
chmod +x /etc/init.d/autotest >> $LOG
update-rc.d autotest defaults >> $LOG
service autotest stop >> $LOG
rm -f $ATHOME/autotest-scheduler.pid $ATHOME/autotest-scheduler-watcher.pid
service autotest start >> $LOG
}

start_scheduler_rh() {
print_log "INFO" "Installing/starting scheduler"
if [ ! -d /etc/systemd ]
then
    cp $ATHOME/utils/autotest-rh.init /etc/init.d/autotest >> $LOG
    chmod +x /etc/init.d/autotest >> $LOG
    chkconfig --level 2345 autotest on >> $LOG
    service autotest stop >> $LOG
    rm -f $ATHOME/autotest-scheduler.pid $ATHOME/autotest-scheduler-watcher.pid
    service autotest start >> $LOG
else
    cp $ATHOME/utils/autotestd.service /etc/systemd/system/ >> $LOG
    systemctl daemon-reload >> $LOG
    systemctl enable autotestd.service >> $LOG
    systemctl stop autotestd.service >> $LOG
    rm -f $ATHOME/autotest-scheduler.pid $ATHOME/autotest-scheduler-watcher.pid
    systemctl start autotestd.service >> $LOG
fi
}

setup_firewall_firewalld() {
    echo "Opening firewall for http traffic" >> $LOG
    echo "Opening firewall for http traffic"

    $ATHOME/installation_support/autotest-firewalld-add-service -s http
    firewall-cmd --reload
}

setup_firewall_iptables() {
if [ "$(grep -- '--dport 80 -j ACCEPT' /etc/sysconfig/iptables)" = "" ]
then
    echo "Opening firewall for http traffic" >> $LOG
    echo "Opening firewall for http traffic"
    awk '/-A INPUT -i lo -j ACCEPT/ { print; print "-A INPUT -m state --state NEW -m tcp -p tcp --dport 80 -j ACCEPT"; next}
{print}' /etc/sysconfig/iptables > /tmp/tmp$$
    if [ ! -f /etc/sysconfig/iptables.orig ]
    then
        cp /etc/sysconfig/iptables /etc/sysconfig/iptables.orig
    fi
    cp /tmp/tmp$$ /etc/sysconfig/iptables
    rm /tmp/tmp$$

    if [ -x /etc/init.d/iptables ]
    then
        service iptables restart >> $LOG
    else
        systemctl restart iptables.service >> $LOG
    fi
fi
}

setup_firewall() {
if [ -f /etc/sysconfig/iptables ]
then
   setup_firewall_iptables
elif [ -x /usr/bin/firewall-cmd ]
then
   setup_firewall_firewalld
fi
}


print_install_status() {
if [ -x /etc/init.d/autotest ]
then
    print_log "INFO" "$(service autotest status)"
else
    print_log "INFO" "$(systemctl status autotestd.service)"
fi
}

print_version_and_url() {
cd $ATHOME/client/shared/
VERSION="$(./version.py)"
print_log "INFO" "Finished installing autotest server $VERSION at: $(date)"

DEFAULT_INTERFACE=$(ip route show to 0.0.0.0/0.0.0.0 | cut -d ' ' -f 5)
IP="$(ip address show dev $DEFAULT_INTERFACE | grep 'inet ' | awk '{print $2}' | cut -d '/' -f 1)"
print_log "INFO" "You can access your server on http://$IP/afe"
}

full_install() {
    check_command_line_params

    print_log "INFO" "Installing the Autotest server"
    print_log "INFO" "A log of operation is kept in $LOG"
    print_log "INFO" "Install started at: $(date)"

    if [ -f /etc/redhat-release ]
    then
        check_disk_space
        setup_substitute
        setup_epel_repo
        install_basic_pkgs_rh
    elif [ -f /etc/debian_version ]
    then
        check_disk_space
        setup_substitute
        install_basic_pkgs_deb
    else
        print_log "Sorry, I can't recognize your distro, exiting..."
    fi

    if [ $INSTALL_PACKAGES_ONLY == 0 ]
    then
        if [ -f /etc/redhat-release ]
        then
            setup_selinux
            create_autotest_user_rh
            install_autotest
            install_packages
            setup_mysql_service_rh
            restart_mysql_rh
            check_mysql_password
            create_autotest_database
            build_external_packages
            relocate_global_config
            relocate_frontend_wsgi
            relocate_webserver
            configure_webserver_rh
            restart_mysql_rh
            patch_python27_bug
            build_web_rpc_client
            import_tests
            restart_apache_rh
            relocate_scheduler
            start_scheduler_rh
            setup_firewall
            print_install_status
            print_version_and_url
        elif [ -f /etc/debian_version ]
        then
            create_autotest_user_deb
            install_autotest
            install_packages
            setup_mysql_service_deb
            restart_mysql_deb
            check_mysql_password
            create_autotest_database
            build_external_packages
            relocate_global_config
            relocate_frontend_wsgi
            relocate_webserver
            configure_webserver_deb
            restart_mysql_deb
            build_web_rpc_client
            import_tests
            restart_apache_deb
            relocate_scheduler
            start_scheduler_deb
            print_install_status
            print_version_and_url
        else
            print_log "ERROR" "Sorry, I can't recognize your distro, exiting..."
            exit 1
        fi
    fi
}

full_install
