#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from conference import ConferenceApi

class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        # TODO 1
        # use _cacheAnnouncement() to set announcement in Memcache
        ConferenceApi._cacheAnnouncement()

app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
], debug=True)



class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )



class SendSessionConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'New session is created in %s !' %self.request.get('confName'), # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'sessionInfo')
        )



class SetFeaturedSpeakerHandler(webapp2.RequestHandler):
    def post(self):
        """Set Announcement in Memcache."""
        ConferenceApi._cacheFeaturedSpeaker(self.request)
        self.response.set_status(204)


app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/send_session_confirmation_email', SendSessionConfirmationEmailHandler),    
    ('/tasks/set_featured_speaker', SetFeaturedSpeakerHandler),
], debug=True)
