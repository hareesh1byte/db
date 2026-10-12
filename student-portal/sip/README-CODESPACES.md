# Student Information Portal — GitHub Codespaces setup

This project uses Flask + MySQL. **GitHub Pages alone cannot run Flask or MySQL**; run this project in a GitHub Codespace or deploy Flask and MySQL to backend/database hosting.

## 1. Open the project folder

In the Codespaces terminal:

```bash
cd student-portal/sip
```

If your terminal is already in the `sip` folder, skip this command.

## 2. Install and start MySQL (Ubuntu Codespaces)

```bash
sudo apt update
sudo apt install -y mysql-server
sudo service mysql start
sudo service mysql status
```

## 3. Create the database and application user

```bash
sudo mysql
```

Paste the following SQL at the MySQL prompt. Change the sample password to your own:

```sql
CREATE DATABASE IF NOT EXISTS sip CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'webuser'@'localhost' IDENTIFIED BY 'ChangeThisPassword123!';
GRANT ALL PRIVILEGES ON sip.* TO 'webuser'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Import the included tables:

```bash
mysql -u webuser -p sip < schema.sql
```

Enter the password you set above.

## 4. Install Python packages and configure credentials

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=webuser
export DB_PASSWORD='ChangeThisPassword123!'
export DB_NAME=sip
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_PASSWORD='Choose-A-Strong-Password'
```

Keep the terminal session open; these environment variables apply to this terminal. Do not commit passwords or `.env` files to GitHub.

## 5. Start the website

```bash
python app.py
```

In Codespaces, open the **Ports** tab, make port **5000** available, and open its forwarded URL. Check the database using:

`https://YOUR-CODESPACE-URL/api/health`

Expected response:

```json
{"database":"connected","status":"ok"}
```

Sign in with username `admin` and the `ADMIN_PASSWORD` you set before starting the app. If you did not set `ADMIN_PASSWORD`, the development default is `admin123`; change it before using real data.

## Troubleshooting

- `Can't connect ... (111)`: run `sudo service mysql start`, then `sudo ss -ltnp | grep 3306`.
- `Access denied`: make sure `DB_USER` and `DB_PASSWORD` match the MySQL user created above.
- `Unknown database`: import `schema.sql` as shown above.
- If MySQL is hosted elsewhere, set `DB_HOST` to that provider's database hostname, not `localhost`.
- GitHub Pages serves static files only. It cannot host this Flask app; use Codespaces for development and a Python-capable host for deployment.
