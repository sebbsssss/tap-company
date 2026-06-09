#!/usr/bin/env node
/**
 * Mint a Google OAuth2 refresh token for use with the Google Workspace MCP server.
 *
 * Usage:
 *   node scripts/mint-google-refresh-token.js ~/Downloads/client_secret_*.json
 *
 * Prerequisites:
 *   - Node.js 18+ (uses built-in http/https — no npm install needed)
 *   - The client_secret JSON downloaded from Google Cloud Console → OAuth 2.0 Clients
 *   - In Google Cloud Console, add http://127.0.0.1:8080/callback to the client's
 *     Authorised redirect URIs before running this script.
 *
 * What it does:
 *   1. Reads client_id and client_secret from the provided JSON file.
 *   2. Starts a local HTTP server on 127.0.0.1:8080 to catch the OAuth redirect.
 *   3. Prints the consent URL — open it in your browser and sign in as the TAP
 *      service Google account.
 *   4. Exchanges the returned auth code for tokens.
 *   5. Prints the refresh_token plus copy-paste instructions for Paperclip.
 */

"use strict";

const fs = require("fs");
const http = require("http");
const https = require("https");
const path = require("path");
const { URLSearchParams } = require("url");

const REDIRECT_URI = "http://127.0.0.1:8080/callback";
const PORT = 8080;

const SCOPES = [
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/gmail.compose",
  "https://www.googleapis.com/auth/drive.readonly",
  "https://www.googleapis.com/auth/calendar",
];

function loadCredentials(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  const parsed = JSON.parse(raw);
  // Google Cloud Console downloads have either a "web" or "installed" top-level key.
  const creds = parsed.web || parsed.installed;
  if (!creds) {
    throw new Error(
      'Could not find "web" or "installed" key in client_secret JSON. ' +
        "Download a fresh copy from Google Cloud Console → OAuth 2.0 Clients."
    );
  }
  return {
    clientId: creds.client_id,
    clientSecret: creds.client_secret,
    tokenUri: creds.token_uri || "https://oauth2.googleapis.com/token",
  };
}

function buildAuthUrl(clientId) {
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: SCOPES.join(" "),
    access_type: "offline",
    prompt: "consent", // force Google to always return a refresh_token
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

function waitForCallback() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const reqUrl = new URL(req.url, `http://127.0.0.1:${PORT}`);

      if (reqUrl.pathname !== "/callback") {
        res.writeHead(404);
        res.end("Not found");
        return;
      }

      const code = reqUrl.searchParams.get("code");
      const error = reqUrl.searchParams.get("error");

      if (error) {
        res.writeHead(400, { "Content-Type": "text/html" });
        res.end(
          `<h1>Authorization failed</h1><p>${error}</p><p>You can close this tab.</p>`
        );
        server.close();
        reject(new Error(`Google OAuth error: ${error}`));
        return;
      }

      res.writeHead(200, { "Content-Type": "text/html" });
      res.end(
        "<h1>Authorization successful!</h1>" +
          "<p>You can close this tab and return to your terminal.</p>"
      );
      server.close();
      resolve(code);
    });

    server.on("error", (err) => {
      if (err.code === "EADDRINUSE") {
        reject(
          new Error(
            `Port ${PORT} is already in use. Stop whatever is running on it and retry.`
          )
        );
      } else {
        reject(err);
      }
    });

    server.listen(PORT, "127.0.0.1");
  });
}

function exchangeCode(code, credentials) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({
      code,
      client_id: credentials.clientId,
      client_secret: credentials.clientSecret,
      redirect_uri: REDIRECT_URI,
      grant_type: "authorization_code",
    }).toString();

    const options = {
      hostname: "oauth2.googleapis.com",
      path: "/token",
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": Buffer.byteLength(body),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(
              new Error(
                `Token exchange failed: ${parsed.error} — ${parsed.error_description}`
              )
            );
          } else {
            resolve(parsed);
          }
        } catch (_) {
          reject(new Error(`Could not parse token response: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function main() {
  const secretPath = process.argv[2];
  if (!secretPath) {
    process.stderr.write(
      "Usage: node scripts/mint-google-refresh-token.js <path-to-client_secret_*.json>\n"
    );
    process.exit(1);
  }

  let credentials;
  try {
    credentials = loadCredentials(path.resolve(secretPath));
  } catch (err) {
    process.stderr.write(`Error reading client_secret JSON: ${err.message}\n`);
    process.exit(1);
  }

  const authUrl = buildAuthUrl(credentials.clientId);

  process.stdout.write("\n=== Google OAuth2 Refresh Token Minter ===\n\n");
  process.stdout.write(
    "Before you open the URL below, make sure http://127.0.0.1:8080/callback\n" +
      "is listed under Authorised redirect URIs in your Google Cloud Console client.\n\n"
  );
  process.stdout.write(
    "Open this URL in your browser (sign in as the TAP service Google account):\n\n"
  );
  process.stdout.write(`  ${authUrl}\n\n`);
  process.stdout.write(
    `Waiting for Google to redirect to 127.0.0.1:${PORT}/callback...\n\n`
  );

  let code;
  try {
    code = await waitForCallback();
  } catch (err) {
    process.stderr.write(`OAuth callback error: ${err.message}\n`);
    process.exit(1);
  }

  process.stdout.write("Exchanging authorization code for tokens...\n\n");

  let tokens;
  try {
    tokens = await exchangeCode(code, credentials);
  } catch (err) {
    process.stderr.write(`Token exchange error: ${err.message}\n`);
    process.exit(1);
  }

  if (!tokens.refresh_token) {
    process.stderr.write(
      "No refresh_token in response.\n" +
        "This happens when the account has already granted access and Google won't re-issue.\n" +
        "Fix: revoke the existing access at https://myaccount.google.com/permissions\n" +
        "then re-run this script.\n"
    );
    process.exit(1);
  }

  process.stdout.write("=== SUCCESS — copy these three values into Paperclip ===\n\n");
  process.stdout.write(
    "For each agent in the table in docs/google-mcp.md, go to:\n" +
      "  Paperclip > Agent > Configuration > Environment variables\n" +
      "and add (all sealed):\n\n"
  );
  process.stdout.write(`GOOGLE_CLIENT_ID=${credentials.clientId}\n`);
  process.stdout.write(
    "GOOGLE_CLIENT_SECRET=<client_secret field from your JSON>\n"
  );
  process.stdout.write(`GOOGLE_REFRESH_TOKEN=${tokens.refresh_token}\n\n`);
  process.stdout.write(
    "See docs/google-mcp.md for which agents get these vars.\n"
  );
}

main().catch((err) => {
  process.stderr.write(`Unexpected error: ${err.message}\n`);
  process.exit(1);
});
