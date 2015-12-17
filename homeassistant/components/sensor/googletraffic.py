from datetime import timedelta, datetime
from collections import OrderedDict
from homeassistant.helpers.entity import Entity
import logging

REQUIREMENTS = ['googlemaps==2.4.2']

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """

    """
    import googlemaps
    _LOGGER.debug("attempting to setup google traffic sensor with hass={h} config={c}".format(h=hass, c=config))
    try:
        api_key = config['api_key']
        from_addr = config['from']
        to_addr = config['to']
        name = config['name']
    except KeyError as e:
        _LOGGER.error("Missing required {e} configuration option for googletraffic sensor".format(e=e))
        return False

    try:
        gmaps = googlemaps.Client(key=api_key)
        add_devices([GoogleTrafficSensor(gmaps=gmaps, from_addr=from_addr, to_addr=to_addr, name=name)])
    except Exception as e:
        _LOGGER.exception("Error setting up googlemaps api: {e}".format(e=e))


def getRoute(gmaps, departure_time, fromAddr, toAddr):
    """
    returns a dict similar to:
        {
        {
            "description": "starting_address to destination",
            "fastest": {
            "name": "I-435 E",
            "time": 1406.0,
            "text": "23.43 min via I-435 E",
            "minutes": 23.433333333333334
        },
        "I-435 E": {  }  # contains the textual directions for the route
        }
    """
    results = OrderedDict()

    # from https://www.python.org/dev/peps/pep-0476/
    # TODO: For some reason, requests doesn't like https://maps.googleapis.com
    # - figure out why and fix it instead of this since this is bad
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    # TODO

    directions_result = gmaps.directions(fromAddr,
                                         toAddr,
                                         mode="driving",
                                         departure_time=departure_time,
                                         alternatives=True)
    results['description'] = "{fromAddr} to {toAddr}".format(fromAddr=fromAddr, toAddr=toAddr)
    results['fastest'] = {'time': None, 'text': None, 'name': None}
    for route in directions_result:
        total_distance = 0.0
        total_time = 0.0
        results[route['summary']] = OrderedDict(legs=[])
        for leg in route['legs']:
            total_distance += leg['distance']['value']
            total_time += leg['duration']['value']
            for step in leg['steps']:
                results[route['summary']]['legs'].append("{distance} {duration} {desc}".format(
                    distance=step['distance']['text'],
                    duration=step['duration']['text'],
                    desc=step['html_instructions']
                ))

    results[route['summary']]['total_miles'] = (total_distance * 0.00062137)
    results[route['summary']]['total_minutes'] = (total_time / 60)
    if not results['fastest']['time'] or results['fastest']['time'] > total_time:
        # new fastest route
        results['fastest'].update(time=total_time,
                                  name=route['summary'],
                                  text="{minutes:.2f} min via {name}".format(minutes=results[route['summary']]['total_minutes'], name=route['summary']))
    return results


class GoogleTrafficSensor(Entity):
    """Represents a traffic route from google's traffic api"""
    def __init__(self, gmaps, from_addr, to_addr, name, route_method=None):
        self.route_method = route_method or "fastest"
        self.from_addr = from_addr
        self.to_addr = to_addr
        self._name = name
        self._state = None
        # self.unit_of_measurement = "minutes"
        self.gmaps = gmaps

    @property
    def name(self):
        return "traffic_" + self._name

    @property
    def state(self):
        return self._state

    def update(self):
        _LOGGER.debug("update called")
        results = getRoute(gmaps=self.gmaps,
                           departure_time=datetime.now(),
                           fromAddr=self.from_addr,
                           toAddr=self.to_addr)
        _LOGGER.debug("received new route: {r}".format(r=results['fastest']))
        self._state = results['time']

