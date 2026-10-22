How to run this backend:

(note: import the graftpredict.sql file in to database(phpMyAdmin), because this file contains all the database tables.)

0) To change the port number, change the "PORT=5000" number in ".env" file into specific  port number sir.

1) python -m venv venv
(this will create a vertual environment sir.)

2) .\venv\Scripts\Activate
(this command is used to activate the vertual environment sir.)

3) python -m pip install --upgrade pip
(this command is used to update the pip (installer).)

4) pip install -r requirements.txt
(this command is used to install all the dependients (requirements) from the requirements.txt file.)

5) $env:MAIL_USERNAME = "your otp email mail id"
(this command is used to set the email for otp verification sir.)

6) $env:MAIL_PASSWORD = "your password"
(this command is used to set the secret key for accessing the google cloud verification service sir.)

7) python complete_backend.py
(this command is used to run the final backend code. complete_backend.py is my final backend code (main code).)
