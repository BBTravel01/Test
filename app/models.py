from . import db
from datetime import datetime
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'organizer' or 'worker'
    jobs = db.relationship('Job', backref='worker', lazy=True)

    # New address fields for staff
    street = db.Column(db.String(200))
    town = db.Column(db.String(100))
    postcode = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # New fields for availability
    contracted_hours = db.Column(db.Integer)
    work_days = db.Column(db.String(100)) # e.g., "Mon,Tue,Wed,Thu,Fri"

    def __repr__(self):
        return f'<User {self.username}>'

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    notes = db.Column(db.Text)
    jobs = db.relationship('Job', backref='customer', lazy=True)

    # New structured address fields
    street = db.Column(db.String(200))
    town = db.Column(db.String(100))
    postcode = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    def __repr__(self):
        return f'<Customer {self.name}>'

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False) # Can be more specific than customer address
    duration = db.Column(db.Integer, nullable=False) # Estimated duration in minutes
    status = db.Column(db.String(20), nullable=False, default='scheduled') # scheduled, in_progress, completed
    start_time = db.Column(db.DateTime, nullable=True) # Actual start time
    end_time = db.Column(db.DateTime, nullable=True) # Actual end time
    notes = db.Column(db.Text)
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

    # Scheduling fields
    scheduled_date = db.Column(db.Date, nullable=True)
    scheduled_time = db.Column(db.Time, nullable=True)
    recurrence_rule = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f'<Job {self.id} for {self.customer.name}>'

class EmailTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<EmailTemplate {self.name}>'
