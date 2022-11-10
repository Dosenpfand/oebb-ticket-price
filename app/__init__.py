import logging
from typing import Optional, Union

import click
from flask import Flask, current_app, request, session, flash
from flask.cli import with_appcontext
from flask_babel import Babel, format_number
from flask_babel import lazy_gettext as _
from flask_bootstrap import Bootstrap4
from flask_crontab import Crontab
from flask_debugtoolbar import DebugToolbarExtension
from flask_migrate import Migrate
from flask_security import SQLAlchemyUserDatastore, Security, current_user
from flask_security.models import fsqla_v2 as fsqla
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from app.extended_security.forms import ExtendedRegisterForm

bootstrap = Bootstrap4()
db = SQLAlchemy()
security = Security()
migrate = Migrate()
babel = Babel()
csrf = CSRFProtect()
debug_toolbar = DebugToolbarExtension()
crontab = Crontab()


def create_app(
    import_name: Optional[str] = None, config: Union[object, str] = "config"
) -> Flask:
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
    logging.getLogger().setLevel(logging.WARNING)

    import_name = import_name if import_name else __name__

    app = Flask(import_name)

    with app.app_context():
        app.config.from_object(config)
        app.config.from_envvar("APPLICATION_SETTINGS", silent=True)
        app.config.from_prefixed_env(loads=str)
        bootstrap.init_app(app)
        db.init_app(app)
        # TODO: check for alternative
        #  https://stackoverflow.com/questions/37908767/table-roles-users-is-already-defined-for-this-metadata-instance
        db.metadata.clear()
        migrate.init_app(app, db)
        babel.init_app(app)
        csrf.init_app(app)
        debug_toolbar.init_app(app)
        crontab.init_app(app)

        app.jinja_env.add_extension("jinja2.ext.i18n")
        app.jinja_env.filters["format_number"] = format_number

        app.cli.add_command(init_db_command)
        app.cli.add_command(update_oldest_price_command)

        fsqla.FsModels.set_db_info(db)
        from app.models import User, Role  # noqa

        user_datastore = SQLAlchemyUserDatastore(db, User, Role)
        security.init_app(app, user_datastore, register_form=ExtendedRegisterForm)

        from app.main import bp as main_bp  # noqa

        app.register_blueprint(main_bp)

        from app.journal import bp as journal_bp  # noqa

        app.register_blueprint(journal_bp)

        from app.ticket_price import bp as ticket_price_bp  # noqa

        app.register_blueprint(ticket_price_bp)

        @babel.localeselector
        def get_locale() -> str:
            if current_app.config["TESTING"]:
                return "en"
            lang = request.args.get("lang", None)
            if lang in current_app.config["LANGUAGES"]:
                if current_user.is_authenticated:
                    user = User.query.filter_by(id=current_user.id).one()
                    user.language = lang
                    db.session.commit()
                flash(_("Language changed"))
                session["lang"] = lang
            elif current_user.is_authenticated:
                session["lang"] = current_user.language
            elif "lang" not in session:
                lang = request.accept_languages.best_match(
                    list(current_app.config["LANGUAGES"].keys())
                )
                if lang:
                    session["lang"] = lang
            return session.get("lang", default=current_app.config["DEFAULT_LANGUAGE"])

    return app


def init_db(drop: bool = True) -> None:
    if drop:
        db.drop_all()
    db.create_all()


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """Clear existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


@click.command("update-oldest-price")
@click.argument("count", default=1)
@with_appcontext
def update_oldest_price_command(count: int = 1) -> None:
    """Update the COUNT oldest prices in the database."""
    from app.models import Price  # noqa

    print(Price.update_oldest(count))
