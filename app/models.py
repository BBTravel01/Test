from . import db
from datetime import datetime
from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'organizer' or 'worker'
    jobs = db.relationship('Job', backref='worker', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.Integer, nullable=False) # Estimated duration in minutes
    status = db.Column(db.String(20), nullable=False, default='scheduled') # scheduled, in_progress, completed
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Job {self.id} for {self.customer_name}>'
