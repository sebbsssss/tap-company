# Settlement Runner (Paperclip skill)
Equips the TAP Paperclip agent to run the monthly owner settlements end-to-end with
every line auto-filled. See SKILL.md for the workflow and triggers.

## Install
Add this skill to the TAP agent (Save skill), or drop the folder into the plugin's
skills directory. Requires the CRM (x-api-key), Xero (Custom Connection), and jarvis
Gmail MCP connectors already configured on the agent.

## Files
- SKILL.md                     — agent instructions / triggers / workflow
- scripts/settlement_inputs.py — email-intake parser + apply-to-settlement (tested)
- requirements.txt
