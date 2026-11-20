# Judge-ready demo script (follows the FAQ's 5-step demo flow)

Track: AI Companions for Everyday Life. Theme: Real-Time Conversational AI Meets Agentic Workflows.
Before the demo: sign in, press **Load demo context**, make sure Google Calendar and SMTP are configured (Integrations page), wear headphones, rehearse once. Keep a screen recording as a backup (FAQ allows a video demo).

## 0. One-minute pitch
"PACTLINE turns a spoken conversation into agreed commitments and real actions. It remembers, checks your real calendar, never acts without your approval, and follows up by email."

## 1. Initiate (Agora + Murf)
Press Start. Say: "Plan my day." The agent speaks (Murf Falcon) and the live transcript appears.

## 2. Understand / Plan (Before)
The agent calls getDailyBriefing and reports, from stored data: your preference (meetings after 10 AM), the pending commitment, today's tasks and real Google Calendar events. Point at the Outcome panel: same data.

## 3. Execute (Action, with approval)
Say: "Book the bank visit tomorrow at 11 for one hour, and remind me at 9 AM to carry my ID."
- If the slot clashes, the agent says so and asks (conflict detection against the real calendar).
- Otherwise two requests appear in **Approvals**. Press Approve. Nothing changes before that.

## 4. Confirm
The agent calls getApprovalStatus and says what actually happened. Open the event link in the Outcome panel to show it in Google Calendar. Show an error path once: disconnect or break an integration; the agent states the failure instead of claiming success.

## 5. Follow up (After)
Press "Send due reminders now" (or wait): the reminder email arrives and the panel shows `sent`. Ask: "What is still pending?" The agent answers from follow-ups (overdue and unassigned tasks, reminder status).

## Optional: commitment conflict
Say: "Asha will book the venue by Friday." Then: "Ravi thinks it was Thursday." The agent raises the disagreement, refuses to choose, asks which date you agree on, and only then requests approval to update.

## Judging criteria cheat-sheet
Problem-solution fit: everyday coordination with real follow-through. Innovation: commitment tracking, disagreement detection, server-side approvals. Use of Agora and Murf: live voice, transcripts, interruption, tool calling, Falcon voice. Functionality: Calendar event and email delivered for real. Future scope: family members, WhatsApp, Indian languages, payments (sandbox only).

## Honest limits (say them if asked)
Single-user voice room; calendar and email are one connected account; reminders go to the approving user's email; the DevOps/Jenkins module is not part of this demo.
