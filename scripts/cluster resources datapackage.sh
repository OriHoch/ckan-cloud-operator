#!/usr/bin/env bash

echo DATAPACKAGE_PREFIX="${DATAPACKAGE_PREFIX}"
echo NON_CKAN_INSTANCES="${NON_CKAN_INSTANCES}"
echo SKIP_CKAN_IMAGES="${SKIP_CKAN_IMAGES}"

[ -z "${DATAPACKAGE_PREFIX}" ] && echo invalid args && exit 1

rm -rf .checkpoints &&\
rm -rf "data/${DATAPACKAGE_PREFIX}" &&\
python3 ${CKAN_CLOUD_OPERATOR_SRC:-/home/jenkins/ckan-cloud-operator/ckan_cloud_operator}/dataflows/resources.py
[ "$?" != "0" ] && exit 1
! python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/${DATAPACKAGE_PREFIX}/resources/datapackage.json'),
  printer(tablefmt='html', num_rows=9999)
).process()
" > resources.html && exit 1

if [ "${SKIP_CKAN_IMAGES}" != "yes" ]; then
  ! python3 ${CKAN_CLOUD_OPERATOR_SRC:-/home/jenkins/ckan-cloud-operator/ckan_cloud_operator}/dataflows/ckan_images.py && exit 1
  ! python3 -c "
from dataflows import Flow, load, printer
Flow(
  load('data/${DATAPACKAGE_PREFIX}/ckan_images/datapackage.json'),
  printer(resources=['dockerfiles'], tablefmt='html', num_rows=9999, fields=['gitlab_repo','name', 'url', 'instances','from','ckan_exts','ckanext-s3filestore'])
).process()
" > dockerfiles.html && exit 1
fi

exit 0