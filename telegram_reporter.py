"""
Telegram Reporter for BINGO365 Monitoring
Sends daily reports to Telegram
"""
import os
import requests
import streamlit as st


def get_telegram_config():
    """Get Telegram credentials from Streamlit secrets or environment"""
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        bot_token = st.secrets.get("telegram", {}).get("bot_token")
        chat_id = st.secrets.get("telegram", {}).get("chat_id")
        if bot_token and chat_id:
            return bot_token, chat_id
    except:
        pass

    # Fall back to environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    return bot_token, chat_id


class TelegramReporter:
    """Telegram bot for sending reports"""

    def __init__(self):
        self.bot_token, self.chat_id = get_telegram_config()

        if not self.bot_token or not self.chat_id:
            raise ValueError(
                "Telegram credentials not configured. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in environment or Streamlit secrets."
            )

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, message, parse_mode='HTML'):
        """
        Send text message to Telegram

        Args:
            message: Text message to send (supports HTML formatting)
            parse_mode: 'HTML' or 'Markdown'

        Returns:
            dict: Telegram API response
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()

            if not result.get('ok'):
                error_desc = result.get('description', 'Unknown error')
                raise Exception(f"Telegram API error: {error_desc}")

            return result

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to send Telegram message: {e}")

    def send_document(self, file_path, caption=None):
        """
        Send a document/file to Telegram

        Args:
            file_path: Path to file to send
            caption: Optional caption for the file

        Returns:
            dict: Telegram API response
        """
        url = f"{self.base_url}/sendDocument"

        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': self.chat_id}
            if caption:
                data['caption'] = caption

            response = requests.post(url, data=data, files=files, timeout=60)
            return response.json()


def test_connection():
    """Test Telegram connection"""
    try:
        reporter = TelegramReporter()
        result = reporter.send_message("🔔 <b>Test Message</b>\n\nBINGO365 Monitoring connection test successful!")
        print(f"✅ Message sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
