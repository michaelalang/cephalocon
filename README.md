# Ceph global RGW Lab

This lab is dedicated to the SFP (Special Focus Project) titled 'Maximizing the Value of Your Rados Gateway with Ingress Strategies' for the Cephalocon event on December 4th, 2024. The purpose of this lab is to provide a hands-on experience in optimizing the performance and efficiency of the Rados Gateway by implementing various ingress strategies. Participants will gain a deeper understanding of the benefits and challenges associated with different ingress strategies and learn how to effectively utilize them to maximize the value of their Rados Gateway

## Use Cases for Rados Gateway (RGW)

The following use cases have been identified for Rados Gateway:

* **Global Access**: Provide global access to RGW, independent of zones or regions, enabling seamless access to data from anywhere.
* **Global Rate Limiting**: Apply rate limiting globally, encompassing all included zones, regions, and authorities, to ensure consistent and controlled access to resources.
* **S3 Metrics Integration**: Embed S3 metrics within the request, eliminating the need for log parsing, and providing real-time insights across zones, regions, and authorities.
* **Future-Proofing**: Explore additional features that can be utilized to further enhance the capabilities of RGW and stay ahead of evolving requirements.

# Requirements

Lab Requirements for Independent Execution

This lab will be live-demonstrated, but if you'd like to run it independently, please ensure you meet the following system requirements:

**System 1: Ceph Cluster Nodes (2x)**

* Operating System: CentOS 9
* CPU: Minimum 4 Cores
* Memory: 16 GB
* Storage:
  * 1 x 50 GB Disk (System Disk)
  * 2 x 50 GB Disks (OSD Disks)

**System 2: Monitoring Node (1x)**

* Operating System: CentOS 9
* CPU: Minimum 4 Cores
* Memory: 8 GB (dependent on metrics storage duration)
* Storage:
  * 1 x 50 GB Disk

# Envoy 
Envoy is an open-source edge and service proxy, specifically designed for cloud-native applications. You may have already heard of Envoy in the context of microservices and service mesh architectures, where it plays a crucial role in enabling scalable, secure, and observable communication between services.

**Utilizing Envoy for Scalability and Control**

We will leverage Envoy's powerful features to enable easy scalability, routing, and filtering in our architecture. Specifically, we will utilize Envoy's external authorization feature to implement the following global controls:

* **Global Rate Limiting**: Enforce rate limits across all services and regions to prevent abuse and ensure consistent performance.
* **Global S3-Specific Metrics**: Collect and report S3-specific metrics across all regions, providing a unified view of storage usage and performance.
* **Global Access with AWS_REGION-Based Routing**: Route requests based on AWS region, enabling global access to services while maintaining region-specific routing decisions.

# Open Policy Framework for Cloud-Native Environments

The Open Policy Framework provides policy-based control for cloud-native environments, offering flexible and fine-grained control for administrators across the entire stack.

**Integration with Envoy**

Envoy will leverage the Open Policy Framework to implement policies, including:

* **Role-Based Access Control (RBAC)**: Enforce access controls based on user roles and permissions.
* **Rate Limiting**: Apply rate limits to prevent abuse and ensure consistent performance.
* **Metrics Collection**: Collect and report metrics through an API frontend to a Redis cluster.

For the purposes of this lab, and due to the current limitation of OPA not supporting Redis writes, we have replaced the OPA agent with a custom-coded gRPC protobuf daemon.

# Redis: In-Memory Database for Caching and Streaming

Redis serves as an in-memory database, providing a high-performance solution for caching and streaming data.

# Flask API: Metrics Collection Frontend

The Flask API acts as a frontend for collecting metrics, providing a simple and efficient way to gather data from various sources.

# Centralized Rate Limiting with Redis

With Redis, we can store statistics used in rate limiting decisions in a centralized, fast storage solution. This allows us to share rate limiting information between multiple daemons within a Ceph cluster, overcoming the limitation of RGW's built-in rate limiting, which is tied to a single daemon.


## Use cases

**Please ensure to follow the [Lab setup guide](#lab-setup-guide) carefully to set up your environment correctly. This will ensure that you can complete the lab exercises successfully and get the most out of the experience.**.

### Global RGW access independent of Zone/Regions

Setting up the client environment

```
# on system wkst execute
export AWS_EC2_METADATA_DISABLED=true
export AWS_ENDPOINT_URL=https://s3.example.com
export AWS_ACCESS_KEY_ID=user1
export AWS_SECRET_ACCESS_KEY=user1
export AWS_CA_BUNDLE=certs/tls.crt
```

To highlty the endpoint more clearly we are going to use bash color codes for east and west

```
# on system wkst execute
echo "echo -e '\e[0;31m'" > .east
echo "echo -e '\e[0;32m'" > .west
echo "echo -e '\e[1;37m'" > .tr

echo "echo -e '\e[0;31m'" > .fail
echo "echo -e '\e[0;32m'" > .succeed
```

We should be able to connect to our RGW Clusters individually 

```
# on system wkst execute
# cluster 1
. .east ; AWS_ENDPOINT_URL=http://ceph1.example.com aws s3 ls ; . .tr

# cluster 
. .west ; AWS_ENDPOINT_URL=http://ceph2.example.com aws s3 ls ; . .tr
```

We aim to utilize a single, globally accessible endpoint (e.g., s3.example.com) that benefits from the global or geo-distributed RGW clusters. To 
achieve this, we will skip traditional BGP and global load balancing approaches and instead use a DNS round-robin record to distribute traffic across 
our multiple RGW clusters.

```
# on system wkst execute
# Checking with a User existing only in one region
export AWS_ACCESS_KEY_ID=user-east
export AWS_SECRET_ACCESS_KEY=user-east
. .east ; AWS_REGION=us-east-1 aws s3 ls ; . .tr

# and failing on the other region accordingly
. .west ; AWS_REGION=us-west-1 aws s3 ls ; . .tr
```

The Lab setup simplifies the process of selecting which endpoint to use, allowing you to specify a specific endpoint (e.g., Cluster 2) and still 
access resources from other clusters. While this approach introduces some latency as traffic passes from one cluster to another before reaching the 
client, it provides a convenient way to interact with multiple clusters without needing to manually determine which endpoint is best suited for each 
request.

![image](screenshots/global_rgw_access.gif)

#### hostname-style Bucket resolution

Currently, hostname bucket resolution requires manual configuration of used names and their assignment to corresponding clusters. This means that 
regex-based routing is not feasible in this scenario, which can lead to limitations in managing and scaling your RGW deployments. I am actively 
investigating ways to mitigate these limitations and provide a more flexible and scalable solution for hostname resolution.

### Global Rate limiting spawning all included Zone/Regions/Authorities

The lab includes two key components: a Redis deployment and an GRPC external authorization Service written in Python. 

For this example, we have configure a single rule to match specific criteria. The rule will be triggered when all of the following conditions are met:

* The authority is `s3.example.com`
* The user or bucket equals `user1`
* The requests per minute exceed 3

To ensure that our rate limits are applied consistently, regardless of the S3 region being addressed, we'll verify our rule on all clusters.

```
# on system wkst execute
export AWS_EC2_METADATA_DISABLED=true
export AWS_ENDPOINT_URL=https://s3.example.com
export AWS_ACCESS_KEY_ID=user1
export AWS_SECRET_ACCESS_KEY=user1
export AWS_CA_BUNDLE=certs/tls.crt
export AWS_MAX_ATTEMPTS=1

# the first three requests are expected to pass successful
. .east
for x in $(seq 1 4) ; do 
    echo "$(date) $(AWS_REGION=us-east-1 aws s3 ls 2>&1)"
done 
. .tr

. .west
for x in $(seq 1 4) ; do 
    echo "$(date) $(AWS_REGION=us-west-1 aws s3 ls 2>&1)"
done 
. .tr
```

Expected Output
```
2024-06-09 08:37:04 user1
2024-06-09 08:37:04 user1
2024-06-09 08:37:04 user1
An error occurred (429) when calling the ListBuckets operation: Too Many Requests

An error occurred (429) when calling the ListBuckets operation: Too Many Requests
An error occurred (429) when calling the ListBuckets operation: Too Many Requests
An error occurred (429) when calling the ListBuckets operation: Too Many Requests
```

Now it's time to get creative! Let's configure some advanced rate limiting scenarios:

1. **User-specific GET requests**: Limit requests for user `user1` using the `GET` method.
2. **User-specific non-listing requests**: Restrict all methods (except listing buckets) for user `user1`.
3. **Region-specific DELETE requests**: Apply a separate limit for user `user1` using the `DELETE` method, but only in the `us-east-1` region.
4. **Global total request limit**: Set a global limit for all users across all regions.
5. **Time-of-day GET requests outside of business hours**: Enforce a separate limit for `GET` requests from all users outside of business hours (6pm 
to 6am).

![image](screenshots/global_rgw_ratelimiting.gif)

### Policy related topics 

Mimiking AWS behavior with Ceph, there is one topic that comes to everyone's mind ... Signature versions. Ceph still supports the AWS deprecated and removed Signature Version `s3v2`. We want our deployments to behave like AWS so we want to disable the Signature version `s3v2`. 

Unfortunately, `aws-cli` does not provide a parameter to generate Signatures for `s3v2`. Let's do that with a tool in the cephalocon-tools image we first need to build

```
# on system wkst execute
podman build -f Dockerfile.tools -t localhost/cephalocon-tools:latest
```

No we need to create random content that we want to presign.

```
# on system wkst execute
. .east ; AWS_REGION=us-east-1 aws s3 cp /etc/redhat-release s3://user1/test ; . .tr
. .west ; AWS_REGION=us-west-1 aws s3 cp /etc/redhat-release s3://user1/test ; . .tr
```

Generate the presign Urls with the script created before

```
# on system wkst execute
cat <<'EOF'> aws_c.env 
AWS_EC2_METADATA_DISABLED=true
AWS_ENDPOINT_URL=https://s3.example.com
AWS_CA_BUNDLE=/certs/tls.crt
AWS_MAX_ATTEMPTS=1
EOF

podman run \
  --env-file aws_c.env \
  -v $(pwd)/certs:/certs \
  -e AWS_ACCESS_KEY_ID=user1 \
  -e AWS_SECRET_ACCESS_KEY=user1 \
  -e BUCKET=user1 \
  localhost/cephalocon-tools:latest -- sig_verify test
```

Copy & paste the curl commands one after the other to see that we successfully block `s3v2` presigned requests 

```
# on system wkst execute
# blocking signature_version s3v2
. .fail ; curl -s --cacert certs/tls.crt 'https://s3.example.com/user1/test?AWSAccessKeyId=user1&Signature=2GkWsG4QIqoYvqkoknj%2FSWdtmX0%3D&Expires=1727546647' ; . .tr
<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>AccessDenied</Code><Message>Access Denied signature v2 has been disabled</Message><HostId>s3.example.com</HostId></Error>

# granting signature_version s3v4
. .succeed ; curl -s --cacert certs/tls.crt 'https://s3.example.com/user1/test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=user1%2F20240928%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240928T175407Z&X-Amz-Expires=600&X-Amz-SignedHeaders=host&X-Amz-Signature=729d615efeed4d9d6e70247f57c3a36febd569cd787c4c1d9e72ef5ca7154ae2' ; . .tr
CentOS Stream release 9
```

The next Policy we want to evaluate is redirecting us-east-1 to the us-east-1 endpoint and us-west-1 to the us-west-1 endpoint by responding with a HTTP 308 accordingly.

Let's re-use the sig_verify script for that
```
# on system wkst execute
# explicitly specify the oposite endpoint of the Region
podman run  \
  --env-file aws_c.env \
  -v $(pwd)/certs:/certs \
  -e AWS_ACCESS_KEY_ID=user1 \
  -e AWS_SECRET_ACCESS_KEY=user1 \
  -e BUCKET=user1 \
  -e AWS_ENDPOINT_URL=https://s3-west.example.com \
  -e AWS_REGION=us-east-1 \
  localhost/cephalocon-tools:latest -- sig_verify test

# We can skip s3v2 and use only the generated s3v4 presigned url
. .fail ; curl --cacert certs/tls.crt 'https://s3-west.example.com/user1//test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=user1%2F20240928%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240928T175911Z&X-Amz-Expires=600&X-Amz-SignedHeaders=host&X-Amz-Signature=d75f878e8fea12ff474057b2f173850b0f2f18d976b37ebc38cc88a054dd7ef3' ; . .tr

<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>PermanentRedirect</Code><Message>The bucket you are attempting to access must be addressed using the specified endpoint. Please send all future requests to this endpoint.</Message><Endpoint>s3-east.example.com</Endpoint><HostId>s3-west.example.com</HostId></Error>
```

![image](screenshots/global_rgw_policy.gif)

Last but not least, let's assume we want a time based access policy to apply for our RGW instance.
Let's enable the already included timebased example in the `policy.py` by executing:

```
# on system wkst execute
cd cephalocon
sed -i -e ' s#disable_policy_check_timebase#policy_check_timebase#; ' policy.py
./run_ext_authz
```

The policy rejects requests every three minutes 
```
# on system wkst execute
. .succeed ; echo "$(date) $(AWS_REGION=us-east-1 aws s3 ls s3://user1/test 2>&1)" ; . .tr
Sat Sep 28 02:07:21 PM EDT 2024 2024-09-28 13:53:25         24 test

# wait for 02:09:..
. .fail ; echo "$(date) $(AWS_REGION=us-east-1 aws s3 ls s3://user1/test 2>&1)" ; . .tr

Sat Sep 28 02:09:01 PM EDT 2024 
An error occurred (PreconditionFailed) when calling the ListObjectsV2 operation (reached max retries: 0): The bucket s not accessible due to time restrictions.
```

Revert the change to ensure it's not blocking us on further tasks

```
sed -i -e ' s#policy_check_timebase#disable_policy_check_timebase#; ' policy.py
./run_ext_authz
```

### global load balanced S3 

With our Lab setup, we've implemented a DNS RoundRobin to simulate global load balancing. This allows us to emulate a globally distributed system, 
where connections can be routed to the nearest available Ceph cluster for the region. As long as the Ceph cluster for the region is available, we're 
able to connect and retrieve content from anywhere in the world.

This configuration enables us to provide a seamless user experience, regardless of their location, by automatically routing requests to the closest 
available cluster.

```
# on system wkst execute
# create some unique content in both Clusters
export AWS_ACCESS_KEY_ID=user1
export AWS_SECRET_ACCESS_KEY=user1

. .succeed ; echo 'I am user1 zone us-east-1' | AWS_REGION=us-east-1 /usr/local/bin/aws s3 cp - s3://user1/content ; . .tr
. .succeed ; echo 'I am user1 zone us-west-1' | AWS_REGION=us-west-1 /usr/local/bin/aws s3 cp - s3://user1/content ; . .tr
```

```
# we check which Envoy frontend we are connecting to by tcdumping the syn packets
tcpdump -nnNi any 'port 443 and (tcp[tcpflags] & (tcp-syn) != 0)' & 


# then we access the same Region/Bucket and see that we utilize a differnt Envoy in RoundRobin DNS manner

export AWS_ACCESS_KEY_ID=user1
export AWS_SECRET_ACCESS_KEY=user1

. .east ; AWS_REGION=us-east-1 aws s3 cp s3://user1/content - ; . .tr
```

Expected Output:
```
#09:50:35.771401 eth0  Out IP 192.168.192.211.35954 > 192.168.192.129.443: Flags [S], seq 432983531, win 32120, options [mss 1460,sackOK,TS val 1200448334 ecr 0,nop,wscale 7], length 0
#09:50:35.772723 eth0  In  IP 192.168.192.129.443 > 192.168.192.211.35954: Flags [S.], seq 3019979653, ack 432983532, win 31856, options [mss 1460,sackOK,TS val 493905351 ecr 1200448334,nop,wscale 7], length 0
I am user1 zone us-east-1
```

Stop one ingress Envoy by executing 
```
podman rm -f envoy 
```

Reexecute the command 
```
. .east ; AWS_REGION=us-east-1 aws s3 cp s3://user1/content - ; . .tr
```

Expected Output:
```
09:51:41.702404 eth0  Out IP 192.168.192.211.40700 > 192.168.192.129.443: Flags [S], seq 647938130, win 32120, options [mss 1460,sackOK,TS val 1105568207 ecr 0,nop,wscale 7], length 0
09:51:41.702666 eth0  Out IP 192.168.192.211.39810 > 192.168.192.99.443: Flags [S], seq 1013611424, win 32120, options [mss 1460,sackOK,TS val 2637918530 ecr 0,nop,wscale 7], length 0
09:51:41.703014 eth0  In  IP 192.168.192.99.443 > 192.168.192.211.39810: Flags [S.], seq 4161283351, ack 1013611425, win 31856, options [mss 1460,sackOK,TS val 913863567 ecr 2637918530,nop,wscale 7], length 0
I am user1 zone us-east-1
```

Restart the stopped envoy for the next steps
```
./run_envoy 
```

### global S3 specific metrics

Now that we've collected a range of metrics with our Lab setup, let's open a browser and explore the Prometheus UI interface. This will allow us to 
visualize and analyze the data we've collected, gaining valuable insights into the performance and behavior of our RGW clusters.

In the Prometheus UI, we can query the metrics we've collected and generate graphs, tables, or other visualizations to help us understand what's 
happening in our system.

Alternatively, you can access the metrics endpoint directly using a tool like `curl`

```
# on system wkst execute
curl wkst.example.com:8080/metrics
``` 

The metrics returned appear similar to the following format:

```
# HELP s3_request_total S3 Protocol request
# TYPE s3_request_total counter
s3_request_total{authority="s3.example.com",bucket="*",method="GET",region="us-west-1",source="192.168.192.208",user="user1"} 4.0
s3_request_total{authority="s3.example.com",bucket="*",method="GET",region="us-east-1",source="192.168.192.208",user="user1"} 4.0
# HELP s3_rate_limited_total S3 total rate limited requests
# TYPE s3_rate_limited_total counter
s3_rate_limited_total{authority="s3.example.com",bucket="*",method="GET",region="us-west-1",source="192.168.192.208",user="user1"} 4.0
s3_rate_limited_total{authority="s3.example.com",bucket="*",method="GET",region="us-east-1",source="192.168.192.208",user="user1"} 1.0
```


To further analyze the scraped metrics, you can execute a query using `jq`, a lightweight and flexible command-line JSON processor. For example, to 
extract the total request for user1 in all regions.
The following query uses `jq` to:

* Select only the metrics total S3 requests
* Extract the region, bucket, username, method and value

```
# on system wkst execute
curl -ksg 'http://wkst.example.com:9090/api/v1/query?query=s3_request_total{}' | \
  jq -r '.data.result[] |
    select(.metric.authority=="s3.example.com") |
    [.metric.region, .metric.bucket, .metric.user,
     .metric.method, .value[1]] |
    join(" ") '
```

Expected Output:
```
us-east-1 user1 user1 GET 6
us-east-1 user1 user1 PUT 2
us-west-1 user1 user1 PUT 2
us-east-1 user1 user1 HEAD 6
```

Similar to analyze the rate limited metrics 

```
# on system wkst execute
curl -ksg 'http://wkst.example.com:9090/api/v1/query?query=s3_rate_limited_total{}' | \
  jq -r '.data.result[] |
    select(.metric.authority=="s3.example.com") |
    [.metric.region, .metric.bucket, .metric.user,
     .metric.method, .value[1]] |
    join(" ") '
```

Expected Output:
```
us-east-1 * user1 GET 1
us-west-1 * user1 GET 4
```

### Payment/finops use-case 

In addition to exploring the technical aspects of our Lab setup, we can also delve into financial operations and payment limitations. By using our 
rate limiting capabilities, we can create custom pricing plans for our customers, ensuring that their usage aligns with their budget.

For example, we could set a daily limit on the number of requests or data transferred, thereby controlling costs and preventing unexpected overages. 
This would be particularly useful for businesses that require predictable expenses and budgeting.

To test the payment limitations, let's update the `payment.py` file by changing the `limit` value to 0.0001. This will simulate a payment limit that can 
be reached relatively quickly.

By setting the `limit` to 0.0001, we'll be able to see how our system responds when a customer reaches their payment limit and needs to make a new payment 
to continue using our services.


```
# on system wkst execute
# get and update the payment check on wkst
sed -i -e 's#> 500#> 50#' payment.py 

./run_ext_authz
```

To simulate a scenario where we reach the payment limit, let's iterate 50 requests. For the purpose of this lab, it doesn't matter if these requests 
are actually valid or not - what matters is that they are not rate-limited requests.

```
# on system wkst execute
export AWS_ACCESS_KEY_ID=user2
export AWS_SECRET_ACCESS_KEY=user2

. .east ; AWS_REGION=us-east-1 aws s3 cp /etc/redhat-release s3://user2/content ; . .tr
. .west ; AWS_REGION=us-west-1 aws s3 cp /etc/redhat-release s3://user2/content ; . .tr

for x in $(seq 1 50); do 
    for region in us-east-1 us-west-1 ; do 
      [ "${region}" == "us-east-1" ] && source .east
      [ "${region}" == "us-west-1" ] && source .west
      AWS_REGION=${region} /usr/local/bin/aws s3 cp s3://user2/content -
      source .tr
    done
done 
```

Expected Output:
```
I am user1 zone us-west-1
I am user1 zone us-east-1
download failed: s3://user1/content to - An error occurred (402) when calling the GetObject operation (reached max retries: 0): Payment Required
download failed: s3://user1/content to - An error occurred (402) when calling the HeadObject operation (reached max retries: 0): Payment Required

```

### Conclusion of possiple additional features to be utilized

**Potential Enhancements**

Despite some limitations in our setup, by using Envoy as a frontend and introducing additional 
daemons, we can enhance RGW with functionality not currently available in Ceph.

One of the most impressive aspects of our setup is the ability to seamlessly switch between multiple clusters based on a single parameter - region. 
This allows us to dynamically route content and provide a high level of availability and scalability.

**Benefits of Envoy**

While there is some overhead associated with introducing Envoy as a frontend, I believe it's well worth the benefits we gain. For example:

* Outlier detection: automatically bringing RGW instances online or taking them offline as needed
* Persistent connections: reducing the need for handshakes and improving overall performance
* Dynamic configuration: simplifying scaling and reducing the need to reload/redeploy configurations

**Additional Features**

I'm also excited about some of the additional features we could implement, such as:

* Time-based access or rejection: allowing us to limit updates during certain times of day or temporarily disable all updates for maintenance
* Cluster-level maintenance: allowing us to take a cluster offline for maintenance without affecting overall availability

These are just a few ideas, but I believe there are many more opportunities to enhance RGW and provide even more value to users.

Take a look at some [screenshots](Dashboards-Routing.md) showcasing various use cases for visualizing and routing traffic within the lab.

#####  Lab setup guide

For the OS we are going to use [Centos9 Stream](https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2).
To prepare the images with cloud-init we need to create a directory and touch meta-data as well as addin `user-data` file with the necessary information.

Make sure to have the `genisoimage` package/binary installed through you preferred package manager

```
mkdir cloud-init 
cd cloud-init 
touch meta-data
cat <<'EOF'> user-data
#cloud-config

user: cloud-user
password: changeme

chpasswd:
  expire: False

ssh_authorized_keys:
   - ssh-key ....
EOF

genisoimage -output cloudinit.iso -volid cidata -joliet -rock user-data meta-data
# Mac brew alternative
# mkisofs -output cloudinit.iso -volid cidata -joliet -rock {user-data,meta-data}'
```

###### Configure three Virtual machines 

* Workstation (wkst.example.com)
  * 2 Cores
  * 4GB Memory
  * copy of CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2 as root-disk
  * cloudinit.iso as CD-Rom
  * Network with internet access shared with all VMs

* Ceph Cluster1 (ceph1.example.com)
  * 4 Cores
  * 16GB Memory
  * copy of CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2 as root-disk
  * 2 empty 50G (or more) disk
  * cloudinit.iso as CD-Rom
  * Network with internet access shared with all VMs


###### Setup the Workstation instance as it will provide DNS for our Lab

* Workstation preparation

``` 
# install dependencies
dnf install podman dnsmasq unzip bind-utils git -y

# install aws-cli
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
ln -s /usr/local/bin/aws /usr/bin/aws
``` 

* configure dnsmasq for the Lab

```
mkdir /etc/dnsmasq.d/hosts
cat <<'EOF' > /etc/dnsmasq.d/lab.conf
no-resolv
strict-order
domain=example.com
server=8.8.8.8
interface=*
hostsdir=/etc/dnsmasq.d/hosts
EOF

export IP1=<ip-of-ceph1>
export IP2=<ip-of-ceph2>
export IP3=<ip-of-wkst>

cat <<EOF > /etc/dnsmasq.d/hosts/lab
${IP1} s3.example.com ceph1.example.com s3-east.example.com grafana.example.com
${IP2} s3.example.com ceph2.example.com s3-west.example.com grafana.example.com
${IP3} wkst.example.com 
EOF

systemctl enable --now dnsmasq
```
* change the Network interface for System wkst

```
nmcli c m "System eth0" ipv4.ignore-auto-dns yes
nmcli c m "System eth0" ipv4.dns "$IP3"
nmcli c m "System eth0" ipv4.dns-search "example.com"
hostnamectl hostname wkst.example.com
nmcli c u "System eth0"
```

* change the Network interface for System ceph1

```     
nmcli c m "System eth0" ipv4.ignore-auto-dns yes
nmcli c m "System eth0" ipv4.dns "$IP3"
nmcli c m "System eth0" ipv4.dns-search "example.com"
hostnamectl hostname ceph1.example.com
nmcli c u "System eth0"
``` 

* change the Network interface for System ceph2

```
nmcli c m "System eth0" ipv4.ignore-auto-dns yes
nmcli c m "System eth0" ipv4.dns "$IP3"
nmcli c m "System eth0" ipv4.dns-search "example.com"
hostnamectl hostname ceph2.example.com
nmcli c u "System eth0"
```

* verify the names by pinging each record

```
# -W1 sets a timeout of 1sec if you have not started all VM's
ping -W1 -c1 ceph1.example.com

ping -W1 -c1 ceph2.example.com

ping -W1 -c1 wkst.example.com

ping -W1 -c1 s3.example.com
```

###### Boot strapping the Ceph Single node instances

* Ceph bootstrap preparation

```
# on systems ceph1 and ceph2 execute 

# install quincy release 
# dnf install centos-release-ceph-quincy -y
# dnf install --enablerepo=centos-ceph-quincy cephadm podman dnsmasq unzip bind-utils git -y

# install reef release 
# dnf install centos-release-ceph-reef -y
# dnf install --enablerepo=centos-ceph-reef cephadm podman dnsmasq unzip bind-utils git -y

# install squid release 
# dnf install centos-release-ceph-squid -y
# dnf install --enablerepo=centos-ceph-squid cephadm podman dnsmasq unzip bind-utils git -y

# create cephadmin unprivileged user 
useradd -G wheel cephadmin

# enable password less sudo
sed -i -e " s#^%wheel.*#%wheel     ALL=(ALL)       NOPASSWD: ALL#; " /etc/sudoers

# create ssh key for cephadm deployment
runuser -u cephadmin -- ssh-keygen -N '' -f /home/cephadmin/.ssh/id_rsa
```

* clone the Lab repository for the templates and scripts used in this Lab


```
#on all three systems execute
git clone https://github.com/michaelalang/cephalocon.git
cd cephalocon
```

* set the Region and Zones for the lab (the second zone is just for service identification)

```
# on system ceph1 execute
export RGWREGION=us
export RGWZONE=us-east-1
export RGWZONE2=us-east-2
export RGWPORT2=81
```

* adjust the block device list for the two OSD's according to your setup

    * in this lab we have vdb and vdc with 50G to be used

    ``` 
    lsblk

    # output
    vda                                                           252:0    0   50G  0 disk 
    `-vda1                                                        252:1    0   50G  0 part /rootfs
    vdb                                                           252:16   0   50G  0 disk 
    vdc                                                           252:32   0   50G  0 disk 
    vdd                                                           252:48   0  364K  1 disk 
    ```

    * update the rollout-tmpl.yml accordingly

    ```
    vi rollout-tmpl.yml

    # update the OSD spec to
    ---
    service_type: osd
    service_id: default_osd_group
    placement:
      hosts:
        - ${RGWHOST}
    data_devices:
      paths:
        - /dev/vdb    # <<< first device
        - /dev/vdc    # <<< second device
    ```

* execute the bootstrap process

```
# on system ceph1 execute
sh bootstrap.sh 
```

* you should now have a working Single Node Ceph Cluster
* verify that the Cluster is `HEALTHY` prior progressing

```
# on system ceph1 execute
cephadm shell -v /root/cephalocon:/tmp 
ceph -s
```

* setup the `us-east-1` zone 

```
# on system ceph1 execute
export RGWREGION=us
export RGWZONE=us-east-1
export RGWMASTER=ceph1
export RGWZONE2=us-east-2

sh /tmp/zone-boostrap-primary.sh 

# restart the second RGW instance as it's only used in this lab
ceph orch restart rgw.default.us-east-2 
``` 

* check that RGW instances are up and running

```
# on system ceph1 execute
ceph orch ls 
ceph orch ps --daemon_type rgw
```

* repeat the steps for the second instance with following env variables

```
# on system ceph2 execute
# for bootstraping
export RGWREGION=us
export RGWZONE=us-west-1
export RGWZONE2=us-west-2
export RGWPORT2=81

sh bootstrap.sh

cephadm shell -v /root/cephalocon:/tmp 
ceph -s

# for zone setup
export RGWREGION=us
export RGWZONE=us-west-1
export RGWZONE2=us-west-2
export RGWMASTER=ceph2

sh /tmp/zone-boostrap-primary.sh

# restart the second RGW instance as it's only used in this lab
ceph orch restart rgw.default.us-west-2
```

###### Adding Users and Buckets to operate on

* On Ceph cluster us-east-1 execute following to create 50 users

```
# on system ceph1 execute
cephadm shell -v /root/cephalocon:/tmp
export RGWREALM=us
export RGWZONE=us-east-1
/tmp/create_users

u='-east'
/usr/bin/radosgw-admin user create --uid=user${u} \
      --display-name=user${u} \
      --access-key=user${u} \
      --secret-key=user${u} \
      --rgw-zone=${RGWZONE} \
      --rgw-realm=${RGWREALM}
```

* On Ceph cluster us-west-1 execute following to create 50 users

```
# on system ceph2 execute
cephadm shell -v /root:/tmp
export RGWREALM=us
export RGWZONE=us-west-1
/tmp/create_users

u='-west'
/usr/bin/radosgw-admin user create --uid=user${u} \
      --display-name=user${u} \
      --access-key=user${u} \
      --secret-key=user${u} \
      --rgw-zone=${RGWZONE} \
      --rgw-realm=${RGWREALM}
```

* On the Workstation execute following to create the buckets on both Clusters accordingly

```
# on system wkst execute
cd cephalocon
./create_buckets
```

###### Adding Envoy as frontend

* create the envoy config by executing `create_config.sh` in the tmpl directory.

```
# on systems ceph1 and ceph2 execute 
cd cephalocon/tmpl
./create_config.sh

# if you are using the names from the lab, you can hit enter for all inputs
# Region1 Name(us-east-1): 
# Region2 Name(us-west-1): 
# S3 Endpoint Port(443): 
# S3 Endpoint fqdn(s3.example.com): 
# RGW (us-east-1) endpoint(ceph1.example.com): 
# RGW (us-west-1) endpoint(ceph2.example.com): 
# OpenPolicyAgent (all) endpoint(wkst.example.com): 
# RGW (all) endpoint port1(80): 
# RGW (all) endpoint port2(81): 
# RGW (all) dashboard port(8443): 
# OpenPolicyAgent (all) port(9191): 

cd ..
```

* create the config and the cert directory for envoy

```
# on systems ceph1 and ceph2 execute 
mkdir certs config 
```

* create a Self-Signed certificate for the Lab

```
# on systems ceph1 execute
cat <<'EOF'> openssl.cnf
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no
[req_distinguished_name]
C = US
ST = US
L = Example
O = Demo
OU = Demo
CN = *.example.com
[v3_req]
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = *.example.com
EOF

openssl req -x509 -nodes -days 30 -newkey rsa:2048 -keyout certs/tls.key -out certs/tls.crt -config openssl.cnf -extensions 'v3_req'
```

* copy the generated tls cert and key to the system `ceph2` into `cephalocon/certs/`.

* copy the generated tls cert to the system `wkst` into `cephalocon/certs/tls.crt` for CA verification in aws-cli.

  * ensure to call `chcon -t container_file_t -R certs` 

* copy the generated config into the directories

```
# on systems ceph1 and ceph2 execute 
cp tmpl/{envoy-config.yaml,308-*.xml,403-signature.xml} config/ 
chcon -t container_file_t -R certs config
```

* startup envoy by executing `run_envoy` 

```
# on systems ceph1 and ceph2 execute 
./run_envoy
```

* At this point we should have SSL access for our RGW instances.

###### Adding OpenPolicyAgent as authorization framework

Unfortunately, OpenPolicyAgent lacks the possibility to write Redis directly. For the Lab I moved to a custom implementation to reduce the overhead when calling the Service.

* building the image 

```
# on system wkst execute 
cd cephalocon
podman build -f Dockerfile -t ceph-ext-authz:1.1.1
chcon -t container_file_t *.py
```

* startup the external authz service by executing `run_ext_authz` 

```
# on system wkst execute 
./run_ext_authz
```

###### Adding backends for metrics and limits

Since we want to have global data for metrics and payment, we simulate a centralized Redis and Prometheus backend by running the services on the workstation of the lab.

```
# on system wkst execute 
chcon -t container_file_t redis.conf
./run_redis

chcon -t container_file_t prometheus.yml
./run_prometheus

chcon -t container_file_t -R provisioning
./run_grafana

# Default credentials for Grafana are admin:admin
``` 


###### Stressing the infrastructure for nice graphs 

```
./run_stresser
./run_peaker
```
