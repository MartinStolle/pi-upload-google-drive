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


class DriveError(Exception):
    pass

class GoogleDrive:
    """
    Handling the Google Drive Access
    """

    SCOPES = ['https://www.googleapis.com/auth/drive']
    FOLDER_MIME = "application/vnd.google-apps.folder"

    def __init__(self, secret, name):
        if not os.path.exists(secret):
            raise DriveError("Secret file does not exists")
        self.client_secret_file = secret
        self.application_name = name
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
            self.client_secret_file, scopes=scopes)
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
            'description': '',
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

    def share_folder_with_users(self, fileid, emails):
        """
        Share the folder or file with a specific user.
        :param fileid: id of the object we want to share, can be file or folder
        :param emails: list of email addresses of the user to share the folder with.
        """
        for email in emails:
            if not self.share_folder_with_user(fileid, email):
                return False
        return True

    def share_folder_with_user(self, fileid, email):
        """
        Share the folder or file with a specific user.
        :param fileid: id of the object we want to share, can be file or folder
        :param email: email address of the user to share the folder with.
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

    def __init__(self):
        self.logger = logging.getLogger('GoogleDriveUploader-Configuration')
        self._latest_uploaded = []
        self._shared_folder = []
        self.client_secret_file = ''
        self.application_name = ''
        self.search_directory = os.path.join(os.getcwd(), "timelapse")
        self._share_with = []
        self.date_directory = True
        self.interval = 30
        self.n_last_images = 5

        self.read_configuration()

    def read_configuration(self):
        '''
        Read configuration file
        '''
        config = configparser.ConfigParser()
        config.read(self.filename)
        self.latest_uploaded = config['Information']['latest_uploaded']
        self.client_secret_file = config['Drive']['client_secret_file']
        self.application_name = config['Drive']['application_name']
        self.share_with = config['Drive']['share_with']
        self.shared_folder = config['Drive']['shared_folder']
        self.search_directory = config['Application']['search_directory']
        if not os.path.exists(self.search_directory):
            self.logger.warning('Directory %s does not yet exists...', self.search_directory)
        self.date_directory = config['Application'].getboolean('date_directory')
        self.interval = int(config['Application']['interval'])
        self.n_last_images = int(config['Application']['n_last_images'])

        self.log_configuration()

    def write_configuration(self):
        '''
        Write configuration file
        '''
        config = configparser.ConfigParser()
        config['Information'] = {}
        config['Information']['latest_uploaded'] = ','.join(self.latest_uploaded)

        config['Drive'] = {}
        config['Drive']['client_secret_file'] = self.client_secret_file
        config['Drive']['application_name'] = self.application_name
        config['Drive']['share_with'] = ','.join(self.share_with)
        config['Drive']['shared_folder'] = ','.join(self.shared_folder)

        config['Application'] = {}
        config['Application']['search_directory'] = self.search_directory
        config['Application']['date_directory'] = str(self.date_directory)
        config['Application']['interval'] = str(self.interval)
        config['Application']['n_last_images'] = str(self.n_last_images)

        with open(self.filename, 'w') as configfile:
            config.write(configfile)

    def log_configuration(self):
        '''
        Just log the configuration
        '''
        self.logger.info("latest_uploaded: %s", self.latest_uploaded)
        self.logger.info("shared_folder: %s", self.shared_folder)
        self.logger.info("client_secret_file: %s", self.client_secret_file)
        self.logger.info("application_name: %s", self.application_name)
        self.logger.info("search_directory: %s", self.search_directory)
        self.logger.info("share_with: %s", self.share_with)
        self.logger.info("date_directory: %s", self.date_directory)
        self.logger.info("interval: %s", self.interval)
        self.logger.info("n_last_images: %s", self.n_last_images)

    @property
    def shared_folder(self):
        """Get list of people to share the uploads with."""
        return self._shared_folder

    @shared_folder.setter
    def shared_folder(self, value):
        if value:
            self._shared_folder = [i for i in value.split(',') if i]

    @property
    def share_with(self):
        """Get list of people to share the uploads with."""
        return self._share_with

    @share_with.setter
    def share_with(self, value):
        if value:
            self._share_with = [i for i in value.split(',') if i]

    @property
    def latest_uploaded(self):
        """Get list of people to share the uploads with."""
        return self._latest_uploaded

    @latest_uploaded.setter
    def latest_uploaded(self, value):
        if isinstance(value, str):
            self._latest_uploaded = [i for i in value.split(',') if i]
        elif isinstance(value, list):
            self._latest_uploaded = value


class ImageUpload:

    def __init__(self):
        self.logger = logging.getLogger('GoogleDriveUploader')
        self.config = Configuration()
        self.drive = GoogleDrive(self.config.client_secret_file, self.config.application_name)

    def get_latest_images(self, directory, n_last_images):
        '''
        Returns the names of the n newest images in the directory
        '''
        latest = None
        try:
            latest = sorted([os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.jpg')],
                            key=os.path.getctime, reverse=True)
        except ValueError:
            self.logger.error('No images found in directory %s', directory)

        if not latest or len(latest) == 0:
            return None
        return latest[0:n_last_images]

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

    def create_missing_date_folders(self, filename):
        """
        Returns the ID of the day folder and creates the folder if they does not exist
        :param filename: absolute path
        :returns: Tuple with foldername and ID
        """
        directory = os.path.dirname(filename)
        # remove the current directory
        directory = directory.split(os.getcwd())[1]
        # first element will be empty, therefore we remove it
        year, month, day = directory.split(os.sep)[2:]
        yid = self.get_folder_or_create_it(year)
        mid = self.get_folder_or_create_it(month, yid)
        did = self.get_folder_or_create_it(day, mid)

        return year, did

    def create_missing_folder(self, filename):
        """
        Returns the ID of folder and creates the folder if they does not exist
        :param filename: absolute path
        :returns: Tuple with foldername and ID
        """
        directory = os.path.dirname(filename)
        # get foldername
        directory = directory.split(os.sep)[-1]
        did = self.get_folder_or_create_it(directory)

        return directory, did

    def current_date_directory(self):
        '''Returns the current date directory where the images are stored in'''
        now = datetime.datetime.now()
        path = '{0}{1}{2}{3}{4}'.format(now.year, os.sep, now.month, os.sep, now.day)
        path = os.path.join(self.config.search_directory, path)
        if not os.path.exists(path):
            self.logger.warning('Directory %s does not yet exists...', path)
            return None
        return path

    def upload_newest_images(self):
        '''
        Looks into the timelapse directory and uploads the newest images
        '''
        if self.config.date_directory:
            path = self.current_date_directory()
            if not path:
                return
        else:
            path = self.config.search_directory

        images = self.get_latest_images(path, self.config.n_last_images)
        if not images:
            return

        self.logger.info("Newest images are %s", images)
        for image in images:
            if not self.upload_image(image):
                self.logger.warning("Unable to upload image %s", image)

        self.config.latest_uploaded = [os.path.basename(image) for image in images]

        self.config.write_configuration()

    def upload_image(self, image):
        ''' Uploads newest image
        '''
        return_val = None
        if os.path.basename(image) in self.config.latest_uploaded:
            self.logger.info("Image %s already uploaded, will skip this one.", image)
            return None

        fid = None
        foldername = ''
        if self.config.date_directory:
            foldername, fid = self.create_missing_date_folders(image)
        else:
            foldername, fid = self.create_missing_folder(image)

        if self.drive.upload_image(image, fid):
            return_val = image

        if foldername not in self.config.shared_folder:
            files = self.drive.search_files(self.drive.FOLDER_MIME)
            for key, value in files.items():
                if value == foldername:
                    if self.drive.share_folder_with_users(key, self.config.share_with):
                        self.logger.info("Folder %s not yet shared, sharing it now and writing configuration",
                                         foldername)
                        self.config.shared_folder.append(foldername)
                    else:
                        self.config.shared_folder = []

        return return_val

    def __delete_all_files(self):
        '''
        Clears the complete drive, for debugging purposes
        '''
        files = self.drive.search_files(self.drive.FOLDER_MIME)
        for key, value in files.items():
            self.drive.delete_file(key)

    def check_for_new_images(self):
        '''
        Runs every n seconds and checks for new images
        '''

        try:
            while True:
                timer = threading.Timer(self.config.interval, self.upload_newest_images)
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
