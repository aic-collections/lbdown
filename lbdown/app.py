import logging

from flask import Flask, Response, request

from lbdown.config import flask as flask_conf


def create_app(config):
    app = Flask(__name__)
    app.config.update(config)

    return app


app = create_app(flask_conf)

if __name__ == '__main__':
    app.run(host='0.0.0.0')

