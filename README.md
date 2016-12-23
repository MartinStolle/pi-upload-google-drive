# pi-upload-google-drive
Raspberry Pi upload to Google Drive

I created the project because I wanted to view the images created with the Raspberry Pi Camera everywhere where I am without having to deal with the security issues using port forwarding and my own webserver.

The images created are in the subfolder timelapse/year/month/day. The script looks into the

#Requirements

See Google Drive API Quickstart for instructions on how to get the secrets file.
I am using a service account key because this script runs unattended as a cronjob.

- Python 3 `sudo apt-get install python3`
- Pip `sudo apt-get install python3-pip`
- `pip3 install --upgrade google-api-python-client`

#Configuration

Configuration file is image-upload.config.
The script uses the configuration to remember if the current year folder is already shared, in order to avoid the additional call, and the last image uploaded. Therefore there is no need to touch that file. Exception is, if you deleted your shared folder and want to share it again you have to delete the folder in the configuration file.

The configuration to get that script running is inside the script:

Add your application name and secret file.
```python
class GoogleDrive:
    """
    Handling the Google Drive Access
    """

    SCOPES = ['https://www.googleapis.com/auth/drive']
    CLIENT_SECRET_FILE = 'secret-file.json'  # INSERT INFO
    APPLICATION_NAME = 'my-image-upload'  # INSERT INFO
    FOLDER_MIME = "application/vnd.google-apps.folder"
```
Change home if you want to search for images in another folder.
```python
class ImageUpload:

    home = os.path.join(os.getcwd(), "timelapse")
```
Change interval, default 30s.
```python
    def check_for_new_images(self):
        '''
        Runs every n seconds and checks for new images
        '''

        try:
            while True:
                timer = threading.Timer(30.0, self.upload_newest_image)  # CHANGE INTERVAL
                timer.start()
                timer.join()
        except KeyboardInterrupt:
            self.logger.info("Leaving timer thread. Goodbye!")
```
E-Mail to share to.
```python
if self.drive.share_folder_with_user(key, "email"):
```
#Run

`python3 image-upload.py`

#Log

image-upload.log

#TODO

Move configurable parameter, like CLIENT_SECRET_FILE or check interval time, into the configuration.

#Further reading

##Other Google Drive related projects

https://github.com/googledrive/PyDrive/tree/master/pydrive
https://github.com/supersaiyanmode/gapi/blob/master/GApi4Term/core/drive.py

##SDK

https://developers.google.com/drive/v3/web/about-sdk
https://developers.google.com/drive/v3/reference

##API Dashboard

https://console.developers.google.com/apis/dashboard
