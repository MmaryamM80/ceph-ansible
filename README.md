# Deploying ceph with ansible  and sync with multisite

## Topology Guid
                                       ┌───────────────┐
                                       │    Site A     │
                                       │  Ceph Cluster │
                                       │ RGW Zone: A   │
                                       └───────┬───────┘
                                               │
                                           Multi-site
                                               │
                                       ┌───────┴───────┐
                                       │    Site B     │
                n                      │  Ceph Cluster │
                                       │ RGW Zone: B   │
                                       └───────────────┘
                 
### Directory Structure

```
automation/
├── playbook/
│   ├── siteA/               # Ceph deployment for Site A
│   │   ├── inventory.ini
│   │   └── ceph-install/    # Ceph ansible clone directory
│   ├── siteB/               # Ceph deployment for Site B
│   ├── multi-sync/          # Multisite configuration tasks
│   │   ├── rgw-install.yml
│   │   ├── multisite-config.yml
│   │   └── multisite-join.yml
|   ├── ceph-venv/           # python virtual enviroment for running playbooks
└── scripts/
    ├── sync-exporter.py      # Custom metrics exporter
    ├── exporter-siteA.log
    └── exporter-siteB.log
    └── .env                  # variables 

```

## Installation

### Requierments
Ubuntu 22.0

Docker

Nodes need to have accsess to each other without password

Define nodes in /etc/hosts

### Deployment
Fist we need to clone clone ceph-ansible from repository
```
git clone --branch stable-7.0 https://github.com/ceph/ceph-ansible.git
```
After cloning make a virtual enviroment for running playbooks
```
python3 -m venv ceph-venv
source  ceph-venv/bin/activate
```
Cd to the clone direcoty and
Install requierments
```
pip install -r requirements.txt
```
Then cd to the group_vars/
```
cp site.yml.sample site.yml
```
Then start to edit confihuration base on your needs


Afer edditing configuratons you need to create and inventory with below format
```
[mons]
ceph01 ansible_host=185.231.183.2 ansible_user=ubuntu monitor_address=192.168.1.3
ceph02 ansible_host=185.226.117.99 ansible_user=ubuntu monitor_address=192.168.1.4
ceph03 ansible_host=188.213.197.68 ansible_user=ubuntu monitor_address=192.168.1.239

[mgrs]
ceph01
ceph02

[osds]
ceph01 devices=/dev/vdb
ceph02 devices=/dev/vdb
ceph03 devices=/dev/vdb

[rgws]
ceph03 radosgw_address=188.213.197.68 ansible_user=ubuntu

[monitoring]
ceph02 ansible_host=185.226.117.99 ansible_user=ubuntu

[all:vars]
mon_host=185.231.183.2,185.226.117.99,188.213.197.68
ansible_user=ubuntu
```
Start to run ansible in your manager host

Note : DO NOT run ansible with root user
```
ansible-playbook  -i /path/to/inventory.ini  site.yml   -vvv
```
## Verify Installation

```
ceph -s
ceph health detail
ceph osd tree
ceph osd ls
ceph crash ls 
```
To see more details use below command
```
ceph mon stat
ceph mgr stat
ceph pg stat
```
After checking cluster health its time to deploy multisite with radosgw

for installying and syncing two ceph cluster together run below playbooks in order 

```
ansible-playbook -i siteA-inventory rgw-install.yml
ansible-playbook -i siteB-inventory rgw-install.yml

ansible-playbook -i siteA-inventory multisite-config.yml
ansible-playbook -i siteB-inventory multisite-join.yml
```
or you can deploy it manully with below command:

Site A → The primary site (origin of the realm)


Site B → The secondary site (joins the realm)


Realm name: multisite-realm


Zonegroup: multisite-zonegroup


Zone names: zoneA, zoneB


RGW endpoints:


Site A: http://siteA-rgw.example.com


Site B: http://siteB-rgw.example.com


1. On Site A (Primary)
   
Create an S3 user for RGW multisite replication and tests
```
radosgw-admin user create \
  --uid=sitea-sync-user \
  --display-name="SiteA Sync User" \
  --access-key=SITEA_ACCESS_KEY \
  --secret=SITEA_SECRET_KEY \
  --system
```
Create Realm
```
radosgw-admin realm create --rgw-realm=multisite-realm --default
```
Create ZoneGroup
```
radosgw-admin zonegroup create \
  --rgw-zonegroup=multisite-zonegroup \
  --master \
  --default \
  --endpoints=http://siteA-rgw.example.com
```
Create Zone

```
radosgw-admin zone create \
  --rgw-zonegroup=multisite-zonegroup \
  --rgw-zone=zoneA \
  --master \
  --default \
  --endpoints=http://siteA-rgw.example.com \
  --access-key=<ACCESS_KEY_SITEA> \
  --secret=<SECRET_KEY_SITEA>
```

```
radosgw-admin period update --commit
```
2. On Site B (Secondary)

Create S3 user
```
radosgw-admin user create \
  --uid=siteb-sync-user \
  --display-name="SiteB Sync User" \
  --access-key=SITEB_ACCESS_KEY \
  --secret=SITEB_SECRET_KEY \
  --system
```
Pull Realm from Site A
```
radosgw-admin realm pull \
  --url=http://siteA-rgw.example.com \
  --access-key=<ACCESS_KEY_SITEA> \
  --secret=<SECRET_KEY_SITEA>
  ```

Pull Period
```
radosgw-admin period pull \
  --url=http://siteA-rgw.example.com \
  --access-key=<ACCESS_KEY_SITEA> \
  --secret=<SECRET_KEY_SITEA>
```
  
Create Zone for Site B
```
radosgw-admin zone create \
  --rgw-zonegroup=multisite-zonegroup \
  --rgw-zone=zoneB \
  --endpoints=http://siteB-rgw.example.com \
  --access-key=<ACCESS_KEY_SITEB> \
  --secret=<SECRET_KEY_SITEB>
```

Period Update
```
radosgw-admin period update --commit
```

3. Verify Multisite

On either site:

```
radosgw-admin realm list
radosgw-admin zonegroup list
radosgw-admin zone list
radosgw-admin sync status
```

3.1 Install aws tools for creating buckets and test syncing
```
apt install awscli
```
NOTE: in this step you need to create another S3 user with nessecery permision

```
radosgw-admin user create --uid="S3 user" --display-name="Exporter User" --access-key="3349611a-8e56-49c9-bddc-d0004ecead29-access-key" --secret="3349611a-8e56-49c9-bddc-d0004ecead29-secret-key"
```

on siteA
```
aws configure --profile siteA
AWS Access Key ID [None]: SITEA_ACCESS_KEY
AWS Secret Access Key [None]: SITEA_SECRET_KEY
Default region name [None]: us-east-1
Default output format [None]: json
```

Test connectivity
```
aws --profile siteA --endpoint-url http://siteA-rgw.example.com s3 ls
```
create bucker in siteA
```
aws --profile siteA --endpoint-url http://siteA-rgw.example.com s3 mb s3://multisite-test-bucket
```

On siteB
```
aws configure --profile siteB
AWS Access Key ID [None]: SITEB_ACCESS_KEY
AWS Secret Access Key [None]: SITEB_SECRET_KEY
Default region name [None]: us-east-1
Default output format [None]: json
```
check replication in siteB
```
aws --profile siteB --endpoint-url http://siteB-rgw.example.com s3 ls s3://multisite-test-bucket/
```

At the end go to the script directory and run the synce-exporter.py to see the output of clusters buckets

Note that there in a .env file and you can change the user keys and endpoints in there


## Dashboards

ceph Dashboard is available in ceph01 and ceph11 on port 8443


NOTE: PLEASE note that this project is launched on IP Private so dashboards are not available in normal situaltion and it needs to use tunnel to appear in https://localhost:port


use : ssh -L 8484:192.168.1.2:8484 root@185.231.183.2


## FailOver Guid

During a failover in your Ceph multisite RGW setup — specifically when Site A (the primary) goes down — here’s what actually happens under the hood:

1. Site A Goes Offline

The radosgw daemons on Site A stop responding.


Any clients pointing to Site A’s endpoint will get connection failures or S3 errors like Connection refused or 503 Service Unavailable.

Internal sync processes in Site A obviously stop — it’s no longer receiving or sending multisite replication traffic.

3. Site B Assumes Active Role for Clients

If you’ve properly configured DNS, load balancers, or client endpoint settings, applications can seamlessly switch to Site B’s RGW endpoint.


Site B continues to operate normally — it has its own local OSD storage pool for RADOS objects, so it can accept new PUT, GET, and DELETE requests

independently of Site A.


Writes and reads at Site B complete without needing Site A to be online.


5. Data Accumulation in Site B

New objects written to Site B during this period are stored locally and logged in its metadata journal for sync purposes.

These writes are tagged with the zone ID (zoneB) and remain pending until Site A comes back.

Site A doesn’t know about these objects yet, because it’s offline.

7. Site A Returns

Once Site A’s RGW daemons restart, the multisite sync agents detect the gap in logs.

Site B starts pushing its pending objects and metadata updates to Site A’s zone.

This is part of the bidirectional replication model — although Site A is the “master” (realm/zonegroup leader), it still pulls/receives changes from Site B.

The sync speed depends on the number of pending objects, bandwidth, and shard count.

9. Post-Failover State

Eventually, both zones become in sync again (radosgw-admin sync status shows 0 pending items).

From the S3 user’s perspective:

Data written before outage is still available in Site B (because it was replicated earlier).

Data written during the outage is backfilled once Site A recovers.

If your failback strategy is automatic, DNS or clients can start pointing to Site A again.

