import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta  # timedelta যুক্ত করা হয়েছে ডেট রেঞ্জ এর জন্য
import socket

app = Flask(__name__)

# --- কনফিগারেশন ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'skyline_pro_secret_key')

# ডাটাবেস সেটআপ
database_url = os.environ.get('DATABASE_URL', 'sqlite:///mcdry_erp.db')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- ডাটাবেস মডেল ---
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='member', lazy=True, cascade="all, delete-orphan")
    leaves = db.relationship('Leave', backref='member', lazy=True, cascade="all, delete-orphan")

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Leave(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    leave_date = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(200))

with app.app_context():
    db.create_all()

# --- কমন ডাটা ---
def get_common_data():
    return {
        'c_name': 'McDRY DESICCANT LTD',
        'now': datetime.now(),
        'dev': {
            'name': 'Md Saimun Islam Takrim',
            'role': 'Lead Software Engineer',
            'photo': 'https://i.postimg.cc/4xZpdWGg/Gemini-Generated-Image-rxji00rxji00rxji.png',
            'logo': 'https://i.postimg.cc/C1njRh0B/IMG-6497-(1).png',
            'email': 'saimun.dhk.mcdrybd@gmail.com',
            'whatsapp': '+8801617972438'
        }
    }

# --- রাউটস ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == 'acmcdry' and request.form.get('password') == 'mcdry2026@@':
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('অ্যাক্সেস ডিনাইড! সঠিক পাসওয়ার্ড দিন।', 'danger')
    return render_template('main.html', show_login=True, **get_common_data())

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'logged_in' not in session: return redirect(url_for('login'))
    
    if request.method == 'POST' and 'add_member' in request.form:
        m_id = request.form.get('member_id_no')
        name = request.form.get('name')
        bal = float(request.form.get('initial_balance') or 0)
        
        if Member.query.filter_by(member_id_no=m_id).first():
            flash('এই আইডি ইতিমধ্যে ব্যবহৃত হয়েছে!', 'warning')
        else:
            db.session.add(Member(name=name, member_id_no=m_id, balance=bal))
            db.session.commit()
            flash('সফলভাবে মেম্বার যুক্ত হয়েছে', 'success')
        return redirect(url_for('index'))

    members = Member.query.all()
    total_bal = sum(m.balance for m in members)
    return render_template('main.html', members=members, total_m=len(members), total_b=total_bal, **get_common_data())

@app.route('/member/<int:member_id>', methods=['GET', 'POST'])
def view_member(member_id):
    if 'logged_in' not in session: return redirect(url_for('login'))
    member = Member.query.get_or_404(member_id)
    
    if request.method == 'POST':
        # --- Transaction Logic ---
        if 'amount' in request.form:
            amt = float(request.form.get('amount'))
            desc = request.form.get('description') or "General Transaction"
            if request.form.get('type') == 'add':
                member.balance += amt
                db.session.add(Transaction(member_id=member.id, amount=amt, description=desc))
            else:
                member.balance -= amt
                db.session.add(Transaction(member_id=member.id, amount=-amt, description=desc))
        
        # --- [NEW] Date Range Leave Logic (একসাথে অনেক দিনের ছুটি) ---
        if 'leave_start' in request.form and 'leave_end' in request.form:
            try:
                s_str = request.form.get('leave_start')
                e_str = request.form.get('leave_end')
                reason = request.form.get('reason') or "Personal"
                
                s_date = datetime.strptime(s_str, '%Y-%m-%d')
                e_date = datetime.strptime(e_str, '%Y-%m-%d')
                
                # লুপ চালিয়ে মাঝখানের সব দিন অ্যাড করা
                delta = e_date - s_date
                if delta.days >= 0:
                    for i in range(delta.days + 1):
                        day = s_date + timedelta(days=i)
                        day_str = day.strftime('%Y-%m-%d')
                        
                        # ডুপ্লিকেট চেক
                        existing = Leave.query.filter_by(member_id=member.id, leave_date=day_str).first()
                        if not existing:
                            db.session.add(Leave(member_id=member.id, leave_date=day_str, reason=reason))
                    flash(f'{delta.days + 1} দিনের ছুটি রেকর্ড করা হয়েছে!', 'success')
                else:
                    flash('শেষের তারিখ শুরুর তারিখের চেয়ে বড় হতে হবে!', 'danger')
            except Exception as e:
                flash('তারিখ ফরম্যাটে সমস্যা হয়েছে!', 'danger')
            
        db.session.commit()
        return redirect(url_for('view_member', member_id=member.id))

    transactions = Transaction.query.filter_by(member_id=member_id).order_by(Transaction.date.desc()).all()
    # লিভ সাজানো (নতুন তারিখ উপরে)
    leaves = Leave.query.filter_by(member_id=member_id).order_by(Leave.leave_date.desc()).all()
    
    return render_template('main.html', member=member, transactions=transactions, leaves=leaves, **get_common_data())

@app.route('/delete/<int:member_id>')
def delete_member(member_id):
    if 'logged_in' not in session: return redirect(url_for('login'))
    db.session.delete(Member.query.get(member_id))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_transaction/<int:trans_id>')
def delete_transaction(trans_id):
    if 'logged_in' not in session: return redirect(url_for('login'))
    
    trans = Transaction.query.get_or_404(trans_id)
    member = Member.query.get(trans.member_id)
    
    # ব্যালেন্স রিভার্স করা
    member.balance -= trans.amount
    
    db.session.delete(trans)
    db.session.commit()
    
    flash('Transaction deleted & Balance updated!', 'warning')
    return redirect(url_for('view_member', member_id=member.id))

@app.route('/delete_leave/<int:leave_id>')
def delete_leave(leave_id):
    if 'logged_in' not in session: return redirect(url_for('login'))
    
    leave = Leave.query.get_or_404(leave_id)
    member_id = leave.member_id
    
    db.session.delete(leave)
    db.session.commit()
    
    flash('Leave record deleted!', 'warning')
    return redirect(url_for('view_member', member_id=member_id))

if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n >>> Mobile Link: http://{local_ip}:5000 \n")
    app.run(debug=True, host='0.0.0.0', port=5000)