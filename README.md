## Public Service Report System

A web application for reporting community service issues such as broken streetlights, water issues, garbage collection, road damage, and drainage problems.

## Features

Citizen registration and login with hashed passwords

Submit reports with category, location, description, and optional image

Unique reference numbers for submitted reports

Citizen dashboard showing only that citizen's reports

Admin dashboard showing all reports and open/resolved counts

Admin status updates: Pending, In Progress, Resolved

Status history with optional admin notes

Authorization checks on report details and uploaded images

Responsive HTML/CSS interface

## Technology

Python

Flask

SQLite

HTML and Jinja templates

CSS

Pillow for validating uploaded image content

Gunicorn for deployment

## Local Setup (Windows PowerShell)

Install Python 3.12 or newer.
Open a terminal in the project folder.

Create and activate a virtual environment. Run commands one at a time:

py -m venv .venv
.venv\Scripts\Activate.ps1

If activation is blocked, run:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Then repeat the activation command.

Install the required packages:

python -m pip install -r requirements.txt

Create the database tables:

flask --app app init-db

Create a local administrator account:

flask --app app create-admin

Follow the prompts to enter the administrator's name, email, and password. This command creates an administrator in your local database.

Start the local development server:

python app.py

Open http://127.0.0.1:5000 in your browser.

## Deployment

The application is deployed on Render:

Live website: https://public-service-report-system.onrender.com

## Environment Variables

Configure these variables in the Render service's Environment settings:

SECRET_KEY — a strong, private key used to protect Flask sessions.

ADMIN_SETUP_TOKEN — a separate secret used to authorize initial administrator creation through the setup page.

Do not commit environment secrets, passwords, or database files to GitHub.

## Initial Administrator Setup on Render

Configure ADMIN_SETUP_TOKEN in Render and deploy the application.

Open /setup-admin on the live website.

If the setup form is available, enter the setup token, administrator details, and a strong password.

Log in through /login with the administrator credentials.

Open the admin dashboard to view and manage submitted reports.

The setup route is designed to return a 404 response if the token is not configured or an administrator already exists.

Important: Online administrator setup has not yet been verified. The /setup-admin page previously returned a 404, so confirm the cause before relying on this procedure.

## Database and File Storage

The application currently uses SQLite. On Render, files stored on the instance's local filesystem may not persist across restarts, redeployments, or instance replacement unless persistent storage is configured.

For a more reliable production deployment, consider a managed PostgreSQL database and persistent or external storage for uploaded images.

## First-use Checklist

Register a citizen account.

Log in as the citizen and submit a test report.

Log out.

Log in using the administrator account.

Open the admin dashboard and change the report status.

Log out and sign back in as the citizen to verify the updated status.


## Potential improvements include:

Search and filtering of reports

Email notifications

Exportable reports

Persistent production database storage

More comprehensive automated tests

## Assessor Testing Instructions

**Live Website:** https://public-service-report-system.onrender.com

### 1. Citizen Access
1. Open the live website.
2. Register a citizen account using the Register page.
3. Log in and submit a sample service report.
4. View the submitted report on the citizen dashboard.

### 2. Administrator Access
1. Open the Login page.
2. Log in using the administrator credentials provided separately by the project developer.
3. Open the administrator dashboard to view submitted reports.
4. Update a report's status to Pending, In Progress, or Resolved.
5. Open a report to review its details and status history.

### 3. Verify Access Controls
- Confirm that citizens can view their own reports.
- Confirm that the administrator can view and manage all reports.
- Confirm that users cannot access pages or reports they are not authorized to view.

### Notes
- Administrator login credentials will be provided privately for assessment.
- Do not share passwords or secret setup tokens publicly.
- The deployed demonstration database may reset if the hosting environment or database storage is reset.

