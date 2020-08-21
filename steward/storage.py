import errno
import os
import warnings
from datetime import datetime

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import File, locks
from django.core.files.move import file_move_safe
from django.core.signals import setting_changed
from django.utils import timezone
from django.utils._os import abspathu, safe_join
from django.utils.crypto import get_random_string
from django.utils.deconstruct import deconstructible
#from django.utils.deprecation import RemovedInDjango20Warning
from django.utils.encoding import filepath_to_uri, force_text
from django.utils.functional import LazyObject, cached_property
from django.utils.module_loading import import_string
from django.utils.six.moves.urllib.parse import urljoin
from django.utils.text import get_valid_filename

from django.core.files.storage import Storage


@deconstructible
class ProtectedFileStorage(Storage):
    """
    Standard filesystem storage
    """

    def __init__(self, location=None, base_url=None, file_permissions_mode=None,
                 directory_permissions_mode=None):
        self._location = location
        if base_url is not None and not base_url.endswith('/'):
            base_url += '/'
        self._base_url = base_url
        self._file_permissions_mode = file_permissions_mode
        self._directory_permissions_mode = directory_permissions_mode
        setting_changed.connect(self._clear_cached_properties)

    def _clear_cached_properties(self, setting, **kwargs):
        """Reset setting based property values."""
        if setting == 'PROTECTED_ROOT':
            self.__dict__.pop('base_location', None)
            self.__dict__.pop('location', None)
        elif setting == 'PROTECTED_URL':
            self.__dict__.pop('base_url', None)
        elif setting == 'FILE_UPLOAD_PERMISSIONS':
            self.__dict__.pop('file_permissions_mode', None)
        elif setting == 'FILE_UPLOAD_DIRECTORY_PERMISSIONS':
            self.__dict__.pop('directory_permissions_mode', None)

    def _value_or_setting(self, value, setting):
        return setting if value is None else value

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PROTECTED_ROOT)

    @cached_property
    def location(self):
        return abspathu(self.base_location)

    @cached_property
    def base_url(self):
        return self._value_or_setting(self._base_url, settings.PROTECTED_URL)

    @cached_property
    def file_permissions_mode(self):
        return self._value_or_setting(self._file_permissions_mode, settings.FILE_UPLOAD_PERMISSIONS)

    @cached_property
    def directory_permissions_mode(self):
        return self._value_or_setting(self._directory_permissions_mode, settings.FILE_UPLOAD_DIRECTORY_PERMISSIONS)

    def _open(self, name, mode='rb'):
        return File(open(self.path(name), mode))

    def _save(self, name, content):
        full_path = self.path(name)

        # Create any intermediate directories that do not exist.
        # Note that there is a race between os.path.exists and os.makedirs:
        # if os.makedirs fails with EEXIST, the directory was created
        # concurrently, and we can continue normally. Refs #16082.
        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            try:
                if self.directory_permissions_mode is not None:
                    # os.makedirs applies the global umask, so we reset it,
                    # for consistency with file_permissions_mode behavior.
                    old_umask = os.umask(0)
                    try:
                        os.makedirs(directory, self.directory_permissions_mode)
                    finally:
                        os.umask(old_umask)
                else:
                    os.makedirs(directory)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        if not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # There's a potential race condition between get_available_name and
        # saving the file; it's possible that two threads might return the
        # same name, at which point all sorts of fun happens. So we need to
        # try to create the file, but if it already exists we have to go back
        # to get_available_name() and try again.

        while True:
            try:
                # This file has a file path that we can move.
                if hasattr(content, 'temporary_file_path'):
                    file_move_safe(content.temporary_file_path(), full_path)

                # This is a normal uploadedfile that we can stream.
                else:
                    # This fun binary flag incantation makes os.open throw an
                    # OSError if the file already exists before we open it.
                    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, 'O_BINARY', 0))
                    # The current umask value is masked out by os.open!
                    fd = os.open(full_path, flags, 0o666)
                    _file = None
                    try:
                        locks.lock(fd, locks.LOCK_EX)
                        for chunk in content.chunks():
                            if _file is None:
                                mode = 'wb' if isinstance(chunk, bytes) else 'wt'
                                _file = os.fdopen(fd, mode)
                            _file.write(chunk)
                    finally:
                        locks.unlock(fd)
                        if _file is not None:
                            _file.close()
                        else:
                            os.close(fd)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    # Ooops, the file exists. We need a new file name.
                    name = self.get_available_name(name)
                    full_path = self.path(name)
                else:
                    raise
            else:
                # OK, the file save worked. Break out of the loop.
                break

        if self.file_permissions_mode is not None:
            os.chmod(full_path, self.file_permissions_mode)

        # Store filenames with forward slashes, even on Windows.
        return force_text(name.replace('\\', '/'))

    def delete(self, name):
        assert name, "The name argument is not allowed to be empty."
        name = self.path(name)
        # If the file exists, delete it from the filesystem.
        # If os.remove() fails with ENOENT, the file may have been removed
        # concurrently, and it's safe to continue normally.
        try:
            os.remove(name)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def exists(self, name):
        return os.path.exists(self.path(name))

    def listdir(self, path):
        path = self.path(path)
        directories, files = [], []
        for entry in os.listdir(path):
            if os.path.isdir(os.path.join(path, entry)):
                directories.append(entry)
            else:
                files.append(entry)
        return directories, files

    def path(self, name):
        return safe_join(self.location, name)

    def size(self, name):
        return os.path.getsize(self.path(name))

    def url(self, name):
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        url = filepath_to_uri(name)
        if url is not None:
            url = url.lstrip('/')
        return urljoin(self.base_url, url)

    def accessed_time(self, name):
        warnings.warn(
            'FileSystemStorage.accessed_time() is deprecated in favor of '
            'get_accessed_time().',
            RemovedInDjango20Warning,
            stacklevel=2,
        )
        return datetime.fromtimestamp(os.path.getatime(self.path(name)))

    def created_time(self, name):
        warnings.warn(
            'FileSystemStorage.created_time() is deprecated in favor of '
            'get_created_time().',
            RemovedInDjango20Warning,
            stacklevel=2,
        )
        return datetime.fromtimestamp(os.path.getctime(self.path(name)))

    def modified_time(self, name):
        warnings.warn(
            'FileSystemStorage.modified_time() is deprecated in favor of '
            'get_modified_time().',
            RemovedInDjango20Warning,
            stacklevel=2,
        )
        return datetime.fromtimestamp(os.path.getmtime(self.path(name)))

    def _datetime_from_timestamp(self, ts):
        """
        If timezone support is enabled, make an aware datetime object in UTC;
        otherwise make a naive one in the local timezone.
        """
        if settings.USE_TZ:
            # Safe to use .replace() because UTC doesn't have DST
            return datetime.utcfromtimestamp(ts).replace(tzinfo=timezone.utc)
        else:
            return datetime.fromtimestamp(ts)

    def get_accessed_time(self, name):
        return self._datetime_from_timestamp(os.path.getatime(self.path(name)))

    def get_created_time(self, name):
        return self._datetime_from_timestamp(os.path.getctime(self.path(name)))

    def get_modified_time(self, name):
        return self._datetime_from_timestamp(os.path.getmtime(self.path(name)))
