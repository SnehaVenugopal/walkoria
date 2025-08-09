from social_core.pipeline.social_auth import social_user as default_social_user
from social_core.exceptions      import AuthAlreadyAssociated
from social_django.models        import UserSocialAuth

def social_user_or_get_existing(*args, **kwargs):
    """
    A drop-in replacement for social_core.pipeline.social_auth.social_user
    that won’t blow up if the UID is already linked: it just pulls
    the existing UserSocialAuth and returns that user.
    """
    try:
        # exact same call as the built-in step
        return default_social_user(*args, **kwargs)
    except AuthAlreadyAssociated:
        # extract backend & uid from kwargs (pipeline always provides them)
        uid     = kwargs.get('uid')
        backend = kwargs.get('backend')
        provider = getattr(backend, 'name', kwargs.get('provider'))
        usa = UserSocialAuth.objects.get(uid=uid, provider=provider)
        return {
            'social': usa,
            'user':   usa.user,
        }
