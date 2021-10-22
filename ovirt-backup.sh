#!/bin/bash
#
# backup service      Startup script for eg_daemon
#
# chkconfig: - 87 12
# description: backup service is a dummy Python-based daemon
# config: /etc/backup service/backup service.conf
# config: /etc/sysconfig/backup service
# pidfile: /var/run/ov-backup.pid
#
### BEGIN INIT INFO
# Provides: backup service
# Required-Start: $local_fs
# Required-Stop: $local_fs
# Short-Description: start and stop backup service
# Description: backup service is a dummy Python-based daemon
### END INIT INFO

main_daemon=$(pwd)/main_daemon.py
prog='backup service'
pidfile=${PIDFILE-/var/run/xrdp/ov-backup.pid}
RETVAL=0

OPTIONS=""

start() {
        echo $"Starting $prog... "

        if [[ -f ${pidfile} ]] ; then
            pid=$( cat $pidfile  )
            isrunning=$( ps -elf | grep  $pid | grep -v grep )

            if [[ -n ${isrunning} ]] ; then
                echo $"$prog already running"
                return 0
            fi
        fi
        python $main_daemon -p $pidfile $OPTIONS
        RETVAL=$?
        # [ $RETVAL = 0 ] && success || failure
        return $RETVAL
}

stop() {
    if [[ -f ${pidfile} ]] ; then
        pid=$( cat $pidfile )
        isrunning=$( ps -elf | grep $pid | grep -v grep | awk '{print $4}' )

        if [[ ${isrunning} -eq ${pid} ]] ; then
            echo $"Stopping $prog... "
            kill $pid
        fi
        RETVAL=$?
    else
        echo $"$prog already stopped"
    fi
    return $RETVAL
}

reload() {
    echo -n $"Reloading $prog: "
    echo
}

# See how we were called.
case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  status)
    status -p $pidfile $main_daemon
    RETVAL=$?
    ;;
  restart)
    stop
    start
    ;;
  force-reload|reload)
    reload
    ;;
  *)
    echo $"Usage: $prog {start|stop|restart|force-reload|reload|status}"
    RETVAL=2
esac

exit $RETVAL
