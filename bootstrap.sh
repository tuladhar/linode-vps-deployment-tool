#!/bin/bash

echo "==== Bootstrap Started ===="
export DEBIAN_FRONTEND=noninteractive

LOGS_DATA_DIRS="/logs/app_services /data/app_services /data/core_services"
PUPPET_MASTER="dev.easycompany.com"
PUPPET_RUN_INTERVAL=20
PUPPET_DEB_FILE="puppetlabs-release-squeeze.deb"
PUPPET_DEB_FILE_URL="http://apt.puppetlabs.com/$PUPPET_DEB_FILE" 
PUPPET_SSL_DIR="/var/lib/puppet/ssl"
PUPPET_CONF_FILE="/etc/puppet/puppet.conf"
HOSTNAME="%{hostname}"

echo "---> SETTING HOSTNAME..."
echo "$HOSTNAME" > /etc/hostname
hostname -F /etc/hostname

echo "---> SETTING UP $LOGS_DATA_DIRS DIRECTORIES..."
mkdir -p $LOGS_DATA_DIRS

echo "---> DOWNLOADING $PUPPET_DEB_FILE_URL..."
wget $PUPPET_DEB_FILE_URL -qO /tmp/$PUPPET_DEB_FILE

echo "---> INSTALLING $PUPPET_DEB_FILE..."
dpkg -i /tmp/$PUPPET_DEB_FILE

echo "---> REMOVING $PUPPET_DEB_FILE..."
rm -f /tmp/$PUPPET_DEB_FILE

echo "---> UPDATING APT REPOSITORY..."
apt-get update

echo "---> INSTALLING PUPPET CLIENT..."
apt-get -yq install puppet

echo "---> STOPPING PUPPET CLIENT..."
service puppet stop

echo "---> REMOVING PUPPET SSL DIRECTORY ($PUPPET_SSL_DIR)..."
rm -rf $PUPPET_SSL_DIR

echo "---> CONFIGURING PUPPET CLIENT TO CONTACT PUPPET MASTER EVERY $PUPPET_RUN_INTERVAL seconds..." 
cat >> $PUPPET_CONF_FILE <<-EOF
[agent]
certname = $HOSTNAME
server = $PUPPET_MASTER
runinterval = $PUPPET_RUN_INTERVAL
EOF

echo "---> ENABLING PUPPET SERVICE ON START..."
cat > /etc/default/puppet <<-EOF
# Defaults for puppet - sourced by /etc/init.d/puppet

# Enable puppet agent service?
# Setting this to "yes" allows the puppet agent service to run.
# Setting this to "no" keeps the puppet agent service from running.
START=yes

# Startup options
DAEMON_OPTS=""
EOF

echo "---> STARTING PUPPET CLIENT..."
service puppet start

export DEBIAN_FRONTEND=dialog
echo "==== Bootstrap Completed ===="
