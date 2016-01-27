#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'prakash+api@google.com (prakash)'


from datetime import datetime
import json
import endpoints
import re
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize
from models import Session
from models import SessionForm
from models import SessionForms
from models import SpeakerName


from utils import getUserId

from settings import WEB_CLIENT_ID

from google.appengine.api import memcache

from models import StringMessage
from google.appengine.api import taskqueue

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
MEMCACHE_SPEAKERS_KEY = 'FEATURED SPEAKERS'
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

#------Session starts

DEFAULTSSESSION = {
    "duration": "1",
    "typeOfSession": "Theory",
    "highlights": "Very good session",
}

#------Session ends

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SES_GET_BY_TYPE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
)

SES_GET_BY_CONF_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SES_GET_SPEAKER_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1),
)

SES_GET_SPEAKERMAIL_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1),
    speakerEmail=messages.StringField(2),
)

SES_ADD_TO_WISHLIST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1)
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESS_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

SES_DELETE_FROM_WISHLIST = endpoints.ResourceContainer(
    SessionForm,
    websafeSessionKey=messages.StringField(1)
)

SES_GET_BY_DURATION_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    duration=messages.StringField(1),
    websafeConferenceKey=messages.StringField(2),
)

SES_GET_BEFORE_SEVEN_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', 
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf

#----------------session starts----------------
    def _copySessionToForm(self, ses):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(ses, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(sf, field.name, str(getattr(ses, field.name)))
                elif field.name == 'startTime':
                    setattr(sf, field.name, str(getattr(ses, field.name)))
                else:
                    setattr(sf, field.name, getattr(ses, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, ses.key.urlsafe())
        sf.check_initialized()
        return sf
#----------------session ends----------------

    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        # confirmation email sending task to queue
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        """update Conference object, returning ConferenceForm/request."""        
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

#------------session starts-----------------------
    def _createSessionObject(self, request):
        """Create or update Session object, returning SessionForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)
        """check mandatory fiels are populated starts"""
        if not request.name:
            raise endpoints.BadRequestException("session 'name' field required")

        if not request.speaker:
            raise endpoints.BadRequestException("session 'speaker name' field required")

        if not request.speakerEmail:
            raise endpoints.BadRequestException("session 'speaker email' field required")

        elif not EMAIL_REGEX.match(request.speakerEmail):
            raise endpoints.BadRequestException("session 'speaker email' valid format required")
        """check mandatory fiels are populated ends"""

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        
        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTSSESSION:
            if data[df] in (None, []):
                data[df] = DEFAULTSSESSION[df]
                setattr(request, df, DEFAULTSSESSION[df])
                
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'], "%H:%M").time()

        #get conference key based on websafe conference key
        wsck = request.websafeConferenceKey
        c_key = ndb.Key(urlsafe=wsck)
        if not c_key.get():
            raise endpoints.NotFoundException('No conference found with key: %s' % wsck)

        s_id = Session.allocate_ids(size=1, parent=c_key)[0]
        s_key = ndb.Key(Session, s_id, parent=c_key)
        data['key'] = s_key
        #data['organizerUserId'] = request.organizerUserId = user_id

        del data['websafeConferenceKey']

        # creation of Session & return (modified) SessionForm
        Session(**data).put()
        session = s_key.get()

        #get the conference based on session created
        conf = session.key.parent().get()
        """task for setting featured speakers by sending
           speaker email,speaker name and websafeconferencekey"""
        if data['speaker'] and data['speakerEmail']:
            taskqueue.add(params={'speaker': data['speaker'],'speakerEmail': data['speakerEmail'],
                                  'confName':conf.name,'websafeConferenceKey': wsck},
                          url='/tasks/set_featured_speaker'
                          )
        #send email to conference owner regarding new session
        taskqueue.add(params={'email': user.email(),'confName': conf.name,
            'sessionInfo': repr(request)},
            url='/tasks/send_session_confirmation_email'
        )                
        return self._copySessionToForm(session)



    @endpoints.method(SESS_POST_REQUEST, SessionForm,
                      path='session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session."""
        return self._createSessionObject(request)

    @endpoints.method(SES_GET_SPEAKER_REQUEST, SessionForms,
            path='getSessionsBySpeaker',
            http_method='POST', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Return sessions based on speaker."""
        sessions = Session.query(Session.speaker == request.speaker)
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )

    @endpoints.method(SES_GET_SPEAKERMAIL_REQUEST, SessionForms,
            path='getSessionsBySpeakerAndMail',
            http_method='POST', name='getSessionsBySpeakerAndMail')
    def getSessionsBySpeakerAndMail(self, request):
        """Return sessions based on speaker and speaker email address."""
        
        if not request.speaker:
            raise endpoints.BadRequestException("session 'speaker name' field required")

        if not request.speakerEmail:
            raise endpoints.BadRequestException("session 'speaker email' field required")

        elif not EMAIL_REGEX.match(request.speakerEmail):
            raise endpoints.BadRequestException("session 'speaker email' valid format required")
        
        sessions = Session.query(Session.speaker == request.speaker)
        sessions = sessions.filter(Session.speakerEmail == request.speakerEmail)
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )

    @endpoints.method(SES_GET_BY_TYPE_REQUEST, SessionForms,
            path='getConferenceSessionsByType',
            http_method='POST', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):        
        """Return sessions based on type of session."""
        sessions = Session.query(ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        sessions = sessions.filter(Session.typeOfSession == request.typeOfSession)
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )

    @endpoints.method(SES_GET_BY_DURATION_REQUEST, SessionForms,
            path='getConferenceSessionsByDuration',
            http_method='POST', name='getConferenceSessionsByDuration')
    def getConferenceSessionsByDuration(self, request):        
        """Return sessions based on duration"""
        sessions = Session.query(ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        sessions = sessions.filter(Session.duration == request.duration)
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )

    @endpoints.method(SES_GET_BY_CONF_REQUEST, SessionForms,
            path='getConferenceSessions',
            http_method='POST', name='getConferenceSessions')
    def getConferenceSessions(self, request):        
        """Return sessions created in a conference."""
        sessions = Session.query(ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )


    @endpoints.method(SES_ADD_TO_WISHLIST, BooleanMessage,
            path='session/wishlist/{websafeSessionKey}',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add session to user's wishlist."""
        prof = self._getProfileFromUser()  
        wssk = request.websafeSessionKey
        wssk = wssk.strip()
        sess = ndb.Key(urlsafe=wssk).get()
        if not sess:
            raise endpoints.NotFoundException(
                'No session found')
        if wssk in prof.wishlist:
            raise ConflictException(
                "You have already registered for this conference")
        #append the websafe key into users wishlist 
        prof.wishlist.append(wssk)        
        #save the profile to datastore
        prof.put()
        return BooleanMessage(data=True)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='session/getConferenceFromSessionsWishlist',
            http_method='GET', name='getConferenceFromSessionsWishlist')
    def getConfFromSessionsInWishlist(self, request):
        "returns conferences for the corresponding sessions in wishlist"
        prof = self._getProfileFromUser()

        if not prof:
            raise ConflictException(
                "profile not found")

        if prof.wishlist:
            seskey = [ndb.Key(urlsafe=wlsk) for wlsk in prof.wishlist]
            sessions = ndb.get_multi(seskey)
            conferences =[]
            for ses in sessions:
                #get parent for each session
                conferences.append(ses.key.parent().get())
                
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in conferences]
        )


    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='session/wishlist',
            http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):        
        """get sessions from user's wishlist."""
        prof = self._getProfileFromUser()

        if not prof:
            raise ConflictException(
                "profile not found")

        if prof.wishlist:
            seskey = [ndb.Key(urlsafe=wlsk) for wlsk in prof.wishlist]
            sessions = ndb.get_multi(seskey)

        else:
            raise ConflictException(
                "You dont have no sessions in your wish list")

        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )
    
    @endpoints.method(SES_DELETE_FROM_WISHLIST, SessionForms,
            path='session/wishlist/{websafeSessionKey}',
            http_method='DELETE', name='deleteSessionInWishlist')
    def deleteSessionInWishlist(self, request):
        "delete a session from wishlist"
        prof = self._getProfileFromUser()
        if not prof:
            raise ConflictException(
                "profile not found")
        wssk = request.websafeSessionKey
        wssk = wssk.strip()
        sess = ndb.Key(urlsafe=wssk).get()
        if not sess:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % wssk)
        if wssk in prof.wishlist:
            prof.wishlist.remove(wssk)
        else:
            raise ConflictException(
                "You dont have any sessions in your wish list")
        seskey = [ndb.Key(urlsafe=wlsk) for wlsk in prof.wishlist]
        #get all the sessions
        sessions = ndb.get_multi(seskey)
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sessions]
        )

    @endpoints.method(
        SES_GET_BEFORE_SEVEN_REQUEST,
        SessionForms,
        path='getSessionsBeforeSeven',
        http_method='GET',
        name='getSessionsBeforeSeven'
    )
    def getSessionsBeforeSeven(self, request):
        """get session before 7 pm in a conference"""
        wsck = request.websafeConferenceKey
        c_key = ndb.Key(urlsafe=wsck)
        conf = c_key.get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)        
        sessionTime = datetime.strptime("19:00", "%H:%M").time()
        #fetch session and filter by time less than 7:00 pm
        q = Session.query(ancestor=c_key).\
            filter(Session.startTime < sessionTime).\
            order(Session.startTime).\
            fetch()
        # Init an empty list where to store filtered sessions
        filteredSessions = []
        for sess in q:
            if sess.typeOfSession != 'WORKSHOP' and  sess.startTime is not None:
                filteredSessions.append(self._copySessionToForm(sess))
        # return set of SessionForm objects
        return SessionForms(
            items=filteredSessions
        )

    @staticmethod
    def _cacheFeaturedSpeaker(request):
        """Create Announcement for featured speaker & assign to memcache."""
        #fitlter session based on websafe onference key,speaker name and mail
        sessions = Session.query(ancestor=ndb.Key(urlsafe=request.get('websafeConferenceKey')))
        sessions = sessions.filter(Session.speaker == request.get('speaker'))
        sessions = sessions.filter(Session.speakerEmail == request.get('speakerEmail'))
        sessions = sessions.fetch()
        if len(sessions) >= 2:
            announcement = '%s speaks at' % sessions[0].speaker
            announcement += ', '.join(sess.name for sess in sessions)
            announcement += 'in conferences '.join(request.get('confName'))
            memcache.set(MEMCACHE_SPEAKERS_KEY, announcement)
        else:
            announcement = ''
        return announcement

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='conference/getFeaturedSpeaker',
                      http_method='GET', name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Get featured speakers."""
        featuredSpeaker = memcache.get(MEMCACHE_SPEAKERS_KEY)
        if not featuredSpeaker:
            featuredSpeaker = "no featured speaker"
        # return json data
        return StringMessage(data=json.dumps(featuredSpeaker))

#------------session ends

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id =  getUserId(user)
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )


# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


api = endpoints.api_server([ConferenceApi]) # register API
