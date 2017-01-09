# pi-upload-google-drive
Raspberry Pi upload to Google Drive

I created the project because I wanted to view the images created with the Raspberry Pi Camera everywhere where I am without having to deal with the security issues using port forwarding and my own webserver.

The images created are in the subfolder timelapse/year/month/day.

#Requirements

See Google Drive API Quickstart for instructions on how to get the secrets file.
I am using a service account key because this script runs unattended as a cronjob.

- Python 3 `sudo apt-get install python3`
- Pip `sudo apt-get install python3-pip`
- `pip3 install --upgrade google-api-python-client`

#Configuration

Configuration file is image-upload.config.

Add your application name and secret file.

`client_secret_file = secretfile.json`

`application_name = my-application-name`


Who do you want to share the files with, should be at least your email.

`share_with = foo@gmail.com,bar@gmail.com`


Change search_directory if you want to search for images in another folder.

`search_directory = /home/pi/images/`


How often do you want to check for new images in seconds.

`interval = 30`

The script uses the configuration to remember if the current year folder is already shared, in order to avoid the additional call, and the last image uploaded.
Exception is, if you deleted your shared folder and want to share it again you have to delete the folder in the configuration file.

#Run

`python3 image-upload.py`

#Log

image-upload.log

#TODO

 - Synchronize complete folder

#Further reading

##Other Google Drive related projects

https://github.com/googledrive/PyDrive/tree/master/pydrive
https://github.com/supersaiyanmode/gapi/blob/master/GApi4Term/core/drive.py

##SDK

https://developers.google.com/drive/v3/web/about-sdk
https://developers.google.com/drive/v3/reference

##API Dashboard

https://console.developers.google.com/apis/dashboard
