# ChatGPT Together

### ChatGPT 함께쓰기 (동시에 많은 유저가 하나의 ChatGPT와 떠들기)

A Collaborative Chat Application

![output](https://github.com/Alfex4936/chatgpt-together/assets/2356749/d2e42b51-031b-49b2-b857-2154384e1e39)

![gui](https://github.com/Alfex4936/Bard-rs/assets/2356749/964a0efb-af86-4b8b-a52a-d62ecec4fbfa)

ChatGPT Together is a project that allows you to run a collaborative chat application with OpenAI's GPT-3.5-turbo or GPT-4. 

This simple Python [Flet](https://flet.dev/) project creates a server for a chat application where multiple users can interact with each other and with only ONE GPT.

> Lots of features/improvements to be implemented

## Features
- Real-time, collaborative chat with multiple users to only one GPT.
- UI with markdown support for messages.
- Username uniqueness check.

## Installation

Clone this repository:
```
git clone https://github.com/Alfex4936/chatgpt-together.git
```
Navigate to the project directory:
```
cd chatgpt-together
```
Set up the required environment variables. Create a `.env` file in the root directory of the project and add the following:
```
OPENAI_API_KEY=your_openai_api_key
```
Replace `your_openai_api_key` with your actual OpenAI API key. 

## Configuration

To switch between gpt-3.5-turbo and gpt-4, adjust the `model` parameter in the `openai.ChatCompletion.create()` method in the code.

To make it remember a history of GPT responses, adjust `N` in the top line.

## Usage

You can run your ChatGPT Together application server by executing the main python file:
```
python gpt.py
```
Your server will start running on the port 8550.

## Acknowledgements

- OpenAI's GPT-3.5-turbo and GPT-4.
- The OpenAI community for providing resources and support.

Enjoy chatting with your friends and AI together with ChatGPT Together!


