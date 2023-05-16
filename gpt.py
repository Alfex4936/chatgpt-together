import os
import queue

import flet as ft
import openai
from dotenv import load_dotenv

load_dotenv()  # load environment variables

openai.api_key = os.getenv("OPENAI_API_KEY")  # get api key from .env file
message_queue = queue.Queue()
last_gpt_message = None
is_api_call_in_progress = False
users = set()
N = 3  # Change this number to affect history


class MessageHistory:
    def __init__(self, max_length):
        self.max_length = max_length
        self.history = []

    def add(self, message):
        self.history.append(message)
        if len(self.history) > self.max_length:
            self.history.pop(0)

    def get(self):
        return self.history


# Initialize a MessageHistory object with a maximum length of N
gpt_history = MessageHistory(N)


class Message:
    def __init__(self, user_name: str, text: str, message_type: str):
        self.user_name = user_name
        self.text = text
        self.message_type = message_type


class ChatMessage(ft.Row):
    def __init__(self, message: Message, page: ft.Page):
        super().__init__()
        self.message = message
        self.vertical_alignment = "start"
        self.controls = [
            ft.CircleAvatar(
                content=ft.Text(self.get_initials(message.user_name))
                if message.user_name != "ChatGPT"
                else ft.Icon(ft.icons.CHAT_ROUNDED),
                color=ft.colors.WHITE,
                bgcolor=self.get_avatar_color(message.user_name),
            ),
            ft.Column(
                [
                    ft.Text(message.user_name, weight="bold", size=18),
                    ft.Markdown(
                        message.text,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme="atom-one-dark",
                        code_style=ft.TextStyle(font_family="Roboto Mono"),
                        on_tap_link=lambda e: page.launch_url(e.data),
                        # size=20,
                        # width=page.window_width * 0.8
                        width=700,
                    )
                    # ft.Text(md.render(message.text), style=ft.TextThemeStyle.HEADLINE_SMALL, selectable=True, size=20,width=page.window_width * 0.8),
                ],
                tight=True,
                spacing=5,
            ),
        ]

    def get_initials(self, user_name: str):
        return user_name[:1].capitalize()

    def get_avatar_color(self, user_name: str):
        colors_lookup = [
            ft.colors.AMBER,
            ft.colors.BLUE,
            ft.colors.BROWN,
            ft.colors.CYAN,
            ft.colors.GREEN,
            ft.colors.INDIGO,
            ft.colors.LIME,
            ft.colors.ORANGE,
            ft.colors.PINK,
            ft.colors.PURPLE,
            ft.colors.RED,
            ft.colors.TEAL,
            ft.colors.YELLOW,
        ]
        return colors_lookup[hash(user_name) % len(colors_lookup)]


def main(page: ft.Page):
    page.horizontal_alignment = "stretch"
    page.title = "ChatGPT Together"
    page.window_width = 1280
    page.window_height = 720

    def join_chat_click(e):
        if not join_user_name.value:
            join_user_name.error_text = "Name cannot be blank!"
            join_user_name.update()
        elif join_user_name.value in users:
            join_user_name.error_text = "User name exists already!"
            join_user_name.update()
        else:
            page.session.set("user_name", join_user_name.value)
            users.add(join_user_name.value)
            page.dialog.open = False
            new_message.prefix = ft.Text(f"{join_user_name.value}: ")
            page.pubsub.send_all(
                Message(
                    user_name=join_user_name.value,
                    text=f"{join_user_name.value} has joined the chat.",
                    message_type="login_message",
                )
            )
            page.update()

    def send_message_click(e):
        if new_message.value != "":
            if (
                not is_api_call_in_progress
            ):  # only process the queue if no API call is in progress
                user_msg = Message(
                    page.session.get("user_name"),
                    new_message.value,
                    message_type="chat_message",
                )
                page.pubsub.send_all(user_msg)
                message_queue.put(user_msg)
                new_message.value = ""
                page.pubsub.send_all(
                    Message(
                        user_name="ChatGPT",
                        text=f"Answering to {page.session.get('user_name')}...",
                        message_type="chat_message",
                    )
                )  # add the "Thinking..." message to the chat
                process_queue()
            new_message.focus()
            page.update()

    def on_message(message: Message):
        if message.message_type == "chat_message":
            m = ChatMessage(message, page)
        elif message.message_type == "login_message":
            m = ft.Text(message.text, italic=True, color=ft.colors.WHITE, size=16)
        chat.controls.append(m)
        page.update()

    def process_queue():
        global is_api_call_in_progress, last_gpt_message

        if message_queue.empty():
            return

        page.controls[1].controls[1].icon = ft.icons.CLOSE_ROUNDED
        page.update(page.controls[1].controls[1])

        is_api_call_in_progress = (
            True  # set the flag to indicate an API call is in progress
        )
        message = message_queue.get()

        # When generating a new response, use gpt_history.get() to get the list of previous GPT messages
        history = [
            {"role": "assistant", "content": message} for message in gpt_history.get()
        ]

        history.append({"role": "user", "content": message.text})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=history,
        )
        gpt_message = response.choices[0].message["content"]

        # When adding a new GPT message to the history
        gpt_history.add(gpt_message)

        for msg in reversed(chat.controls):
            try:
                if msg.controls[1].controls[0].value == "ChatGPT":
                    chat.controls.remove(msg)
                    break
            except:
                continue

        page.pubsub.send_all(
            Message(user_name="ChatGPT", text=gpt_message, message_type="chat_message")
        )

        is_api_call_in_progress = False  # reset the flag after receiving a response

        page.controls[1].controls[1].icon = ft.icons.SEND_ROUNDED
        page.update(page.controls[1].controls[1])
        # if not message_queue.empty():  # if there are any messages waiting in the queue, process them
        #     process_queue()

    page.pubsub.subscribe(on_message)

    # A dialog asking for a user display name
    join_user_name = ft.TextField(
        label="Enter your name to join the chat",
        autofocus=True,
        on_submit=join_chat_click,
    )
    page.dialog = ft.AlertDialog(
        open=True,
        modal=True,
        title=ft.Text("Welcome!"),
        content=ft.Column([join_user_name], width=300, height=70, tight=True),
        actions=[ft.ElevatedButton(text="Join chat", on_click=join_chat_click)],
        actions_alignment="end",
    )

    # Chat messages
    chat = ft.ListView(
        expand=True,
        spacing=10,
        auto_scroll=True,
    )

    # A new message entry form
    new_message = ft.TextField(
        hint_text="Write a message...",
        autofocus=True,
        shift_enter=True,
        min_lines=1,
        max_lines=5,
        filled=True,
        expand=True,
        on_submit=send_message_click,
    )

    # Add everything to the page
    page.add(
        ft.Container(
            content=chat,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=5,
            padding=10,
            expand=True,
        ),
        ft.Row(
            [
                new_message,
                ft.IconButton(
                    icon=ft.icons.SEND_ROUNDED,
                    tooltip="Send message",
                    on_click=send_message_click,
                ),
            ]
        ),
    )


ft.app(port=8550, target=main, view=ft.WEB_BROWSER)  # or desktop app: ft.FLET_APP
