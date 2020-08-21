import pytz

from django.utils import timezone

from toolbox.models import Profile


class TimezoneMiddleware(object):
    def process_request(self, request):
        if 'django_timezone' in request.session:
            tzname = request.session['django_timezone']
        else:
            user = request.user
            if user.is_anonymous():
                tzname = 'America/Chicago'
            else:
                if hasattr(user, 'profile'):
                    request.session['django_timezone'] = user.profile.timezone
                    tzname = request.session['django_timezone']
                else:
                    profile = Profile.objects.create(user_id=user.id)
                    request.session['django_timezone'] = profile.timezone
                    tzname = request.session['django_timezone']
        timezone.activate(pytz.timezone(tzname))
