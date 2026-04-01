
I built a long box spread analyser on excel but I got the idea to vibe code it so that arbitrages can be seen via a website with an API link to my broker directly 

How can you help? I don't know coding

12:29

Assessed broker API integration needs for options strategy tool
Assessed broker API integration needs for options strategy tool
Great idea — taking a working Excel model and turning it into a live, API-connected web app is very doable, and I can build the whole thing for you. Here's how I can help across every layer:

What I can build for you

The web app UI — a clean dashboard showing your box spread scanner, arbitrage signals, profit/loss per spread, and filters (expiry, strikes, min edge, etc.)
The box spread logic — replicating your Excel formulas in code (pricing the synthetic longs/shorts, calculating the theoretical value vs. cost, net edge after fees)
Broker API integration — connecting to your broker's live options chain data and (optionally) order routing for when you spot an arb
Alerts — flag spreads where edge exceeds your threshold, with real-time or polling updates
The one thing I need from you first

Which broker are you using? The integration depends entirely on their API. Some common ones:

Interactive Brokers (IBKR) — very powerful API, widely used for this
Tastytrade — has a clean REST API
Schwab / TD Ameritrade (thinkorswim) — Schwab now runs the old TDA API
Tradier, Alpaca, Webull — others with varying options support
Once I know the broker, I can check their API docs and tell you exactly what's possible (live quotes, Greeks, order placement, etc.).

On the "I don't know coding" part

That's totally fine — you don't need to. I'll write all the code, explain what each part does in plain English, and walk you through the few setup steps (like entering your API key). Think of yourself as the product owner and me as the dev.

What's your broker? And while you're at it — can you share the key logic from your Excel sheet (the formula or the inputs/outputs)? That'll let me replicate it exactly rather than building a generic version.

zerodha, fyers or groww are the brokers I have

12:30

Anticipated broker-specific financial guidance request
Anticipated broker-specific financial guidance request
Good news — two of these are very buildable, one less so. Quick breakdown:

Zerodha (Kite Connect) ✅ Best choice

Excellent, well-documented REST + WebSocket API
Live options chain data, order placement, everything you need
Small cost: ₹2,000/month for API access (worth it for arb scanning)
The go-to for algo trading in India
Fyers API ✅ Strong alternative

Also solid REST + WebSocket API
Free tier available — no monthly API fee
Good options data, slightly less mature ecosystem than Zerodha
Groww ❌ Not viable

No public trading API — purely a retail app, not built for programmatic access
Before I start building, a few quick questions to make sure I build the right thing:

Also — if you can share the core logic from your Excel sheet (even just a screenshot or description of the inputs and the formula), that'll help me replicate your exact model rather than a generic one.

Did you consider the sheet titles Box Spread ?

12:44

Searched for missing file attachment, found none
Searched for missing file attachment, found none
I don't actually see any file attached to our conversation! It looks like you may have forgotten to upload it. 😊

Could you share the Excel sheet? You can drag and drop it directly into the chat. Once I can see your Box Spread sheet, I'll be able to:

Read your exact formula logic (strike selection, synthetic pricing, edge calculation)
Replicate it precisely in the web app
Make sure the arb signals match what you're already used to seeing
Go ahead and upload it and I'll dig right in!


option-chain-ED-NIFTY-30-Jun-2026 (1).xlsx
xlsx

Box Spread Sheet in Here

12:45

Synthesized app completion and outlined next steps
Synthesized app completion and outlined next steps
I've read the whole workbook — all 5 sheets. Your model is excellent and very thorough. Here's what I found:

What your Excel does (I've fully reverse-engineered it):

Strategy: Buy Call(K1) + Buy Put(K2) + Sell Call(K2) + Sell Put(K1) → Box settles at K2−K1 at expiry
Cost model: Brokerage, GST, STT on sell legs, Settlement STT at 0.125% (this is the big one), NSE txn charges, SEBI fees, stamp duty, slippage
Signal logic: ✅ EXECUTE when Net P&L > 0 AND annualized return ≥ 1% AND bid-ask spread < 1% of box value
351 total pairs analyzed, 60 with complete data, 1 true arb found in this snapshot
Now let me build the full live web app that mirrors everything:

Now let me build the full analyzer — with your exact formula logic, all costs including settlement STT, and a live UI matching your Excel:

V

Connecting to visualize...
This is a fully working replica of your Excel model in the browser. Here's what it does, matching your sheet exactly:

Formula logic replicated:

Net Debit = Call Ask(K1) + Put Ask(K2) − Call Bid(K2) − Put Bid(K1)
Entry STT = 0.05% × sell-side premium (Call Bid K2 + Put Bid K1)
Settlement STT = 0.125% × box value (always charged at expiry — this is the killer cost)
Plus NSE txn, SEBI, brokerage, GST, stamp duty, slippage
Execute signal = P&L > 0 + annualized return ≥ 1% + bid-ask spread < 1% of box width
You can interact with it right now:

Edit any assumption (lot size, brokerage, STT rates, DTE) and all rows instantly recalculate
Filter by Execute / Borderline / Loss
Results are sorted by best annualized return
Next step: tell me which broker you want to connect — Zerodha or Fyers — and I'll build the live version that pulls real-time option chain data automatically so you never have to download a CSV again. Click the "Set up" button in the Broker section or just tell me here.

fyers for free api

12:53

Architected free API integration with authentication and real-time dashboard
Architected free API integration with authentication and real-time dashboard
Good choice. Fyers v3 has a dedicated Option Chain API and it's completely free. Let me build the full system — a Python backend that handles auth + live data, and the updated dashboard that auto-refreshes.


Created 3 files, ran 2 commands, viewed a file
Created 3 files, ran 2 commands, viewed a file
Download that zip, unzip it, and follow the SETUP_GUIDE.txt inside. Here's the full picture of what you're getting:

3 files inside the zip:

app.py — the whole application in one file. It handles Fyers OAuth login, fetches live NIFTY option chain every 30 seconds, runs your exact box spread formula (entry STT + settlement STT + all costs), and serves the dashboard at http://localhost:5000 in your browser.

requirements.txt — just run pip install fyers-apiv3 once.

SETUP_GUIDE.txt — plain English, step by step, no coding assumed.

The 5-minute setup (once only):

Install Python from python.org
Run pip install fyers-apiv3 in Terminal
Go to myapi.fyers.in → Create App → set redirect URI to http://localhost:5000/callback
Run python app.py → browser opens
Enter your App ID + Secret → click Login → done, live data flows
Every day after that: just open Terminal, run python app.py, done. The dashboard auto-refreshes every 30 seconds with live bid/ask from Fyers and recalculates every box spread pair instantly.

Box spread fyers
ZIP 
can we not host this somewhere that i can share to people with also?

16:31

Evaluated hosting platforms and authentication strategies for shareable web deployment
Evaluated hosting platforms and authentication strategies for shareable web deployment
Great idea — but before I build the hosted version, one important question:

This shapes the whole architecture. Here's why it matters:

Option 1 (your Fyers feeds everyone) — simplest. One API connection, everyone sees the same live NIFTY data. You paste your Fyers key into Railway once, share the URL, done. Best for a tool you want friends/colleagues to use without any setup on their end.

Option 2 (each person logs in) — each visitor authenticates with their own Fyers account. More complex to build, but means you're not "sharing" your API access and each person sees data from their own account.

For a box spread scanner (read-only analysis, no order placement), Option 1 is almost always the right call — it's just a data viewer, like a shared dashboard. Go ahead and answer above and I'll build the full deployable version with step-by-step Railway instructions.

Q: Who provides the Fyers data feed when others visit?
A: My Fyers account feeds everyone (they just view)

Q: Should visitors be able to change assumptions (lot size, brokerage etc)?
A: No, locked to my settings

Q: Which hosting platform? (I'll set it all up for you)
A: whichever is easier, i cant code remember

16:33

Deliberated hosting platforms and architected Flask deployment strategy
Deliberated hosting platforms and architected Flask deployment strategy
Railway it is — and honestly it's about 10 clicks, no command line needed. Let me build the full hosted version now.


Created 4 files, ran 2 commands, read a file
Created 4 files, ran 2 commands, read a file
Download that. Inside you'll find 4 files and the full DEPLOY_GUIDE.txt which walks you through every click. Here's the summary of how it works once live:

For you (owner):

Every morning, visit your-url.up.railway.app/admin, enter your password, click "Login with Fyers" — takes 30 seconds. This refreshes the daily Fyers token.
That's literally it. The server runs 24/7 on Railway.
For everyone you share with:

They just visit your URL and see live NIFTY box spread signals
No login, no Fyers account, nothing to install
Auto-refreshes every 30 seconds
The 4 files you upload to GitHub:

File	What it does
app.py	The whole application
requirements.txt	Libraries to install
Procfile	Tells Railway how to start it
DEPLOY_GUIDE.txt	Your step-by-step instructions
Railway free tier gives you $5/month credit — this app uses maybe ₹100/month equivalent of compute. Effectively free.

The only limitation: Fyers tokens expire daily at midnight, so you need that 30-second morning login. There's no way around this — it's Fyers' security requirement for all API users.

Box spread hosted
ZIP 
But How can I continuously improve this if I do this once? 

For example, the current model is only built for June 2026 expiry but since I have API, I will have data for multiple expiries

16:37

Architected sustainable workflow for non-coders to continuously enhance live applications
Architected sustainable workflow for non-coders to continuously enhance live applications
Really good question — and the answer is simple once you understand the workflow. Let me explain it, then immediately prove it by building the multi-expiry feature right now.

Your improvement workflow (forever, 2 minutes each time):

You tell me what you want →  I update app.py  →  You paste it into GitHub  →  Railway auto-deploys  →  Live in 60 seconds
That's it. You never touch code. You just describe the feature in plain English, I hand you an updated file, and GitHub + Railway do the rest. Let me demonstrate right now with multiple expiries:


Ran 2 commands, created a file, read a file
Ran 2 commands, created a file, read a file
That's v2 with multi-expiry support. Here's what changed and how to deploy it:

What's new in v2:

Expiry buttons across the top — click any expiry to instantly switch
Each expiry badge shows how many arb opportunities exist (green number)
DTE auto-calculates correctly per expiry — no more hardcoded 91 days
All expiries fetch in parallel on login
How to deploy this update — literally 3 clicks:

Go to your GitHub repo → click app.py → click the ✏️ pencil (edit) icon
Select all the text, delete it, paste the new app.py contents
Click "Commit changes"
Railway sees the change and auto-deploys in about 60 seconds. That's the entire workflow, forever.

Your improvement roadmap — just ask me for any of these:

Feature	Just say...
BankNifty + Sensex scanner	"Add BankNifty and Sensex"
Sound/browser alert on new arb	"Alert me when a new Execute signal appears"
WhatsApp/Telegram alert	"Send me a WhatsApp when Execute signal found"
Historical log of signals	"Save and show history of arb signals found today"
OI filter (min open interest)	"Filter out pairs where OI is below X"
Mobile-friendly layout	"Make it look better on phone"
Password protect the dashboard	"Add a password so only I can share the link"
Every single one of those is just one conversation with me → paste one file → live in 60 seconds.

Box spread v2
ZIP 
can we continue ? what did we have to do

21:32

Recapped project progress and identified pending deployment steps
Recapped project progress and identified pending deployment steps
Here's exactly where we are and what's left to do:

✅ Built and ready (you have these zips):

box_spread_v2.zip — the latest version with multi-expiry support. This is the one to use.
⏳ Still to do — deploying it live:

GitHub — create a free account at github.com, make a new repo, upload the 3 files from box_spread_v2.zip (app.py, requirements.txt, Procfile)
Railway — create a free account at railway.app, connect it to your GitHub repo, click Deploy
Fyers app — go to myapi.fyers.in, create an app, set the redirect URI to your Railway URL + /callback
Environment variables — paste 5 values into Railway (your Fyers App ID, Secret Key, Admin Password, App URL, Flask Secret)
First login — visit your live URL at /admin, click "Login with Fyers", done
The full step-by-step for all of this is in DEPLOY_GUIDE.txt inside the first box_spread_hosted.zip.

Where are you stuck — or have you started any of these steps yet?

If you've done none of it, the best place to start right now is Step 1 — have you got a GitHub account already?

Screenshot 2026-04-01 at 9.37.37 PM.png
help what to do next

21:37

Assessed repository setup and charted file upload pathway
Assessed repository setup and charted file upload pathway
You've created the repo — perfectly done. Now upload the 3 files. Follow these exact steps:

Step 1 — Click "uploading an existing file" You can see that link on your screen right now (in the blue "Quick setup" box). Click it.

Step 2 — Drag and drop 3 files From the box_spread_v2 folder you downloaded, drag these 3 files onto the GitHub upload page:

app.py
requirements.txt
Procfile
Step 3 — Commit Scroll down, click the green "Commit changes" button. Leave the message as-is.

One thing to fix first — your repo is set to Private. Railway needs to read it, so either:

Click Settings (top of your repo) → scroll down to "Change visibility" → make it Public
OR keep it private and connect Railway with GitHub permissions (slightly more steps). Public is easier for now since there's no sensitive code in the files.

Once you've uploaded the files, send me a screenshot and we'll move straight to Railway.

Screenshot 2026-04-01 at 9.40.22 PM.png
here?

21:40

Deliberated prerequisite file uploads before proceeding with platform integration
Deliberated prerequisite file uploads before proceeding with platform integration
You're ahead of yourself! Two things first:

⚠️ Did you upload the 3 files to GitHub yet? If not, go back and do that first — otherwise Railway will deploy an empty repo and nothing will work. Open a new tab, go to your GitHub repo (github.com/shubham-grover9/boxspreadanalyser), click "uploading an existing file", and drop in the 3 files from box_spread_v2.zip.

Once files are on GitHub, come back here and:

Click "GitHub Repository" (the top option you can see right now)
It will ask you to authorise Railway to access GitHub — click Authorise
You'll see a list of your repos — click boxspreadanalyser
Click Deploy Now
Railway will start building. Send me a screenshot of whatever screen comes up after that and I'll walk you through the next step (adding your environment variables).

Also — I can see your repo is Private. When Railway asks for GitHub access, make sure to grant access to all repositories (not just public ones), otherwise it won't find your repo.

Go upload the files first, then come back and click GitHub Repository. Screenshot me both!

Screenshot 2026-04-01 at 9.41.31 PM.png
21:41

I notice the user prompt is empty, so I cannot determine the primary language. However, based on the thinking block being in English, here is my summary: Orchestrated deployment guidance and next-step navigation
I notice the user prompt is empty, so I cannot determine the primary language. However, based on the thinking block being in English, here is my summary: Orchestrated deployment guidance and next-step navigation
Railway is building your app right now — you can see "Building (00:06)" on screen. Don't touch anything, wait about 60 seconds.

While it builds, let's get your environment variables ready. You'll need to paste these in immediately after the build finishes.

Open a notepad and fill these in now:

FYERS_CLIENT_ID    →  your App ID from myapi.fyers.in  (e.g. ABCD1234-100)
FYERS_SECRET_KEY   →  your Secret Key from Fyers
ADMIN_PASSWORD     →  make up any password (e.g. nifty2026)
APP_URL            →  leave blank for now (we'll get this from Railway)
FLASK_SECRET       →  type any random letters (e.g. xk92mPlqw8nZ3vBt)
LOT_SIZE           →  75
DTE                →  91
Once the build finishes (spinning icon stops), do this:

Click on the "web" card in the middle of your screen
Look for a "Variables" tab and click it
Add each variable above one by one
Then send me a screenshot — I'll also help you get your Railway URL (which you need for APP_URL and for your Fyers redirect URI).

You're very close now — literally 5 minutes away from a live shareable link! 🎯

Screenshot 2026-04-01 at 9.48.23 PM.png
21:48

I cannot provide a summary because the user prompt is empty. Please provide the user's actual question or request
I cannot provide a summary because the user prompt is empty. Please provide the user's actual question or request
You're on the right page! But stop before filling this in — you need your Railway URL first to put in the Redirect URL field. Without the correct URL here, the login will fail.

First — go get your Railway URL:

Switch to your Railway tab (it's open in your browser — "beneficial-victory")
Click on the "web" card
Click "Settings" tab
Under "Domains" → click "Generate Domain"
Copy the full URL (looks like web-production-08478.up.railway.app)
Then come back here and fill in:

Field	What to type
App name	Box Spread Analyser
Redirect URL	https://YOUR-RAILWAY-URL/callback
Description	anything
Permissions	leave as-is
⚠️ Also notice the yellow warning on your Fyers page — SEBI new algo trading regulations took effect today (April 1, 2026) with changes to App ID flow. Once you create the app, double-check the App ID format looks like XXXX-100 before pasting it into Railway.

Get the Railway URL first, then fill this form. Screenshot me both!

Screenshot 2026-04-01 at 9.52.26 PM.png
?

21:52

Orchestrated next steps for app configuration and deployment
Orchestrated next steps for app configuration and deployment
Your Railway URL is right there — I can see it:

web-production-08478.up.railway.app
And your app is already Online (green dot)! 🎉

Now do these two things in order:

Step A — Go back to Fyers and fill in the form:

App name: Box Spread Analyser
Redirect URL: https://web-production-08478.up.railway.app/callback
Click Create App → then copy the App ID and Secret Key that appear.

Step B — Come back to Railway and click "Variables" tab (you can see it at the top — Deployments / Variables / Metrics / Settings)

Add these one by one:

Variable	Value
FYERS_CLIENT_ID	Your Fyers App ID
FYERS_SECRET_KEY	Your Fyers Secret Key
ADMIN_PASSWORD	any password you choose
APP_URL	https://web-production-08478.up.railway.app
FLASK_SECRET	any random text e.g. abc123xyz987
LOT_SIZE	75
DTE	91
Do Step A first — switch to the Fyers tab now and create the app. Screenshot me the result!

Screenshot 2026-04-01 at 9.54.30 PM.png
21:55

The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block alone, here is a summary: Identified optimal method for batch variable configuration
The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block alone, here is a summary: Identified optimal method for batch variable configuration
You're on the Variables tab — perfect. The fastest way is to add all variables at once using Raw Editor.

Click "Raw Editor" (top right, next to "New Variable")

Then paste this entire block in — just fill in your 3 values:

FYERS_CLIENT_ID=PASTE_YOUR_FYERS_APP_ID_HERE
FYERS_SECRET_KEY=PASTE_YOUR_FYERS_SECRET_KEY_HERE
ADMIN_PASSWORD=choose_any_password_you_want
APP_URL=https://web-production-08478.up.railway.app
FLASK_SECRET=niftyboxsecret2026xkz
LOT_SIZE=75
DTE=91
REFRESH_SECONDS=30
Replace the first two lines with your actual Fyers credentials. For ADMIN_PASSWORD just pick anything memorable like nifty2026 — this is what you'll type at /admin every morning.

Do you have your Fyers App ID and Secret Key yet? Looking at your tabs I can see you still have the Fyers API tab open — did the app get created? If yes, copy those credentials in and paste the whole block into Raw Editor, then click Save.

Screenshot me once you've saved and I'll tell you the exact next step — you're literally 2 minutes from a live shareable link!

Screenshot 2026-04-01 at 9.56.27 PM.png
21:56

The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block content, here is a summary: Identified deployment readiness and next action required
The user prompt is empty, so I cannot determine the primary language. However, based on the thinking block content, here is a summary: Identified deployment readiness and next action required
All 8 variables are in! Now hit the "Deploy ⇧+Enter" button (the purple button top left of your screen).

Railway will redeploy with your credentials — takes about 30 seconds.

Once it goes back to "Online", you're live. Then visit:

https://web-production-08478.up.railway.app/admin
Enter your admin password → click "Login with Fyers" → log in with your Fyers account → you'll be redirected back and live data starts flowing.

Click Deploy now and screenshot what happens! 🚀

Screenshot 2026-04-01 at 9.57.28 PM.png
21:57

Awaited system deployment completion before proceeding
Awaited system deployment completion before proceeding
It's building right now — "Online · Building (00:27)". Wait about 30 more seconds until the "Building" text disappears and it just says "Online".

Then immediately go to this URL in a new tab:

https://web-production-08478.up.railway.app/admin
Type your admin password → click "Login with Fyers" → the orange button → log in with your Fyers account → you'll be sent back automatically.

That's the last step. Once you do that, your shareable link is:

https://web-production-08478.up.railway.app
Watch the card — the moment "Building" disappears, go to /admin. Screenshot me what you see there!

Screenshot 2026-04-01 at 9.58.58 PM.png
this is what it looks like

21:59

Diagnosed live app connectivity and pinpointed formatting bugs
Diagnosed live app connectivity and pinpointed formatting bugs
It's LIVE! 🎉 The app is deployed, connected to Fyers, and auto-refreshing every 30s!

But I can see two bugs to fix right now:

Expiry buttons showing timestamps (1776074400) instead of dates (27-Jun-2026) — Fyers is returning Unix timestamps, not formatted dates
0 complete pairs — because the wrong expiry format is being sent back to the API
This is a quick fix. Let me patch it now:


Reconciled timestamp formats for API integration
Reconciled timestamp formats for API integration
Good — they're Unix timestamps. Fyers sends numbers, we need to convert them to dates for display but pass them back as-is to the API. Let me fix the full app.py:


Edited 4 files, ran a command, read a file
Edited 4 files, ran a command, read a file
Download that app.py — now replace it on GitHub in 3 clicks:

Go to your GitHub repo (github.com/shubham-grover9/boxspreadanalyser)
Click on app.py → click the ✏️ pencil icon (top right of the file)
Select all text → delete → paste the new file contents → click "Commit changes"
Railway auto-deploys in ~60 seconds. The expiry buttons will then show 07-Apr-2026, 13-Apr-2026 etc. instead of timestamps, and the option chain will load correctly for each one.

Your shareable link is already working:

https://web-production-08478.up.railway.app
Share that with anyone — they just open it, no login needed!

App
PY 
Screenshot 2026-04-01 at 10.03.41 PM.png
22:03

Diagnosed app crash, traced code changes, prepared comprehensive rewrite
Diagnosed app crash, traced code changes, prepared comprehensive rewrite
The new app.py has a crash on startup — likely from my partial edits leaving some inconsistency. I need to see the exact error.

Click "Go to Railway" → then click on the "web" card → click "Deployments" tab → click the latest deployment → look for red error text.

But actually, let me just give you a completely clean fixed file right now — faster than debugging:


Assessed syntax warning validity and proceeded with solution
Assessed syntax warning validity and proceeded with solution
Good — that's just a JavaScript regex inside a Python string, harmless. The app is clean. Let me copy to outputs:


Ran a command, read a file
Ran a command, read a file
Download that app.py. Now replace it on GitHub:

Go to github.com/shubham-grover9/boxspreadanalyser
Click app.py → click the ✏️ pencil icon
Select all (Cmd+A) → delete → paste the new file
Click "Commit changes"
Railway auto-deploys in ~60 seconds. The expiry buttons will show 07-Apr-2026, 13-Apr-2026 etc. and the pairs will load properly.

The crash was from my partial edits earlier leaving some leftover references to expiry_str — this is a completely fresh rewrite with no such issues. After this deploy, go to /admin and do the Fyers login again since the app restarted.

App
PY 
Screenshot 2026-04-01 at 10.09.37 PM.png
22:10
Deployment successful! 🟢

Now the last step — do the Fyers login to start the live data:

Open a new tab and go to:
https://web-production-08478.up.railway.app/admin
Enter your admin password → click Login
Click the orange "Login with Fyers" button
Fyers page opens → log in with your Fyers credentials → you'll be redirected back automatically
Then visit:

https://web-production-08478.up.railway.app
You should see proper expiry buttons like 07-Apr-2026, 24-Apr-2026 etc. and live pairs loading. Screenshot me what you see! 🚀

Screenshot 2026-04-01 at 10.11.32 PM.png
nothing happening

22:11

Diagnosed authentication failure and pinpointed API connection issue
Diagnosed authentication failure and pinpointed API connection issue
It's stuck on "Connecting" — the Fyers login hasn't completed yet. Can you see the Admin tab open in your browser? Click it and tell me what it shows.

Or go directly to:

https://web-production-08478.up.railway.app/admin
You should see one of these:

A password box → enter your admin password, then click "Login with Fyers"
The admin dashboard → click the orange "Login with Fyers" button
"✓ Fyers login successful" → if so, wait 30 seconds and refresh the main page
Which one do you see? Screenshot it for me.

Screenshot 2026-04-01 at 10.12.08 PM.png
22:12
Everything is working perfectly! 🎉

I can see:

✅ "Fyers login successful! Fetching all expiries now."
✅ Token active today
✅ 18 expiries loaded — 07-Apr-2026, 13-Apr-2026, 21-Apr-2026, 28-Apr-2026...
Now click "← Dashboard" and wait about 30 seconds for all 18 expiries to finish loading. You should see the expiry buttons appear across the top with live pairs.

Your shareable link is:

https://web-production-08478.up.railway.app
Send anyone that link — they just open it, no login needed, live NIFTY box spread analysis across all 18 expiries. 🚀

Its not loading anything :(

22:12

Diagnosed potential timing issue with data loading delay
Diagnosed potential timing issue with data loading delay
Try a hard refresh first — press Cmd + Shift + R on your Mac while on the dashboard page.

If that doesn't work, the issue is that the page first loaded before data was ready, and the poll interval is 60 seconds so it's waiting. Let me fix it to poll faster until data appears:


Edited 3 files, ran 3 commands, viewed a file
Edited 3 files, ran 3 commands, viewed a file
Two things to do simultaneously:

Right now — try Cmd+Shift+R on the dashboard tab. Since admin confirmed 18 expiries are loaded, a hard refresh might just work immediately.

If that doesn't work — update GitHub with this new app.py the same way as before (pencil icon → select all → paste → commit). This version polls every 5 seconds until data appears instead of waiting 60 seconds.

What does the hard refresh show?

App
PY 
Screenshot 2026-04-01 at 10.13.25 PM.png
cmd shift r still it only says connecting

22:14



Claude is AI and can make mistakes. Please double-check responses.
App · PY
Copy

"""
NIFTY Box Spread Arbitrage Analyzer v2 — Multi-Expiry + Fyers API v3
"""
 
import os, json, time, threading, hashlib, secrets
from datetime import datetime, date
from flask import Flask, render_template_string, request, redirect, jsonify, session, url_for
 
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))
 
FYERS_CLIENT_ID  = os.environ.get("FYERS_CLIENT_ID", "")
FYERS_SECRET_KEY = os.environ.get("FYERS_SECRET_KEY", "")
ADMIN_PASSWORD   = os.environ.get("ADMIN_PASSWORD", "changeme")
APP_URL          = os.environ.get("APP_URL", "http://localhost:5000")
REFRESH_SECONDS  = int(os.environ.get("REFRESH_SECONDS", "60"))
 
PARAMS = {
    "lot_size":       int(os.environ.get("LOT_SIZE", "75")),
    "num_lots":       int(os.environ.get("NUM_LOTS", "1")),
    "broker_per_leg": float(os.environ.get("BROKER_PER_LEG", "20")),
    "stt_entry_pct":  float(os.environ.get("STT_ENTRY_PCT", "0.05")),
    "stt_settl_pct":  float(os.environ.get("STT_SETTL_PCT", "0.125")),
    "txn_pct":        float(os.environ.get("TXN_PCT", "0.03503")),
    "sebi_pct":       float(os.environ.get("SEBI_PCT", "0.0001")),
    "gst_pct":        float(os.environ.get("GST_PCT", "18")),
    "stamp_pct":      float(os.environ.get("STAMP_PCT", "0.003")),
    "slip_per_leg":   float(os.environ.get("SLIP_PER_LEG", "0.5")),
    "rfr":            float(os.environ.get("RFR", "6.5")),
    "min_ann_ret":    float(os.environ.get("MIN_ANN_RET", "1.0")),
    "max_spread_pct": float(os.environ.get("MAX_SPREAD_PCT", "1.0")),
}
 
state = {
    "expiries":     [],   # list of display strings e.g. "07-Apr-2026"
    "raw_map":      {},   # display_str -> raw value from Fyers
    "data":         {},   # display_str -> {results, cmp, dte, ...}
    "access_token": None,
    "token_date":   None,
    "global_error": None,
}
 
TOKEN_FILE = "/tmp/fyers_token.json"
 
# ── TOKEN HELPERS ─────────────────────────────────────────────────────────────
def save_token(token):
    state["access_token"] = token
    state["token_date"]   = str(date.today())
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"token": token, "date": str(date.today())}, f)
    except Exception:
        pass
 
def load_token():
    if state["access_token"] and state["token_date"] == str(date.today()):
        return state["access_token"]
    try:
        with open(TOKEN_FILE) as f:
            d = json.load(f)
        if d.get("date") == str(date.today()):
            state["access_token"] = d["token"]
            state["token_date"]   = d["date"]
            return d["token"]
    except Exception:
        pass
    return None
 
def is_authenticated():
    return bool(load_token())
 
# ── EXPIRY HELPERS ────────────────────────────────────────────────────────────
def expiry_to_display(raw):
    """Convert Fyers expiry value (Unix timestamp int or date string) to display string."""
    try:
        ts = int(raw)
        return datetime.fromtimestamp(ts).strftime("%d-%b-%Y")
    except (ValueError, TypeError):
        pass
    return str(raw)
 
def expiry_to_dte(raw):
    """Days to expiry from a Fyers raw expiry value."""
    try:
        ts = int(raw)
        exp = datetime.fromtimestamp(ts).date()
        return max(1, (exp - date.today()).days)
    except (ValueError, TypeError):
        pass
    try:
        exp = datetime.strptime(str(raw), "%d-%b-%Y").date()
        return max(1, (exp - date.today()).days)
    except Exception:
        pass
    return 30
 
# ── FYERS AUTH ────────────────────────────────────────────────────────────────
def get_auth_url():
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=f"{APP_URL}/callback",
            response_type="code", grant_type="authorization_code",
        )
        return s.generate_authcode()
    except Exception:
        return None
 
def exchange_code(auth_code):
    try:
        from fyers_apiv3 import fyersModel
        s = fyersModel.SessionModel(
            client_id=FYERS_CLIENT_ID, secret_key=FYERS_SECRET_KEY,
            redirect_uri=f"{APP_URL}/callback",
            response_type="code", grant_type="authorization_code",
        )
        s.set_token(auth_code)
        resp = s.generate_token()
        return resp.get("access_token")
    except Exception as e:
        state["global_error"] = str(e)
        return None
 
# ── BOX SPREAD ENGINE ─────────────────────────────────────────────────────────
def calc_pair(r1, r2, dte):
    p    = PARAMS
    ca1  = r1.get("ca")
    pb1  = r1.get("pb")
    cb2  = r2.get("cb")
    pa2  = r2.get("pa")
    if any(v is None for v in [ca1, pb1, cb2, pa2]):
        return None
 
    k1, k2 = r1["k"], r2["k"]
    lots   = p["lot_size"] * p["num_lots"]
    box_w  = k2 - k1
    nd     = (ca1 + pa2 - cb2 - pb1) * lots
    bv     = box_w * lots
    estt   = (p["stt_entry_pct"] / 100) * (cb2 + pb1) * lots
    sstt   = (p["stt_settl_pct"] / 100) * bv
    tp     = (ca1 + pa2 + cb2 + pb1) * lots
    other  = (
        (p["txn_pct"]  / 100) * tp +
        (p["sebi_pct"] / 100) * tp +
        4 * p["broker_per_leg"] * (1 + p["gst_pct"] / 100) +
        (p["stamp_pct"] / 100) * (ca1 + pa2) * lots +
        4 * p["slip_per_leg"] * lots
    )
    net    = bv - nd - estt - sstt - other
    ret    = (net / nd * 100) if nd else 0
    ann    = (ret * 365 / dte) if dte else 0
 
    cb1 = r1.get("cb"); ca2 = r2.get("ca")
    pa1 = r1.get("pa"); pb2 = r2.get("pb")
    sp  = None
    if all(v is not None for v in [ca1, cb1, ca2, cb2, pa1, pb1, pa2, pb2]):
        sp = ((ca1-cb1) + (ca2-cb2) + (pa1-pb1) + (pa2-pb2)) / box_w * 100
 
    if net <= 0:
        sig = "loss"
    elif ann < p["min_ann_ret"]:
        sig = "borderline"
    elif sp is not None and sp < p["max_spread_pct"]:
        sig = "execute"
    else:
        sig = "borderline"
 
    return {
        "k1": k1, "k2": k2, "box_w": box_w,
        "net_debit":   round(nd,    0),
        "box_value":   round(bv,    0),
        "entry_stt":   round(estt,  0),
        "settl_stt":   round(sstt,  0),
        "other_costs": round(other, 0),
        "net_pnl":     round(net,   0),
        "ret_pct":     round(ret,   2),
        "ann_ret":     round(ann,   2),
        "spread_pct":  round(sp,    2) if sp is not None else None,
        "signal":      sig,
    }
 
# ── FETCH ONE EXPIRY ──────────────────────────────────────────────────────────
def fetch_one_expiry(fyers, raw_expiry):
    """Fetch option chain for one expiry (raw value from Fyers) and return analysis."""
    try:
        resp = fyers.optionchain(data={
            "symbol":      "NSE:NIFTY50-INDEX",
            "strikecount": "25",
            "timestamp":   str(raw_expiry),
        })
 
        if resp.get("s") != "ok":
            return {"error": f"API: {resp.get('message', str(resp))}", "results": [], "cmp": None}
 
        opt = resp.get("data", {})
        cmp = opt.get("ltp")
 
        chain = {}
        for row in opt.get("optionChain", []):
            k = row.get("strikePrice")
            if k is None:
                continue
            if k not in chain:
                chain[k] = {"k": k, "cb": None, "ca": None, "pb": None, "pa": None}
            ot = row.get("option_type")
            if ot == "CE":
                chain[k]["cb"] = row.get("bid_price")
                chain[k]["ca"] = row.get("ask_price")
            elif ot == "PE":
                chain[k]["pb"] = row.get("bid_price")
                chain[k]["pa"] = row.get("ask_price")
 
        strikes = sorted(chain.values(), key=lambda x: x["k"])
        dte     = expiry_to_dte(raw_expiry)
        results = []
        for i in range(len(strikes)):
            for j in range(i + 1, len(strikes)):
                r = calc_pair(strikes[i], strikes[j], dte)
                if r:
                    results.append(r)
        results.sort(key=lambda x: x["ann_ret"], reverse=True)
 
        return {
            "results":    results,
            "cmp":        cmp,
            "dte":        dte,
            "last_fetch": datetime.now().strftime("%H:%M:%S"),
            "error":      None,
        }
 
    except Exception as e:
        return {"error": str(e), "results": [], "cmp": None, "last_fetch": None, "dte": None}
 
# ── FETCH ALL EXPIRIES ────────────────────────────────────────────────────────
def fetch_all_expiries():
    token = load_token()
    if not token:
        state["global_error"] = "No access token — admin login required."
        return
    try:
        from fyers_apiv3 import fyersModel
        fyers = fyersModel.FyersModel(client_id=FYERS_CLIENT_ID, token=token, log_path="")
 
        # Get list of all expiries
        resp = fyers.optionchain(data={"symbol": "NSE:NIFTY50-INDEX", "strikecount": "1", "timestamp": ""})
        if resp.get("s") != "ok":
            state["global_error"] = f"Fyers API: {resp.get('message')}"
            return
 
        raw_expiries = [e["expiry"] for e in resp.get("data", {}).get("expiryData", [])]
        if not raw_expiries:
            state["global_error"] = "No expiries returned by Fyers API."
            return
 
        # Build display names and raw mapping
        expiry_displays = []
        raw_map         = {}
        for raw in raw_expiries:
            display = expiry_to_display(raw)
            expiry_displays.append(display)
            raw_map[display] = raw
 
        state["expiries"]     = expiry_displays
        state["raw_map"]      = raw_map
        state["global_error"] = None
 
        # Fetch chain for each expiry
        for display in expiry_displays:
            raw    = raw_map[display]
            result = fetch_one_expiry(fyers, raw)
            state["data"][display] = result
            time.sleep(0.4)
 
    except Exception as e:
        state["global_error"] = str(e)
 
def refresh_loop():
    while True:
        if is_authenticated():
            fetch_all_expiries()
        time.sleep(REFRESH_SECONDS)
 
# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML, refresh_sec=REFRESH_SECONDS)
 
@app.route("/api/expiries")
def api_expiries():
    return jsonify({
        "expiries":      state["expiries"],
        "authenticated": is_authenticated(),
        "global_error":  state["global_error"],
        "refresh_sec":   REFRESH_SECONDS,
    })
 
@app.route("/api/data/<path:expiry>")
def api_data(expiry):
    d   = state["data"].get(expiry, {})
    res = d.get("results", [])
    arb  = sum(1 for r in res if r["signal"] == "execute")
    bord = sum(1 for r in res if r["signal"] == "borderline")
    best = max((r["net_pnl"] for r in res), default=None)
    mxa  = max((r["ann_ret"] for r in res), default=None)
    return jsonify({
        "expiry":    expiry,
        "results":   res,
        "last_fetch": d.get("last_fetch"),
        "error":     d.get("error"),
        "cmp":       d.get("cmp"),
        "dte":       d.get("dte"),
        "params":    PARAMS,
        "scorecard": {
            "total": len(res), "arb": arb, "borderline": bord,
            "loss": len(res) - arb - bord,
            "best_pnl": best, "max_ann": mxa,
        },
    })
 
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hashlib.sha256(pw.encode()).hexdigest() == hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest():
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template_string(ADMIN_HTML, error="Wrong password", logged_in=False, state=state, auth_url=None)
    if not session.get("admin"):
        return render_template_string(ADMIN_HTML, error=None, logged_in=False, state=state, auth_url=None)
    return render_template_string(ADMIN_HTML, error=None, logged_in=True, state=state, auth_url=get_auth_url())
 
@app.route("/callback")
def callback():
    auth_code = request.args.get("auth_code")
    if not auth_code:
        return "<h2>No auth code received.</h2><a href='/admin'>Back</a>"
    token = exchange_code(auth_code)
    if token:
        save_token(token)
        threading.Thread(target=fetch_all_expiries, daemon=True).start()
        return redirect("/admin?success=1")
    return f"<h2>Token exchange failed.</h2><p>{state['global_error']}</p><a href='/admin'>Back</a>"
 
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/admin")
 
# ── DASHBOARD HTML ─────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NIFTY Box Spread — Live</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:#f4f6f9;color:#1a1a1a}
.topbar{background:#0f172a;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.title{font-size:16px;font-weight:700;color:#f8fafc}
.subtitle{font-size:11px;color:#94a3b8;margin-top:2px}
.status{display:flex;align-items:center;gap:8px;font-size:12px;color:#94a3b8}
.dot{width:8px;height:8px;border-radius:50%;background:#475569}
.dot.live{background:#22c55e;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.main{padding:20px 24px;max-width:1400px;margin:0 auto}
.expiry-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;align-items:center}
.expiry-label{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.eb{padding:5px 14px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:12px;color:#475569;font-weight:500;font-family:inherit}
.eb:hover{border-color:#94a3b8}
.eb.active{background:#0f172a;color:#fff;border-color:#0f172a}
.arb-badge{display:inline-block;margin-left:5px;background:#dcfce7;color:#15803d;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700}
.eb.active .arb-badge{background:#22c55e;color:#fff}
.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px}
@media(max-width:800px){.cards{grid-template-columns:repeat(2,1fr)}}
.card{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
.cl{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px}
.cv{font-size:22px;font-weight:700;font-family:'Courier New',monospace}
.cv.g{color:#16a34a}.cv.a{color:#d97706}.cv.r{color:#dc2626}.cv.b{color:#2563eb}
.section{background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:16px;overflow:hidden}
.sechdr{padding:12px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:13px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}
.filters{display:flex;gap:6px;flex-wrap:wrap}
.fb{padding:4px 12px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:12px;color:#64748b;font-family:inherit}
.fb.active{background:#0f172a;color:#fff;border-color:#0f172a}
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#f8fafc;padding:8px 12px;text-align:right;font-size:11px;color:#475569;font-weight:700;border-bottom:2px solid #e2e8f0;white-space:nowrap;text-transform:uppercase;letter-spacing:.4px}
th:first-child,th:nth-child(2){text-align:left}
td{padding:7px 12px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Courier New',monospace;white-space:nowrap}
td:first-child,td:nth-child(2){text-align:left;font-family:inherit;font-weight:600;color:#0f172a}
tr:hover td{background:#f8fafc}
.pill{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;font-family:inherit}
.pill-g{background:#dcfce7;color:#15803d}
.pill-a{background:#fef3c7;color:#92400e}
.pill-r{background:#fee2e2;color:#b91c1c}
.empty{text-align:center;padding:48px;color:#94a3b8;font-size:13px}
.ref{font-size:11px;color:#94a3b8;white-space:nowrap}
</style>
</head>
<body>
<div class="topbar">
  <div>
    <div class="title">NIFTY Box Spread Arbitrage Scanner</div>
    <div class="subtitle" id="subtitle">Loading...</div>
  </div>
  <div class="status"><div class="dot" id="dot"></div><span id="statusTxt">Connecting</span></div>
</div>
<div class="main">
  <div class="expiry-bar" id="expiryBar"><span class="expiry-label">Expiry</span><span style="font-size:12px;color:#94a3b8">Loading expiries...</span></div>
  <div id="scoreCards" class="cards"></div>
  <div class="section">
    <div class="sechdr">
      <span id="tableTitle">Results</span>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <div class="filters" id="filterBtns"></div>
        <span class="ref" id="refreshInfo"></span>
      </div>
    </div>
    <div><div class="tbl-wrap">
      <table>
        <thead><tr>
          <th style="text-align:left">K1</th>
          <th style="text-align:left">K2</th>
          <th>Width</th><th>DTE</th>
          <th>Net Debit</th><th>Box Value</th>
          <th>Entry STT</th><th>Settl. STT</th><th>Other Costs</th>
          <th>Net P&amp;L</th><th>Return%</th><th>Ann.%</th>
          <th>Spread%</th><th>Signal</th>
        </tr></thead>
        <tbody id="tBody"><tr><td colspan="14"><div class="empty">Select an expiry above</div></td></tr></tbody>
      </table>
    </div></div>
  </div>
  <div style="text-align:center;font-size:11px;color:#94a3b8;padding-bottom:24px">
    Live data via Fyers API v3 &nbsp;·&nbsp; NSE European-style cash-settled index options &nbsp;·&nbsp; Not financial advice
  </div>
</div>
<script>
let filter='all', allExpiries=[], activeExpiry=null, cache={};
const fi=(v,d=0)=>v==null?'—':(v<0?'−':'')+'₹'+Math.abs(v).toFixed(d).replace(/\B(?=(\d{3})+(?!\d))/g,',');
const fp=v=>v==null?'—':(v>=0?'+':'')+v.toFixed(2)+'%';
const pills={execute:'pill-g',borderline:'pill-a',loss:'pill-r'};
const plabs={execute:'EXECUTE',borderline:'BORDERLINE',loss:'AVOID'};
 
async function loadExpiries(){
  try{
    const r=await fetch('/api/expiries');
    const d=await r.json();
    allExpiries=d.expiries||[];
    document.getElementById('dot').className=d.global_error?'dot':'dot live';
    document.getElementById('statusTxt').textContent=d.global_error||('Live · refreshes every '+d.refresh_sec+'s');
    document.getElementById('refreshInfo').textContent='Auto-refreshes every '+d.refresh_sec+'s';
    renderExpiryBar();
    if(allExpiries.length&&!activeExpiry){
      activeExpiry=allExpiries[0];
      await loadExpiry(activeExpiry);
    }
  }catch(e){
    document.getElementById('statusTxt').textContent='Connection error';
  }
}
 
async function loadExpiry(exp){
  activeExpiry=exp;
  renderExpiryBar();
  document.getElementById('tBody').innerHTML='<tr><td colspan="14"><div class="empty">Loading '+exp+'...</div></td></tr>';
  try{
    const r=await fetch('/api/data/'+encodeURIComponent(exp));
    const d=await r.json();
    cache[exp]=d;
    document.getElementById('subtitle').textContent=
      exp+' · '+(d.dte||'?')+' days · CMP ₹'+(d.cmp||0).toLocaleString('en-IN')+'  · Lot '+(d.params?.lot_size||75);
    renderResults(d);
    renderExpiryBar();
  }catch(e){
    document.getElementById('tBody').innerHTML='<tr><td colspan="14"><div class="empty">Error loading data</div></td></tr>';
  }
}
 
function renderExpiryBar(){
  const bar=document.getElementById('expiryBar');
  if(!allExpiries.length){
    bar.innerHTML='<span class="expiry-label">Expiry</span><span style="font-size:12px;color:#94a3b8">Waiting for data...</span>';
    return;
  }
  bar.innerHTML='<span class="expiry-label">Expiry</span>'+allExpiries.map(e=>{
    const c=cache[e];
    const n=c?.scorecard?.arb;
    const badge=n>0?'<span class="arb-badge">'+n+'</span>':'';
    return '<button class="eb'+(e===activeExpiry?' active':'')+'" onclick="loadExpiry(\''+e+'\')">'+e+badge+'</button>';
  }).join('');
}
 
function renderResults(d){
  const s=d.scorecard||{};
  document.getElementById('scoreCards').innerHTML=[
    ['Complete pairs',s.total,'b'],
    ['Arbitrage',s.arb,'g'],
    ['Borderline',s.borderline,'a'],
    ['Best P&L/lot',fi(s.best_pnl),'g'],
    ['Max ann. return',fp(s.max_ann),'g'],
  ].map(([l,v,c])=>'<div class="card"><div class="cl">'+l+'</div><div class="cv '+c+'" style="font-size:'+(typeof v==="string"&&v.length>6?'14px':'22px')+'">'+v+'</div></div>').join('');
 
  const res=d.results||[];
  const fc={
    all:res.length,
    execute:res.filter(r=>r.signal==='execute').length,
    borderline:res.filter(r=>r.signal==='borderline').length,
    loss:res.filter(r=>r.signal==='loss').length
  };
  document.getElementById('filterBtns').innerHTML=
    Object.keys(fc).map(k=>'<button class="fb'+(filter===k?' active':'')+'" onclick="setFilter(\''+k+'\')">'+
      k.charAt(0).toUpperCase()+k.slice(1)+' ('+fc[k]+')</button>').join('');
  document.getElementById('tableTitle').textContent=
    activeExpiry+' — '+res.length+' complete pairs · DTE: '+(d.dte||'?');
 
  const f=(filter==='all'?res:res.filter(r=>r.signal===filter))
    .sort((a,b)=>b.ann_ret-a.ann_ret);
 
  if(!f.length){
    document.getElementById('tBody').innerHTML=
      '<tr><td colspan="14"><div class="empty">'+(d.error?'Error: '+d.error:'No complete pairs with all 4 legs priced')+'</div></td></tr>';
    return;
  }
 
  document.getElementById('tBody').innerHTML=f.map(r=>
    '<tr>'+
    '<td>'+r.k1.toLocaleString('en-IN')+'</td>'+
    '<td>'+r.k2.toLocaleString('en-IN')+'</td>'+
    '<td>'+r.box_w.toLocaleString('en-IN')+'</td>'+
    '<td>'+(d.dte||'?')+'</td>'+
    '<td>'+fi(r.net_debit)+'</td>'+
    '<td>'+fi(r.box_value)+'</td>'+
    '<td>'+fi(r.entry_stt)+'</td>'+
    '<td>'+fi(r.settl_stt)+'</td>'+
    '<td>'+fi(r.other_costs)+'</td>'+
    '<td style="color:'+(r.net_pnl>=0?'#16a34a':'#dc2626')+';font-weight:700">'+fi(r.net_pnl)+'</td>'+
    '<td style="color:'+(r.ret_pct>=0?'#16a34a':'#dc2626')+'">'+fp(r.ret_pct)+'</td>'+
    '<td style="color:'+(r.ann_ret>=1?'#16a34a':r.ann_ret>=0?'#d97706':'#dc2626')+';font-weight:700">'+fp(r.ann_ret)+'</td>'+
    '<td>'+(r.spread_pct!=null?r.spread_pct.toFixed(2)+'%':'—')+'</td>'+
    '<td><span class="pill '+pills[r.signal]+'">'+plabs[r.signal]+'</span></td>'+
    '</tr>'
  ).join('');
}
 
function setFilter(f){
  filter=f;
  if(activeExpiry&&cache[activeExpiry]) renderResults(cache[activeExpiry]);
}
 
let _poll=null;
function startPolling(){
  if(_poll) clearInterval(_poll);
  const interval = allExpiries.length ? {{refresh_sec}}*1000 : 5000;
  _poll=setInterval(async()=>{
    const hadData=allExpiries.length>0;
    await loadExpiries();
    if(activeExpiry) loadExpiry(activeExpiry);
    if(!hadData && allExpiries.length>0) startPolling();
  }, interval);
}
loadExpiries().then(startPolling);
</script>
</body></html>"""
 
# ── ADMIN HTML ─────────────────────────────────────────────────────────────────
ADMIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#f1f5f9;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.box{background:#fff;border-radius:12px;padding:36px;width:100%;max-width:480px;box-shadow:0 4px 20px rgba(0,0,0,.1)}
h1{font-size:20px;margin-bottom:6px}
p{font-size:13px;color:#64748b;margin-bottom:20px;line-height:1.5}
label{display:block;font-size:12px;color:#64748b;margin-bottom:4px;font-weight:600}
input[type=password]{width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px;margin-bottom:14px}
.btn{display:block;width:100%;padding:11px;background:#0f172a;color:#fff;border:none;border-radius:7px;font-size:14px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none;margin-bottom:8px}
.btn-fyers{background:#ff6600}.btn-fyers:hover{background:#e55a00}
.err{background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:10px;color:#b91c1c;font-size:13px;margin-bottom:14px}
.ok{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;padding:10px;color:#15803d;font-size:13px;margin-bottom:14px}
.stat{background:#f8fafc;border-radius:8px;padding:14px;font-size:12px;color:#475569;margin-bottom:16px;line-height:2}
.stat b{color:#0f172a}
hr{border:none;border-top:1px solid #e2e8f0;margin:20px 0}
a{color:#2563eb;font-size:13px}
</style></head>
<body><div class="box">
  <h1>Scanner Admin</h1>
  <p>Only for you — share the main URL (<a href="/">/</a>) with everyone else.</p>
  {% if not logged_in %}
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="POST">
      <label>Admin password</label>
      <input type="password" name="password" autofocus>
      <button type="submit" class="btn">Login</button>
    </form>
  {% else %}
    {% if request.args.get('success') %}
    <div class="ok">✓ Fyers login successful! Fetching all expiries now.</div>
    {% endif %}
    <div class="stat">
      <b>Auth:</b> {{ '✓ Token active today' if state.access_token else '✗ No token — login required' }}<br>
      <b>Expiries loaded:</b> {{ state.expiries|length }}
      {% if state.expiries %}({{ ', '.join(state.expiries[:4]) }}{% if state.expiries|length > 4 %}...{% endif %}){% endif %}<br>
      {% if state.global_error %}<b>Error:</b> <span style="color:#dc2626">{{ state.global_error }}</span>{% endif %}
    </div>
    <p style="font-size:12px;color:#64748b;margin-bottom:12px">Fyers tokens expire daily at midnight. Click below each morning before market opens.</p>
    {% if auth_url %}
    <a href="{{ auth_url }}" class="btn btn-fyers">Login with Fyers (refresh token) →</a>
    {% endif %}
    <hr>
    <a href="/">← Dashboard</a> &nbsp;·&nbsp; <a href="/admin/logout">Logout</a>
  {% endif %}
</div></body></html>"""
 
# ── STARTUP ────────────────────────────────────────────────────────────────────
def startup():
    if is_authenticated():
        print("✓ Token found — fetching all expiries")
        threading.Thread(target=fetch_all_expiries, daemon=True).start()
    else:
        print("⚠ No token — visit /admin to login with Fyers")
    threading.Thread(target=refresh_loop, daemon=True).start()
 
startup()
 
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
 

