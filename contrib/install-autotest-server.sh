#!/bin/sh

ATHOME=/usr/local/autotest
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
Currently supported systems: Fedora 16 and RHEL 6.2.

GENERAL OPTIONS:
   -h      Show this message
   -u      Autotest user password
   -d      MySQL password (both mysql root and autotest_web db)

INSTALLATION STEP SELECTION:
   -p      Only install packages
EOF
}

while getopts "hu:d:p" OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         u)
             ATPASSWD=$OPTARG
             ;;
         d)
             MYSQLPW=$OPTARG
             ;;
         p)
             INSTALL_PACKAGES_ONLY=1
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
            rpm -ivh http://download.fedoraproject.org/pub/epel/6/`arch`/epel-release-6-5.noarch.rpm >> $LOG 2>&1
        fi
    fi
fi
}

install_packages() {
PACKAGES_UTILITY=(unzip wget)
PACAKGES_WEBSERVER=(httpd mod_python Django)
PACKAGES_MYSQL=(mysql-server MySQL-python)
PACKAGES_DEVELOPMENT=(git java-1.6.0-openjdk-devel)
PACKAGES_PYTHON_LIBS=(python-imaging python-crypto python-paramiko python-httplib2 numpy python-matplotlib python-atfork)
PACKAGES_SELINUX=(selinux-policy selinux-policy-targeted policycoreutils-python)
PACKAGES_ALL=( \
    ${PACKAGES_UTILITY[*]}
    ${PACAKGES_WEBSERVER[*]}
    ${PACKAGES_MYSQL[*]}
    ${PACKAGES_DEVELOPMENT[*]}
    ${PACKAGES_PYTHON_LIBS[*]}
    ${PACKAGES_SELINUX[*]}
)

PKG_COUNT=$(echo ${PACKAGES_ALL[*]} | wc -w)
INSTALLED_PKG_COUNT=$(rpm -q ${PACKAGES_ALL[*]} | grep -v 'not installed' | wc -l)

if [ $PKG_COUNT == $INSTALLED_PKG_COUNT ]; then
    print_log "INFO" "All packages already installed"
else
    print_log "INFO" "Installing all packages (${PACKAGES_ALL[*]})"
    yum install -y ${PACKAGES_ALL[*]} >> $LOG 2>&1
fi
}

setup_selinux() {
# Turns out the problem "AttributeError: 'module' object has no attribute 'default'"
# is in fact an SELinux problem. I did try to fix it, but couldn't, this needs to
# be investigated more carefully.
print_log "INFO" "Disabling SELinux (sorry guys...)"
if [ -x /selinux/enforce ]
then
    echo 0 > /selinux/enforce
fi
setenforce 0
}

setup_mysql_service() {
print_log "INFO" "Starting MySQL server"
if [ -x /etc/init.d/mysqld ]
then
    chkconfig --level 2345 mysqld on >> $LOG
    /etc/init.d/mysqld restart >> $LOG
else
    systemctl enable mysqld.service >> $LOG
    systemctl restart mysqld.service >> $LOG
fi
}

install_autotest() {
print_log "INFO" "Installing autotest"
if [ "$(grep "^autotest:" /etc/passwd)" = "" ]
then
    print_log "INFO" "Adding user autotest"
    useradd -b /usr/local autotest
    print_log "INFO" "Setting autotest user password"
    echo "$ATPASSWD
$ATPASSWD" | passwd --stdin autotest >> $LOG
fi

mkdir -p /usr/local
if [ ! -e $ATHOME/.git/config ]
then
    print_log "INFO" "Cloning autotest repo in $ATHOME"
    cd $ATHOME
    git init
    git fetch -f -u -t git://github.com/autotest/autotest.git master:master
    git checkout master
else
    print_log "INFO" "Updating autotest repo in $ATHOME"
    cd $ATHOME
    git checkout master
    git pull
fi

print_log "INFO" "Setting proper permissions for the autotest directory"
chown -R autotest:autotest $ATHOME
chmod 775 $ATHOME
}

check_mysql_password() {
print_log "INFO" "Verifying MySQL root password"
mysqladmin -u root password $MYSQLPW > /dev/null 2>&1

DB=$(echo "use autotest_web;" | mysql --user=root --password=$MYSQLPW 2>&1)
if [ "$(echo $DB | grep 'Access denied')" != "" ]
then
    print_log "ERROR" "MySQL already has a different root password"
    exit 1
fi
}

create_autotest_database() {
if [ "$(echo $DB | grep 'Unknown database')" != "" ]
then
    print_log "INFO" "Creating MySQL databases for autotest"
    cat << SQLEOF | mysql --user=root --password=$MYSQLPW >> $LOG
create database autotest_web;
grant all privileges on autotest_web.* TO 'autotest'@'localhost' identified by "$MYSQLPW";
grant SELECT on autotest_web.* TO 'nobody'@'%';
grant SELECT on autotest_web.* TO 'nobody'@'localhost';
SQLEOF
fi
}

build_external_packages() {
print_log "INFO" "Running autotest dependencies build (may take a while since it might download files)"
cat << EOF | su - autotest >> $LOG 2>&1
/usr/local/autotest/utils/build_externals.py
EOF
}

configure_webserver() {
print_log "INFO" "Configuring Web server"
if [ ! -e  /etc/httpd/conf.d/autotest.conf ]
then
    ln -s /usr/local/autotest/apache/conf/all-directives /etc/httpd/conf.d/autotest.conf
    service httpd configtest
fi
if [ -x /etc/init.d/httpd ]
then
    chkconfig --level 2345 httpd on
else
    systemctl enable httpd.service >> $LOG
fi
}

configure_autotest() {
print_log "INFO" "Setting up the autotest configuration files"

# TODO: notify_email in [SCHEDULER] section of global_config.ini

cat << EOF | su - autotest >> $LOG 2>&1
/usr/local/bin/substitute please_set_this_password "$MYSQLPW" $ATHOME/global_config.ini
EOF
}

setup_databse_schema() {
TABLES=$(echo "use autotest_web; show tables;" | mysql --user=root --password=$MYSQLPW 2>&1)

if [ "$(echo $TABLES | grep tko_test_view_outer_joins)" = "" ]
then
    print_log "INFO" "Setting up the database schemas"
    cat << EOF | su - autotest >> $LOG 2>&1
yes yes | $ATHOME/database/migrate.py --database=AUTOTEST_WEB sync
yes no | /usr/local/autotest/frontend/manage.py syncdb
/usr/local/autotest/frontend/manage.py syncdb
EOF
else
    print_log "INFO" "Database schemas are already in place"
fi
}

restart_mysql() {
print_log "INFO" "Re-starting MySQL server"
if [ -x /etc/init.d/mysqld ]
then
    /etc/init.d/mysqld restart >> $LOG
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
/usr/local/autotest/utils/compile_gwt_clients.py -a
EOF
}

import_tests() {
print_log "INFO" "Import the base tests and profilers"
cat << EOF | su - autotest >> $LOG
/usr/local/autotest/utils/test_importer.py -A
EOF
}

restart_httpd() {
print_log "INFO" "Restarting web server"
if [ -x /etc/init.d/httpd ]
then
    /etc/init.d/httpd restart
else
    systemctl restart httpd.service
fi
}

start_scheduler() {
print_log "INFO" "Starting the scheduler"
if [ ! -d /etc/systemd ]
then
    cp $ATHOME/utils/autotest-rh.init /etc/init.d/autotest >> $LOG
    chmod +x /etc/init.d/autotest >> $LOG
    chkconfig --level 2345 autotest on >> $LOG
    /etc/init.d/autotest stop >> $LOG
    rm -f $ATHOME/autotest-scheduler.pid $ATHOME/autotest-scheduler-watcher.pid
    /etc/init.d/autotest start >> $LOG
else
    cp $ATHOME/utils/autotestd.service /etc/systemd/system/ >> $LOG
    systemctl daemon-reload >> $LOG
    systemctl enable autotestd.service >> $LOG
    systemctl stop autotestd.service >> $LOG
    rm -f $ATHOME/autotest-scheduler.pid $ATHOME/autotest-scheduler-watcher.pid
    systemctl start autotestd.service >> $LOG
fi
}

setup_firewall() {
[ -f /etc/sysconfig/iptables ] || return;
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
        /etc/init.d/iptables restart >> $LOG
    else
        systemctl restart iptables.service >> $LOG
    fi
fi
}

print_install_status() {
if [ -x /etc/init.d/autotest ]
then
    print_log "INFO" "$(service autotest status)"
else
    print_log "INFO" "$(systemctl status autotestd.service)"
fi

cd $ATHOME/client/shared/
VERSION="$(./version.py)"
print_log "INFO" "Finished installing autotest server $VERSION at: $(date)"

IP="$(ifconfig | grep 'inet addr:' | grep -v '127.0.0.1' | grep -v '192.168.122.1$' | cut -d: -f2 | awk '{ print $1}')"
print_log "INFO" "You can access your server on http://$IP/afe"
}

full_install() {
    check_command_line_params

    print_log "INFO" "Installing the Autotest server"
    print_log "INFO" "A log of operation is kept in $LOG"
    print_log "INFO" "Install started at: $(date)"

    check_disk_space
    setup_substitute
    setup_epel_repo
    install_packages

    if [ $INSTALL_PACKAGES_ONLY == 0 ]; then
	setup_selinux
	setup_mysql_service
	install_autotest
	check_mysql_password
	create_autotest_database
	build_external_packages
	configure_webserver
	configure_autotest
	setup_databse_schema
	restart_mysql
	patch_python27_bug
	build_web_rpc_client
	import_tests
	restart_httpd
	start_scheduler
	setup_firewall
	print_install_status
    fi
}

full_install
