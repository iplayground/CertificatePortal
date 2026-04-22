from __future__ import annotations

import azure.functions as func

from src.functions.assets import blueprint as assets_blueprint
from src.functions.home import blueprint as home_blueprint
from src.functions.portal import blueprint as portal_blueprint
from src.functions.public_verification import blueprint as public_verification_blueprint

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

app.register_blueprint(portal_blueprint)
app.register_blueprint(public_verification_blueprint)
app.register_blueprint(assets_blueprint)
app.register_blueprint(home_blueprint)
