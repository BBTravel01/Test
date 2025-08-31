from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scheduler.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'a-secret-key' # Needed for session management
    app.config['TESTING'] = True # This will suppress email sending
    app.config['MAIL_SUPPRESS_SEND'] = True # Also helps to suppress sending
    app.config['MAIL_DEFAULT_SENDER'] = 'noreply@scheduler.com'

    db.init_app(app)
    mail.init_app(app)

    # Import and register blueprint
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # The models are imported when routes.py is imported.
    # This ensures they are known to SQLAlchemy before create_all is called.

    with app.app_context():
        db.create_all()

    return app
