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

- `sh docker-run.sh` command on terminal to start. If you make any changes, run this command again.
  if this command gives error try change the scrip in the file to `docker-compose down` and `docker-compose up`

# How to use

This api runs on `0.0.0.0:8000`. you can access it with `localhost:8000` as well.</br>

This api contains 3 GET requests:

- `http://localhost:8000/` is the root page contains nothing.
- `http://localhost:8000/start` runs file check python script, once success it will generates csv file with analyzed results.
- `http://localhost:8000/get_all` downloads the analyzed csv file. this request will download the csv file contains current date in the filename. e.g,`scicat_files_complete_20230119.csv`
- `http://localhost:8000/get_false` downloads file that contains false path only

For now, you can only access to the other analyzed .csv files from the repository inside the `/data` folder.

# Base path setting to run the script

- `base_mount_point = "/usr/src/app/"` 

When everything is ready and the script is expected to run on the scicatfileserver `dfFiles['local_full_path']` should be changed to `dfFiles['file_full_path']` for the line of code below

```
dfFiles['file_exists'] = dfFiles['local_full_path'].apply(
    lambda v: checkExist(v))
```
