# Run list: switching a live agent to a new model

One agent at a time. Finish, watch it for a few days, then do the next one. Start with the one that has the most
traffic to learn from, and leave yourself time: the first one took three days of testing, the rest go faster.

Every build is different. The steps hold on any platform. The commands are for n8n agents that start from a
webhook, and lines marked **(n8n)** or **(if it applies)** only matter when your build has that part. Skip what
you don't have.

## 0. Take inventory

- [ ] Check the shutoff date on OpenAI's own deprecations page. Set your own deadline a few weeks earlier so the old
      model is still there if you need to roll back.
- [ ] List every workflow that calls the old model. For each: the agent node and its version, every model node,
      prompt size, and how many runs your platform still keeps.
- [ ] Look for model nodes with **no model picked** (classifiers and filters are the usual ones). They run on a
      default that may be on the same shutoff list. Set each one explicitly.
- [ ] Pick the new model. One candidate is enough if you already trust it elsewhere.

## 1. Save real messages now

Most platforms delete old runs (n8n often after 2 to 3 weeks). Every day you wait is test data lost. If yours
keeps no run history, export conversations from your CRM or start logging input and reply today.

- [ ] For each run, save what the agent saw (the full webhook body) and what the old model replied. The old reply
      is your free baseline. `python3 harvest.py`
- [ ] Run it again every week until the switch, so low-traffic agents build up enough.

## 2. Build a copy that can't send

- [ ] Duplicate the live workflow. Remove every node that sends, writes to the CRM, tags, books or calls out. That
      includes HTTP Request nodes, tools attached to the agent, and memory nodes that write to a real thread.
      `python3 build_sandbox.py myagent` prints the plan and stops on any node it isn't sure about.
- [ ] Same prompt, same inputs, same node layout. The only thing that changes is the model.
- [ ] Smoke test: 3 real messages on the new model. `python3 replay.py myagent-test --models NEW --last 3`
- [ ] **(n8n)** If every run fails with `Unsupported parameter: 'stop'`: your agent node is the old v1 conversational
      agent, which newer OpenAI models reject. Rebuild the sandbox with `--agent-v2`. That node upgrade then ships
      with the model change.

## 3. Build the test set

- [ ] About 200 real messages. Cap repeats of the same text at 2.
- [ ] Count them by type (access, hours, billing, complaints, thanks, and so on) and note what's thin.
- [ ] Write about 12 edge cases for what real traffic didn't cover: STOP, wrong number, "is this a bot", another
      language, a refund demand, an emergency, a reaction or tapback, a bare "thanks", and whatever your agent must
      never get wrong (codes, prices, medical or legal lines).

## 4. Run it

- [ ] Full run on the new model. `python3 replay.py myagent-test --models NEW --set testset.json`
- [ ] Write down: failed runs, median and slowest response time, tokens per reply.

## 5. Grade it

- [ ] Mechanical flags first: failed run, empty reply, JSON or code in the text, markdown, line breaks, too long.
      `python3 judge_prep.py <runfile>`
- [ ] Then an AI grader per slice, with the live prompt and [judge-prompt.md](judge-prompt.md): better, same, worse
      or major, against the prompt and against the old reply.
- [ ] You read every "worse", every "major" and every flag. Skip the rest.
- [ ] Pass bar: no failed runs, no made-up facts, no majors.

## 6. Check what the replies set off (if it applies)

Only for builds where something downstream reads the agent's reply. If yours uses tool calls or structured
output in place of phrases, check those the same way: does the new model call the same tool, with the same
fields, on the same messages?

- [ ] Open every automation that looks for a phrase in the reply (GHL workflows with "contains", Zaps, IF nodes).
      List each phrase in `triggers.json`.
- [ ] Compare old and new replies against the list. `python3 trigger_check.py <runfile> triggers.json`
- [ ] Read the automations themselves while you're there. We found three that had never fired: two with trailing
      spaces in the phrase, one with a typo.
- [ ] If your workflow cleans the text before it's written (strips emoji, swaps dashes), check the cleaned text.

## 7. Fix the prompt, then rerun

- [ ] Fix one named problem at a time, in a copy of the prompt. Keep a before file, an after file and a diff.
- [ ] Rerun the texts the fix was for, plus every text of that type, plus a control sample. A fix that works on
      its target often over-fires somewhere else.
- [ ] Don't judge a fix on one run. Replies vary run to run, so rerun before you call something fixed or broken.
- [ ] Repeat steps 5 to 7 until the pass bar holds.

## 8. Build the go-live version

- [ ] A new copy of the agent, switched off, on the same entry point as the live one (in n8n, the same webhook
      path). Going live is then "old off, new on" with nothing to change in the CRM.
- [ ] Add an output check between the agent and the CRM write. Empty reply, JSON or code leak, or failed run:
      retry once on the old model. If that fails too: write nothing, tag the contact, and alert yourself.
- [ ] **(if it applies)** Texting agent: turn line breaks into spaces before the write.
- [ ] Add an error workflow that emails you when a run fails or no reply went out.
- [ ] Make a no-send sandbox of this exact build and rerun the test set. Force the fallback and the double
      failure on purpose to see both paths work.

## 9. Get the ok

- [ ] One page for the client or partner: what you ran, better / same / worse counts, every "worse" side by side,
      what you changed in the prompt, speed, and the rollback plan.

## 10. Switch and watch

- [ ] Back up both workflows. Deactivate the old one, activate the new one. Rename the old one "ROLLBACK (off)".
- [ ] Rollback is the same two clicks in reverse. Keep it available until the old model is shut off.
- [ ] Read every conversation on day 1. Check runs daily for 3 business days.
- [ ] Deactivate the sandboxes. Their webhook URLs can spend your credits.
- [ ] Next agent. Agents built from the same prompt template usually share the same problems, so check for those
      first.
