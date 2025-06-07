import pywhatkit


def send_whatsapp_message(phone_number, message, time_hour, time_minute):
    """
    Sends a WhatsApp message to a specified phone number at a specified time.
    
    :param phone_number: str, the phone number in the format '+1234567890'
    :param message: str, the message to send
    :param time_hour: int, the hour to send the message (24-hour format)
    :param time_minute: int, the minute to send the message
    """
    pywhatkit.sendwhatmsg(phone_number, message, time_hour, time_minute)

send_whatsapp_message("+4917658815100", "Hello, this is a test message!", 15, 22)  # Example usage