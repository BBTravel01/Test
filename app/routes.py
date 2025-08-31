from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .models import User, Job, Customer
from flask import Blueprint
from datetime import datetime, timedelta

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'worker')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists.', 'warning')
            return redirect(url_for('main.register'))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            role=role
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for('main.login'))

        login_user(user)
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

from functools import wraps

def organizer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'organizer':
            return redirect(url_for('main.login')) # Or show a 403 error
        return f(*args, **kwargs)
    return decorated_function

@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'organizer':
        jobs = Job.query.order_by(Job.id.desc()).all()
        return render_template('dashboard_organizer.html', jobs=jobs)
    else: # worker
        jobs = Job.query.filter_by(worker_id=current_user.id).order_by(Job.id.desc()).all()
        return render_template('dashboard_worker.html', jobs=jobs)

@main.route('/job/<int:job_id>')
@login_required
def job_details(job_id):
    job = Job.query.get_or_404(job_id)
    # Ensure the logged-in user is the one assigned to the job or an organizer
    if current_user.role != 'organizer' and job.worker_id != current_user.id:
        flash('You are not authorized to view this job.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('job_details.html', job=job)

@main.route('/job/<int:job_id>/signin', methods=['POST'])
@login_required
def sign_in(job_id):
    job = Job.query.get_or_404(job_id)
    if job.worker_id != current_user.id:
        flash('Not authorized.')
        return redirect(url_for('main.dashboard'))

    job.status = 'in_progress'
    job.start_time = datetime.utcnow()
    db.session.commit()
    flash('Signed in successfully!')
    return redirect(url_for('main.job_details', job_id=job_id))

@main.route('/job/<int:job_id>/signout', methods=['POST'])
@login_required
def sign_out(job_id):
    job = Job.query.get_or_404(job_id)
    if job.worker_id != current_user.id:
        flash('Not authorized.')
        return redirect(url_for('main.dashboard'))

    job.status = 'completed'
    job.end_time = datetime.utcnow()
    db.session.commit()
    flash('Signed out successfully!')
    return redirect(url_for('main.job_details', job_id=job_id))

@main.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
@organizer_required
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)
    if request.method == 'POST':
        job.customer_id = int(request.form.get('customer_id'))
        job.location = request.form.get('location')
        job.duration = int(request.form.get('duration'))
        job.worker_id = int(request.form.get('worker_id'))

        scheduled_date_str = request.form.get('scheduled_date')
        scheduled_time_str = request.form.get('scheduled_time')

        job.scheduled_date=datetime.strptime(scheduled_date_str, '%Y-%m-%d').date() if scheduled_date_str else None
        job.scheduled_time=datetime.strptime(scheduled_time_str, '%H:%M').time() if scheduled_time_str else None
        job.recurrence_rule = request.form.get('recurrence_rule') if request.form.get('recurrence_rule') else None

        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    workers = User.query.filter_by(role='worker').all()
    customers = Customer.query.all()
    return render_template('edit_job.html', job=job, workers=workers, customers=customers)

@main.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
@organizer_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Job deleted successfully!')
    return redirect(url_for('main.dashboard'))

@main.route('/create_job', methods=['GET', 'POST'])
@login_required
@organizer_required
def create_job():
    if request.method == 'POST':
        customer_id = int(request.form.get('customer_id'))
        location = request.form.get('location')
        duration = int(request.form.get('duration'))
        worker_id = int(request.form.get('worker_id'))

        scheduled_date_str = request.form.get('scheduled_date')
        scheduled_time_str = request.form.get('scheduled_time')
        recurrence_rule = request.form.get('recurrence_rule')

        new_job = Job(
            customer_id=customer_id,
            location=location,
            duration=duration,
            worker_id=worker_id,
            scheduled_date=datetime.strptime(scheduled_date_str, '%Y-%m-%d').date() if scheduled_date_str else None,
            scheduled_time=datetime.strptime(scheduled_time_str, '%H:%M').time() if scheduled_time_str else None,
            recurrence_rule=recurrence_rule if recurrence_rule else None
        )
        db.session.add(new_job)
        db.session.commit()
        flash('Job created successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    workers = User.query.filter_by(role='worker').all()
    customers = Customer.query.all()
    return render_template('create_job.html', workers=workers, customers=customers)

from flask import jsonify

# Customer Management Routes

@main.route('/api/jobs')
@login_required
@organizer_required
def api_jobs():
    jobs = Job.query.filter(Job.scheduled_date.isnot(None)).all()
    job_list = []
    for job in jobs:
        if job.scheduled_date:
            start_datetime = datetime.combine(job.scheduled_date, job.scheduled_time or datetime.min.time())
            end_datetime = start_datetime + timedelta(minutes=job.duration)

            job_list.append({
                'title': f'{job.customer.name} ({job.worker.username})',
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'allDay': job.scheduled_time is None
            })
    return jsonify(job_list)

@main.route('/calendar')
@login_required
@organizer_required
def calendar():
    return render_template('calendar.html')

@main.route('/customers')
@login_required
@organizer_required
def customers():
    all_customers = Customer.query.all()
    return render_template('customers.html', customers=all_customers)

@main.route('/add_customer', methods=['GET', 'POST'])
@login_required
@organizer_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        email = request.form.get('email')
        new_customer = Customer(name=name, address=address, phone=phone, email=email)
        db.session.add(new_customer)
        db.session.commit()
        flash('Customer added successfully!', 'success')
        return redirect(url_for('main.customers'))
    return render_template('add_customer.html')

@main.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
@login_required
@organizer_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.address = request.form.get('address')
        customer.phone = request.form.get('phone')
        customer.email = request.form.get('email')
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('main.customers'))
    return render_template('edit_customer.html', customer=customer)

@main.route('/delete_customer/<int:customer_id>', methods=['POST'])
@login_required
@organizer_required
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('main.customers'))

from dateutil.relativedelta import relativedelta

@main.route('/generate_recurring')
@login_required
@organizer_required
def generate_recurring():
    recurring_jobs = Job.query.filter(Job.recurrence_rule.isnot(None)).all()
    generated_count = 0

    for job in recurring_jobs:
        if not job.scheduled_date:
            continue

        next_date = None
        if job.recurrence_rule == 'weekly':
            next_date = job.scheduled_date + timedelta(weeks=1)
        elif job.recurrence_rule == 'bi-weekly':
            next_date = job.scheduled_date + timedelta(weeks=2)
        elif job.recurrence_rule == 'monthly':
            next_date = job.scheduled_date + relativedelta(months=1)

        if next_date:
            # Check if a job for this customer on this date already exists
            existing_job = Job.query.filter_by(customer_id=job.customer_id, scheduled_date=next_date).first()
            if not existing_job:
                new_recurring_job = Job(
                    customer_id=job.customer_id,
                    location=job.location,
                    duration=job.duration,
                    worker_id=job.worker_id,
                    scheduled_date=next_date,
                    scheduled_time=job.scheduled_time,
                    recurrence_rule=job.recurrence_rule # The new job is also recurring
                )
                db.session.add(new_recurring_job)
                generated_count += 1

    if generated_count > 0:
        db.session.commit()
        flash(f'Successfully generated {generated_count} new recurring jobs.', 'success')
    else:
        flash('No new recurring jobs to generate.', 'info')

    return redirect(url_for('main.dashboard'))
