from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from .models import User, Job
from flask import Blueprint

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return '<h1>Welcome to the Scheduler</h1>'

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

from datetime import datetime

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
        job.customer_name = request.form.get('customer_name')
        job.location = request.form.get('location')
        job.duration = int(request.form.get('duration'))
        job.worker_id = int(request.form.get('worker_id'))
        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    workers = User.query.filter_by(role='worker').all()
    return render_template('edit_job.html', job=job, workers=workers)

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
        customer_name = request.form.get('customer_name')
        location = request.form.get('location')
        duration = request.form.get('duration')
        worker_id = request.form.get('worker_id')

        new_job = Job(
            customer_name=customer_name,
            location=location,
            duration=int(duration),
            worker_id=int(worker_id)
        )
        db.session.add(new_job)
        db.session.commit()
        flash('Job created successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    workers = User.query.filter_by(role='worker').all()
    return render_template('create_job.html', workers=workers)
