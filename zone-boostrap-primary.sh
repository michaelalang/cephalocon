export DOMAIN=${DOMAIN:-"example.com"}
export RGWREGION=${RGWREGION:-"default"}
export RGWZONE=${RGWZONE:-"default"}
export RGWPORT=${RGWPORT:-80}
export RGWMASTER=${RGWMASTER:-"east-rgw"}

ceph config set global mon_allow_pool_delete true
for id in alertmanager grafana prometheus ; do ceph orch rm ${id} ; done

sleep 10

radosgw-admin realm create --rgw-realm=${RGWREGION} --default
radosgw-admin zonegroup create --rgw-zonegroup=${RGWREGION} --endpoints=http://${RGWMASTER}.${DOMAIN}:${RGWPORT} --rgw-realm=${RGWREGION} --master --default
radosgw-admin zone create --rgw-zonegroup=${RGWREGION} --rgw-zone=${RGWZONE} --master --default --endpoints=http://${RGWMASTER}.${DOMAIN}:${RGWPORT}

echo "Waiting 60 seconds to settle zone creation"
sleep 60

radosgw-admin zonegroup delete --rgw-zonegroup=default --rgw-zone=default
radosgw-admin period update --commit
radosgw-admin zone delete --rgw-zone=default
radosgw-admin period update --commit
radosgw-admin zonegroup delete --rgw-zonegroup=default
radosgw-admin period update --commit

sleep 5

for x in default.rgw.log default.rgw.control default.rgw.meta ; do ceph osd pool rm ${x} ${x} --yes-i-really-really-mean-it ; done

sleep 10

radosgw-admin user create --uid=eastwestrepluser --display-name=”Replication_user” --access-key=eastwestrepl --secret=eastwestrepl123456789 --system
radosgw-admin zone modify --rgw-zone=${RGWZONE} --access-key=eastwestrepl --secret=eastwestrepl123456789
radosgw-admin period update --commit

ceph config set client.rgw rgw_zone ${RGWZONE}
ceph orch restart rgw.default.${RGWZONE}
