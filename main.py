import json
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
ssc_origdatablocks_url = "/".join([ssc_api_url, "origdatablocks"])
ssc_proposals_url = "/".join([ssc_api_url, "proposals"])
ssc_published_data_url = "/".join([ssc_api_url, "publisheddata"])
ssc_samples_url = "/".join([ssc_api_url, "samples"])

psc_base_url = os.getenv("PSC_BASE_URL")
psc_ldap_login_url = "/".join([psc_base_url, "auth", "msad"])
psc_api_url = "/".join([psc_base_url, "api", "v3"])
psc_functional_login_url = "/".join([psc_api_url, "users", "login"])
psc_datasets_url = "/".join([psc_api_url, "datasets"])
psc_origdatablocks_url = "/".join([psc_api_url, "origdatablocks"])
psc_proposals_url = "/".join([psc_api_url, "proposals"])
psc_published_data_url = "/".join([psc_api_url, "publisheddata"])
psc_samples_url = "/".join([psc_api_url, "samples"])


global_dfFiles = pd.DataFrame()
global_data_file_pkl = ""
directory = "./data"

filter = json.dumps({"limit": os.getenv("FILE_LIMIT")})


def checkExist(f):
    return os.path.exists(f) if f else False


# Routes

@app.get("/", response_class=HTMLResponse)
def read_root():
    return "query <b>/start</b> to run the file checker script"


@app.get("/start")
async def read_root():
    try:
        # staging connection
        sscClient = pyScClient.ScicatClient(
            base_url=ssc_api_url,
            username=username,
            password=password_staging,
        )

        # production connection
        pscClient = pyScClient.ScicatClient(
            base_url=psc_api_url,
            username=username,
            password=password_production,
        )

        # response from staging original data blocks
        s_o_response = requests.get(
            ssc_origdatablocks_url,
            params=dict({"access_token": sscClient._token, "filter": filter}),
            headers=sscClient._headers,
            timeout=sscClient._timeout_seconds,
            stream=False,
        )

        # response from production original data blocks
        p_o_response = requests.get(
            psc_origdatablocks_url,
            params=dict({"access_token": pscClient._token, "filter": filter}),
            headers=pscClient._headers,
            timeout=pscClient._timeout_seconds,
            stream=False,
        )

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

        dfODB_2 = pd.DataFrame(p_o_response.json())
        dfODB_2["environment"] = "production"

        dfODB_3 = pd.concat([dfODB_1, dfODB_2])
        dfODB_4 = dfODB_3.explode("dataFileList")
        dfODB_5 = pd.concat(
            [
                dfODB_4,
                dfODB_4["dataFileList"]
                .apply(pd.Series)
                .rename(columns={"size": "file_size", "path": "file_path"}),
            ],
            axis=1,
        )
        dfODB_6 = dfODB_5[
            ["environment", "id", "size", "datasetId", "file_size", "file_path"]
        ].rename(columns={"id": "origdablockId", "size": "origdatablock_size"})

        # response from staging dataset
        s_d_response = requests.get(
            ssc_datasets_url,
            params=dict({"access_token": sscClient._token, "filter": filter}),
            headers=sscClient._headers,
            timeout=sscClient._timeout_seconds,
            stream=False,
        )

        # response from production dataset
        p_d_response = requests.get(
            psc_datasets_url,
            params=dict({"access_token": pscClient._token, "filter": filter}),
            headers=pscClient._headers,
            timeout=pscClient._timeout_seconds,
            stream=False,
        )

        # handle Error for dataset
        assert s_d_response.status_code == 200, "Staging dataset data response error"
        assert p_d_response.status_code == 200, "Production dataset data response error"

        dfD_1 = pd.DataFrame(s_d_response.json())
        dfD_1["environment"] = "staging"

        dfD_2 = pd.DataFrame(p_d_response.json())
        dfD_2["environment"] = "production"

        dfD_3 = pd.concat([dfD_1, dfD_2], axis=0)
        dfD_4 = dfD_3[
            ["pid", "sourceFolder", "size", "numberOfFiles", "type", "environment"]
        ].rename(columns={"pid": "datasetId", "size": "datasetSize"})

        dfFiles = pd.merge(dfD_4, dfODB_6, how="right", on=["environment", "datasetId"])

        dfFiles["sourceFolder"] = dfFiles["sourceFolder"].fillna("")
        dfFiles["file_full_path"] = dfFiles.apply(
            lambda r: os.path.join(r["sourceFolder"], r["file_path"]), axis=1
        )

        # create data folder if there is none - modify the path later

        if not os.path.exists(directory):
            os.makedirs(directory)

        now = datetime.now()

        # Part 2 portion ----

        dfFiles = dfFiles[
            dfFiles["file_full_path"].apply(
                lambda v: any([d in v for d in folders_to_check])
            )
        ]

        dfFiles["file_exists"] = dfFiles["file_full_path"].apply(
            lambda v: checkExist(v)
        )


        dfFiles[dfFiles["file_exists"] == True]


        now = datetime.now()
        # save in pkl & csv
        data_file_pkl = now.strftime("scicat_files_complete_%Y%m%d")
        dfFiles.to_pickle(os.path.join(directory, data_file_pkl + ".pkl"))
        dfFiles.to_csv(os.path.join(directory, data_file_pkl + ".csv"))

        dfFiles = pd.read_pickle(os.path.join(directory, data_file_pkl + ".pkl"))
    
        global global_dfFiles
        global global_data_file_pkl


        global_data_file_pkl = data_file_pkl
        global_dfFiles = dfFiles
        get_false_number = dfFiles["file_exists"].value_counts().to_json()
        total_number = dfFiles.shape[0]


        return HTMLResponse("<p>Calculation is done!</p> <p>Total counts: {total}</p><p>File_exist counts: {count}<p> <p>/get_all and /get_false to get csv files</p>".format(count=json.loads(get_false_number),total=total_number)) 

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@app.get("/get_all")
def read_root():
    path = os.path.join(directory, global_data_file_pkl + ".csv")
    isExist = os.path.exists(path)

    if isExist:
        return  FileResponse(path)
    else:
        return PlainTextResponse(
            "use GET /start to generate CSV file first before download"
        )



@app.get("/get_false")
def read_root():

    now = datetime.now()

    try:
        file_false = global_dfFiles[global_dfFiles["file_exists"] == False]
        file_title_false = now.strftime("scicat_files_false_path_%Y%m%d")
        file_false.to_pickle(os.path.join(directory, file_title_false + ".pkl"))
        file_false.to_csv(os.path.join(directory, file_title_false + ".csv"))
        path = os.path.join(directory, file_title_false + ".csv")

        isExist = os.path.exists(path)

        if isExist:
            return FileResponse(path) 
        else:
            return PlainTextResponse(
                "Failed to generate CSV file"
            )
    except Exception as error:
        return PlainTextResponse("use GET /start to generate CSV file first")



# Run server
if __name__ == "__main__":

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info("****************** Starting Server *****************")
    uvicorn.run(app, host=os.getenv("HOST"), port= os.getenv("PORT"))
