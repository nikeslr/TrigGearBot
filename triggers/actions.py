# triggers/actions.py
class Action:
    async def execute(self, message, context):
        raise NotImplementedError

class SendMessage(Action):
    def __init__(self, text):
        self.text = text

    async def execute(self, message, context):
        await context["bot"].send_message(chat_id=message.chat.id, text=self.text)