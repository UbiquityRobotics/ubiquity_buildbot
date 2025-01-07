from twisted.internet import defer
from twisted.internet import reactor

from buildbot import config
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep

from buildbot.plugins import *

import json

# use the 'requests' lib: http://python-requests.org
try:
    import txrequests
    import requests
except ImportError:
    txrequests = None


# This step uses a global Session object, which encapsulates a thread pool as
# well as state such as cookies and authentication.  This state may pose
# problems for users, where one step may get a cookie that is subsequently used
# by another step in a different build.

_session = None


def getSession():
    global _session
    if _session is None:
        _session = txrequests.Session()
        reactor.addSystemEventTrigger("before", "shutdown", closeSession)
    return _session


def setSession(session):
    global _session
    _session = session


def closeSession():
    global _session
    if _session is not None:
        _session.close()
        _session = None

class AptlyUpdatePublishStep(steps.HTTPStepNewStyle):

    '''
    PUT an empty dict to /api/publish/ENDPOINT
    '''
    def __init__(self, aptly_base_url, auth, endpoint, **kwargs):
        super().__init__(
            aptly_base_url + '/api/publish/' + endpoint,
            auth=auth, method='PUT', json={},
            **kwargs
        )

class AptlyCopyPackageStep(BuildStep):

    name = 'AptlyCopyPackageStep'
    description = 'Copying Package'
    descriptionDone = 'Copied Package'
    renderables = ["aptly_base_url", "from_repo", "dest_repo", "package_query"]
    session = None

    def __init__(self, aptly_base_url, auth, from_repo, dest_repo, package_query, **kwargs):
        if txrequests is None:
            config.error(
                "Need to install txrequest to use this step:\n\n pip3 install txrequests")

        self.aptly_base_url = aptly_base_url
        self.from_repo = from_repo
        self.dest_repo = dest_repo
        self.package_query = package_query
        self.auth = auth

        super().__init__(**kwargs)

    def start(self):
        d = self.doCopy()
        d.addErrback(self.failed)

    @defer.inlineCallbacks
    def doRequest(self, request_kwargs):
        log = self.getLog('log')
        log.addHeader('Performing %s request to %s\n' %
                      (request_kwargs['method'], request_kwargs['url']))
        if 'params' in request_kwargs:
            log.addHeader('Parameters:\n')
            for k, v in request_kwargs['params'].items():
                log.addHeader('\t%s: %s\n' % (k, v))

        try:
            r = yield self.session.request(**request_kwargs)
        except requests.exceptions.ConnectionError as e:
            log.addStderr(
                'An exception occurred while performing the request: %s' % e)
            self.finished(FAILURE)
            return

        if r.history:
            log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
            for rr in r.history:
                self.log_response(rr)
                log.addStdout('=' * 60 + '\n')

        self.log_response(r)

        return r

    @defer.inlineCallbacks
    def doCopy(self):
        # create a new session if it doesn't exist
        self.session = getSession()
        log = self.addLog('log')

        search_kwargs = {
            'method': 'GET',
            'url': self.aptly_base_url + '/api/repos/' + self.from_repo + '/packages',
            'auth': self.auth,
            'params': {'q' : self.package_query}
        }

        r_search = yield self.doRequest(search_kwargs)
        if (r_search.status_code >= 400):
            self.finished(FAILURE)
            log.finish()
        
        copy_kwargs = {
            'method': 'POST',
            'url': self.aptly_base_url + '/api/repos/' + self.dest_repo + '/packages',
            'auth': self.auth,
            'json': {'PackageRefs' : r_search.json()}  
        }

        r_copy = yield self.doRequest(copy_kwargs)
        if (r_search.status_code >= 400):
            self.finished(FAILURE)
            log.finish()

        self.finished(SUCCESS)

    def log_response(self, response):
        log = self.getLog('log')

        log.addHeader('Request Header:\n')
        for k, v in response.request.headers.items():
            if k == 'Authorization':
                v = '[not logging secrets]'
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout('URL: %s\n' % response.url)

        if response.status_code == requests.codes.ok:
            log.addStdout('Status: %s\n' % response.status_code)
        else:
            log.addStderr('Status: %s\n' % response.status_code)

        log.addHeader('Response Header:\n')
        for k, v in response.headers.items():
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout(' ------ Content ------\n%s' % response.text)
        self.addLog('content').addStdout(response.text)

