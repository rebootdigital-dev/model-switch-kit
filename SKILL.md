---
name: model-switch
description: Move a live SMS or chat agent to a new AI model safely. Replays real customer messages through a no-send copy of the agent, grades the new model's replies against what the old model sent, checks downstream trigger phrases, fixes the prompt, and builds a go-live version with a fallback and one-step rollback. Use for "switch my agent off GPT-4.1", "test my agent on the new model", "model migration", "will my prompt work on GPT-6", "GPT-4.1 is being shut off", or before changing the model on any agent that talks to customers.
---

# Model switch

Walk the user through [RUNLIST.md](RUNLIST.md), one agent at a time, in order. The steps and their checkboxes are
there. This file covers how to work and what goes wrong.

## Rules

- **Never change, activate or deactivate a live workflow.** Read it, copy it, test the copy. The go-live swap in
  step 10 is the user's to do, after they've seen the results.
- **The sandbox must be unable to send.** Before the first replay, list every node in the copy with its type and
  confirm with the user that none can text, email, write to the CRM, tag, book or write to a real memory thread.
- **Create nothing without a dry run first.** Show the plan, get a yes, then create.
- **Customer messages stay local.** Harvest, run and grading files go in a data folder outside git. Reports for
  anyone else leave customer names out.
- **Say what each run will cost** before a full run: messages times prompt tokens. Smoke test with 3 messages.
- **Report what happened.** Failed runs, misses and anything you didn't rerun go in the summary with the counts.
- **Change one thing at a time.** Model first, on the current prompt, so any change in behavior comes from the
  model. Prompt fixes after, each with a before file, an after file and a diff.

## How to start

1. Map the build before anything else. Ask or read: the platform, what starts the agent, the current model and
   the new one, every place a model is called, what tools the agent has, where memory lives, what happens to the
   reply after the agent writes it, and what reads that reply downstream. Then tell the user which steps of the
   run list apply to their build, which don't, and what you'd add.
2. If it's n8n and starts from a webhook, use [scripts/](scripts/): copy `config.example.json` to `config.json`,
   fill it in with the user, have them set `N8N_API_KEY` in their own shell (never paste a key into chat or a
   file), and run `harvest.py <agent> --limit 5` to prove the node names are right.
3. On any other build (another platform, a chat trigger, a voice agent, an agent with tools), do the same steps
   with what the platform gives you, and write small scripts for that build if it helps. The scripts here are one
   example. Three things have to be true on any build: you have the exact input the agent saw, you have the reply
   the old model sent, and the test copy can't reach a customer or change real data.
   - Agent with tools: stub each tool in the test copy so it returns a saved result and writes nothing. Grade the
     tool calls as well as the text.
   - Multi-turn memory: replay each message with the thread as it stood at that point.
   - No run history: export conversations from the CRM, or log input and reply for a week first.
4. Run step 0's inventory before anything else. Harvest the same day, because old executions get deleted.

## Grading

- Run `judge_prep.py`, then give each slice to a grader subagent with the live prompt and
  [judge-prompt.md](judge-prompt.md). Run the slices in parallel. Use a different model from the one under test.
- Show the user the counts, then every "worse" and "major" as a table: message, old reply, new reply, why.
- Check the graders. Read a few "same" verdicts yourself, and reread any "worse" against the full thread.

## What went wrong on the first switch

These come from one build: an n8n agent with a long prompt, writing replies to GoHighLevel, where workflows look
for phrases in the reply. Use them as a list of things to check. Some won't exist in the user's build, and theirs
will have problems this list doesn't. Find those from the graded results.

- **Old n8n agent node (n8n only).** The v1 conversational agent sends a `stop` parameter. Newer OpenAI models answer
  `400 Unsupported parameter: 'stop'`, so every reply fails. Swapping only the model would have taken the agent
  down. Fix: agent node v2.2 (`build_sandbox.py --agent-v2`), shipped with the model change.
- **Line breaks.** The new model copied line breaks from the prompt into its replies. A trigger phrase that was
  split across two lines in the prompt never matched downstream. Fix: one prompt line saying every reply is a
  single line, each scripted phrase on one line in the prompt, and a cleanup step that turns breaks into spaces.
- **Reworded scripts.** The new model paraphrased lines the prompt wanted word for word, which dropped a phone
  number and broke "contains" triggers. One general "copy exact wording" rule at the top of the prompt did not fix
  it. What worked: finding each script the prompt left loose (prose after "say exactly this", a script with no
  quotes, two rules that conflict) and tightening that one spot.
- **It follows the prompt more literally.** The old model had been covering for gaps: repeating step one, which
  had the phone number, where the prompt called for step two, which didn't. The new model followed the steps and
  the number vanished. When a new reply looks worse, read the prompt before blaming the model.
- **Fixes over-fire.** A tightened rule for plain thank-you texts also caught a customer who was passing on new
  information during an open problem. Rerun every text of the type you touched, not only the ones you meant to fix.
- **Broken automations that predate the switch.** Reading the downstream workflows turned up conditions with
  trailing spaces and a typo that had never matched. Check the automation, not only the reply.
- **Unset model nodes.** Classifier nodes with no model picked run on a default. Set them.
- **Run-to-run variation.** The same message gets different wording each run. Rerun before deciding a single
  reply proves anything, and compare trigger counts across runs.

## The go-live build

Follow RUNLIST step 8. The parts that matter:

- a switched-off copy on the same entry point (in n8n, the same webhook path), so the switch is old off, new on
- output check before the CRM write, one retry on the old model, then write nothing, tag and alert
- a no-send sandbox of that exact build, with the fallback and the double failure forced on purpose

## When you're done with an agent

Give the user a one-page summary: what ran, the counts, each remaining "worse", the prompt diff, speed and
tokens per reply, and the rollback step. Remind them to deactivate the sandboxes. Then ask which agent is next.
