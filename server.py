import os
import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import extract, func
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    budgets = db.relationship('Budget', backref='user', lazy=True)
    notifications_enabled = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    expenses = db.relationship('Expense', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.Date, nullable=False, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    shared_with = db.Column(db.String(200), default="") 

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)  
    year = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    alert_threshold = db.Column(db.Float, default=100.0)  

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this feature')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_budget_alerts(user_id, category_id=None):
    today = datetime.datetime.today()
    current_month = today.month
    current_year = today.year
    
    categories = [Category.query.get(category_id)] if category_id else Category.query.all()
    
    for category in categories:
        budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=category.id,
            month=current_month,
            year=current_year
        ).first()
        
        if not budget:
            continue 
        total_expenses = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.category_id == category.id,
            extract('month', Expense.date) == current_month,
            extract('year', Expense.date) == current_year
        ).scalar() or 0
        
        if budget.amount > 0:  
            budget_used_percent = (total_expenses / budget.amount) * 100
            
            if budget_used_percent >= budget.alert_threshold:
                existing_alert = Alert.query.filter_by(
                    user_id=user_id,
                    category_id=category.id,
                    is_read=False
                ).first()
                
                if not existing_alert:
                    if budget_used_percent >= 100:
                        message = f"ALERT: You've exceeded your budget for {category.name}! " \
                                 f"(₹{total_expenses:.2f} / ₹{budget.amount:.2f})"
                    else:
                        message = f"WARNING: You've used {budget_used_percent:.1f}% of your " \
                                 f"{category.name} budget (₹{total_expenses:.2f} / ₹{budget.amount:.2f})"
                    
                    alert = Alert(user_id=user_id, category_id=category.id, message=message)
                    db.session.add(alert)
                    db.session.commit()
                    
                    user = User.query.get(user_id)
                    if user.notifications_enabled:
                        send_email_notification(user.email, message)
                    
                    return alert

def send_email_notification(email, message):
    try:
        sender_email = "expensetracker@example.com"  
        password = "your_password"  
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = "Expense Tracker Alert"
        
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, email, text)
        server.quit()
        
        print(f"Email notification sent to {email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required')
            return redirect(url_for('register'))
            
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return redirect(url_for('register'))
            
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
            
        session['user_id'] = user.id
        flash('Login successful!')
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('login'))

# Routes - Main Application
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    today = datetime.datetime.today()
    current_month = today.month
    current_year = today.year
    
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == current_month,
        extract('year', Expense.date) == current_year
    ).order_by(Expense.date.desc()).all()
    
    category_totals = {}
    categories = Category.query.all()
    
    for category in categories:
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.category_id == category.id,
            extract('month', Expense.date) == current_month,
            extract('year', Expense.date) == current_year
        ).scalar() or 0
        
        budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=category.id,
            month=current_month,
            year=current_year
        ).first()
        
        budget_amount = budget.amount if budget else 0
        
        category_totals[category.id] = {
            'name': category.name,
            'spent': total,
            'budget': budget_amount,
            'percent': (total / budget_amount * 100) if budget_amount > 0 else 0
        }
    
    alerts = Alert.query.filter_by(user_id=user_id, is_read=False).all()
    
    return render_template('dashboard.html', 
                           user=user, 
                           expenses=expenses, 
                           category_totals=category_totals,
                           alerts=alerts,
                           current_month=today.strftime('%B %Y'))

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    user_id = session['user_id']
    
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        description = request.form.get('description', '')
        category_id = int(request.form.get('category_id'))
        date_str = request.form.get('date')
        shared_with = request.form.get('shared_with', '')
        
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.date.today()
        
        expense = Expense(
            amount=amount,
            description=description,
            date=date,
            user_id=user_id,
            category_id=category_id,
            shared_with=shared_with
        )
        
        db.session.add(expense)
        db.session.commit()
        check_budget_alerts(user_id, category_id)
        
        flash('Expense added successfully!')
        return redirect(url_for('expenses'))
    
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
    categories = Category.query.all()
    users = User.query.all()  
    
    return render_template('expenses.html', 
                           expenses=expenses, 
                           categories=categories,
                           users=users)

@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    user_id = session['user_id']
    expense = Expense.query.filter_by(id=expense_id, user_id=user_id).first()
    
    if not expense:
        flash('Expense not found')
        return redirect(url_for('expenses'))
        
    db.session.delete(expense)
    db.session.commit()
    
    flash('Expense deleted successfully')
    return redirect(url_for('expenses'))

@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    user_id = session['user_id']
    
    if request.method == 'POST':
        category_id = int(request.form.get('category_id'))
        amount = float(request.form.get('amount'))
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        alert_threshold = float(request.form.get('alert_threshold', 90))
        
        existing_budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=category_id,
            month=month,
            year=year
        ).first()
        
        if existing_budget:
            existing_budget.amount = amount
            existing_budget.alert_threshold = alert_threshold
            flash('Budget updated successfully!')
        else:
            budget = Budget(
                amount=amount,
                month=month,
                year=year,
                user_id=user_id,
                category_id=category_id,
                alert_threshold=alert_threshold
            )
            db.session.add(budget)
            flash('Budget added successfully!')
            
        db.session.commit()
        check_budget_alerts(user_id, category_id)
        
        return redirect(url_for('budgets'))
    today = datetime.datetime.today()
    current_month = today.month
    current_year = today.year
    
    budgets = Budget.query.filter_by(
        user_id=user_id,
        month=current_month,
        year=current_year
    ).all()
    
    categories = Category.query.all()
    
    return render_template('budgets.html', 
                           budgets=budgets, 
                           categories=categories,
                           current_month=current_month,
                           current_year=current_year)

@app.route('/reports')
@login_required
def reports():
    user_id = session['user_id']
    
    month = int(request.args.get('month', datetime.datetime.today().month))
    year = int(request.args.get('year', datetime.datetime.today().year))

    categories = Category.query.all()
    category_spending = []
    
    for category in categories:
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.category_id == category.id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).scalar() or 0
        
        budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=category.id,
            month=month,
            year=year
        ).first()
        
        budget_amount = budget.amount if budget else 0
        
        category_spending.append({
            'name': category.name,
            'spent': total,
            'budget': budget_amount,
            'remaining': budget_amount - total if budget_amount > 0 else 0,
            'percent': (total / budget_amount * 100) if budget_amount > 0 else 0
        })
    
    # Total monthly spending
    total_spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == month,
        extract('year', Expense.date) == year
    ).scalar() or 0
    

    total_budget = db.session.query(func.sum(Budget.amount)).filter(
        Budget.user_id == user_id,
        Budget.month == month,
        Budget.year == year
    ).scalar() or 0
    

    daily_spending = db.session.query(
        Expense.date, 
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == month,
        extract('year', Expense.date) == year
    ).group_by(Expense.date).all()

    dates = [d[0].strftime('%d') for d in daily_spending]
    amounts = [float(d[1]) for d in daily_spending]

    month_name = datetime.date(year, month, 1).strftime('%B %Y')
    
    return render_template('reports.html',
                           category_spending=category_spending,
                           total_spent=total_spent,
                           total_budget=total_budget,
                           month=month,
                           year=year,
                           month_name=month_name,
                           dates=dates,
                           amounts=amounts)

@app.route('/alerts')
@login_required
def alerts():
    user_id = session['user_id']
    alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).all()
    
    return render_template('alerts.html', alerts=alerts)

@app.route('/alerts/<int:alert_id>/mark_read', methods=['POST'])
@login_required
def mark_alert_read(alert_id):
    user_id = session['user_id']
    alert = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
    
    if alert:
        alert.is_read = True
        db.session.commit()
    
    return redirect(url_for('alerts'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if request.method == 'POST':
        # Update notification settings
        notifications_enabled = 'notifications_enabled' in request.form
        user.notifications_enabled = notifications_enabled
        
        # Update email
        new_email = request.form.get('email')
        if new_email and new_email != user.email:
            existing_email = User.query.filter_by(email=new_email).first()
            if existing_email and existing_email.id != user_id:
                flash('Email already in use by another account')
            else:
                user.email = new_email
                flash('Email updated successfully')
        
        # Update password
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password and new_password and confirm_password:
            if not user.check_password(current_password):
                flash('Current password is incorrect')
            elif new_password != confirm_password:
                flash('New passwords do not match')
            else:
                user.set_password(new_password)
                flash('Password updated successfully')
        
        db.session.commit()
        return redirect(url_for('settings'))
    
    return render_template('settings.html', user=user)

# API Routes for Mobile/SPA support
@app.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def api_expenses():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        
        expense = Expense(
            amount=data['amount'],
            description=data.get('description', ''),
            date=datetime.datetime.strptime(data['date'], '%Y-%m-%d').date() if 'date' in data else datetime.date.today(),
            user_id=user_id,
            category_id=data['category_id'],
            shared_with=data.get('shared_with', '')
        )
        
        db.session.add(expense)
        db.session.commit()
        
        # Check for budget alerts
        check_budget_alerts(user_id, data['category_id'])
        
        return jsonify({'success': True, 'id': expense.id})
    
    # Handle GET request
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
    
    result = []
    for expense in expenses:
        result.append({
            'id': expense.id,
            'amount': expense.amount,
            'description': expense.description,
            'date': expense.date.strftime('%Y-%m-%d'),
            'category_id': expense.category_id,
            'category_name': expense.category.name,
            'shared_with': expense.shared_with
        })
    
    return jsonify(result)

@app.route('/api/budgets', methods=['GET', 'POST'])
@login_required
def api_budgets():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        
        existing_budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=data['category_id'],
            month=data['month'],
            year=data['year']
        ).first()
        
        if existing_budget:
            existing_budget.amount = data['amount']
            existing_budget.alert_threshold = data.get('alert_threshold', 90)
        else:
            budget = Budget(
                amount=data['amount'],
                month=data['month'],
                year=data['year'],
                user_id=user_id,
                category_id=data['category_id'],
                alert_threshold=data.get('alert_threshold', 90)
            )
            db.session.add(budget)
        
        db.session.commit()
        
        # Check for budget alerts
        check_budget_alerts(user_id, data['category_id'])
        
        return jsonify({'success': True})
    
    # Handle GET request
    month = request.args.get('month', datetime.datetime.today().month, type=int)
    year = request.args.get('year', datetime.datetime.today().year, type=int)
    
    budgets = Budget.query.filter_by(user_id=user_id, month=month, year=year).all()
    
    result = []
    for budget in budgets:
        result.append({
            'id': budget.id,
            'amount': budget.amount,
            'month': budget.month,
            'year': budget.year,
            'category_id': budget.category_id,
            'category_name': budget.category.name,
            'alert_threshold': budget.alert_threshold
        })
    
    return jsonify(result)

@app.route('/api/categories', methods=['GET'])
@login_required
def api_categories():
    categories = Category.query.all()
    
    result = []
    for category in categories:
        result.append({
            'id': category.id,
            'name': category.name
        })
    
    return jsonify(result)

@app.route('/api/reports', methods=['GET'])
@login_required
def api_reports():
    user_id = session['user_id']
    month = request.args.get('month', datetime.datetime.today().month, type=int)
    year = request.args.get('year', datetime.datetime.today().year, type=int)
    
    # Category spending
    categories = Category.query.all()
    category_data = []
    
    for category in categories:
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.category_id == category.id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).scalar() or 0
        
        budget = Budget.query.filter_by(
            user_id=user_id,
            category_id=category.id,
            month=month,
            year=year
        ).first()
        
        budget_amount = budget.amount if budget else 0
        
        category_data.append({
            'name': category.name,
            'spent': float(total),
            'budget': float(budget_amount),
            'remaining': float(budget_amount - total) if budget_amount > 0 else 0,
            'percent': float(total / budget_amount * 100) if budget_amount > 0 else 0
        })

    daily_data = []
    daily_spending = db.session.query(
        Expense.date, 
        func.sum(Expense.amount)
    ).filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == month,
        extract('year', Expense.date) == year
    ).group_by(Expense.date).all()
    
    for day in daily_spending:
        daily_data.append({
            'date': day[0].strftime('%Y-%m-%d'),
            'amount': float(day[1])
        })
 
    total_spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        extract('month', Expense.date) == month,
        extract('year', Expense.date) == year
    ).scalar() or 0
    
    total_budget = db.session.query(func.sum(Budget.amount)).filter(
        Budget.user_id == user_id,
        Budget.month == month,
        Budget.year == year
    ).scalar() or 0
    
    return jsonify({
        'category_spending': category_data,
        'daily_spending': daily_data,
        'total_spent': float(total_spent),
        'total_budget': float(total_budget),
        'month': month,
        'year': year
    })

@app.route('/api/alerts', methods=['GET'])
@login_required
def api_alerts():
    user_id = session['user_id']
    
    # Get unread alerts by default
    unread_only = request.args.get('unread_only', 'true') == 'true'
    
    if unread_only:
        alerts = Alert.query.filter_by(user_id=user_id, is_read=False).order_by(Alert.created_at.desc()).all()
    else:
        alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).all()
    
    result = []
    for alert in alerts:
        result.append({
            'id': alert.id,
            'message': alert.message,
            'created_at': alert.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': alert.is_read,
            'category_id': alert.category_id,
            'category_name': Category.query.get(alert.category_id).name
        })
    
    return jsonify(result)

@app.route('/api/alerts/<int:alert_id>/mark_read', methods=['POST'])
@login_required
def api_mark_alert_read(alert_id):
    user_id = session['user_id']
    alert = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
    
    if alert:
        alert.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Alert not found'}), 404

@app.before_first_request
def initialize_db():
    db.create_all()

    default_categories = ['Food', 'Transport', 'Entertainment', 'Housing', 'Utilities', 'Healthcare', 'Shopping', 'Education', 'Travel', 'Other']
    
    for category_name in default_categories:
        if not Category.query.filter_by(name=category_name).first():
            category = Category(name=category_name)
            db.session.add(category)
    
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
