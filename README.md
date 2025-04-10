# 💸 Expense Tracker Web App

A full-featured web application built with Flask that helps users track their expenses, set budgets, receive alerts when budgets are exceeded, and visualize spending patterns over time.

---

## 🚀 Features

- 🔐 User Authentication (Register, Login, Logout)
- 💰 Expense Logging and Management
- 📊 Monthly Budget Setup per Category
- 🚨 Alerts when expenses exceed budget thresholds (with email notifications)
- 📈 Reports with budget vs actual spending
- ⚙️ User Settings and Preferences
- 📱 API Support for Mobile or SPA Integration

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLite/PostgreSQL (via SQLAlchemy ORM)
- **Frontend**: Jinja2 templates (HTML/CSS)
- **Email Service**: SMTP (Gmail)
- **APIs**: RESTful API routes for expenses, budgets, alerts, and reports

---

## 📦 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/expense-tracker-flask.git
cd expense-tracker-flask
```

### 2. Create Virtual Environment and Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SQLALCHEMY_DATABASE_URI=sqlite:///tracker.db
SECRET_KEY=your_secret_key
EMAIL_USER=your_gmail_address
EMAIL_PASS=your_gmail_app_password
```

> **Note**: For Gmail, enable **App Passwords** and use that instead of your main password.

### 4. Run the Application

```bash
flask run
```

The app will be available at [http://localhost:5000](http://localhost:5000)

---

## 🧪 API Endpoints

These routes can be used for mobile/SPA clients.

### 🔹 Expenses

- `GET /api/expenses` – Get user expenses
- `POST /api/expenses` – Add new expense

### 🔹 Budgets

- `GET /api/budgets?month=MM&year=YYYY`
- `POST /api/budgets`

### 🔹 Alerts

- `GET /api/alerts?unread_only=true`
- `POST /api/alerts/<id>/mark_read`

### 🔹 Reports

- `GET /api/reports?month=MM&year=YYYY`

---

## 📁 Folder Structure (Important Files)

```
├── server.py              # Main Flask app
├── templates/             # Jinja2 HTML templates
├── static/                # Static files (CSS/JS)
├── .env                   # Environment variables (not committed)
├── requirements.txt       # Python dependencies
```

---

## 📧 Email Alerts

Budget alerts are emailed when:

- Spending exceeds **configured alert thresholds**
- User has notifications enabled

> Uses Gmail SMTP. Make sure to enable "less secure app access" or use App Passwords.

---

## 🧙 Admin Hints

- Default categories auto-populate on first launch
- Email and password changes are supported via settings

---

## 🔒 Security Notes

- Passwords are hashed using Werkzeug
- Session is secured with `SECRET_KEY`
- Sensitive credentials should always be kept in `.env`

---

## 📜 License

MIT License — feel free to use, modify, and distribute.
