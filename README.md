# Model switch kit

A tested way to move a live SMS or chat agent off GPT-4.1 (or any model that's being shut off) without
finding out from a customer that something broke.

It comes from one real switch in November 2026: a client's texting agent on n8n and GoHighLevel, moved from GPT-4.1
to gpt-6-sol. About 200 real customer messages were replayed through a copy of the agent that can't send
anything. The new model's replies were graded against what the old model had sent, the prompt got fixed where
the new model read it differently, and the switch itself took seconds, and so would a rollback.

## What's here

| File | Use it when |
|---|---|
| [RUNLIST.md](RUNLIST.md) | You want the steps as a checklist. Works on any stack. |
| [SKILL.md](SKILL.md) | You use Claude Code or Claude with skills. Claude runs the steps with you. |
| [judge-prompt.md](judge-prompt.md) | You're at the grading step. Paste it into any strong model. |
| [scripts/](scripts/) | Your agent runs on n8n and starts from a webhook. Python 3, no installs. |

## Three ways to use it

- **By hand:** follow RUNLIST.md. The scripts are optional.
- **With Claude Code:** clone it into your skills folder, open your project and say
  "help me switch my agent off GPT-4.1".

  ```bash
  git clone https://github.com/rebootdigital-dev/model-switch-kit.git ~/.claude/skills/model-switch
  ```
- **Scripts only (n8n):** copy `scripts/config.example.json` to `scripts/config.json`, fill it in, set
  `N8N_API_KEY` in your shell, and run the scripts in the order RUNLIST.md gives.

## If your build is different

It will be. The method is the same on any build: save real inputs and the old model's replies, replay them
through a copy that can't send, grade, fix, switch with a way back. What changes is how you do each part.

- **Not on n8n, or no webhook trigger:** use the run list and the grader prompt. Skip the scripts, or hand
  them to Claude as an example and have it write the same thing for your platform.
- **Agent has tools** (calendar, CRM lookup, booking): the sandbox has to stub them, and you grade the tool
  calls too. `build_sandbox.py` stops on tool nodes and asks you what to do with each.
- **Nothing reads the reply downstream:** skip step 6.
- **Voice, email or web chat:** same steps. Drop the texting-only checks (length, line breaks).
- The "what went wrong" list in SKILL.md is from one build. Treat it as things to check. Your own results
  will show you what your build's problems are.

## Before you start

- The replay files hold real customer messages. Keep the data folder out of git and out of shared drives.
- Every sandbox run is a real model call on your OpenAI account. 200 messages on a 25k-token prompt is about
  5 million input tokens per full run. Smoke test with 3 first.
- Nothing here touches a live workflow. `harvest.py` only reads. `build_sandbox.py` creates a new, inactive
  workflow and only with `--go`. The go-live swap in step 10 is yours to do by hand.
- Tested: harvest against a live n8n instance, the sandbox build as a dry run on a real workflow export, and
  replay, grading prep and trigger check against a local stand-in. Not tested on your n8n version, so read the
  dry run before you add `--go`.

## License

MIT. Use it, change it, share it. No warranty: read the dry run before you create anything.
