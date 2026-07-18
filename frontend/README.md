# ChatRoom Frontend

Vite React frontend for the ChatRoom teaching project.

## Scripts

Requires Node.js 20.19+ (see `.nvmrc`).

```sh
nvm use
npm run dev
npm run build
npm run lint
```

Set `VITE_API_URL` in the project `.env` if the backend is not on `http://127.0.0.1:8001`.

## UI Overview

ChatGPT-style layout:

- **Sidebar** — New chat, conversation list, model selector (Ollama / OpenAI / Bedrock), Settings
- **Main** — centered messages and composer (Enter to send; chats auto-create)
- **Settings** — connector tools, CSV uploads, and custom agents
- **Inspect** — optional right panel for Trace, Artifacts, and Tools

See the project root [README](../README.md) and [group chat flow](../docs/local_group_chat_flow.md) for the end-to-end request flow.
