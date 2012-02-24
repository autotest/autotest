#!/bin/sh

ATHOME=/usr/local/autotest
DATETIMESTAMP=$(date "+%m-%d-%Y-%H-%M-%S")
BASENAME=$(echo $(basename $0) | cut -f1 -d '.')
LOG="/tmp/$BASENAME-$DATETIMESTAMP.log"

print_log() {
echo $(date "+%H:%M:%S") $1 '|' $2 | tee -a $LOG
}

usage() {
cat << EOF
usage: $0 [options]

This script installs the autotest server on a given Fedora 16 system.

OPTIONS:
   -h      Show this message
   -u      Autotest user password
   -d      Autotest MySQL database password
EOF
}

ATPASSWD=
MYSQLPW=
while getopts "hu:d:" OPTION
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
         ?)
             usage
             exit
             ;;
     esac
done

if [[ -z $ATPASSWD ]] || [[ -z $MYSQLPW ]]
then
     usage
     exit 1
fi

print_log "INFO" "Installing the Autotest server"
print_log "INFO" "A log of operation is kept in $LOG"
print_log "INFO" "Install started at: $(date)"

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

print_log "INFO" "Installing utility packages"
yum install -y unzip wget >> $LOG 2>&1
print_log "INFO" "Installing webserver packages"
yum install -y httpd mod_python Django >> $LOG 2>&1
print_log "INFO" "Installing py-mysql packages"
yum install -y mysql-server MySQL-python >> $LOG 2>&1
print_log "INFO" "Installing development packages"
yum install -y git java-1.6.0-openjdk-devel >> $LOG 2>&1
print_log "INFO" "Installing python libraries"
yum install -y python-imaging python-crypto python-paramiko python-httplib2 numpy python-matplotlib python-atfork >> $LOG 2>&1
print_log "INFO" "Installing/updating selinux policy"
yum install -y selinux-policy selinux-policy-targeted policycoreutils-python >> $LOG 2>&1

# Turns out the problem "AttributeError: 'module' object has no attribute 'default'"
# is in fact an SELinux problem. I did try to fix it, but couldn't, this needs to
# be investigated more carefully.
print_log "INFO" "Disabling SELinux (sorry guys...)"
if [ -x /selinux/enforce ]
then
    echo 0 > /selinux/enforce
fi
setenforce 0

print_log "INFO" "Starting MySQL server"
if [ -x /etc/init.d/mysqld ]
then
    chkconfig --level 2345 mysqld on >> $LOG
    /etc/init.d/mysqld restart >> $LOG
else
    systemctl enable mysqld.service >> $LOG
    systemctl restart mysqld.service >> $LOG
fi

print_log "INFO" "Installing autotest"
if [ "$(grep "^autotest:" /etc/passwd)" = "" ]
then
    print_log "INFO" "Adding user autotest"
    useradd autotest
    print_log "INFO" "Setting autotest user password"
    echo "$ATPASSWD
$ATPASSWD" | passwd --stdin autotest >> $LOG
fi

mkdir -p /usr/local
if [ ! -e $ATHOME/.git/config ]
then
    print_log "INFO" "Cloning autotest repo in $ATHOME"
    cd /usr/local
    git clone git://github.com/autotest/autotest.git
else
    print_log "INFO" "Updating autotest repo in $ATHOME"
    cd $ATHOME
    git checkout master
    git pull
fi

print_log "INFO" "Setting proper permissions for the autotest directory"
chown -R autotest:autotest $ATHOME

print_log "INFO" "Verifying MySQL root password"
mysqladmin -u root password $MYSQLPW > /dev/null 2>&1

DB=$(echo "use autotest_web;" | mysql --user=root --password=$MYSQLPW 2>&1)
if [ "$(echo $DB | grep 'Access denied')" != "" ]
then
    print_log "ERROR" "MySQL already has a different root password"
    exit 1
fi
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

print_log "INFO" "Running autotest dependencies build (may take a while since it might download files)"
cat << EOF | su - autotest >> $LOG 2>&1
/usr/local/autotest/utils/build_externals.py
EOF

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

print_log "INFO" "Setting up the autotest configuration files"

# TODO: notify_email in [SCHEDULER] section of global_config.ini

cat << EOF | su - autotest >> $LOG 2>&1
/usr/local/bin/substitute please_set_this_password "$MYSQLPW" $ATHOME/global_config.ini
EOF

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

print_log "INFO" "Re-starting MySQL server"
if [ -x /etc/init.d/mysqld ]
then
    /etc/init.d/mysqld restart >> $LOG
else
    systemctl restart mysqld.service >> $LOG
fi

# Patch up a python 2.7 problem
if [ "$(grep '^CFUNCTYPE(c_int)(lambda: None)' /usr/lib64/python2.7/ctypes/__init__.py)" != "" ]
then
    /usr/local/bin/substitute 'CFUNCTYPE(c_int)(lambda: None)' '# CFUNCTYPE(c_int)(lambda: None)' /usr/lib64/python2.7/ctypes/__init__.py
fi

print_log "INFO" "Building the web rpc client (may take up to 10 minutes)"
cat << EOF | su - autotest >> $LOG
/usr/local/autotest/utils/compile_gwt_clients.py -a
EOF

print_log "INFO" "Import the base tests and profilers"
cat << EOF | su - autotest >> $LOG
/usr/local/autotest/utils/test_importer.py -A
EOF

print_log "INFO" "Restarting web server"
if [ -x /etc/init.d/httpd ]
then
    /etc/init.d/httpd restart
else
    systemctl restart httpd.service
fi

print_log "INFO" "Starting the scheduler"
if [ -x /etc/init.d/httpd ]
then
    cp $ATHOME/utils/autotest-rh.init /etc/init.d/autotest >> $LOG
    chmod +x /etc/init.d/autotest >> $LOG
    chkconfig --level 2345 autotest on >> $LOG
    /etc/init.d/autotest stop >> $LOG
    rm -f $ATHOME/monitor_db_babysitter.pid $ATHOME/monitor_db.pid
    /etc/init.d/autotest start >> $LOG
else
    cp $ATHOME/utils/autotestd.service /etc/systemd/system/ >> $LOG
    systemctl daemon-reload >> $LOG
    systemctl enable autotestd.service >> $LOG
    systemctl stop autotestd.service >> $LOG
    rm -f $ATHOME/monitor_db_babysitter.pid $ATHOME/monitor_db.pid
    systemctl start autotestd.service >> $LOG
fi

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

print_log "INFO" "$(systemctl status autotestd.service)"

cd $ATHOME/client/common_lib/
VERSION="$(./version.py)"
print_log "INFO" "Finished installing autotest server $VERSION at: $(date)"

IP="$(ifconfig | grep 'inet addr:' | grep -v '127.0.0.1' | grep -v 192.168.122 | cut -d: -f2 | awk '{ print $1}')"
print_log "INFO" "You can access your server on http://$IP/afe"
