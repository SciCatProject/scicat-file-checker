import json
import urllib.parse

import requests
from dotenv import load_dotenv

# import urllib3
# import urllib
# import re
import time
import os
import uvicorn
import logging
import pyscicat.client as pyScClient
import pyscicat.model as pyScModel
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, HTMLResponse


# Load the .env file
load_dotenv()

app = FastAPI()
logger = logging.getLogger("fastapi_logger")
logger.setLevel(logging.INFO)


username = os.getenv("USERNAME")
password_production = os.getenv("PASSWORD_PROD")
password_staging = os.getenv("PASSWORD_STAGING")

folders_to_check = ["/nfs/groups/beamlines", "/mnt/groupdata", "/ess/data", "/users/detector/experiments", "/mnt/groupdata/guide_optimizations"]

# NOTE: Use this path for local
# base_mount_point = "/Users/junjiequan/Documents/GitHub/2953_swap/"

# NOTE: Use this path when you run on docker container
base_mount_point = "/usr/src/app/"

ssc_base_url = os.getenv("SSC_BASE_URL")
ssc_ldap_login_url = "/".join([ssc_base_url, "auth", "msad"])
ssc_api_url = "/".join([ssc_base_url, "api", "v3"])
ssc_functional_login_url = "/".join([ssc_api_url, "users", "login"])
ssc_datasets_url = "/".join([ssc_api_url, "datasets"])
ssc_datasets_count_url = "/".join([ssc_api_url, "datasets", "count"])
ssc_origdatablocks_url = "/".join([ssc_api_url, "origdatablocks"])
ssc_proposals_url = "/".join([ssc_api_url, "proposals"])
ssc_published_data_url = "/".join([ssc_api_url, "publisheddata"])
ssc_samples_url = "/".join([ssc_api_url, "samples"])

psc_base_url = os.getenv("PSC_BASE_URL")
psc_ldap_login_url = "/".join([psc_base_url, "auth", "msad"])
psc_api_url = "/".join([psc_base_url, "api", "v3"])
psc_functional_login_url = "/".join([psc_api_url, "users", "login"])
psc_datasets_url = "/".join([psc_api_url, "datasets"])
psc_datasets_count_url = "/".join([psc_api_url, "datasets", "count"])
psc_origdatablocks_url = "/".join([psc_api_url, "origdatablocks"])
psc_proposals_url = "/".join([psc_api_url, "proposals"])
psc_published_data_url = "/".join([psc_api_url, "publisheddata"])
psc_samples_url = "/".join([psc_api_url, "samples"])

origdatablock_fields = ["id", "size", "datasetId", "file_size", "file_path"]
dataset_fields = ["pid", "sourceFolder", "size", "numberOfFiles", "type"]

items_per_call = 10000


file_names = {}

directory = "./data"

filter = json.dumps({"limit": os.getenv("FILE_LIMIT")}) if os.getenv("FILE_LIMIT") else ""


def checkExist(f):
    return os.path.exists(f)


# Routes

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    query <b>/start</b> to run the file checker script
    """


@app.get("/start")
async def read_root():
    global file_names

    try:
        # staging connection
        sscClient = pyScClient.ScicatClient(
            base_url=ssc_api_url,
            username=username,
            password=password_staging,
        )
        logger.info("staging client instantiated")

        # production connection
        pscClient = pyScClient.ScicatClient(
            base_url=psc_api_url,
            username=username,
            password=password_production,
        )
        logger.info("production client instantiated")

        # response from staging original data blocks
        params = {"access_token": sscClient._token}
        if filter:
            params['filter'] : filter
        s_o_response = requests.get(
            ssc_origdatablocks_url,
            params=params,
            headers=sscClient._headers,
            timeout=sscClient._timeout_seconds,
            stream=False,
        )
        logger.info("Retrieved original datablocks from staging")

        # response from production original data blocks
        params = {"access_token": pscClient._token}
        if filter:
            params['filter'] : filter
        p_o_response = requests.get(
            psc_origdatablocks_url,
            params=params,
            headers=pscClient._headers,
            timeout=pscClient._timeout_seconds,
            stream=False,
        )
        logger.info("Retrieved original datablocks from production")

        # handle Error for original block
        assert (
            s_o_response.status_code == 200
        ), "Staging original block data response error"
        assert (
            p_o_response.status_code == 200
        ), "Production original block data response error"

        # get table of original block
        dfODB_1 = pd.DataFrame(s_o_response.json())
        dfODB_1["environment"] = "staging"
        logger.info("Loaded staging datablocks in data frame")

        dfODB_2 = pd.DataFrame(p_o_response.json())
        dfODB_2["environment"] = "production"
        logger.info("Loaded production datablocks in data frame")

        dfODB_3 = pd.concat([dfODB_1, dfODB_2])
        logger.info("Merged datablocks lists")

        dfODB_4 = dfODB_3.explode("dataFileList")
        logger.info("Unstack file lists")

        dfODB_5 = pd.concat(
            [
                dfODB_4,
                dfODB_4["dataFileList"]
                .apply(pd.Series)
                .rename(columns={"size": "file_size", "path": "file_path"}),
            ],
            axis=1,
        )
        logger.info("Properly formatted files information")

        dfODB_6 = dfODB_5[
            ["environment", "id", "size", "datasetId", "file_size", "file_path"]
        ].rename(columns={"id": "origdatablockId", "size": "origdatablock_size"})
        logger.info("Formatted datablocks information")

        # retrieve the number of datasets from staging
        s_d_c_response = requests.get(
            ssc_datasets_count_url,
            params=dict({"access_token": sscClient._token}),
            headers=sscClient._headers,
            timeout=sscClient._timeout_seconds,
            stream=False,
        )
        logger.info("Loaded staging datasets information")

        # handle Error for dataset
        assert s_d_c_response.status_code == 200, "Staging dataset count error"
#        assert p_d_response.status_code == 200, "Production dataset data response error"
        s_datasets_count = s_d_c_response.json()["count"]

        # retrieve the datasets from staging
        lD_1 = []
        items_count = 0
        # filter should look something like this
        # filter=%7B%22limits%22%3A%20%7B%22limit%22%3A%2010%2C%20%22skip%22%3A%200%2C%20%22order%22%3A%20%22asc%22%7D%7D
        while (not lD_1 or items_count < s_datasets_count):
            logger.info("Loading first batch of datasets from staging")
            s_d_response = requests.get(
                ssc_datasets_url,
                params={
                    "filter": json.dumps({
                        "fields": dataset_fields,
                        "limits":{
                            "limit" : items_per_call,
                            "skip" : items_count
                        }
                    })
                },
                headers=sscClient._headers,
                timeout=sscClient._timeout_seconds,
                stream=False,
            )
            assert s_d_response.status_code == 200, "Staging dataset retrieval error"
            lD_1.append(pd.DataFrame(s_d_response.json()))
            logger.info("Loaded {} datasets".format(len(lD_1[-1])))
            items_count += len(lD_1[-1])

        dfD_1 = pd.concat(lD_1,ignore_index=True)
        dfD_1["environment"] = "staging"
        logger.info("Loaded staging datasets information in data frame")
        logger.info("Total number of staging datasets loaded: {}".format(len(dfD_1)))
        del lD_1

        # retrieve the number of datasets from production
        p_d_c_response = requests.get(
            psc_datasets_count_url,
            params=dict({"access_token": pscClient._token}),
            headers=pscClient._headers,
            timeout=pscClient._timeout_seconds,
            stream=False,
        )
        logger.info("Loaded production datasets information")

        # handle Error for dataset
        assert p_d_c_response.status_code == 200, "Production dataset count error"
        p_datasets_count = p_d_c_response.json()["count"]

        # retrieve the datasets from production
        lD_1 = []
        items_count = 0
        # filter should look something like this
        # filter=%7B%22limits%22%3A%20%7B%22limit%22%3A%2010%2C%20%22skip%22%3A%200%2C%20%22order%22%3A%20%22asc%22%7D%7D
        while (not lD_1 or items_count < p_datasets_count):
            logger.info("Loading first batch of datasets from staging")
            p_d_response = requests.get(
                psc_datasets_url,
                params={
                    "filter": json.dumps({
                        "fields": dataset_fields,
                        "limits": {
                            "limit": items_per_call,
                            "skip": items_count
                        }
                    })
                },
                headers=pscClient._headers,
                timeout=pscClient._timeout_seconds,
                stream=False,
            )
            assert p_d_response.status_code == 200, "Production dataset retrieval error"
            lD_1.append(pd.DataFrame(p_d_response.json()))
            logger.info("Loaded {} datasets".format(len(lD_1[-1])))
            items_count += len(lD_1[-1])

        dfD_2 = pd.concat(lD_1, ignore_index=True)
        dfD_2["environment"] = "production"
        logger.info("Loaded production datasets information in data frame")
        logger.info("Total number of production datasets loaded: {}".format(len(dfD_2)))
        del lD_1

        dfD_3 = pd.concat([dfD_1, dfD_2], axis=0)
        logger.info("Merge dataset information")
        del dfD_1, dfD_2

        dfD_4 = dfD_3[dataset_fields + ["environment"]]\
            .rename(columns={"pid": "datasetId", "size": "datasetSize"})
        dfD_4["pid"] = dfD_4["datasetId"]
        logger.info("Properly formatted datasets information ")
        del dfD_3

        dfAllInfo = pd.merge(dfD_4, dfODB_6, how="outer", on=["environment", "datasetId"])
        logger.info("Merged datasets and files information")

        dfAllInfo["sourceFolder"] = dfAllInfo["sourceFolder"].fillna("")
        dfAllInfo["file_path"] = dfAllInfo["file_path"].fillna("")
        dfAllInfo["file_full_path"] = dfAllInfo.apply(
            lambda r: os.path.join(r["sourceFolder"], r["file_path"]), axis=1
        )
        dfAllInfo["orphaned_orig_datablock"] = dfAllInfo["pid"].isnull()
        logger.info("Saved files full path")

        # create data folder if there is none - modify the path later
        if not os.path.exists(directory):
            os.makedirs(directory)


        # Check if files exists, only relevant when running on scicta fileserver
        dfAllInfo["to_be_checked"] = False
        dfAllInfo["to_be_checked"] = dfAllInfo["file_full_path"].apply(
            lambda v: any([d in v for d in folders_to_check])
        )
        logger.info("Decided which files need to be checked")

        dfAllInfo["file_exists"] = dfAllInfo.apply(
            lambda r: checkExist(r['file_full_path']) if r['to_be_checked'] else False,
            axis=1
        )
        logger.info("Checked file existance")

        #now = datetime.now()
        #timestamp = now.strftime('%Y%m%d%H%M%S')
        # files names
        # datablocks_file_name = os.path.join(directory, f"scicat_origdatablocks_complete_${timestamp}")
        # datasets_file_name = os.path.join(directory, f"scicat_datasets_complete_${timestamp}")
        # all_files_file_name = os.path.join(directory, f"scicat_files_complete_${timestamp}")
        # files_to_be_checked_file_name = os.path.join(directory, f"scicat_files_to_be_checked_${timestamp}")
        datablocks_file_name = os.path.join(directory, f"scicat_origdatablocks_complete")
        datasets_file_name = os.path.join(directory, f"scicat_datasets_complete")
        all_files_file_name = os.path.join(directory, f"scicat_files_complete")
        files_to_be_checked_file_name = os.path.join(directory, f"scicat_files_to_be_checked")
        logger.info("Built file names")

        # save in pkl & csv
        dfODB_6.to_pickle(datablocks_file_name + ".pkl")
        dfODB_6.to_csv(datablocks_file_name + ".csv")
        dfD_4.to_pickle(datasets_file_name + ".pkl")
        dfD_4.to_csv(datasets_file_name + ".csv")
        dfAllInfo.to_pickle(all_files_file_name + ".pkl")
        dfAllInfo.to_csv(all_files_file_name + ".csv")
        dfAllInfo[dfAllInfo["file_exists"]].to_pickle(files_to_be_checked_file_name + ".pkl")
        dfAllInfo[dfAllInfo["file_exists"]].to_csv(files_to_be_checked_file_name + ".csv")
        logger.info("Saved data in files")

        # save file names for download
        file_names = {
            "datablocks": {
                "csv": datablocks_file_name + ".csv",
                "pkl": datablocks_file_name + ".pkl"
            },
            "datasets": {
                "csv": datasets_file_name + ".csv",
                "pkl": datasets_file_name + ".pkl"
            },
            "all_info" : {
                "csv": all_files_file_name + ".csv",
                "pkl": all_files_file_name + ".pkl"
            },
            "to_be_checked": {
                "csv": files_to_be_checked_file_name + ".csv",
                "pkl": files_to_be_checked_file_name + ".pkl"
            }
        }
        logger.info("Saved file names for later : " + json.dumps(file_names))

        # prepare some stats
        datasets_total = len(dfD_4)
        datablocks_total = len(dfODB_3)
        files_total = len(dfAllInfo)
        files_accessible = len(dfAllInfo[dfAllInfo["file_exists"] == True])
        files_not_accessible = len(dfAllInfo[dfAllInfo["file_exists"] == False])
        logger.info("Computed statistics")

        return HTMLResponse(
            "<p>Data is ready</p>" +
            "<p><ul>" +
            f"<li>Total number of datasets: {datasets_total}</li>"
            f"<li>Total number of datablocks: {datablocks_total}</li>"
            f"<li>Total number of files: {files_total}</li>" +
            f"<li>Total number of accessible files: {files_accessible}</li>" +
            f"<li>Total number of non accessible files: {files_not_accessible}</li>" +
            f"</ul></p>" +
            "<p>Please use the following endpoints to download the information collected:<ul>" +
            "<li>get_dataset_csv: dataset information in csv format</li>" +
            "<li>get_datablocks_csv: datablocks information in csv format</li>" +
            "<li>get_all_files_csv: all files information in csv format</li>" +
            "<li>get_files_to_be_checked_csv: not accessible files information in csv format</li>" +
            "</ul></p>"
        )

    except Exception as e:
        logger.error("Error : " + str(e))
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/get_all_files_csv")
def read_root():
    global file_names
    filename = file_names["all_info"]["csv"]
    if os.path.exists(filename):
        return FileResponse(filename)
    else:
        return PlainTextResponse("File does not exists. Please use GET /start to generate data files")

@app.get("/get_files_to_be_checked_csv")
def read_root():
    global file_names
    filename = file_names["to_be_checked"]["csv"]
    if os.path.exists(filename):
        return FileResponse(filename)
    else:
        return PlainTextResponse("File does not exists. Please use GET /start to generate data files")

@app.get("/get_datasets_csv")
def read_root():
    global file_names
    filename = file_names["datasets"]["csv"]
    if os.path.exists(filename):
        return FileResponse(filename)
    else:
        return PlainTextResponse("File does not exists. Please use GET /start to generate data files")

@app.get("/get_datablocks_csv")
def read_root():
    global file_names
    filename = file_names["datablocks"]["csv"]
    if os.path.exists(filename):
        return FileResponse(filename)
    else:
        return PlainTextResponse("File does not exists. Please use GET /start to generate data files")



# Run server
if __name__ == "__main__":

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("****************** Starting Server *****************")
    uvicorn.run(app, host=os.getenv("HOST"), port= int(os.getenv("PORT")))
