#!/bin/sh

. /etc/default/plainbox-ci-mailer
[ -z "$SUBMIT_CGI" ] && exit 1
RELEASE=$(lsb_release -ds)
IP=$(ip addr show dev eth0 |grep "inet " |cut -f 6 -d " ")
HOST=$(hostname)

notification() {
    if [ -f $CHECKBOX_SERVER_CONF ]; then
        curl -F mini_ci_notification_installed="CheckBox NG CI testing run has installed on $RELEASE server $HOST $IP" $SUBMIT_CGI
    elif [ -f $CHECKBOX_DESKTOP_XDG ]; then
        curl -F mini_ci_notification_installed="CheckBox NG CI testing run has installed on $RELEASE desktop $HOST $IP" $SUBMIT_CGI
    else
        curl -F mini_ci_notification_installed="CheckBox NG CI testing run installation has something wrong on $RELEASE $HOST $IP" $SUBMIT_CGI
    fi
}

mailer() {
    if [ -f $CHECKBOX_UPSTART_LOG ]; then
        MESSAGE=$CHECKBOX_UPSTART_LOG
        # workaround for 14.04.1 and 14.04.2 will get tag 14.04.3
        # because the package base-files update its information
        RELEASE=$(awk {'print $2'} /var/log/installer/media-info)
        SUBJECT="CheckBox NG CI testing run for $RELEASE server"
    elif [ -f $CHECKBOX_DESKTOP_LOG ]; then
        MESSAGE=$CHECKBOX_DESKTOP_LOG
        SUBJECT="CheckBox NG CI testing run for $RELEASE desktop"
    else
        MESSAGE="Something failed and CheckBoxNG didn't even start."
        SUBJECT="FAILED CheckBoxNG CI testing run for $RELEASE"
    fi
    IP=$(ip addr show dev eth0 |grep "inet " |cut -f 6 -d " ")
    HOST=$(hostname)
    SUBJECT="$SUBJECT - $HOST $IP"
    if [ -f "$MESSAGE" ] ; then
        dpkg --list "*checkbox*" "*plainbox*" >> $MESSAGE
        if run_chc >> $MESSAGE ; then
            SUBJECT="$SUBJECT and canonical-hw-collection(Tested); "
        else
            SUBJECT="$SUBJECT and canonical-hw-collection(Failed); "  
        fi
        curl -F subject="$SUBJECT" -F plainbox_output=@$MESSAGE $SUBMIT_CGI
    else
        curl -F subject="$SUBJECT" -F plainbox_output="$MESSAGE" $SUBMIT_CGI
    fi
    sleep 10
    shutdown -h now
}

run_chc() {
# run canonical-hw-collection tests

if which canonical-hw-collection ; then

    canonical-hw-collection --staging "$(checkbox check-config|grep secure_id|cut -d= -f2 )"

else
    
    echo "canonical-hw-collection may not install correctly"

fi
}

case "$1" in
   notification)
      notification
   ;;
   mailer)
      mailer
   ;;
   run_chc)
      run_chc
   ;;
   *)
      echo "Usage: $0 {notification|mailer}"
   ;;
esac

