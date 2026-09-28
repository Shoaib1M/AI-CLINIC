from .appointments import bp as appointments_bp
from .auth import bp as auth_bp
from .health import bp as health_bp
from .patients import bp as patients_bp
from .predictions import bp as predictions_bp
from .prescriptions import bp as prescriptions_bp

BLUEPRINTS = (health_bp, auth_bp, appointments_bp, patients_bp, predictions_bp, prescriptions_bp)


def register_blueprints(app) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix="/api")
