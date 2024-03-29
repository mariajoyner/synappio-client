import re
import os
import csv
import base64
import urlparse
from datetime import datetime
from cStringIO import StringIO

import chardet
import requests
import pkg_resources
from bag import csv2


TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'
re_wildcard = re.compile(r'(\{[a-zA-Z][^\}]*\})')
manager = pkg_resources.ResourceManager()


def pattern_for(path):
    '''Convert a swagger path spec to a url'''
    if not path.startswith('/'):
        path = '/' + path
    parts = re_wildcard.split(path)
    pattern_parts = []
    for part in parts:
        if part.startswith('{'):
            name = part[1:-1]
            pattern_parts.append('(?P<{}>[^/]+)'.format(name))
        else:
            pattern_parts.append(re.escape(part))
    return re.compile(''.join(pattern_parts) + '$')


def really_unicode(s):
    # Try to guess the encoding
    def encodings():
        yield None
        yield 'utf-8'
        yield chardet.detect(s[:1024])['encoding']
        yield chardet.detect(s)['encoding']
        yield 'latin-1'
    return _attempt_encodings(s, encodings())


def load_content(url):
    '''Versatile text loader. Handles the following url types:

    http[s]://...
    file:///... (or just leave off the file://)
    egg://EggName/path
    '''
    parsed = urlparse.urlparse(url)
    if parsed.scheme == 'file://':
        assert not parsed.netloc, 'File urls must start with file:///'
        return open(parsed.path).read()
    if parsed.scheme == '':
        return open(parsed.path).read()
    elif parsed.scheme in ('http', 'https'):
        return requests.get(url).text
    elif parsed.scheme == 'egg':
        dist = pkg_resources.get_distribution(parsed.netloc)
        fn = dist.get_resource_filename(manager, parsed.path)
        return open(fn).read()
    else:
        assert False, "Don't know how to handle {} URLs".format(parsed.scheme)


def jsonify(obj, **json_kwargs):
    if isinstance(obj, datetime):
        return obj.isoformat() + 'Z'   #strftime(TIMESTAMP_FORMAT)
    elif hasattr(obj, '__json__'):
        return jsonify(obj.__json__(**json_kwargs))
    elif isinstance(obj, dict):
        return dict((k, jsonify(v)) for k, v in obj.items())
    elif isinstance(obj, list):
        return map(jsonify, obj)
    return obj


def chunk(iterator, chunksize):
    chunk = []
    iterator = iter(iterator)
    while True:
        try:
            chunk.append(iterator.next())
        except StopIteration:
            if chunk:
                yield chunk
            break
        if len(chunk) >= chunksize:
            yield chunk
            chunk = []


def csv_from_row_iter(it):
    sio = StringIO()
    wr = csv2.CsvWriter(sio)
    for row in it:
        sio.seek(0)
        sio.truncate()
        wr.put(row)
        yield sio.getvalue()


def nonce(size=48, encoding='base64url'):
    raw = os.urandom(size)
    if encoding == 'base64url':
        return base64.urlsafe_b64encode(raw).strip()
    else:
        return raw.encode(encoding).strip()


def _attempt_encodings(s, encodings):
    if s is None:
        return u''
    for enc in encodings:
        try:
            if enc is None:
                return unicode(s)  # try default encoding
            else:
                return unicode(s, enc)
        except (UnicodeDecodeError, LookupError):
            pass
    # Return the repr of the str -- should always be safe
    return unicode(repr(str(s)))[1:-1]
