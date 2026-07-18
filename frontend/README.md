# ChatRoom Frontend

React and TypeScript UI for conversations, provider selection, custom agents, CSV knowledge, and execution inspection.

Requires the Node.js version declared in `.nvmrc`.

```sh
npm ci
npm run dev
npm run lint
npm run build
```

The API defaults to `http://127.0.0.1:8001`. Set `VITE_API_URL` when the backend uses another address.

See the project [README](../README.md) for setup and [high-level design](../docs/high_level_design.md) for the request flow.
