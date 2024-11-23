#!/bin/bash

cat static.tmpl > envoy-config.yaml

echo -n 'Region1 Name(us-east-1): '
read region1
[ "${region1}" == "" ] && region1="us-east-1"
export Oregion1=${region1} 
echo -n 'Region2 Name(us-west-1): '
read region2
[ "${region2}" == "" ] && region2="us-west-1"
export Oregion2=${region2}


echo -n 'S3 Endpoint Port(443): '
read dstrport
[ "${dstrport}" == "" ] && dstrport="443"
echo -n 'S3 Endpoint fqdn(s3.example.com): '
read dstrfqdn
[ "${dstrfqdn}" == "" ] && dstrfqdn="s3.example.com"

export name=${dstrfqdn}
export port=${dstrport}
export region="global"
export region1="s3-$(echo ${Oregion1} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
export region2="s3-$(echo ${Oregion2} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"

cat listeners.tmpl | envsubst >> envoy-config.yaml
cat filterchains.tmpl | envsubst >> envoy-config.yaml
cat virtualservice.tmpl | envsubst >> envoy-config.yaml

export region=${Oregion1}
export region1=${Oregion1}
export region2=${Oregion2}
export rewrite="s3-$(echo ${region1} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
cat routes_dashboard.tmpl | envsubst >> envoy-config.yaml
export region=${Oregion2}
export region1=${Oregion2}
export region2=${Oregion1}
export rewrite="s3-$(echo ${region1} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
cat routes_dashboard.tmpl | envsubst >> envoy-config.yaml

export region=${Oregion1}
export region1=${Oregion1}
export region2=${Oregion2}
export rewrite="s3-$(echo ${region1} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
cat routes.tmpl | envsubst >> envoy-config.yaml

export region=${Oregion2}
export region1=${Oregion2}
export region2=${Oregion1}
export rewrite="s3-$(echo ${region1} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
cat routes.tmpl | envsubst >> envoy-config.yaml

region=${Oregion1}
region2=${Oregion2}
export name="s3-$(echo ${region} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')"
export port=${dstrport}
cat virtualservice.tmpl | envsubst >> envoy-config.yaml
cat routes_specific.tmpl | envsubst >> envoy-config.yaml

region=${Oregion2}
region2=${Oregion1}
export name="s3-$(echo ${region} | cut -f2 -d'-').$(echo ${dstrfqdn} | cut -f2- -d'.')" 
export port=${dstrport}
cat virtualservice.tmpl | envsubst >> envoy-config.yaml
cat routes_specific.tmpl | envsubst >> envoy-config.yaml

cat filters.tmpl >> envoy-config.yaml
export region="global"
cat listeners_tls.tmpl | envsubst >> envoy-config.yaml

export name="grafana"
cat filterchains_grafana.tmpl | envsubst >> envoy-config.yaml
cat virtualservice_grafana.tmpl | envsubst >> envoy-config.yaml
cat routes_grafana.tmpl | envsubst >> envoy-config.yaml
cat filters_grafana.tmpl >> envoy-config.yaml
export region="global"
cat listeners_tls.tmpl | envsubst >> envoy-config.yaml

cat clusters.tmpl >> envoy-config.yaml

export region=${Oregion1}
export region1=${Oregion1}
export region2=${Oregion2}
echo -n "RGW (${region1}) endpoint(ceph1.example.com): "
read upfqdn1
[ "${upfqdn1}" == "" ] && upfqdn1="ceph1.example.com"
echo -n "RGW (${region2}) endpoint(ceph2.example.com): "
read upfqdn2
[ "${upfqdn2}" == "" ] && upfqdn2="ceph2.example.com"
echo -n "OpenPolicyAgent (all) endpoint(wkst.example.com): "
read opametrics
[ "${opametrics}" == "" ] && opametrics=$(host ${opametrics:-wkst.example.com} | awk ' { print $NF } ')

echo -n "RGW (all) endpoint port1(80): "
read upport1
[ "${upport1}" == "" ] && upport1="80"
echo -n "RGW (all) endpoint port2(81): "
read upport2
[ "${upport2}" == "" ] && upport2="81"
echo -n "RGW (all) dashboard port(8443): "
read upport3
[ "${upport3}" == "" ] && upport3="8443"
echo -n "OpenPolicyAgent (all) port(9191): "
read opaport
[ "${opaport}" == "" ] && opaport="9191"
echo -n "Dashboard (all) port(3000): "
read dashport
[ "${dashport}" == "" ] && dashport="3000"

export name="dashboard-${region1}"
cat cluster.tmpl | envsubst >> envoy-config.yaml

export port=${upport3}
export ip=$(host ${upfqdn1} | awk ' { print $NF } ')
cat endpoint.tmpl | envsubst >> envoy-config.yaml
cat cluster_tls.tmpl | envsubst >> envoy-config.yaml

export name="s3-rgw-${region1}"
cat cluster.tmpl | envsubst >> envoy-config.yaml

export name=${region1}
export port=${upport1}
cat endpoint.tmpl | envsubst >> envoy-config.yaml

export port=${upport2}
cat endpoint.tmpl | envsubst >> envoy-config.yaml

export name="dashboard-${region2}"
cat cluster.tmpl | envsubst >> envoy-config.yaml

export port=${upport3}
export ip=$(host ${upfqdn2} | awk ' { print $NF } ')
cat endpoint.tmpl | envsubst >> envoy-config.yaml
cat cluster_tls.tmpl | envsubst >> envoy-config.yaml

export name="s3-rgw-${region2}"
cat cluster.tmpl | envsubst >> envoy-config.yaml

export name=${region2}
export port=${upport1}
cat endpoint.tmpl | envsubst >> envoy-config.yaml

export port=${upport2}
cat endpoint.tmpl | envsubst >> envoy-config.yaml

export name="metrics-opa"
cat cluster_grpc.tmpl | envsubst >> envoy-config.yaml
export port=${opaport}
export ip=$(host ${opametrics} | awk ' { print $NF } ')
cat endpoint.tmpl | envsubst >> envoy-config.yaml

export name="grafana"
cat cluster.tmpl | envsubst >> envoy-config.yaml

export port=${dashport}
export ip=$(host ${opametrics} | awk ' { print $NF } ')
cat endpoint.tmpl | envsubst >> envoy-config.yaml
