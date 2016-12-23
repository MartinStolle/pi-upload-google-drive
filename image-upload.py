#!/usr/bin/python
'''
See README.md
'''
import configparser
import datetime
import logging
import os
import threading
import httplib2
# Required oauth2client==3.0.0
from apiclient import discovery
from apiclient import errors
from apiclient.http import MediaFileUpload


class GoogleDrive:
    """
    Handling the Google Drive Access
    """

    SCOPES = ['https://www.googleapis.com/auth/drive']
    CLIENT_SECRET_FILE = 'secret-file.json'  # INSERT INFO
    APPLICATION_NAME = 'my-image-upload'  # INSERT INFO
    FOLDER_MIME = "application/vnd.google-apps.folder"

    def __init__(self):
        self.logger = logging.getLogger('GoogleDriveUploader')
        self.service = self.authorize()

    def authorize(self):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.
        """
        from oauth2client.service_account import ServiceAccountCredentials
        scopes = self.SCOPES
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self.CLIENT_SECRET_FILE, scopes=scopes)
        http = credentials.authorize(httplib2.Http())
        return discovery.build('drive', 'v3', http=http)

    def upload_image(self, filename, parents=None):
        """
        Upload image file
        :param filename: ...
        """
        media_body = MediaFileUpload(filename, mimetype='image/jpeg', resumable=True)
        if parents and isinstance(parents, str):
            parents = [parents]
        body = {
            'name': os.path.basename(filename),
            'description': 'Test 1',
            'parents': parents
        }

        try:
            upload = self.service.files().create(body=body, media_body=media_body).execute()
            self.logger.info("Uploaded image to Drive (Id: %s)", upload['id'])
        except errors.HttpError as error:
            self.logger.error("Could not upload image %s", error)
            return False
        else:
            return True

    def create_folder(self, name, parents=None):
        """
        :param name:
        :param kwargs: Anything that create(body=kwargs) accepts
        """
        body = {
            'mimeType': self.FOLDER_MIME,
            'name': name,
        }
        if parents:
            body['parents'] = [parents]
        fid = self.service.files().create(body=body).execute()
        return fid

    def share_folder_with_user(self, fileid, email):
        """
        Share the folder or file with a specific user.
        :param fileid: id of the object we want to share, can be file or folder
        :param email: Email address of the user to share the folder with.
        """
        body = {
            'role': 'writer',
            'type': 'user',
            'emailAddress': email
        }
        self.logger.debug("Creating permission for id %s", fileid)
        try:
            self.service.permissions().create(fileId=fileid, body=body,
                                              sendNotificationEmail=False).execute()
        except errors.HttpError as error:
            self.logger.error("Unable to set permissions %s", error)
            return False
        else:
            return True

    def delete_file(self, fileid):
        """Delete a file using Files.Delete()
        (WARNING: deleting permanently deletes the file!)
        :param param: additional parameter to file.
        :type param: dict.
        :raises: ApiRequestError
        """
        try:
            self.service.files().delete(fileId=fileid).execute()
        except errors.HttpError as error:
            self.logger.error("Could not delete image %s", error)
            return False
        else:
            return True

    def search_files(self, mime_type=None):
        """
        Search files with given query, return name and id
        :returns: dict with keys name and id
        """
        if not mime_type:
            mime_type = "image/jpeg"

        query = "mimeType='%s'" % mime_type
        return self.query(query)


    def query(self, query):
        """
        :returns: dict with the id, name pair of the result
        """
        result = {}
        page_token = None
        while True:
            response = self.service.files().list(q=query,
                                                 spaces='drive',
                                                 fields='nextPageToken, files(id, name)',
                                                 pageToken=page_token).execute()
            for file in response.get('files', []):
                result[file.get('id')] = file.get('name')
                self.logger.info('Found file: %s (%s)', file.get('name'), file.get('id'))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        return result


class Configuration:

    filename = os.path.join(os.getcwd(), "image-upload.config")
    year = str(datetime.datetime.now().year)

    def __init__(self):
        self.latest_uploaded = ''
        self.shared_year = ''
        self.read_configuration()

    def read_configuration(self):
        '''
        Read configuration file
        '''
        config = configparser.ConfigParser()
        config.read(self.filename)
        self.latest_uploaded = config.get('Information', 'latest_uploaded')
        try:
            config.get('SharedYears', self.year)
        except configparser.NoOptionError:
            pass
        else:
            self.shared_year = self.year


    def write_configuration(self):
        '''
        Write configuration file
        '''
        config = configparser.ConfigParser()
        config.add_section('Information')
        config.set('Information', 'latest_uploaded', self.latest_uploaded)
        config.add_section('SharedYears')
        config.set('SharedYears', self.year, '')
        with open(self.filename, 'w') as configfile:
            config.write(configfile)

    def year_already_shared(self):
        '''
        We can skip the shared if the current year is already shared
        '''
        if self.year == self.shared_year:
            return True
        return False


class ImageUpload:

    home = os.path.join(os.getcwd(), "timelapse")

    def __init__(self):
        self.logger = logging.getLogger('GoogleDriveUploader')
        self.drive = GoogleDrive()
        self.config = Configuration()

    def get_latest_image(self, directory):
        '''
        Returns the name of the newest image in the directory
        '''
        latest = None
        try:
            latest = max([os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.jpg')],
                         key=os.path.getctime)
            latest = os.path.join(directory, latest)
        except ValueError:
            self.logger.error('No images found in directory %s', directory)
        return latest

    def get_folder_or_create_it(self, foldername, parentid=None):
        """
        If the given folder does not exists, create it
        :returns: id
        """
        query = str.format("mimeType='{0}' and name='{1}'",
                           self.drive.FOLDER_MIME, foldername)
        if parentid:
            query += str.format(" and '{0}' in parents", parentid)

        resultid = None

        result = self.drive.query(query)
        if len(result) > 1:
            self.logger.warning("Multiple results found for folder. Using the first!")

        for key in result.keys():
            self.logger.info("Using key %s", key)
            resultid = key
            break

        if not resultid:
            if parentid:
                return self.drive.create_folder(foldername, parents=parentid).get('id')
            else:
                return self.drive.create_folder(foldername).get('id')
        else:
            return resultid


    def create_missing_folders(self, filename):
        """
        Returns the ID of the day folder and creates the folder if they does not exist
        :param filename: absolute path
        """
        directory = os.path.dirname(filename)
        # remove the current directory
        directory = directory.split(os.getcwd())[1]
        # first element will be empty, therefore we remove it
        year, month, day = directory.split(os.sep)[2:]
        yid = self.get_folder_or_create_it(year)
        mid = self.get_folder_or_create_it(month, yid)
        did = self.get_folder_or_create_it(day, mid)

        return did

    def current_date_directory(self):
        '''Returns the current date directory where the images are stored in'''
        now = datetime.datetime.now()
        path = '{0}{1}{2}{3}{4}'.format(now.year, os.sep, now.month, os.sep, now.day)
        path = os.path.join(self.home, path)
        if not os.path.exists(path):
            self.logger.warning('Directory %s does not yet exists...', path)
            return None
        return path

    def upload_newest_image(self):
        '''
        Looks into the timelapse directory and uploads the newest image
        '''
        path = self.current_date_directory()
        if not path:
            return
        image = self.get_latest_image(path)
        if not image:
            return

        self.logger.info("Newest image is %s", image)
        if self.config.latest_uploaded == os.path.basename(image):
            self.logger.info("Image %s already uploaded, will skip this one.", image)
            return

        fid = self.create_missing_folders(image)
        if self.drive.upload_image(image, fid):
            self.config.latest_uploaded = os.path.basename(image)

        if not self.config.year_already_shared():
            files = self.drive.search_files(self.drive.FOLDER_MIME)
            for key, value in files.items():
                if value == self.config.year:
                    if self.drive.share_folder_with_user(key, "email"):
                        self.logger.info("Year %s not yet shared, sharing it now and writing configuration",
                                         self.config.year)
                        self.config.shared_year = self.config.year
        self.config.write_configuration()

    def __delete_all_files(self):
        '''
        Clears the complete drive, for debugging purposes
        '''
        files = self.drive.search_files(self.drive.FOLDER_MIME)
        for key, value in files.items():
            self.drive.delete_file(key)
        files = self.drive.search_files()
        for key, value in files.items():
            self.drive.delete_file(key)

    def check_for_new_images(self):
        '''
        Runs every n seconds and checks for new images
        '''

        try:
            while True:
                timer = threading.Timer(30.0, self.upload_newest_image)
                timer.start()
                timer.join()
        except KeyboardInterrupt:
            self.logger.info("Leaving timer thread. Goodbye!")


def init_logging():
    """ initalize logging
    """
    # set up logging to file - see previous section for more details
    logging.basicConfig(level=logging.DEBUG,
                        filename='image-upload.log',
                        filemode='w')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


def main():
    """ Here we go
    """
    init_logging()
    upload = ImageUpload()
    #upload._ImageUpload__delete_all_files()
    upload.check_for_new_images()

if __name__ == '__main__':
    main()
