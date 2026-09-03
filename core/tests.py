from django.test import TestCase, RequestFactory, override_settings
from core.utils import get_frontend_url, get_default_from_email


class UtilsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_frontend_url_from_origin_tresta(self):
        request = self.factory.post('/api/v1/account/invitations/send/', HTTP_ORIGIN='https://tresta.cloud')
        self.assertEqual(get_frontend_url(request), 'https://tresta.cloud')

    def test_get_frontend_url_from_origin_localhost(self):
        request = self.factory.post('/api/v1/account/invitations/send/', HTTP_ORIGIN='http://localhost:3000')
        self.assertEqual(get_frontend_url(request), 'http://localhost:3000')

    def test_get_frontend_url_from_referer_tresta(self):
        request = self.factory.post('/api/v1/account/invitations/send/', HTTP_REFERER='https://tresta.cloud/invite-users')
        self.assertEqual(get_frontend_url(request), 'https://tresta.cloud')

    def test_get_frontend_url_from_referer_localhost(self):
        request = self.factory.post('/api/v1/account/invitations/send/', HTTP_REFERER='http://localhost:3000/users')
        self.assertEqual(get_frontend_url(request), 'http://localhost:3000')

    @override_settings(FRONTEND_URL='https://tresta.cloud')
    def test_get_frontend_url_without_request(self):
        self.assertEqual(get_frontend_url(None), 'https://tresta.cloud')

    @override_settings(FRONTEND_URL='https://custom-domain.com')
    def test_get_frontend_url_custom_setting(self):
        request = self.factory.post('/api/v1/account/invitations/send/')
        self.assertEqual(get_frontend_url(request), 'https://custom-domain.com')

    @override_settings(DEFAULT_FROM_EMAIL='noreply@custom.com')
    def test_get_default_from_email_configured(self):
        self.assertEqual(get_default_from_email(), 'noreply@custom.com')

    @override_settings(DEFAULT_FROM_EMAIL=None)
    def test_get_default_from_email_fallback(self):
        self.assertEqual(get_default_from_email(), 'info@tresta.cloud')
