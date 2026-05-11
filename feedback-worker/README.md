# Feedback Worker

Static GitHub Pages cannot create GitHub issues anonymously without exposing a token in the browser. This Worker receives public feedback submissions and creates GitHub issues with a server-side secret.

## Deploy

1. Create a fine-grained GitHub token with `Issues: Read and write` access for `sdmandel/dynasty-rankings`.
2. Copy `wrangler.toml.example` to `wrangler.toml`.
3. Set the secret:

```bash
wrangler secret put GITHUB_TOKEN
```

4. Deploy:

```bash
wrangler deploy
```

5. If the Worker URL differs from `https://baseball-feedback.stephenmandella.workers.dev`, update `FEEDBACK_ENDPOINT` in `../assets/feedback.js` or set `window.BACKYARD_FEEDBACK_ENDPOINT` before loading `feedback.js`.

The browser never sees `GITHUB_TOKEN`; it only POSTs feedback JSON to the Worker.
