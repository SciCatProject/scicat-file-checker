# File check service

This application serves as file download availability identifier for the scicat application.
Currently, on both staging and prod scicat application, many zipped files are not available for downloading and we don't know what are the issues. This api service checks and provides CSV file that contains file information including download availability, so that later we can further investigate those files have download issues.

This repository is MVP version of file check service.</br>
Credentials are stored in `.env` file, which including (ask someone who has the .env):

- username
- password_staging
- password_prod
- ssc_base_url
- psc_base_url
- HOST
- PORT
- FILE_LIMIT

If you want to run this application locally, you need to change or remove the volumne paths in the `docker-compose.yml`.

# How to install:

1. Create venv virtual environment</br>
   `python -m venv myenv`
2. Activate the virtual environment</br>
   `source myenv/bin/activate`</br>
   For windows:</br>
   `myenv\Scripts\activate`
3. Install the required packages listed in the requirements.txt file using the command</br>
   `pip install -r requirements.txt`

# How to start, create and update image and containers

- in order to start the file checker container, you can run the following command: `docker-compose up -d`
- while to stop it, use the command: `docker-container down`
- if you want to restart the service, you can run `docker-run.sh` script which combines both previous commands

# How to use

This api runs on `0.0.0.0:8000`. you can access it with `localhost:8000` as well.

This api has the following endpoints 

- `GET http://localhost:8000/`: the root page contains used to check if the service is alive.
- `GET http://localhost:8000/start`: runs the file check, and save the results locally in files. It returns some statistics
- `GET http://localhost:8000/get_dataset_csv`: downloads the CSV file containing the information about all the datasets
- `GET http://localhost:8000/get_datablocks_csv` downloads the CSV file containing the information about all the orig datablocks
- `GET http://localhost:8000/get_all_files_csv` downloads the CSV file containing the information about all the files
- `GET http://localhost:8000/get_files_to_be_checked_csv` downloads the CSV file containing the information about the files that needs to be checked


# Base path setting to run the script

- `base_mount_point = "/usr/src/app/"` 

When everything is ready and the script is expected to run on the scicatfileserver `dfFiles['local_full_path']` should be changed to `dfFiles['file_full_path']` for the line of code below

```
dfFiles['file_exists'] = dfFiles['local_full_path'].apply(
    lambda v: checkExist(v))
```
