import unittest
from unittest.mock import patch, MagicMock
from lambda_function import CarrierClient, EmailNotifier, lambda_handler, handler_local


class TestCarrierClient(unittest.TestCase):

    @patch('requests.get')
    def test_fetch_tickets(self, mock_get):
        base_url = 'https://api.example.com'
        token = 'token'
        project_id = '61'
        board_id = '8'

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total": 8,
            "rows": [
                {
                    "id": 58,
                    "status": "in_progress",
                    "type": "Activity",
                    "start_date": "2024-11-28"
                },
                {
                    "id": 59,
                    "status": "done",
                    "type": "Activity",
                    "start_date": "2024-11-28"
                }
            ]
        }
        mock_get.return_value = mock_response

        client = CarrierClient(base_url, token)
        tickets = client.fetch_tickets(project_id, board_id)
        self.assertEqual(len(tickets), 2)
        self.assertEqual(tickets[0]["id"], 58)


class TestEmailNotifier(unittest.TestCase):

    @patch('smtplib.SMTP_SSL')
    def test_send_email(self, mock_smtp):
        smtp_settings = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_sender": "sender@example.com",
            "smtp_user": "user@example.com",
            "smtp_password": "password",
            "smtp_email_recipients": ["recipient@example.com"]
        }

        notifier = EmailNotifier(smtp_settings)
        notifier.send_email("Test Subject", "<h1>Test Body</h1>")

        mock_smtp.assert_called_with(smtp_settings["smtp_host"], smtp_settings["smtp_port"])
        instance = mock_smtp.return_value
        instance.login.assert_called_with(smtp_settings["smtp_user"], smtp_settings["smtp_password"])
        instance.sendmail.assert_called()


class TestHandlers(unittest.TestCase):

    @patch('my_module.CarrierClient.fetch_tickets')
    @patch('my_module.EmailNotifier.send_email')
    @patch('jinja2.Environment.get_template')
    def test_lambda_handler(self, mock_get_template, mock_send_email, mock_fetch_tickets):
        event = {
            "token": "token",
            "base_url": "https://api.example.com",
            "project_id": "61",
            "host": "smtp.example.com",
            "port": 465,
            "user": "user@example.com",
            "passwd": "password",
            "sender": "sender@example.com",
            "board_id": "8",
            "recipients": "recipient@example.com"
        }
        context = {}

        mock_fetch_tickets.return_value = [
            {
                "id": 58,
                "status": "in_progress",
                "type": "Activity",
                "start_date": "2024-11-28"
            },
            {
                "id": 59,
                "status": "done",
                "type": "Activity",
                "start_date": "2024-11-28"
            }
        ]
        mock_template = MagicMock()
        mock_template.render.return_value = '<h1>Test Email</h1>'
        mock_get_template.return_value = mock_template

        response = lambda_handler(event, context)
        self.assertEqual(response['statusCode'], 200)
        mock_send_email.assert_called()

    @patch('my_module.CarrierClient.fetch_tickets')
    @patch('my_module.EmailNotifier.send_email')
    @patch('jinja2.Environment.get_template')
    def test_handler_local(self, mock_get_template, mock_send_email, mock_fetch_tickets):
        event = {
            "base_url": "https://api.example.com",
            "token": "token",
            "project_id": "61",
            "board_id": "8",
            "host": "smtp.example.com",
            "port": 465,
            "user": "user@example.com",
            "passwd": "password",
            "sender": "sender@example.com",
            "recipients": "recipient@example.com"
        }
        context = {}

        mock_fetch_tickets.return_value = [
            {
                "id": 58,
                "status": "in_progress",
                "type": "Activity",
                "start_date": "2024-11-28"
            },
            {
                "id": 59,
                "status": "done",
                "type": "Activity",
                "start_date": "2024-11-28"
            }
        ]
        mock_template = MagicMock()
        mock_template.render.return_value = '<h1>Test Email</h1>'
        mock_get_template.return_value = mock_template

        response = handler_local(event, context)
        self.assertEqual(response['statusCode'], 200)
        mock_send_email.assert_called()


if __name__ == '__main__':
    unittest.main()
