from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, mail
from .models import User, Job, Customer, EmailTemplate
from flask import Blueprint
from datetime import datetime, timedelta, date
from functools import wraps
from dateutil.relativedelta import relativedelta
from geopy.geocoders import Nominatim
from geopy.distance import great_circle
from flask_mail import Message
from jinja2 import Template

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
            email=request.form.get('email'),
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

def organizer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'organizer':
            return redirect(url_for('main.login')) # Or show a 403 error
        return f(*args, **kwargs)
    return decorated_function

# Staff Management
@main.route('/staff')
@login_required
@organizer_required
def staff():
    users = User.query.all()
    return render_template('staff.html', users=users)

@main.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@organizer_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.street = request.form.get('street')
        user.town = request.form.get('town')
        user.postcode = request.form.get('postcode')
        user.contracted_hours = int(request.form.get('contracted_hours') or 0)

        work_days = request.form.getlist('work_days')
        user.work_days = ','.join(work_days)

        # Geocode the address
        try:
            geolocator = Nominatim(user_agent="my-scheduler-app")
            address = f"{user.street}, {user.town}, {user.postcode}"
            location = geolocator.geocode(address)
            if location:
                user.latitude = location.latitude
                user.longitude = location.longitude
        except Exception as e:
            flash(f'Could not geocode address for user. Error: {e}', 'warning')

        db.session.commit()
        flash(f'{user.username}\'s details updated!', 'success')
        return redirect(url_for('main.staff'))
    return render_template('edit_user.html', user=user)


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
        job.notes = request.form.get('notes')

        db.session.commit()
        flash('Job updated successfully!', 'success')

        # Send notification email
        if job.customer.email:
            send_email("Job Updated", job.customer.email, job=job, customer=job.customer, worker=job.worker)
        if job.worker.email:
            send_email("Job Updated", job.worker.email, job=job, customer=job.customer, worker=job.worker)
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
        customer_id_str = request.form.get('customer_id')

        if customer_id_str == 'new_customer':
            # Create a new customer
            new_customer = Customer(
                name=request.form.get('new_customer_name'),
                street=request.form.get('new_customer_street'),
                town=request.form.get('new_customer_town'),
                postcode=request.form.get('new_customer_postcode'),
                email=request.form.get('new_customer_email')
            )
            # Geocode the new customer
            try:
                geolocator = Nominatim(user_agent="my-scheduler-app")
                address = f"{new_customer.street}, {new_customer.town}, {new_customer.postcode}"
                location = geolocator.geocode(address)
                if location:
                    new_customer.latitude = location.latitude
                    new_customer.longitude = location.longitude
            except Exception as e:
                flash(f'Could not geocode address for new customer. Error: {e}', 'warning')

            db.session.add(new_customer)
            db.session.flush() # Flush to get the ID for the new customer
            customer_id = new_customer.id
        else:
            customer_id = int(customer_id_str)

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
            notes=request.form.get('notes'),
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

# Customer Management Routes

@main.route('/api/available_workers')
@login_required
@organizer_required
def available_workers():
    date_str = request.args.get('date')
    customer_id = request.args.get('customer_id')

    if not date_str or not customer_id:
        return jsonify({'error': 'Missing date or customer_id parameter'}), 400

    try:
        job_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        customer = Customer.query.get(customer_id)
        if not customer or not customer.latitude:
            return jsonify({'error': 'Customer not found or not geocoded'}), 404
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid date or customer_id format'}), 400

    unavailable_worker_ids = [
        job.worker_id for job in Job.query.filter_by(scheduled_date=job_date).all()
    ]

    day_of_week = job_date.strftime('%a')
    available_workers_q = User.query.filter(
        User.id.notin_(unavailable_worker_ids),
        User.role == 'worker',
        User.work_days.isnot(None),
        User.work_days.contains(day_of_week)
    ).all()

    workers_with_distance = []
    customer_coords = (customer.latitude, customer.longitude)

    for worker in available_workers_q:
        if worker.latitude and worker.longitude:
            worker_coords = (worker.latitude, worker.longitude)
            distance = great_circle(customer_coords, worker_coords).kilometers
            workers_with_distance.append({'id': worker.id, 'username': worker.username, 'distance': round(distance, 2)})
        else:
            workers_with_distance.append({'id': worker.id, 'username': worker.username, 'distance': float('inf')})

    sorted_workers = sorted(workers_with_distance, key=lambda w: w['distance'])

    return jsonify(sorted_workers)

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
        new_customer = Customer(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            notes=request.form.get('notes'),
            street=request.form.get('street'),
            town=request.form.get('town'),
            postcode=request.form.get('postcode')
        )
        # Geocode the address
        try:
            geolocator = Nominatim(user_agent="my-scheduler-app")
            address = f"{new_customer.street}, {new_customer.town}, {new_customer.postcode}"
            location = geolocator.geocode(address)
            if location:
                new_customer.latitude = location.latitude
                new_customer.longitude = location.longitude
        except Exception as e:
            flash(f'Could not geocode address. Error: {e}', 'warning')

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
        customer.phone = request.form.get('phone')
        customer.email = request.form.get('email')
        customer.notes = request.form.get('notes')
        customer.street = request.form.get('street')
        customer.town = request.form.get('town')
        customer.postcode = request.form.get('postcode')

        # Geocode the address
        try:
            geolocator = Nominatim(user_agent="my-scheduler-app")
            address = f"{customer.street}, {customer.town}, {customer.postcode}"
            location = geolocator.geocode(address)
            if location:
                customer.latitude = location.latitude
                customer.longitude = location.longitude
        except Exception as e:
            flash(f'Could not geocode address. Error: {e}', 'warning')

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

# Email Template Management
@main.route('/templates')
@login_required
@organizer_required
def templates():
    all_templates = EmailTemplate.query.all()
    return render_template('templates.html', templates=all_templates)

@main.route('/add_template', methods=['GET', 'POST'])
@login_required
@organizer_required
def add_template():
    if request.method == 'POST':
        new_template = EmailTemplate(
            name=request.form.get('name'),
            subject=request.form.get('subject'),
            body=request.form.get('body')
        )
        db.session.add(new_template)
        db.session.commit()
        flash('Template created successfully!', 'success')
        return redirect(url_for('main.templates'))
    return render_template('add_template.html')

@main.route('/edit_template/<int:template_id>', methods=['GET', 'POST'])
@login_required
@organizer_required
def edit_template(template_id):
    template = EmailTemplate.query.get_or_404(template_id)
    if request.method == 'POST':
        template.name = request.form.get('name')
        template.subject = request.form.get('subject')
        template.body = request.form.get('body')
        db.session.commit()
        flash('Template updated successfully!', 'success')
        return redirect(url_for('main.templates'))
    return render_template('edit_template.html', template=template)

@main.route('/delete_template/<int:template_id>', methods=['POST'])
@login_required
@organizer_required
def delete_template(template_id):
    template = EmailTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted successfully!', 'success')
    return redirect(url_for('main.templates'))

@main.route('/allocation')
@login_required
@organizer_required
def allocation():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    workers = User.query.filter_by(role='worker').all()

    allocation_data = []
    for worker in workers:
        jobs_this_week = Job.query.filter(
            Job.worker_id == worker.id,
            Job.scheduled_date >= start_of_week,
            Job.scheduled_date <= end_of_week
        ).all()

        total_hours_this_week = sum(job.duration for job in jobs_this_week) / 60.0

        allocation_data.append({
            'worker': worker,
            'assigned_hours': total_hours_this_week,
            'contracted_hours': worker.contracted_hours or 0
        })

    return render_template('allocation.html', allocation_data=allocation_data, week_start=start_of_week, week_end=end_of_week)

# Helper function to send email
def send_email(template_name, recipient_email, **kwargs):
    template = EmailTemplate.query.filter_by(name=template_name).first()
    if not template or not recipient_email:
        return # Or flash a message

    subject = Template(template.subject).render(**kwargs)
    body = Template(template.body).render(**kwargs)

    msg = Message(subject, recipients=[recipient_email], body=body)
    mail.send(msg)
    flash(f'Email "{subject}" sent to {recipient_email}.', 'success')


@main.route('/job/<int:job_id>/send_email', methods=['GET', 'POST'])
@login_required
@organizer_required
def send_job_email(job_id):
    job = Job.query.get_or_404(job_id)
    templates = EmailTemplate.query.all()

    if request.method == 'POST':
        template_id = request.form.get('template_id')
        template = EmailTemplate.query.get(template_id)

        # Decide recipient
        recipient_type = request.form.get('recipient')
        recipient_email = None
        if recipient_type == 'customer' and job.customer.email:
            recipient_email = job.customer.email
        elif recipient_type == 'worker' and job.worker.email: # Note: User model needs an email field
            recipient_email = job.worker.email

        if template and recipient_email:
            send_email(template.name, recipient_email, job=job, customer=job.customer, worker=job.worker)
        else:
            flash('Could not send email. Template or recipient email missing.', 'danger')
        return redirect(url_for('main.job_details', job_id=job.id))

    return render_template('send_email.html', job=job, templates=templates)
