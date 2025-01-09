import os
import queue

import flet as ft
import openai
from dotenv import load_dotenv

load_dotenv()  # load environment variables

openai.api_key = os.getenv("OPENAI_API_KEY")  # get api key from .env file

# --- GLOBALS ---
message_queue = queue.Queue()
waiting_for_gpt = False  # Global flag: True = GPT is generating a response
users = set()
N = 5  # to limit how many past messages you send to GPT

# -- Simple conversation limit.
MAX_CHAT_LENGTH = None  # or None for unlimited

# System message to set GPT context:
SYSTEM_PROMPT = (
    "You are ChatGPT, a large language model from OpenAI. "
    "Multiple users are chatting with you in a single shared session. "
    "Respond helpfully and consider that messages may come from different users."
)

# A unified conversation in memory (for all participants).
# We'll store messages as dictionaries:
#   {"role": "user"/"assistant"/"system", "content": "...", "sender": "username or ChatGPT"}
conversation_history = [
    {"role": "system", "content": SYSTEM_PROMPT, "sender": "system"}
]


def add_to_conversation(role: str, content: str, sender: str):
    """
    Add a new message to our in-memory conversation list.
    Automatically trims the conversation if it exceeds MAX_CHAT_LENGTH.
    """
    conversation_history.append({"role": role, "content": content, "sender": sender})
    if MAX_CHAT_LENGTH and len(conversation_history) > MAX_CHAT_LENGTH:
        # Remove oldest messages but keep the system message
        conversation_history[1 : 1 + (len(conversation_history) - MAX_CHAT_LENGTH)] = []


class Message:
    """
    Simple wrapper for messages broadcasted via pubsub.
    message_type can be 'chat_message', 'login_message', 'control_message', etc.
    """
    def __init__(self, user_name: str, text: str, message_type: str):
        self.user_name = user_name
        self.text = text
        self.message_type = message_type


class ChatMessage(ft.Row):
    """
    Render a single chat bubble in the UI.
    """
    def __init__(self, message: Message, page: ft.Page):
        super().__init__()
        self.message = message
        self.vertical_alignment = "start"
        self.controls = [
            ft.CircleAvatar(
                content=ft.Text(self.get_initials(message.user_name))
                if message.user_name.lower() != "chatgpt"
                else ft.Icon(ft.icons.CHAT_ROUNDED),
                color=ft.colors.WHITE,
                bgcolor=self.get_avatar_color(message.user_name),
            ),
            ft.Column(
                [
                    ft.Text(message.user_name, weight="bold", size=16),
                    ft.Markdown(
                        message.text,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme="atom-one-dark",
                        code_style=ft.TextStyle(font_family="Roboto Mono"),
                        on_tap_link=lambda e: page.launch_url(e.data),
                        width=700,
                    )
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
    
    def send_message_click(e):
        """
        Handler for when the user sends a new message.
        """
        global waiting_for_gpt
        if not new_message_field.value.strip():
            return

        # If GPT is busy, ignore or queue the message.
        if waiting_for_gpt:
            # Optionally queue or show a notice. For now, let's just queue it.
            message_queue.put(
                Message(
                    page.session.get("user_name"),
                    new_message_field.value.strip(),
                    "chat_message",
                )
            )
            new_message_field.value = ""
            new_message_field.update()
            return

        # Otherwise, proceed
        user_msg = Message(
            user_name=page.session.get("user_name"),
            text=new_message_field.value.strip(),
            message_type="chat_message",
        )
        new_message_field.value = ""
        new_message_field.update()

        # Broadcast to all that a user message arrived
        page.pubsub.send_all(user_msg)
        # Put it in the message queue to process
        message_queue.put(user_msg)

        # Show "thinking..."
        page.pubsub.send_all(
            Message(
                user_name="ChatGPT",
                text=f"Thinking...",
                message_type="chat_message"
            )
        )

        # Start queue processing
        process_message_queue()
        
    page.horizontal_alignment = "stretch"
    page.title = "ChatGPT Together"
    page.window.width = 1280
    page.window.height = 720

    # Our main chat container:
    chat_list_view = ft.ListView(expand=True, spacing=10, auto_scroll=True)

    # A read-only list of users:
    user_list_view = ft.ListView(
        expand=False, spacing=2, auto_scroll=True, width=180,
        # bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
    )

    # TextField where users type new messages
    new_message_field = ft.TextField(
        hint_text="Write a message...",
        autofocus=True,
        shift_enter=True,
        on_submit=send_message_click,
        multiline=True,
        min_lines=2,
        max_lines=10,
        filled=True,
        expand=True,
    )

    # Icon button to send messages
    send_button = ft.IconButton(
        icon=ft.icons.SEND_ROUNDED,
        tooltip="Send message",
        on_click=send_message_click,
    )

    def refresh_user_list():
        """
        Update the user list in the UI (so that every user sees the participants).
        """
        user_list_view.controls.clear()
        for u in sorted(users):
            user_list_view.controls.append(
                ft.Text(u, size=14, color=ft.colors.WHITE)
            )
        user_list_view.update()

    def on_pubsub_message(message: Message):
        """
        Called whenever a message is published via page.pubsub.send_all().
        """
        if message.message_type == "chat_message":
            # Normal user or ChatGPT message
            chat_list_view.controls.append(ChatMessage(message, page))
        elif message.message_type == "login_message":
            # A login notice
            chat_list_view.controls.append(
                ft.Text(message.text, italic=True, color=ft.colors.WHITE, size=15)
            )
        elif message.message_type == "control_message":
            # A control message that toggles input availability, etc.
            if message.text == "disable_input":
                new_message_field.disabled = True
                send_button.disabled = True
            elif message.text == "enable_input":
                new_message_field.disabled = False
                send_button.disabled = False
            new_message_field.update()
            send_button.update()

        chat_list_view.update()

    page.pubsub.subscribe(on_pubsub_message)

    def join_chat_click(e):
        """
        When the user clicks or presses Enter on the join dialog, we register them.
        """
        if not join_user_name.value:
            join_user_name.error_text = "Name cannot be blank!"
            join_user_name.update()
            return

        if join_user_name.value in users:
            join_user_name.error_text = "User name exists already!"
            join_user_name.update()
            return

        page.session.set("user_name", join_user_name.value)
        users.add(join_user_name.value)
        refresh_user_list()

        # Close the join dialog
        page.dialog.open = False
        page.update()

        # Broadcast a login message
        page.pubsub.send_all(
            Message(join_user_name.value, f"{join_user_name.value} has joined the chat.", "login_message")
        )


    def process_message_queue():
        """
        Pop messages from the message_queue one by one, generate GPT responses.
        We block new messages while GPT is thinking.
        """
        global waiting_for_gpt

        if message_queue.empty() or waiting_for_gpt:
            return

        # Disable user input for everyone
        waiting_for_gpt = True
        page.pubsub.send_all(Message("system", "disable_input", "control_message"))

        # Pull the next user message from the queue
        next_message = message_queue.get()

        # Add user message to global conversation
        add_to_conversation("user", next_message.text, sender=next_message.user_name)

        if N is not None:
            # Keep the system message + last N user/assistant messages
            relevant_history = [conversation_history[0]] + conversation_history[-N * 2:]
        else:
            relevant_history = conversation_history

        # Build the body for openai
        messages_for_gpt = [
            {"role": msg["role"], "content": msg["content"]} for msg in relevant_history
        ]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages_for_gpt,
            )
            gpt_text = response.choices[0].message.content
        except Exception as ex:
            gpt_text = f"**Error while calling OpenAI API**: {ex}"

        # Remove the "thinking..." message from the chat
        for msg_control in reversed(chat_list_view.controls):
            if isinstance(msg_control, ChatMessage) and msg_control.message.user_name == "ChatGPT" \
               and msg_control.message.text == "Thinking...":
                chat_list_view.controls.remove(msg_control)
                chat_list_view.update()
                break

        # Add GPT's final answer to the conversation and broadcast it
        add_to_conversation("assistant", gpt_text, sender="ChatGPT")

        page.pubsub.send_all(Message("ChatGPT", gpt_text, "chat_message"))

        # Done generating
        waiting_for_gpt = False
        page.pubsub.send_all(Message("system", "enable_input", "control_message"))

        # If there are still messages in the queue, process the next one
        if not message_queue.empty():
            process_message_queue()

    # -- UI Setup --

    # A dialog asking for a user display name:
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

    # Hook up the send button
    send_button.on_click = send_message_click

    # Layout: A row with [Chat column | Participants list]
    content_row = ft.Row(
        [
            ft.Container(
                content=chat_list_view,
                border=ft.border.all(1, ft.colors.OUTLINE),
                border_radius=5,
                padding=10,
                expand=True,
            ),
            ft.Container(
                content=user_list_view,
                border=ft.border.all(1, ft.colors.OUTLINE),
                border_radius=5,
                padding=10,
                expand=False,
            ),
        ],
        expand=True,
    )

    # Bottom row: message box + send button
    input_row = ft.Row(
        [
            new_message_field,
            send_button,
        ]
    )

    # Add everything to the page
    page.add(content_row, input_row)


# Start the app
# view=ft.WEB_BROWSER will open it in a browser
ft.app(
    port=8550, 
    target=main, 
    view=ft.WEB_BROWSER
)
