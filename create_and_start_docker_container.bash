#!/bin/bash
#
# this script create and start the file checker docker container
# By: Max Novelli
#     max.novelli@ess.eu
#

# adjust the image tag accordingly
sfc_image="ghcr.io/scicatproject/file-checker-service"
sfc_image_tag="1988ee6e60ff2f8b36144ccf6e68116edce8975c"


docker container run \
   -d \
   --name scicat-file-checker \
   -v /nfs/groups/beamlines:/nfs/groups/beamlines \
   -v /ess/data:/ess/data \
   -v /users/detector/experiments:/users/detector/experiments \
   -v /mnt/groupdata/guide_optimizations:/mnt/groupdata/guide_optimizations \
   -e USERNAME=ingestor \
   -e PASSWORD_STAGING=aman \
   -e PASSWORD_PROD=veIKtDrHHqlDEZL51bbpo2XCDYvcMmu \
   -e SSC_BASE_URL=https://staging.scicat.ess.eu \
   -e PSC_BASE_URL=https://scicat.ess.eu \
   -e NO_PROXY=localhost,127.0.0.1,172.18.0.21,172.18.25.34 \
   -e HTTP_PROXY=http://172.18.12.30:8123 \
   -e HTTPS_PROXY=http://172.18.12.30:8123 \
   -e FILE_LIMIT= \
   -e HOST=localhost \
   -e PORT=8000 \
   -p 8000:8000 \
   ${sfc_image}:${sfc_image_tag}

