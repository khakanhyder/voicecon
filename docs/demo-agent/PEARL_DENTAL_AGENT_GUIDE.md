# Pearl Dental demo agent: build guide

This guide rebuilds **Ava, the Pearl Dental receptionist**, from an empty Voicecon account. Ava answers the phone for a dental clinic. She answers questions from a knowledge base, checks a Google Calendar for free times, books appointments, and logs every booking to a Google Sheet.

Build it in the order below. Each step depends on the ones before it. Plan about 40 minutes live, or 25 if you paste the prompt and descriptions from the files in this folder.

**Files in this folder**

| File | Use it for |
|---|---|
| `pearl-dental-clinic-guide.md` | The document you upload to the knowledge base (Step 3) |
| `ava-system-prompt.txt` | Ava's system prompt, to paste in Step 8 |
| `workflow-check-available-times.json` | Workflow 1 as an export file: import it instead of building Step 4 |
| `workflow-book-appointment.json` | Workflow 2 as an export file: import it instead of building Step 5 |

---

## 1. What you are building

```
Caller ──voice──▶ Ava (agent)
                   │  decides which tool to call
      ┌────────────┼──────────────────────────┐
      ▼            ▼                          ▼
 Search Clinic   Check Available Times      Book Appointment
 Guide (tool)    (tool → workflow 1)        (tool → workflow 2)
      │            │                          │
      ▼            ▼                          ▼
 Knowledge base  Open-Meteo (today's date)   Calendar: is the slot still free?
 "Clinic Guide"  Google Calendar: free slots Branch: emergency or routine
                                             Google Calendar: create event
                                             Google Sheets: append row
```

| Piece | Name | Type |
|---|---|---|
| Integration | Google Calendar | OAuth connection |
| Integration | Google Sheets | OAuth connection |
| Google Sheet | Pearl Dental — Appointments | a normal Google Sheet |
| Knowledge base | Pearl Dental — Clinic Guide | 1 document |
| Workflow 1 | Pearl Dental — Check Available Times | 5 nodes |
| Workflow 2 | Pearl Dental — Book Appointment | 12 nodes, two branches |
| Tool 1 | Search Clinic Guide | Query Knowledge Base |
| Tool 2 | Check Available Times | Workflow |
| Tool 3 | Book Appointment | Workflow |
| Agent | Ava — Pearl Dental Receptionist | assistant |

**Why tools and not just a prompt:** the language model cannot see your calendar, cannot know today's date, and should not invent prices. Each of those lives behind a tool. The model decides *when* to call a tool, and the tool does the real work.

**Why workflows behind two of the tools:** a workflow can chain several steps (get today's date, read the calendar, reshape the answer) and returns one clean result. The model makes one tool call and gets back exactly what it needs.

---

## 2. Before you start

Check these once, before the meeting.

1. **Plan.** The account needs Workflows and Knowledge Base, which means an active trial or paid plan. A workspace whose subscription has ended can read but not create; the API returns "Your subscription has ended".
2. **Server keys.** Voice needs `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` and `DEEPGRAM_API_KEY` set on the backend. These are platform-wide, not per account.
3. **Google test users.** The Google OAuth app is still in **Testing** mode. Every Google account that will connect Calendar or Sheets must be listed under Google Cloud Console → OAuth consent screen → **Test users**, or Google refuses the connection. Add each developer's Gmail before the meeting.
4. **Google tokens expire after 7 days** while the app is in Testing. If a demo that worked last week fails at the Calendar or Sheets step with `invalid_grant`, reconnect the app on the Integrations page. Publishing the OAuth app to "In production" fixes this for good.
5. **Use one browser tab per account.** Login is stored per browser origin.

---

## 3. Step by step

### Step 1: Connect Google Calendar and Google Sheets

1. Go to **Integrations** and open **Google Calendar** → **Connect**. Sign in with your Google account and allow access.
2. After connecting, the page asks **"Which calendar should bookings use?"** Pick the calendar the clinic's appointments should go into. Your main calendar is fine for a demo.
   - This default matters. Both workflows use it: bookings are created in it, and availability is read from it.
3. Do the same for **Google Sheets** → **Connect**, with the same Google account.

**What this gives you:** two connections. Every workflow step that talks to Google stores the connection it uses. If you ever disconnect and connect again as a *new* connection, reopen both workflows and re-select the connection on each Google step.

### Step 2: Create the Google Sheet

1. In Google Sheets, logged in as the **same Google account** you connected, create a blank spreadsheet named **Pearl Dental — Appointments**.
2. Leave the first tab named **Sheet1**. The workflow writes to `Sheet1!A:I`. If you rename the tab, change the range in workflow 2 to match.
3. Type this header row into row 1, one per column from A to I:

   `Patient name | Phone | Email | Service | Date | Time | Priority | Notes | Calendar link`

4. Copy the spreadsheet ID from the URL. It's the long part between `/d/` and `/edit`:
   `https://docs.google.com/spreadsheets/d/`**`1QCjaEXt2bh5wIlPUy_NOcCXizw9-bBtWKzrUCa0lUGU`**`/edit`

**Why:** the Sheets integration can append rows to an existing sheet, but it cannot create a spreadsheet or a tab. So the sheet and its tab must exist first.

### Step 3: Knowledge base

1. Go to **Knowledge Base** → **New**.
   - Name: `Pearl Dental — Clinic Guide`
   - Description: `Hours, services and prices, emergencies, new patients, payment and cancellation policy for Pearl Dental Care.`
   - Chunk size `800`, overlap `150`. The defaults of 1000/200 also work.
2. Open it and upload **`pearl-dental-clinic-guide.md`** from this folder. Wait until the document shows as completed.
3. Test it with the search box: `How much is a root canal?` should return the *Services and prices* section.

**What it contains:** location and parking, opening hours (Monday to Saturday, 9 to 5, last appointment at 4, no lunch break) and slot times, prices in PKR, what counts as an emergency, new-patient info, payment and insurance, cancellations, visit preparation and the team. It's written as short plain facts, because the agent speaks whatever it finds.

**How the agent uses it:** through Tool 1 (Step 7). The agent searches it whenever a caller asks a factual question, instead of answering from memory.

### Step 4: Workflow 1, "Check Available Times"

**Purpose:** tell Ava today's date, and which one-hour slots are still free on the day the caller wants.

**Why it's needed:** the agent has no clock. Without this, "can I come tomorrow?" has no answer, and it might offer a time that's booked or already over. The workflow works out the free times itself, so Ava only reads them out and never has to reason about the calendar.

Go to **Workflows** → **New**, name it `Pearl Dental — Check Available Times`, and open the **builder**. Build these 5 nodes top to bottom, connecting each one's output to the next one's input.

#### Node 1: Trigger, "Caller asks for a time"

The trigger's **Inputs** become the parameters the agent fills in when it calls the tool.

| Input name | Type | Required | Description (the agent reads this) |
|---|---|---|---|
| `date` | string | **No** | `The day the caller wants, as YYYY-MM-DD. Leave this out completely if the caller has not named a day, and the workflow checks today.` |

Keep `date` optional. The agent's first call has no date, which is how it learns today's date.

#### Node 2: Webhook, "Get today's date in Islamabad"

| Field | Value |
|---|---|
| URL | `https://api.open-meteo.com/v1/forecast?latitude=33.68&longitude=73.05&current=temperature_2m&daily=temperature_2m_max&forecast_days=1&timezone=Asia%2FKarachi` |
| Method | `GET` |
| Retry | on, 2 tries |

**Why a weather API?** Open-Meteo is free, needs no key, and returns the current local date and time for any time zone (`daily.time[0]` is today, `current.time` is now). That gives the workflow a clock. To move the clinic, change `latitude`, `longitude` and `timezone`.

#### Node 3: Set Fields, "Work out which day to check"

| Field name | Value | Transform | Default |
|---|---|---|---|
| `today` | `{{steps.today.body.daily.time[0]}}` | none | |
| `time_now` | `{{steps.today.body.current.time}}` | Format as date, `%H:%M` | |
| `check_date` | `{{trigger.date}}` | none | `{{steps.today.body.daily.time[0]}}` |

**What it does:** `check_date` is the caller's date if the agent passed one, otherwise today. `steps.today` refers to Node 2 by its **node id**. If your builder gave the webhook a different id, use that id instead.

#### Node 4: Integration, "Find free one-hour slots"

| Field | Value |
|---|---|
| Connection | your Google Calendar connection |
| Action | Find Available Slots |
| date | `{{check_date}}` |
| duration_minutes | `60` |
| time_zone | `Asia/Karachi` |
| day_start | `09:00` |
| day_end | `17:00` |
| step_minutes | `60` |
| Calendar | leave empty, so the connection's default calendar from Step 1 is used |
| Retry | on, 2 tries |

**What it does:** it asks Google which parts of the day are busy, then returns every free one-hour slot between 09:00 and 17:00 Islamabad time, on the hour. It leaves out anything that overlaps a booking, and **any slot that has already started**. So late in the afternoon, "today" correctly has nothing left. Each slot comes back as `{start, end, time}`, where `time` is the local `HH:MM`.

- `step_minutes: 60` keeps slots on the hour.
- `day_end: 17:00` means the last slot starts at 16:00.

#### Node 5: Set Fields, "Result for Ava"

The last node's output is what the agent receives, so shape it for the agent.

| Field name | Value | Transform |
|---|---|---|
| `today` | `{{today}}` | none |
| `today_weekday` | `{{today}}` | Format as date, `%A` |
| `time_now_pakistan` | `{{time_now}}` | none |
| `date_checked` | `{{check_date}}` | none |
| `weekday_checked` | `{{check_date}}` | Format as date, `%A` |
| `free_times` | `{{steps.find_slots}}` | Extract field from each, `time` |
| `how_to_use` | `free_times are the one hour slots still free on date_checked, in Pakistan time, already excluding booked and past times. Offer only these. If free_times is empty, or weekday_checked is Sunday (the clinic is closed), check the next day.` | none |

**Why these fields:**
- `free_times` becomes a plain list like `["09:00", "12:00", "14:00"]`, which is easy for the model to read out.
- The weekday fields let the agent say "Saturday" and spot a Sunday.
- `how_to_use` carries the rules together with the data.

**Save**, then **Test run** twice:
- with a future date, e.g. `{"date": "2026-09-19"}`: `date_checked` is that day, and `free_times` lists 09:00 to 16:00 minus anything booked.
- with `{}`: `date_checked` is today, and `free_times` only has times later than now.

All 5 steps should show green.

### Step 5: Workflow 2, "Book Appointment"

**Purpose:** turn a confirmed choice into a real booking: a Google Calendar event and a row in the sheet. Emergencies are labelled differently, and a slot that's already taken is never booked twice.

Create `Pearl Dental — Book Appointment` and build 12 nodes:

```
Trigger → Calendar "Is that slot still free?" → Set Fields (times) → Branch "Still free?"
   ├─ false → Set Fields "Result: slot already taken"          (stops here, nothing written)
   └─ true  → Branch "Is it an emergency?"
                 ├─ true  → Set Fields "Plan: emergency" ─┐
                 └─ false → Set Fields "Plan: routine"  ──┤
                                                  Merge ◀─┘
                    → Google Calendar event → Google Sheets row → Set Fields (result)
```

**Why the "still free?" check:** in testing, a caller who said "yes, that's correct" *after* the booking made the agent book the same slot again. The model only sees the words of earlier turns, not its earlier tool results, so a prompt rule alone didn't stop it. Checking the calendar inside the workflow makes a double booking impossible, whether it comes from the same caller or two callers at once.

#### Node 1: Trigger, "Caller confirms a booking"

| Input | Type | Required | Description |
|---|---|---|---|
| `patient_name` | string | yes | `Patient's full name` |
| `phone` | string | yes | `Patient's mobile number` |
| `service` | string | yes | `What the appointment is for, e.g. Check-up, Teeth cleaning, Root canal, Toothache` |
| `date` | string | yes | `Appointment date as YYYY-MM-DD. Use a date_checked value returned by Check Available Times, never guess it.` |
| `time` | string | yes | `Start time exactly as listed in free_times, 24-hour HH:MM. One o'clock in the afternoon is 13:00.` |
| `is_emergency` | string | no | `yes if the caller has severe pain, swelling, bleeding or a broken or knocked-out tooth, otherwise no` |
| `email` | string | no | `Patient's email for the calendar invite, if they want one` |
| `notes` | string | no | `Anything the dentist should know, e.g. symptoms or new patient` |

Required inputs are enforced before the workflow runs. If the agent calls without, say, `phone`, the tool answers "Ask the caller for: phone" and the agent asks for it. The date description tells the agent to reuse the date from workflow 1, which stops it from inventing dates.

#### Node 2: Integration, "Is that slot still free?" (node id `check_slot`)

Same as Node 4 of workflow 1, but for the requested date:

| Field | Value |
|---|---|
| Connection | your Google Calendar connection |
| Action | Find Available Slots |
| date | `{{trigger.date}}` |
| duration_minutes | `60` |
| time_zone | `Asia/Karachi` |
| day_start / day_end | `09:00` / `17:00` |
| step_minutes | `60` |

#### Node 3: Set Fields, "Work out the appointment times"

| Field name | Value | Transform | Default |
|---|---|---|---|
| `free_now` | `{{steps.check_slot}}` | Extract field from each, `time` | |
| `start_local` | `{{trigger.date}}T{{trigger.time}}:00` | none | |
| `end_local` | `{{trigger.date}}T{{trigger.time}}:00` | Add hours to date `1`, **then** Format as date `%Y-%m-%dT%H:%M:%S` | |
| `spoken_date` | `{{trigger.date}}` | Format as date, `%A %d %B` | |
| `emergency_flag` | `{{trigger.is_emergency}}` | none | `no` |

**Why:**
- `free_now` is the list of times still free, e.g. `["09:00","14:00"]`.
- Google needs a start and an end timestamp, and appointments are one hour. The second transform on `end_local` turns the date back into text Google accepts.
- `spoken_date` gives "Saturday 19 September" for the confirmation.
- `emergency_flag` defaults to `no` when the agent leaves `is_emergency` out.

#### Node 4: Branch, "Still free?"

| Field | Value |
|---|---|
| Variable | `free_now` |
| Operator | contains |
| Value | `{{trigger.time}}` |

#### Node 5: Set Fields, "Result: time not free" (from the **false** output; nothing after it)

| Field | Value |
|---|---|
| `booking_status` | `Not booked - that time is not free` |
| `free_times_that_day` | `{{free_now}}` |
| `say_to_caller` | `That time is not free: it is booked, already past, or outside clinic hours. Offer one of free_times_that_day instead. Only if this caller's booking already succeeded earlier in this call is it confirmed.` |

This is the last node on that path, so it becomes the tool's answer. For a wrong time, Ava gets the real free times to offer. For a repeat of a booking she already made, she says it's already booked rather than booking again.

#### Node 6: Branch, "Is it an emergency?" (from the "Still free?" **true** output)

| Field | Value |
|---|---|
| Variable | `emergency_flag` |
| Operator | equals |
| Value | `yes` (the comparison ignores case) |

#### Node 7: Set Fields, "Plan: emergency" (from the **true** output)

| Field | Value |
|---|---|
| `event_title` | `EMERGENCY - {{trigger.service}} - {{trigger.patient_name}}` |
| `priority` | `Emergency` |
| `caller_note` | `We have marked it as an emergency, so the dentist will see you first when you arrive.` |

#### Node 8: Set Fields, "Plan: routine visit" (from the **false** output)

| Field | Value |
|---|---|
| `event_title` | `{{trigger.service}} - {{trigger.patient_name}}` |
| `priority` | `Routine` |
| `caller_note` | `Please arrive 10 minutes early.` |

Both branches set the **same three field names**. That's the trick that lets everything after the Merge use `{{event_title}}` without caring which branch ran.

#### Node 9: Merge, "Plan ready"

Connect both plan nodes into it. Only one branch runs, and Merge continues once it arrives.

#### Node 10: Integration, "Book the Google Calendar slot" (node id `book_calendar`)

| Field | Value |
|---|---|
| Connection | your Google Calendar connection |
| Action | Book Appointment (`create_event`) |
| title | `{{event_title}}` |
| start_time | `{{start_local}}` |
| end_time | `{{end_local}}` |
| timezone | `Asia/Karachi` |
| attendee_email | `{{trigger.email}}` (if empty, no invite is sent) |
| description | `Patient: {{trigger.patient_name}}` / `Phone: {{trigger.phone}}` / `Service: {{trigger.service}}` / `Priority: {{priority}}` / `Notes: {{trigger.notes}}`, one per line, then a blank line and `Booked by Ava, the Pearl Dental voice agent (Voicecon).` |
| Calendar | leave empty (the connection default) |
| Retry | on, 2 tries |

`timezone` makes Google read `2026-09-19T10:00:00` as 10:00 in Islamabad.

#### Node 11: Integration, "Log the booking in Google Sheets"

| Field | Value |
|---|---|
| Connection | your Google Sheets connection |
| Action | Append Row |
| spreadsheet_id | your ID from Step 2 |
| range_name | `Sheet1!A:I` |
| values | `[["{{trigger.patient_name}}","{{trigger.phone}}","{{trigger.email}}","{{trigger.service}}","{{trigger.date}}","{{trigger.time}}","{{priority}}","{{trigger.notes}}","{{steps.book_calendar.html_link}}"]]` |

`values` is a list of rows, and each row is a list of cells, which is why the brackets are doubled. The last cell links the row to the calendar event created by Node 10.

#### Node 12: Set Fields, "Result for Ava"

| Field | Value |
|---|---|
| `booking_status` | `Booked` |
| `appointment` | `{{spoken_date}} at {{trigger.time}}` |
| `priority` | `{{priority}}` |
| `calendar_event_id` | `{{steps.book_calendar.id}}` |
| `logged_to_sheet` | `yes` |
| `say_to_caller` | `You're booked for {{trigger.service}} on {{spoken_date}} at {{trigger.time}}. {{caller_note}}` |

The system prompt tells Ava to pass on `say_to_caller` in her own words, so the confirmation is always based on what was actually booked.

**Save**, then **Test run** with a free future slot:

```json
{"patient_name": "Test Patient", "phone": "0300 1234567", "service": "Check-up",
 "date": "2026-09-28", "time": "10:00", "is_emergency": "no"}
```

Expect:
- **First run:** every step green except the skipped branches, a new event at 10:00–11:00 in the calendar, and a new row in the sheet.
- **Second run with exactly the same input:** it stops at "Result: slot already taken" and writes nothing.
- **A different time with `"is_emergency": "yes"`:** takes the emergency branch.

### Shortcut: import the workflows instead of building them

Every workflow page and the builder have a **Download JSON** button, and the Workflows page has **Import JSON**. To skip Steps 4 and 5:

1. Do Steps 1 and 2 first. The import needs the Google Calendar and Google Sheets connections to exist.
2. **Workflows → Import JSON**, then choose `workflow-check-available-times.json`. Repeat for `workflow-book-appointment.json`.
3. The import opens the new workflow in the builder. Then:
   - **Connections are re-pointed automatically.** The file records which app each Integration node uses, and the import switches each one to *your* connection for that app. If an app isn't connected yet, the import says so and leaves that node's connection empty; connect the app and pick it in the node.
   - **Change the spreadsheet.** In "Log the booking in Google Sheets", set `spreadsheet_id` to your own sheet's ID. The file still has the demo account's sheet, which your Google account can't write to.
   - **Save**, then use **Test run** as described in Steps 4 and 5.
4. Continue with Step 7.

**What an export file contains:**
- the whole graph: every node, its settings and the connections between nodes
- the trigger, and the app of each connection and the name of each tool used, so the import can match them

It never contains connection credentials or a webhook trigger's secret key.

**Import rules:**
- A name that already exists gets " (imported)" added.
- Manual workflows arrive switched on. Scheduled, webhook and call-event workflows arrive switched **off**, so nothing fires before you've reviewed it.

### Step 6: Workflow settings

On both workflows:
- **Trigger type:** Manual. Tools call them directly, so they need no schedule or webhook.
- **Active:** on. An inactive workflow refuses to run.

### Step 7: Tools

Go to **Tools** → **New** three times. The **description is the most important field**, because it's what the model reads when deciding whether to call the tool. Copy the descriptions exactly.

**Tool 1: Search Clinic Guide.** Assistant Tools → Query Knowledge Base.

| Field | Value |
|---|---|
| Name | `Search Clinic Guide` |
| Knowledge base | Pearl Dental — Clinic Guide |
| Results (top k) | `4` |
| Description | `Search Pearl Dental's clinic guide for services and prices, opening hours, location and parking, payment and insurance, new patient information, emergencies and the cancellation policy. Use it instead of guessing whenever the caller asks about any of these.` |

**Tool 2: Check Available Times.** Workflow Tools → Run Workflow.

| Field | Value |
|---|---|
| Name | `Check Available Times` |
| Workflow | Pearl Dental — Check Available Times |
| Holding line | `Let me check the diary.` (spoken while the workflow runs, to avoid dead air) |
| Description | `Get today's date and the one hour appointment slots still free on a given day. Call it with no date to learn today's date and check today. ALWAYS call this before offering or agreeing any appointment time.` |

**Tool 3: Book Appointment.** Workflow Tools → Run Workflow.

| Field | Value |
|---|---|
| Name | `Book Appointment` |
| Workflow | Pearl Dental — Book Appointment |
| Holding line | `Booking that in for you now.` |
| Description | `Book a one hour appointment. It puts the appointment in the clinic's Google Calendar, marks emergencies, and logs the booking in the clinic's Google Sheet. Only call it once the caller has chosen a free slot and you have their full name, mobile number, what the visit is for, the date and the time.` |

A workflow tool has no parameter form of its own. Its parameters are the workflow trigger's **Inputs** (Steps 4 and 5), and their descriptions are what the model sees for each parameter.

### Step 8: The agent

**Agents** → **New**, then fill in each tab.

**Prompt**

| Field | Value |
|---|---|
| Name | `Ava — Pearl Dental Receptionist` |
| Description | `Answers clinic questions from the knowledge base, checks the Google Calendar, books appointments and logs them to Google Sheets.` |
| First message | `Hello, Pearl Dental Care, this is Ava. How can I help you today?` |
| System prompt | paste all of **`ava-system-prompt.txt`** |

The prompt has five parts, each there for a reason:
1. **Identity:** who Ava is and where the clinic is.
2. **How you speak:** short spoken sentences and no markdown, because every word is read aloud.
3. **"You do not know what day it is":** forces her to get the date from Check Available Times rather than guessing a date from training data.
4. **Your tools:** what each tool is for, and exactly which details Book Appointment needs.
5. **What you remember** and **Taking a phone number:**
   - trust the notes about earlier tool results
   - collect a number said in parts, and repeat the whole number back after each part rather than counting digits (language models miscount)
   - assume a check-up if the caller doesn't say what the visit is for
6. **How a booking goes:** the order of the call. The key step is 5: read the name, day, time and number back, and **wait for "yes" before booking**. That confirmation is what triggers Book Appointment, which stops her booking before the details are right.
7. **Rules:** never invent a detail or use a placeholder such as "Unknown", one tool call at a time, only offering times from `free_times`, booking once (a second "yes" or "thank you" must not book again), emergency handling, "go to hospital" red flags, no medical advice, and honesty when a tool fails.

**LLM Selection:** provider OpenAI, model **`gpt-5.4-mini`**, temperature `0.4`, max tokens `700`.
- Why mini and not nano: in testing, `gpt-5.4-nano` confused "two o'clock" with `14:00` across turns ("two isn't available… we have two o'clock") and sometimes re-booked. `gpt-5.4-mini` got every test call right. It's slightly slower, but still quick enough for voice.
- A low temperature keeps her consistent.
- Some models, for example `gpt-5.5`, only accept temperature 1. The platform now drops a temperature the model rejects, but if you see "I'm having a technical issue", check this first.

**Transcriber:** Deepgram, model `nova-3`, language `en`.

**Voice Selection:** ElevenLabs, voice ID `EXAVITQu4vr4xnSDxMaL` ("Sarah"), speed `1.0`.

**Tools:** add **Search Clinic Guide**, **Check Available Times** and **Book Appointment**.

**Conversation:** interruptions on, silence timeout `3000` ms, max call duration `900` s. Leave **end-call phrases empty**. If a phrase like "have a lovely day" is set, the call hangs up the moment Ava says it, even mid-sentence after "anything else?".

**Knowledge Base tab:** leave it off. The knowledge base is reached through Tool 1, so the agent searches only when it needs to, and the search shows up as a tool call you can point at in the demo.

Save the agent.

### Step 9: Test call

Open the agent and click **Test** to start a live call in the browser, and allow the microphone. Then try:

1. *"How much is a root canal, and do you take insurance?"* She calls **Search Clinic Guide** and answers "from eighteen thousand rupees", and that the clinic gives a receipt to claim from the insurer.
2. *"Can I come in tomorrow for a check-up?"* She calls **Check Available Times** twice: first with no date (to learn today's date), then with tomorrow's date. She offers two or three free times.
3. *"Three o'clock please. It's Ali Raza, zero three zero zero one two three four five six seven."* She reads the name, day, time and number back and asks "Is that right?".
4. *"Yes."* Now she calls **Book Appointment** and confirms. Say *"Yes, that's correct, thanks!"*: she answers "it's already booked for you". If the model does try again, the workflow's "Still free?" check refuses it.
5. Show the audience **Google Calendar** (a new event at 15:00), the **Google Sheet** (a new row), and **Workflows → Book Appointment → history** (every step green).
6. Emergency path: *"I've got terrible toothache and my gum is swollen, can someone see me today?"* She offers the earliest free time (tomorrow morning if today is over), reads back, books it as an emergency, and the calendar title starts with `EMERGENCY`.
7. Red flag: *"My face is swelling up to my eye and it's hard to swallow."* She tells the caller to go to hospital and does not book.

---

## 4. How a tool call actually flows

1. The caller speaks. Deepgram turns the audio into text, which is sent to the agent's reply endpoint with the recent history.
2. The model sees the system prompt plus one function definition per tool. The name and description come from the tool; the parameters come from the workflow trigger's Inputs.
3. The model calls, for example, `book_appointment` with `{patient_name, phone, service, date, time}`.
4. Voicecon checks that the required inputs are present, then runs the workflow **synchronously** with those values as `{{trigger.*}}`. The holding line is spoken meanwhile.
5. The tool result is the **last successful step's output** (the "Result for Ava" node) plus every workflow variable. It goes back to the model.
   - The test-call history keeps only the *words* of earlier turns, not earlier tool results. So on later turns Ava calls Check Available Times again, often twice (once without a date to relearn today's date). That's expected and adds about a second.
6. The model writes a spoken reply. ElevenLabs voices it sentence by sentence while the text streams.

**Templating rules worth knowing**

- `{{trigger.x}}` is a trigger input. `{{steps.<node id>.<path>}}` is a node's output. A bare `{{name}}` is a field published by an earlier Set Fields node.
- A value that is *only* a reference keeps its type (a list stays a list). A reference mixed into text is turned into text.
- A field in a Set Fields node can't use another field from the same node. Put it in the next node, as `today_weekday` does in Node 5 of workflow 1.
- A **Default** applies when the value is *missing*, not when it's an empty string.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Ava says "I'm having a technical issue right now" | The LLM call failed, usually because the model doesn't accept the temperature, or the model name is wrong | Use `gpt-5.4-mini` at 0.4, or `gpt-5.5` at 1.0 |
| Text appears but there's no voice | The browser blocked the audio. Fixed in the frontend's Content-Security-Policy on 2026-09-18 | Hard-refresh. The browser console will show a `media-src` error if it happens again |
| Calendar or Sheets step fails with `invalid_grant` | The Google token expired (7 days in Testing mode) | Reconnect on the Integrations page |
| "Access blocked" when connecting Google | That Google account isn't a test user | Add it under OAuth consent screen → Test users |
| A just-booked slot is still offered | Booking and availability are pointed at different calendars | Leave the Calendar field empty on both Google steps, so both use the connection default |
| Offers times at night or times already past | Find Available Slots is missing its opening hours | Set `time_zone`, `day_start`, `day_end` and `step_minutes` on Node 4 (these options were added on 2026-09-18, so redeploy an older backend) |
| Times are off by hours | Calendar zone differs from the clinic's | Keep `time_zone` / `timezone` = `Asia/Karachi` on both Google steps |
| She books twice | The caller said "yes" after the booking | Workflow 2's "Still free?" branch stops it. Check that Nodes 2 to 5 are in place |
| She mixes up "two" and 14:00, or contradicts herself | A small model losing track over several turns | Use `gpt-5.4-mini` rather than nano |
| Call hangs up mid-sentence | An end-call phrase is set | Clear end-call phrases on the Conversation tab |
| She forgets the name, day or times she offered | Before the 2026-09-18 fix, the test panel sent only the last 10 messages and never the tool results | Update to a build with the fix. It sends 40 messages plus what each tool returned |
| A phone number arrives in pieces, or with digits missing | Before the same fix, speech-to-text sent only the last piece of each turn and cut the turn after 300 ms of silence | Update to a build with the fix. Say the number at a steady pace |
| "Are you still there?" after a few seconds | The check-in reused the 3-second silence timeout | Fixed: the check-in now waits at least 15 seconds |
| She books with name "Unknown" | The model filled a required field with a placeholder | Fixed: placeholders now count as missing, so the tool tells her to ask |
| Sheets step: "Unable to parse range" | The tab isn't named `Sheet1` | Rename the tab, or change `range_name` |
| She guesses a date or says the wrong weekday | She skipped Check Available Times | Keep the "You do not know what day it is" section in the prompt |
| Tool result says `missing_parameters` | A required trigger input wasn't provided | Expected. She asks the caller for it and retries |
| Workflow won't run: "is not active" | Workflow is inactive | Turn Active on |

---

## 6. Reference: the build on the demo account (sajid.techzoid@gmail.com)

| Item | ID |
|---|---|
| Agent | `8cfa30ab-6fca-4735-b556-693d0696b8d5` |
| Knowledge base | `72156ec7-48a2-4688-a6c4-db8643cc04e9` |
| Workflow 1 | `c8f307b2-e7f1-4fd9-b5e7-9e71f04f6481` |
| Workflow 2 | `8136cb01-3a23-424b-84e4-84aa4cdf5f88` |
| Tool: Search Clinic Guide | `96ebc321-4055-431d-9cb4-565dd3e21389` |
| Tool: Check Available Times | `d957893c-97e8-48b6-9023-3f0fd5dfcb2b` |
| Tool: Book Appointment | `38723e59-2631-4544-96b4-a05bf91f33c2` |
| Google Calendar connection | `34ee51ef-00ac-4302-ae9d-ff92c07784b6` |
| Google Sheets connection | `cb721dfb-e695-48b0-af95-1565a4f05173` |
| Spreadsheet | `1QCjaEXt2bh5wIlPUy_NOcCXizw9-bBtWKzrUCa0lUGU` |

These IDs belong to that account. On a new account, every one of them will be different.
