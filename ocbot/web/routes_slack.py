import logging
import threading

from flask import request, make_response, json, redirect, url_for

from config.configs import configs
from ocbot import app
from ocbot.pipeline.routing import RoutingHandler
from ocbot.pipeline.slash_command_handlers.log_handlers import can_view_logs, get_temporary_url, handle_log_view
from ocbot.pipeline.slash_command_handlers.lunch_handler import create_lunch_event
from ocbot.pipeline.slash_command_handlers.testgreet_handler import can_test, create_testgreet_event
from ocbot.web.route_decorators import url_verification, validate_response

VERIFICATION_TOKEN = configs['VERIFICATION_TOKEN']

logger = logging.getLogger(__name__)
logger.level = logging.DEBUG


@app.route('/event_endpoint', methods=['POST'])
@url_verification
@validate_response('token', VERIFICATION_TOKEN, 'json')
def events_route():
    """
    Any event based response will get routed here.
    Decorates first make sure it's a verified route and this isn't a challenge event
    Lastly forwards event data to route director
    """
    response_data = request.get_json()
    logger.debug(f'Event received: {json.dumps(response_data)}')
    route_id = response_data['event']['type']
    threading.Thread(target=RoutingHandler,
                     kwargs={"json_data": response_data, 'route_id': route_id}).start()
    return make_response('', 200)


@app.route("/user_interaction", methods=['POST'])
@validate_response('token', VERIFICATION_TOKEN, 'form')
def interaction_route():
    """
    Receives request from slack interactive messages.
    These are the messages that contain key: 'token_id'
    """
    data = json.loads(request.form['payload'])
    logger.info(f"Interaction received: {data}")
    route_id = data['callback_id']
    threading.Thread(target=RoutingHandler,
                     kwargs={'json_data': data, 'route_id': route_id}).start()
    return make_response('', 200)


@app.route("/zap_airtable_endpoint", methods=['POST'])
def zap_endpoint():
    """
    Endpoint for Zapier to send events when a new
    mentor request in submitted in airtable
    """
    data = request.get_json()
    logger.info(f'Zapier event received: {data}')
    threading.Thread(target=RoutingHandler,
                     kwargs={'json_data': data, 'route_id': 'new_airtable_request'}).start()
    return make_response((json.dumps({'status': 'ok'}), 200))


@app.route('/test/testgreet', methods=['POST'])
@validate_response('token', VERIFICATION_TOKEN, 'values')
def test_greet():
    """
    Endpoint for simulating a Slack 'team_join' event.
    Sends the notification to whichever channel the user
    was in when running the slash-command
    """
    req = request.values
    logger.info(f"testgreet received from {req['user_name']} : {req}")
    if not can_test(req['user_id']):
        logger.info(f"{req['user_name']} attempted to testgreet and was denied")
        return make_response("You are not authorized to do that.", 200)

    event = create_testgreet_event(req)
    threading.Thread(target=RoutingHandler,
                     kwargs={'json_data': event, 'route_id': 'team_join'}).start()
    return make_response('Test completed.', 200)


@app.route("/get_logs", methods=['POST'])
@validate_response('token', VERIFICATION_TOKEN, 'values')
def get_logs():
    """
    Endpoint used by Slack /logs command
    """
    req = request.values
    logger.info(f'Log request received: {req}')

    if not can_view_logs(req['user_id']):
        logger.info(f"{req['user_name']} attempted to view logs and was denied")
        return make_response("You are not authorized to do that.", 200)

    url = get_temporary_url(req['user_id'], req['text'])
    logger.info(f"Created log URL for {req['user_name']} : {url.url}")
    return make_response(f'{request.host_url}logs/{url.url}', 200)


@app.route('/lunch', methods=['POST'])
@validate_response('token', VERIFICATION_TOKEN, 'values')
def random_lunch():
    """
    Endpoint for getting random lunch event.
    Sends the notification to whichever channel the user
    was in when running the slash-command
    """
    req = request.values
    logger.info(f"Lunch request received from {req['user_name']} : {req}")

    lunch_val = create_lunch_event(req)

    return make_response(lunch_val, 200)


@app.route("/logs/<variable>")
def show_logs(variable):
    """
    Routes user to log
    :param variable:  Randomly generated string
    """
    return handle_log_view(variable)


@app.route('/options_load', methods=['POST'])
def options_route():
    """
    Can provide dynamically created options for interactive messages.
    Currently unused.
    """
    return redirect(url_for('HTTP404'))
