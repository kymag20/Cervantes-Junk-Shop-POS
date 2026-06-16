# Junkshop POS Deployment

## Local setup

1. Install Python 3.12 or newer.
2. Open a terminal inside this folder.
3. Create and activate a virtual environment.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Copy `.env.example` to `.env`, then fill in your values.
6. Prepare the database:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

7. Start the server:

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Render deployment

This project includes `render.yaml`.

1. Push this folder to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Set these environment variables in Render:

```env
DEBUG=false
ALLOWED_HOSTS=your-render-domain.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-render-domain.onrender.com
GMAIL_ADDRESS=yourgmail@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
```

Render will install dependencies, collect static files, migrate the database, and start Gunicorn.

## PythonAnywhere deployment

PythonAnywhere deploys Django through the Web tab and a WSGI file. Do not use `runserver` online.

### 1. Upload the project

In PythonAnywhere, open a Bash console and upload or clone the project so this folder exists:

```bash
/home/YOUR_USERNAME/junkshop_pos
```

The folder must contain `manage.py`.

### 2. Create a virtual environment

Use a Python version supported by your PythonAnywhere account and compatible with Django 6:

```bash
cd /home/YOUR_USERNAME/junkshop_pos
mkvirtualenv --python=/usr/bin/python3.12 junkshop-pos-env
pip install -r requirements.txt
```

If Python 3.12 is not available on your account, create a newer paid account image or change the Django version to one supported by the available Python version.

### 3. Create `.env`

Create `/home/YOUR_USERNAME/junkshop_pos/.env`:

```env
DEBUG=False
SECRET_KEY=replace-with-a-long-random-secret-key
ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com
GMAIL_ADDRESS=yourgmail@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password
```

For a custom domain, replace the host values with your domain.

### 4. Prepare database and static files

```bash
cd /home/YOUR_USERNAME/junkshop_pos
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### 5. Create the web app

In PythonAnywhere:

1. Open the Web tab.
2. Add a new web app.
3. Choose Manual Configuration.
4. Choose the same Python version used for the virtualenv.
5. Set Virtualenv to:

```text
/home/YOUR_USERNAME/.virtualenvs/junkshop-pos-env
```

6. Set Source code and Working directory to:

```text
/home/YOUR_USERNAME/junkshop_pos
```

### 6. Edit the PythonAnywhere WSGI file

Open the WSGI file linked in the Web tab. Replace its contents with the contents of `pythonanywhere_wsgi.py`, then replace `YOUR_USERNAME` with your PythonAnywhere username.

### 7. Static files mapping

In the Web tab, add this Static files entry:

```text
URL: /static/
Directory: /home/YOUR_USERNAME/junkshop_pos/staticfiles
```

Click Reload.

Your site should open at:

```text
https://YOUR_USERNAME.pythonanywhere.com/
```

## Make it searchable on Google

After the app is deployed online:

1. Buy or connect an easy domain, for example `cervantesjunkshop.com`.
2. Point the domain to the hosting provider.
3. Set these production values:

```env
ALLOWED_HOSTS=cervantesjunkshop.com,www.cervantesjunkshop.com
CSRF_TRUSTED_ORIGINS=https://cervantesjunkshop.com,https://www.cervantesjunkshop.com
```

4. Open `https://cervantesjunkshop.com/sitemap.xml` and confirm it loads.
5. Submit the domain and sitemap to Google Search Console.

Google search results are not instant. It can take days or weeks before the site appears for a new name, especially if the domain is new.

## Gmail verification

Use a Gmail App Password, not your regular Gmail password.

In Google Account:

1. Turn on 2-Step Verification.
2. Create an App Password for Mail.
3. Put that app password in `GMAIL_APP_PASSWORD`.

## Important database note

SQLite is fine for local use and demos. For a real online POS, use a persistent database service so sales data is not lost when the host restarts or redeploys.
