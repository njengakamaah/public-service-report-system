# Public Service Report System

A website for reporting community service issues such as broken streetlights, water issues, garbage collection, road damage, and drainage problems.

## Features

- Citizen registration and login with hashed passwords
- Submit reports with category, location, description, and optional image
- Unique reference numbers
- Citizen dashboard showing only that citizen's reports
- Admin dashboard showing all reports and open/resolved counts
- Admin status updates: Pending, In Progress, Resolved
- Status history with optional admin notes
- Authorization checks on report details and uploaded images
- Responsive HTML/CSS interface

## Technology

- Python
- Flask
- SQLite
- HTML and Jinja templates
- CSS
- Pillow for checking uploaded image content

## Setup (Windows PowerShell)

1. Install Python 3.12 or newer.
2. Open a terminal in the project folder.
3. Create and activate a virtual environment:

   Note: Run the commands one at a time

   py -m venv .venv
   .venv\Scripts\Activate.ps1 

   <--if the above activation gives an error run this command: 

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   
   then repeat the activation-->
   
4. Install packages:

   python -m pip install -r requirements.txt

5. Create the database:

   flask --app app init-db

6. Create an administrator account:

   flask --app app create-admin

   Follow the prompts.

7. Start the local development server:

   python app.py

8. Open http://127.0.0.1:5000 in your browser.

## First-use checklist

- Register a citizen account.
- Log in as the citizen and submit a test report.
- Log out.
- Log in using the administrator account created in step 6.
- Open the admin dashboard and change the report status.
- Log out and sign back in as the citizen to verify the new status.


## Limitations / future improvements

Potential improvements include search/filtering, email notifications and exportable reports.
